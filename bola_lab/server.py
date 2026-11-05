"""Public, GET-only HTTP surface for the isolated BOLA evaluation lab."""

from __future__ import annotations

import atexit
import json
import logging
import os
from pathlib import Path
from typing import Any

from flask import Flask, Response, g, request

from .network import NetworkPolicyError, parse_allowed_clients
from .scenarios import full_resource, scenario_for, serialize_unauthorized
from .storage import (
    StateError,
    ensure_private_directory,
    fetch_book,
    fetch_first_owned_book,
    fetch_principal,
    is_shared_with,
    read_private_json,
    state_path,
)
from .tokens import TokenError, verify_token


class StartupError(RuntimeError):
    """The controller-prepared private state cannot safely start a server."""


def _validate_manifest(manifest: dict[str, Any]) -> None:
    required = {"format", "run_id", "scenario", "created_at", "token_ttl_seconds", "signing_secret"}
    if set(manifest) != required or manifest["format"] != 1:
        raise StartupError("The active lab manifest is invalid.")
    if not isinstance(manifest["signing_secret"], str) or len(manifest["signing_secret"]) < 24:
        raise StartupError("The active lab manifest is invalid.")
    try:
        scenario_for(manifest["scenario"])
    except (ValueError, TypeError) as exc:
        raise StartupError("The active lab manifest is invalid.") from exc


def _acquire_lock(state_dir: Path) -> Path:
    """Reserve a run with O_EXCL so two servers cannot share mutable state."""
    lock = state_path(state_dir, "lock")
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise StartupError("The lab state is already in use by another process.") from exc
    except OSError as exc:
        raise StartupError("Unable to reserve private lab state.") from exc
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump({"pid": os.getpid()}, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(lock, 0o600)
    except OSError as exc:
        lock.unlink(missing_ok=True)
        raise StartupError("Unable to reserve private lab state.") from exc
    return lock


def _json_response(payload: dict[str, Any], status: int = 200) -> Response:
    # Compact deterministic UTF-8 bytes. The experiment does not use compression.
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return Response(encoded, status=status, content_type="application/json; charset=utf-8")


def _balanced_denial(target: dict[str, str]) -> dict[str, Any]:
    """Return a denial body with the same serialized UTF-8 byte count as a full resource.

    This is a private test-control behavior for S11. Padding contains no secret,
    token, marker, or scenario identifier.
    """
    reference = _json_response(full_resource(target)).get_data()
    base = {"data": {"id": target["id"], "owner": target["owner"], "title": target["title"], "secret": ""}, "padding": ""}
    size_without_padding = len(_json_response(base).get_data())
    padding = len(reference) - size_without_padding
    if padding < 0:
        raise StartupError("Unable to prepare byte-balanced experiment response.")
    base["padding"] = "x" * padding
    if len(_json_response(base).get_data()) != len(reference):
        raise StartupError("Unable to prepare byte-balanced experiment response.")
    return base


def create_app(state_dir_text: str | None = None) -> Flask:
    """Create the public lab app from controller-prepared immutable state."""
    configured_state = state_dir_text or os.environ.get("BOLA_LAB_STATE_DIR")
    if not configured_state:
        raise StartupError("BOLA_LAB_STATE_DIR is required.")
    try:
        state_dir = ensure_private_directory(configured_state)
        manifest = read_private_json(state_path(state_dir, "manifest"))
        _validate_manifest(manifest)
        # Controller-created files must exist before the process exposes HTTP.
        for name in ("database", "tokens", "operator", "answers"):
            if not state_path(state_dir, name).is_file():
                raise StartupError("The prepared lab state is incomplete.")
        scenario = scenario_for(manifest["scenario"])
        access_policy = parse_allowed_clients(os.environ.get("BOLA_LAB_ALLOWED_CLIENTS"))
        lock = _acquire_lock(state_dir)
    except (NetworkPolicyError, StateError) as exc:
        raise StartupError("The prepared lab state cannot be used.") from exc

    try:
        app = Flask(__name__)
        app.config.update(JSON_AS_ASCII=False, PROPAGATE_EXCEPTIONS=False)
        app.logger.handlers.clear()
        app.logger.addHandler(logging.NullHandler())

        def release_lock() -> None:
            lock.unlink(missing_ok=True)

        @app.before_request
        def admit_client() -> Response | None:
            # Use only the TCP peer address. Client-supplied forwarding headers
            # are intentionally ignored because no trusted proxy is configured.
            if not access_policy.allows(request.remote_addr):
                return _json_response({"error": "not_found"}, 404)
            return None

        @app.before_request
        def authenticate() -> Response | None:
            if request.path == "/health":
                return None
            header = request.headers.get("Authorization", "")
            if not header.startswith("Bearer "):
                return _json_response({"error": "unauthorized"}, 401)
            try:
                payload = verify_token(header.removeprefix("Bearer "), manifest["signing_secret"])
                principal = fetch_principal(state_dir, payload["sub"])
                if principal is None:
                    raise TokenError("Unknown principal")
            except TokenError:
                return _json_response({"error": "unauthorized"}, 401)
            g.principal = principal
            return None

        @app.get("/health")
        def health() -> Response:
            return _json_response({"status": "ready"})

        @app.get("/me")
        def me() -> Response:
            return _json_response({"principal": {"username": g.principal["username"], "role": g.principal["role"]}})

        @app.get("/books/<book_id>")
        def get_book(book_id: str) -> Response:
            target = fetch_book(state_dir, book_id)
            if target is None:
                return _json_response({"error": "not_found"}, 404)
            principal = g.principal["username"]
            authorized = target["owner"] == principal or is_shared_with(state_dir, book_id, principal)
            if authorized:
                return _json_response(full_resource(target))

            # S11 includes a denial control whose equal-length body is deliberately
            # returned only to admin, whose experiment policy is declared UNKNOWN.
            if scenario.code == "S11" and principal == "admin":
                return _json_response(_balanced_denial(target), 403)

            alternate = fetch_first_owned_book(state_dir, principal)
            payload, status = serialize_unauthorized(scenario, target, alternate)
            # S10's B2 response intentionally lacks the observed resource ID, so
            # marker attribution cannot be proven from the allowed public evidence.
            if scenario.code == "S10" and target["id"] == "book-B2":
                payload = {"data": {"title": target["title"], "secret": target["secret"]}, "evidence": {"source": "unattributed"}}
            return _json_response(payload, status)

        @app.errorhandler(404)
        def not_found(_: Exception) -> Response:
            return _json_response({"error": "not_found"}, 404)

        @app.errorhandler(Exception)
        def internal_error(_: Exception) -> Response:
            return _json_response({"error": "service_unavailable"}, 500)
    except Exception as exc:
        lock.unlink(missing_ok=True)
        raise StartupError("Unable to initialize the public lab application.") from exc

    atexit.register(release_lock)
    app.extensions["bola_lab_release_lock"] = release_lock
    return app

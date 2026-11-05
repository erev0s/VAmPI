"""Operator-only controller for controlled BOLA lab runs.

This module has no HTTP routes. Run it locally on the lab host before starting
`bola_lab_app.py`; its private outputs are never served by the application.
"""

from __future__ import annotations

import argparse
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from .scenarios import SCENARIO_IDS, ground_truth, scenario_for
from .storage import (
    STATE_FILES,
    StateError,
    ensure_private_directory,
    initialize_database,
    read_private_json,
    state_path,
    write_private_json,
)
from .tokens import issue_token

PRINCIPALS = [
    {"username": "admin", "role": "admin"},
    {"username": "userA", "role": "user"},
    {"username": "userB", "role": "user"},
]
BOOK_BLUEPRINTS = [
    ("book-A1", "userA", "User A book one"),
    ("book-A2", "userA", "User A book two"),
    ("book-B1", "userB", "User B book one"),
    ("book-B2", "userB", "User B book two"),
]


def _upstream_revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unavailable"


def _live_lock(state_dir: Path) -> bool:
    lock = state_path(state_dir, "lock")
    if not lock.exists():
        return False
    try:
        lock_data = read_private_json(lock)
        pid = lock_data.get("pid")
        if not isinstance(pid, int):
            return True
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        lock.unlink(missing_ok=True)
        return False
    except (PermissionError, StateError):
        return True


def _assert_not_running(state_dir: Path) -> None:
    if _live_lock(state_dir):
        raise StateError("A lab server is running; stop it before changing private state.")


def _books_for_run(scenario: str) -> list[dict[str, str]]:
    markers = {book_id: f"marker-{secrets.token_urlsafe(18)}" for book_id, _, _ in BOOK_BLUEPRINTS}
    if scenario == "S10":
        # B1/B2 are the compared cross-owner targets. Reusing their marker
        # supports the intentionally attribution-ambiguous B2 representation.
        markers["book-B2"] = markers["book-B1"]
    return [
        {"id": book_id, "owner": owner, "title": title, "secret": markers[book_id]}
        for book_id, owner, title in BOOK_BLUEPRINTS
    ]


def _shares_for_run(scenario: str) -> list[dict[str, str]]:
    return [{"book_id": "book-B1", "username": "userA"}] if scenario == "S08" else []


def _answer_rows(scenario_code: str, books: list[dict[str, str]], shares: list[dict[str, str]]) -> list[dict[str, Any]]:
    scenario = scenario_for(scenario_code)
    by_id = {book["id"]: book for book in books}
    rows: list[dict[str, Any]] = []
    # The canonical cross-user observation is userA requesting B1.
    shared = {item["book_id"] for item in shares if item["username"] == "userA"}
    allowed = "book-B1" in shared
    kind = scenario.response_kind
    # This dimension is about the requested target's private data. S07 returns
    # userA's own alternate resource and must not be scored as target disclosure.
    disclosed = kind in {"target_full", "balanced_target_full", "formatted_target_full", "ambiguous_marker"}
    returned = "book-A1" if kind == "wrong_object" else "book-B1"
    rows.append(
        {
            "scenario": scenario_code,
            "requester": "userA",
            "requested_resource": "book-B1",
            "http_status": scenario.unauthorized_status,
            "ground_truth": ground_truth(
                scenario,
                authorization_allowed=allowed,
                private_data_disclosed=disclosed,
                returned_resource_identity=returned,
            ),
            "reason": scenario.description,
        }
    )
    # Owner control is a separate invariant rather than a conclusion inferred from status.
    rows.append(
        {
            "scenario": scenario_code,
            "requester": "userB",
            "requested_resource": "book-B1",
            "http_status": 200,
            "ground_truth": {
                "authorization_allowed": True,
                "private_data_disclosed": True,
                "returned_resource_identity": by_id["book-B1"]["id"],
                "expected_classification": "OWNER_CONTROL",
                "acceptable_conclusions": ["POLICY_CONSISTENT"],
                "evidence_requirements": ["owner_identity_verified", "target_identity_matches", "private_marker_observed"],
            },
            "reason": "Owner controls always receive their complete own resource.",
        }
    )
    return rows


def initialize_run(state_dir_text: str, scenario_code: str, token_ttl: int) -> None:
    if scenario_code not in SCENARIO_IDS:
        raise StateError("Unsupported scenario.")
    if token_ttl <= 0:
        raise StateError("Token lifetime must be positive.")
    state_dir = ensure_private_directory(state_dir_text, create=True)
    _assert_not_running(state_dir)
    for name in STATE_FILES.values():
        (state_dir / name).unlink(missing_ok=True)

    books = _books_for_run(scenario_code)
    shares = _shares_for_run(scenario_code)
    initialize_database(state_dir, PRINCIPALS, books, shares)
    now = int(time.time())
    signing_secret = secrets.token_urlsafe(32)
    manifest = {
        "format": 1,
        "run_id": secrets.token_urlsafe(12),
        "scenario": scenario_code,
        "created_at": now,
        "token_ttl_seconds": token_ttl,
        "signing_secret": signing_secret,
    }
    issued = {
        "expires_at": now + token_ttl,
        "tokens": {item["username"]: issue_token(item["username"], signing_secret, now + token_ttl) for item in PRINCIPALS},
    }
    operator = {
        "base_url": "http://LAB_HOST:5003",
        "principal_pointer": "/principal/username",
        "resource_id_pointer": "/data/id",
        "restricted_field_pointers": ["/data/secret"],
        "identities": [{"username": "userA", "role": "user"}, {"username": "userB", "role": "user"}],
        "resources": [{"id": item["id"], "owner": item["owner"], "title": item["title"]} for item in books],
        "policy": {
            "owner_can_read_private": True,
            "shared_users_can_read_private": True,
            "public_fields": ["id", "owner", "title"],
            "admin_policy": "UNKNOWN",
        },
        "denial_convention": {"known_profile": {"pointer": "/result", "value": "access_denied"}, "unknown_profile": None},
    }
    answers = {
        "upstream_base_commit": _upstream_revision(),
        "run_id": manifest["run_id"],
        "policy_source": "Configured experiment policy, not server behavior.",
        "rows": _answer_rows(scenario_code, books, shares),
    }
    write_private_json(state_path(state_dir, "manifest"), manifest)
    write_private_json(state_path(state_dir, "tokens"), issued)
    write_private_json(state_path(state_dir, "operator"), operator)
    write_private_json(state_path(state_dir, "answers"), answers)


def validate_run(state_dir_text: str) -> None:
    state_dir = ensure_private_directory(state_dir_text)
    manifest = read_private_json(state_path(state_dir, "manifest"))
    if manifest.get("format") != 1 or manifest.get("scenario") not in SCENARIO_IDS:
        raise StateError("Active run manifest is invalid.")
    for name in ("database", "tokens", "operator", "answers"):
        path = state_path(state_dir, name)
        if not path.is_file():
            raise StateError("Required private lab state is unavailable.")
    read_private_json(state_path(state_dir, "tokens"))
    read_private_json(state_path(state_dir, "operator"))
    read_private_json(state_path(state_dir, "answers"))


def reset_run(state_dir_text: str, scenario_code: str, token_ttl: int) -> None:
    state_dir = ensure_private_directory(state_dir_text)
    _assert_not_running(state_dir)
    initialize_run(str(state_dir), scenario_code, token_ttl)


def _print_prepared_state_summary(state_dir_text: str, command: str) -> None:
    state_dir = ensure_private_directory(state_dir_text)
    action = "khởi tạo" if command == "init" else "đặt lại"
    print(f"BOLA Lab đã được {action} thành công.")
    if command == "reset":
        print("Token bearer và marker private trước đó đã được thay thế; token cũ không còn hợp lệ.")
    print()
    print("Principal đã seed:")
    for principal in PRINCIPALS:
        print(f"  - {principal['username']} ({principal['role']})")
    print()
    print("Resource đã seed:")
    for book_id, owner, title in BOOK_BLUEPRINTS:
        print(f"  - {book_id} — owner: {owner} — {title}")
    print()
    print("Artifact private (chỉ operator; thư mục mode 0700, file mode 0600):")
    artifact_details = (
        ("database", "Database (principal, resource, ownership và share)"),
        ("operator", "Cấu hình operator (pointer, danh sách identity/resource và policy)"),
        ("tokens", "Bearer token đã cấp (chỉ đọc cục bộ và phân phối qua kênh bảo vệ)"),
        ("manifest", "Manifest run (cấu hình run và signing secret)"),
        ("answers", "Answer sheet evaluator (ground truth; không cung cấp cho tool)"),
    )
    for name, label in artifact_details:
        print(f"  - {label}: {state_path(state_dir, name)}")
    print()
    print("Token, signing secret, marker và nội dung answer sheet không được in ra terminal.")
    print("Bước tiếp theo:")
    print(f"  1. Xác thực state: python -m bola_lab.controller --state-dir {state_dir} validate")
    print("  2. Khởi động service với BOLA_LAB_STATE_DIR trỏ đến thư mục này.")
    print("  3. Chỉ lấy token từ issued-tokens.json trên máy operator qua kênh bảo vệ.")
    print("  4. Không publish, copy sang máy tool hoặc expose state directory qua HTTP.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Private controller for the isolated BOLA lab")
    parser.add_argument("--state-dir", required=True, help="Private state directory (mode 0700)")
    parser.add_argument("--scenario", choices=SCENARIO_IDS)
    parser.add_argument("--token-ttl", type=int, default=3600)
    parser.add_argument("command", choices=("init", "reset", "validate"))
    args = parser.parse_args()
    try:
        if args.command == "validate":
            validate_run(args.state_dir)
        elif args.command == "init":
            if not args.scenario:
                parser.error("init requires --scenario")
            initialize_run(args.state_dir, args.scenario, args.token_ttl)
        else:
            if not args.scenario:
                parser.error("reset requires --scenario")
            reset_run(args.state_dir, args.scenario, args.token_ttl)
    except StateError as exc:
        print(f"Controller error: {exc}", file=sys.stderr)
        return 2
    if args.command == "validate":
        print("Private lab state validated.")
    else:
        _print_prepared_state_summary(args.state_dir, args.command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

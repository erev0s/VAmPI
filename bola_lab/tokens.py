"""Minimal signed bearer tokens for the isolated lab service."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any


class TokenError(ValueError):
    """A bearer token cannot establish a principal."""


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def issue_token(username: str, secret: str, expires_at: int) -> str:
    payload = json.dumps({"sub": username, "exp": expires_at}, sort_keys=True, separators=(",", ":")).encode("utf-8")
    encoded_payload = _encode(payload)
    signature = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
    return f"v1.{encoded_payload}.{_encode(signature)}"


def verify_token(token: str, secret: str, now: int | None = None) -> dict[str, Any]:
    try:
        version, encoded_payload, encoded_signature = token.split(".")
        if version != "v1":
            raise TokenError("Unsupported token")
        expected = hmac.new(secret.encode("utf-8"), encoded_payload.encode("ascii"), hashlib.sha256).digest()
        if not hmac.compare_digest(expected, _decode(encoded_signature)):
            raise TokenError("Bad signature")
        payload = json.loads(_decode(encoded_payload))
        if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("exp"), int):
            raise TokenError("Malformed payload")
        if payload["exp"] <= (int(time.time()) if now is None else now):
            raise TokenError("Expired token")
        return payload
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        if isinstance(exc, TokenError):
            raise
        raise TokenError("Invalid token") from exc

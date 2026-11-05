"""Local-only BOLA Lab account and bearer-token inspection utility."""

from __future__ import annotations

import argparse
import sys

from .storage import StateError, connect_database, ensure_private_directory, read_private_json, state_path


def list_accounts(state_dir_text: str) -> list[dict[str, str]]:
    """Return the locally seeded principals without exposing credentials."""
    state_dir = ensure_private_directory(state_dir_text)
    connection = connect_database(state_dir)
    try:
        rows = connection.execute("SELECT username, role FROM principals ORDER BY username").fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()


def issued_token(state_dir_text: str, username: str) -> str:
    """Return one locally stored bearer token for explicit operator use."""
    state_dir = ensure_private_directory(state_dir_text)
    tokens = read_private_json(state_path(state_dir, "tokens")).get("tokens")
    if not isinstance(tokens, dict) or not isinstance(tokens.get(username), str):
        raise StateError("No issued token exists for the requested principal.")
    return tokens[username]


def main() -> int:
    parser = argparse.ArgumentParser(description="Local-only BOLA Lab account inspection utility")
    parser.add_argument("--state-dir", required=True, help="Private state directory (mode 0700)")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="List seeded principals and roles without credentials")
    token_parser = subcommands.add_parser("show-token", help="Print one bearer token for local operator use")
    token_parser.add_argument("username", help="Seeded principal username")
    args = parser.parse_args()

    try:
        if args.command == "list":
            print("BOLA Lab accounts (password authentication is not used):")
            for account in list_accounts(args.state_dir):
                print(f"  - {account['username']} ({account['role']})")
            print("Authentication uses run-specific bearer tokens in issued-tokens.json.")
            return 0

        print(
            "Warning: writing a bearer token to stdout can expose it in terminal scrollback or logs. "
            "Use only in a protected local operator terminal.",
            file=sys.stderr,
        )
        print(issued_token(args.state_dir, args.username))
        return 0
    except StateError as exc:
        print(f"Account utility error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

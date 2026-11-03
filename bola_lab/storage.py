"""Private state storage and SQLite persistence for the BOLA lab."""

from __future__ import annotations

import json
import os
import sqlite3
import stat
import tempfile
from pathlib import Path
from typing import Any

STATE_FILES = {
    "manifest": "active-run.json",
    "database": "lab.sqlite3",
    "tokens": "issued-tokens.json",
    "operator": "operator-config.json",
    "answers": "answer-sheet.json",
    "lock": "server.lock",
}


class StateError(RuntimeError):
    """Raised when private lab state is unavailable or unsafe."""


def state_path(state_dir: str | Path, name: str) -> Path:
    return Path(state_dir).expanduser().resolve() / STATE_FILES[name]


def ensure_private_directory(state_dir: str | Path, *, create: bool = False) -> Path:
    path = Path(state_dir).expanduser().resolve()
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
        # Docker volumes are commonly created with a permissive mode. The
        # local controller owns the state and tightens it before use.
        os.chmod(path, 0o700)
    if not path.is_dir():
        raise StateError("The lab state directory is unavailable.")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise StateError("The lab state directory must not be group or world accessible.")
    return path


def write_private_json(path: Path, data: dict[str, Any]) -> None:
    """Write JSON atomically with owner-only permissions."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
        directory_fd = os.open(path.parent, os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_private_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise StateError("Required lab state is unavailable.")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        raise StateError("Private lab state has unsafe permissions.")
    with path.open(encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise StateError("Lab state has an invalid format.")
    return data


def connect_database(state_dir: str | Path) -> sqlite3.Connection:
    database = state_path(state_dir, "database")
    connection = sqlite3.connect(database)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database(state_dir: str | Path, principals: list[dict[str, str]], books: list[dict[str, str]], shares: list[dict[str, str]]) -> None:
    database = state_path(state_dir, "database")
    if database.exists():
        database.unlink()
    connection = connect_database(state_dir)
    try:
        connection.executescript(
            """
            PRAGMA foreign_keys = ON;
            CREATE TABLE principals (
                username TEXT PRIMARY KEY,
                role TEXT NOT NULL
            );
            CREATE TABLE books (
                id TEXT PRIMARY KEY,
                owner TEXT NOT NULL REFERENCES principals(username),
                title TEXT NOT NULL,
                secret TEXT NOT NULL
            );
            CREATE TABLE shares (
                book_id TEXT NOT NULL REFERENCES books(id),
                username TEXT NOT NULL REFERENCES principals(username),
                PRIMARY KEY (book_id, username)
            );
            """
        )
        connection.executemany(
            "INSERT INTO principals (username, role) VALUES (:username, :role)", principals
        )
        connection.executemany(
            "INSERT INTO books (id, owner, title, secret) VALUES (:id, :owner, :title, :secret)", books
        )
        connection.executemany(
            "INSERT INTO shares (book_id, username) VALUES (:book_id, :username)", shares
        )
        connection.commit()
    finally:
        connection.close()
    os.chmod(database, 0o600)


def fetch_principal(state_dir: str | Path, username: str) -> dict[str, str] | None:
    connection = connect_database(state_dir)
    try:
        row = connection.execute("SELECT username, role FROM principals WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def fetch_book(state_dir: str | Path, book_id: str) -> dict[str, str] | None:
    connection = connect_database(state_dir)
    try:
        row = connection.execute("SELECT id, owner, title, secret FROM books WHERE id = ?", (book_id,)).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def fetch_first_owned_book(state_dir: str | Path, owner: str) -> dict[str, str] | None:
    connection = connect_database(state_dir)
    try:
        row = connection.execute(
            "SELECT id, owner, title, secret FROM books WHERE owner = ? ORDER BY id LIMIT 1", (owner,)
        ).fetchone()
        return dict(row) if row else None
    finally:
        connection.close()


def is_shared_with(state_dir: str | Path, book_id: str, username: str) -> bool:
    connection = connect_database(state_dir)
    try:
        row = connection.execute(
            "SELECT 1 FROM shares WHERE book_id = ? AND username = ?", (book_id, username)
        ).fetchone()
        return row is not None
    finally:
        connection.close()

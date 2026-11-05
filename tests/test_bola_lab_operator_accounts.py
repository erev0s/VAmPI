"""Tests for the local-only BOLA Lab account inspection utility."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bola_lab.controller import initialize_run
from bola_lab.operator_accounts import issued_token, list_accounts
from bola_lab.storage import StateError


class BolaLabOperatorAccountsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state = Path(self.temp.name) / "state"
        self.state.mkdir(mode=0o700)
        initialize_run(str(self.state), "S01", 60)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_list_accounts_returns_identities_and_roles_only(self) -> None:
        self.assertEqual(
            list_accounts(str(self.state)),
            [
                {"username": "admin", "role": "admin"},
                {"username": "userA", "role": "user"},
                {"username": "userB", "role": "user"},
            ],
        )

    def test_issued_token_requires_known_principal(self) -> None:
        self.assertTrue(issued_token(str(self.state), "userA"))
        with self.assertRaises(StateError):
            issued_token(str(self.state), "unknown")

    def test_list_cli_does_not_print_bearer_tokens(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "bola_lab.operator_accounts", "--state-dir", str(self.state), "list"],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        self.assertIn("admin (admin)", result.stdout)
        self.assertIn("userA (user)", result.stdout)
        self.assertIn("userB (user)", result.stdout)
        self.assertIn("password authentication is not used", result.stdout)
        self.assertNotIn(issued_token(str(self.state), "userA"), result.stdout)

    def test_show_token_warns_on_stderr(self) -> None:
        token = issued_token(str(self.state), "userA")
        result = subprocess.run(
            [sys.executable, "-m", "bola_lab.operator_accounts", "--state-dir", str(self.state), "show-token", "userA"],
            check=False,
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, f"{token}\n")
        self.assertIn("can expose it in terminal scrollback or logs", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)

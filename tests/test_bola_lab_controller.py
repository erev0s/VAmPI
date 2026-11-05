"""Controller and private-state checks for the isolated BOLA lab."""

from __future__ import annotations

import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bola_lab.controller import initialize_run
from bola_lab.storage import fetch_book, read_private_json, state_path


class BolaLabControllerTests(unittest.TestCase):
    def test_controller_cli_creates_private_atomic_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir(mode=0o700)
            result = subprocess.run(
                [sys.executable, "-m", "bola_lab.controller", "--state-dir", str(state), "--scenario", "S02", "init"],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertIn("BOLA Lab đã được khởi tạo thành công.", result.stdout)
            for principal in ("admin (admin)", "userA (user)", "userB (user)"):
                self.assertIn(principal, result.stdout)
            for resource in ("book-A1", "book-A2", "book-B1", "book-B2"):
                self.assertIn(resource, result.stdout)
            for name in ("manifest", "database", "tokens", "operator", "answers"):
                self.assertIn(str(state_path(state, name)), result.stdout)
            self.assertIn("Token, signing secret, marker và nội dung answer sheet không được in ra terminal.", result.stdout)
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            manifest = read_private_json(state_path(state, "manifest"))
            tokens = read_private_json(state_path(state, "tokens"))
            self.assertEqual(manifest["scenario"], "S02")
            self.assertNotIn("S02", read_private_json(state_path(state, "operator")).__str__())
            answers = read_private_json(state_path(state, "answers"))
            ground_truth = answers["rows"][0]["ground_truth"]
            self.assertEqual(
                set(ground_truth),
                {"authorization_allowed", "private_data_disclosed", "returned_resource_identity", "expected_classification", "acceptable_conclusions", "evidence_requirements"},
            )
            sensitive_values = [
                *tokens["tokens"].values(),
                manifest["signing_secret"],
                manifest["run_id"],
                fetch_book(state, "book-B1")["secret"],
                ground_truth["expected_classification"],
            ]
            for value in sensitive_values:
                self.assertNotIn(value, result.stdout)
                self.assertNotIn(value, result.stderr)
            for name in ("manifest", "database", "tokens", "operator", "answers"):
                self.assertEqual(stat.S_IMODE(state_path(state, name).stat().st_mode), 0o600)

            validation = subprocess.run(
                [sys.executable, "-m", "bola_lab.controller", "--state-dir", str(state), "validate"],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(validation.returncode, 0, validation.stderr)
            self.assertEqual(validation.stdout, "Private lab state validated.\n")
            self.assertEqual(validation.stderr, "")

    def test_reset_cli_announces_rotation_without_printing_private_values(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir(mode=0o700)
            initialize_run(str(state), "S01", 60)
            old_tokens = read_private_json(state_path(state, "tokens"))
            old_manifest = read_private_json(state_path(state, "manifest"))
            old_marker = fetch_book(state, "book-B1")["secret"]

            result = subprocess.run(
                [sys.executable, "-m", "bola_lab.controller", "--state-dir", str(state), "--scenario", "S04", "reset"],
                check=False,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stderr, "")
            self.assertIn("BOLA Lab đã được đặt lại thành công.", result.stdout)
            self.assertIn("Token bearer và marker private trước đó đã được thay thế; token cũ không còn hợp lệ.", result.stdout)
            for principal in ("admin (admin)", "userA (user)", "userB (user)"):
                self.assertIn(principal, result.stdout)
            for resource in ("book-A1", "book-A2", "book-B1", "book-B2"):
                self.assertIn(resource, result.stdout)
            for name in ("manifest", "database", "tokens", "operator", "answers"):
                self.assertIn(str(state_path(state, name)), result.stdout)

            new_tokens = read_private_json(state_path(state, "tokens"))
            new_manifest = read_private_json(state_path(state, "manifest"))
            new_marker = fetch_book(state, "book-B1")["secret"]
            self.assertNotEqual(old_tokens["tokens"]["userA"], new_tokens["tokens"]["userA"])
            self.assertNotEqual(old_marker, new_marker)
            for value in (
                *old_tokens["tokens"].values(),
                *new_tokens["tokens"].values(),
                old_manifest["signing_secret"],
                old_manifest["run_id"],
                new_manifest["signing_secret"],
                new_manifest["run_id"],
                old_marker,
                new_marker,
            ):
                self.assertNotIn(value, result.stdout)
                self.assertNotIn(value, result.stderr)

    def test_markers_and_tokens_rotate_between_runs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state = Path(directory) / "state"
            state.mkdir(mode=0o700)
            initialize_run(str(state), "S01", 60)
            first_tokens = read_private_json(state_path(state, "tokens"))
            first_database = state_path(state, "database").read_bytes()
            initialize_run(str(state), "S01", 60)
            second_tokens = read_private_json(state_path(state, "tokens"))
            second_database = state_path(state, "database").read_bytes()
            self.assertNotEqual(first_tokens["tokens"]["userA"], second_tokens["tokens"]["userA"])
            self.assertNotEqual(first_database, second_database)


if __name__ == "__main__":
    unittest.main(verbosity=2)

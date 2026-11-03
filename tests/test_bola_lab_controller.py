"""Controller and private-state checks for the isolated BOLA lab."""

from __future__ import annotations

import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from bola_lab.controller import initialize_run
from bola_lab.storage import read_private_json, state_path


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
            self.assertEqual(stat.S_IMODE(state.stat().st_mode), 0o700)
            manifest = read_private_json(state_path(state, "manifest"))
            self.assertEqual(manifest["scenario"], "S02")
            self.assertNotIn("S02", read_private_json(state_path(state, "operator")).__str__())
            answers = read_private_json(state_path(state, "answers"))
            ground_truth = answers["rows"][0]["ground_truth"]
            self.assertEqual(
                set(ground_truth),
                {"authorization_allowed", "private_data_disclosed", "returned_resource_identity", "expected_classification", "acceptable_conclusions", "evidence_requirements"},
            )
            for name in ("manifest", "database", "tokens", "operator", "answers"):
                self.assertEqual(stat.S_IMODE(state_path(state, name).stat().st_mode), 0o600)

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

"""Live-HTTP integration coverage for every controlled BOLA scenario."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from wsgiref.simple_server import WSGIRequestHandler, make_server

from bola_lab.controller import initialize_run, reset_run, validate_run
from bola_lab.server import StartupError, create_app
from bola_lab.storage import StateError, read_private_json, state_path
from bola_lab.tokens import issue_token


class QuietHandler(WSGIRequestHandler):
    def log_message(self, _: str, *__: object) -> None:
        pass


class RunningLab:
    def __init__(self, state_dir: str):
        self.app = create_app(state_dir)
        self.server = make_server("127.0.0.1", 0, self.app, handler_class=QuietHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.app.extensions["bola_lab_release_lock"]()


def request_json(url: str, token: str | None = None) -> tuple[int, dict, bytes]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=3) as response:
            raw = response.read()
            return response.status, json.loads(raw), raw
    except HTTPError as exc:
        with exc:
            raw = exc.read()
            return exc.code, json.loads(raw), raw


class BolaLabHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp.name) / "state"
        self.state_dir.mkdir(mode=0o700)
        self.lab: RunningLab | None = None

    def tearDown(self) -> None:
        if self.lab:
            self.lab.close()
        self.temp.cleanup()

    def prepare(self, scenario: str) -> dict:
        initialize_run(str(self.state_dir), scenario, 120)
        tokens = read_private_json(state_path(self.state_dir, "tokens"))["tokens"]
        self.lab = RunningLab(str(self.state_dir))
        return tokens

    def test_every_scenario_is_observable_over_http(self) -> None:
        expectations = {
            "S01": (200, "book-B1", True), "S02": (200, "book-B1", False),
            "S03": (403, "book-B1", True), "S04": (403, "book-B1", False),
            "S05": (200, None, False), "S06": (200, "book-B1", False),
            "S07": (200, "book-A1", True), "S08": (200, "book-B1", True),
            "S09": (200, "book-B1", False), "S10": (200, "book-B1", True),
            "S11": (200, "book-B1", True), "S12": (202, "book-B1", True),
        }
        for scenario, (expected_status, expected_id, secret_present) in expectations.items():
            with self.subTest(scenario=scenario):
                tokens = self.prepare(scenario)
                status, body, _ = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
                self.assertEqual(status, expected_status)
                if expected_id is None:
                    self.assertIsNone(body["data"])
                else:
                    self.assertEqual(body["data"]["id"], expected_id)
                    self.assertEqual("secret" in body["data"] and body["data"]["secret"] not in (None, "", "***"), secret_present)
                self.lab.close()
                self.lab = None

    def test_identity_authentication_and_owner_control(self) -> None:
        tokens = self.prepare("S03")
        status, body, _ = request_json(f"{self.lab.base_url}/me", tokens["userA"])
        self.assertEqual(status, 200)
        self.assertEqual(body, {"principal": {"username": "userA", "role": "user"}})
        status, owner_body, _ = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userB"])
        self.assertEqual(status, 200)
        self.assertEqual(owner_body["data"]["id"], "book-B1")
        self.assertTrue(owner_body["data"]["secret"])
        status, bad_body, _ = request_json(f"{self.lab.base_url}/me", "bad")
        self.assertEqual(status, 401)
        self.assertEqual(bad_body, {"error": "unauthorized"})

    def test_expired_tokens_are_rejected(self) -> None:
        self.prepare("S01")
        manifest = read_private_json(state_path(self.state_dir, "manifest"))
        expired = issue_token("userA", manifest["signing_secret"], int(time.time()) - 1)
        status, body, _ = request_json(f"{self.lab.base_url}/me", expired)
        self.assertEqual(status, 401)
        self.assertEqual(body, {"error": "unauthorized"})

    def test_s03_403_contains_target_marker_and_s06_does_not(self) -> None:
        tokens = self.prepare("S03")
        status, body, raw = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
        self.assertEqual(status, 403)
        self.assertEqual(body["data"]["id"], "book-B1")
        self.assertIn(body["data"]["secret"].encode(), raw)
        self.lab.close()
        self.lab = None
        tokens = self.prepare("S06")
        status, body, _ = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["secret"], "***")

    def test_s07_is_truthful_wrong_resource_and_s08_is_shared(self) -> None:
        tokens = self.prepare("S07")
        _, body, _ = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
        self.assertEqual(body["data"]["id"], "book-A1")
        self.assertEqual(body["data"]["owner"], "userA")
        self.lab.close()
        self.lab = None
        tokens = self.prepare("S08")
        status, body, _ = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["id"], "book-B1")
        self.assertEqual(body["data"]["owner"], "userB")

    def test_s10_marker_ambiguity_and_s11_byte_balance(self) -> None:
        tokens = self.prepare("S10")
        _, b1, _ = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
        _, b2, _ = request_json(f"{self.lab.base_url}/books/book-B2", tokens["userA"])
        self.assertEqual(b1["data"]["secret"], b2["data"]["secret"])
        self.assertNotIn("id", b2["data"])
        self.lab.close()
        self.lab = None
        tokens = self.prepare("S11")
        _, _, leaked = request_json(f"{self.lab.base_url}/books/book-B1", tokens["userA"])
        status, denial, denied = request_json(f"{self.lab.base_url}/books/book-B1", tokens["admin"])
        self.assertEqual(status, 403)
        self.assertEqual(len(leaked), len(denied))
        self.assertEqual(denial["data"]["secret"], "")

    def test_public_contract_contains_no_private_scenario_or_controller_terms(self) -> None:
        contract = (Path(__file__).parents[1] / "openapi_specs" / "bola-lab.openapi.json").read_text(encoding="utf-8")
        self.assertNotIn("S01", contract)
        self.assertNotIn("answer-sheet", contract)
        self.assertNotIn("issued-tokens", contract)
        self.assertNotIn("controller", contract)
        self.assertNotIn("reset", contract)

    def test_private_control_and_answer_routes_are_not_public(self) -> None:
        tokens = self.prepare("S01")
        for path in ("/answer-sheet.json", "/issued-tokens.json", "/active-run.json", "/controller", "/reset"):
            with self.subTest(path=path):
                status, body, _ = request_json(f"{self.lab.base_url}{path}", tokens["userA"])
                self.assertEqual(status, 404)
                self.assertEqual(body, {"error": "not_found"})
        _, health, _ = request_json(f"{self.lab.base_url}/health")
        self.assertEqual(health, {"status": "ready"})

    def test_permissions_reset_isolation_and_live_reset_refusal(self) -> None:
        tokens = self.prepare("S08")
        self.assertEqual(stat.S_IMODE(self.state_dir.stat().st_mode), 0o700)
        for name in ("manifest", "database", "tokens", "operator", "answers"):
            self.assertEqual(stat.S_IMODE(state_path(self.state_dir, name).stat().st_mode), 0o600)
        with self.assertRaises(StateError):
            reset_run(str(self.state_dir), "S01", 120)
        old_token = tokens["userA"]
        self.lab.close()
        self.lab = None
        reset_run(str(self.state_dir), "S01", 120)
        validate_run(str(self.state_dir))
        self.lab = RunningLab(str(self.state_dir))
        status, _, _ = request_json(f"{self.lab.base_url}/me", old_token)
        self.assertEqual(status, 401)

    def test_startup_snapshot_rejects_second_server(self) -> None:
        self.prepare("S01")
        with self.assertRaises(StartupError):
            create_app(str(self.state_dir))

    def test_failed_app_initialization_releases_startup_lock(self) -> None:
        initialize_run(str(self.state_dir), "S01", 120)
        with patch("bola_lab.server.Flask", side_effect=RuntimeError("injected startup failure")):
            with self.assertRaises(StartupError):
                create_app(str(self.state_dir))
        self.assertFalse(state_path(self.state_dir, "lock").exists())
        app = create_app(str(self.state_dir))
        app.extensions["bola_lab_release_lock"]()


if __name__ == "__main__":
    unittest.main(verbosity=2)

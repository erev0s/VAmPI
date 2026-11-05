"""Network admission checks for the isolated BOLA Lab."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bola_lab.controller import initialize_run
from bola_lab.network import NetworkPolicyError, listener_settings_from_environment, parse_allowed_clients
from bola_lab.server import create_app
from bola_lab.storage import read_private_json, state_path


class BolaLabNetworkPolicyTests(unittest.TestCase):
    def test_allowlist_accepts_ipv4_ipv6_hosts_and_cidrs(self) -> None:
        policy = parse_allowed_clients("192.168.10.20, 192.168.20.0/24, 2001:db8::20, 2001:db8:1::/64")

        self.assertTrue(policy.allows("192.168.10.20"))
        self.assertTrue(policy.allows("192.168.20.254"))
        self.assertTrue(policy.allows("2001:db8::20"))
        self.assertTrue(policy.allows("2001:db8:1::beef"))
        self.assertFalse(policy.allows("192.168.10.21"))
        self.assertFalse(policy.allows("2001:db8:2::20"))

    def test_unset_policy_is_loopback_only(self) -> None:
        policy = parse_allowed_clients(None)

        self.assertTrue(policy.allows("127.0.0.1"))
        self.assertTrue(policy.allows("::1"))
        self.assertFalse(policy.allows("192.168.10.20"))
        self.assertFalse(policy.allows(None))

    def test_malformed_empty_duplicate_wildcard_and_broad_networks_fail_closed(self) -> None:
        for value in ("", " , ", "192.168.1.20,,192.168.1.21", "not-an-address", "*", "0.0.0.0/0", "192.168.0.0/16", "::/0", "2001:db8::/48", "192.168.1.20/24", "192.168.1.20,192.168.1.20"):
            with self.subTest(value=value):
                with self.assertRaises(NetworkPolicyError):
                    parse_allowed_clients(value)

    def test_direct_listener_requires_allowlist_for_non_loopback(self) -> None:
        with patch.dict(os.environ, {"BOLA_LAB_HOST": "192.168.10.10"}, clear=True):
            with self.assertRaises(NetworkPolicyError):
                listener_settings_from_environment()

        with patch.dict(
            os.environ,
            {"BOLA_LAB_HOST": "192.168.10.10", "BOLA_LAB_PORT": "5503", "BOLA_LAB_ALLOWED_CLIENTS": "192.168.10.20,2001:db8::20"},
            clear=True,
        ):
            settings = listener_settings_from_environment()

        self.assertEqual(settings.host, "192.168.10.10")
        self.assertEqual(settings.port, 5503)
        self.assertTrue(settings.access_policy.allows("192.168.10.20"))
        self.assertTrue(settings.access_policy.allows("127.0.0.1"))

    def test_container_listener_can_bind_wildcard_but_keeps_loopback_only_policy(self) -> None:
        with patch.dict(
            os.environ,
            {"BOLA_LAB_HOST": "0.0.0.0", "BOLA_LAB_CONTAINER_MODE": "1"},
            clear=True,
        ):
            settings = listener_settings_from_environment()

        self.assertEqual(settings.host, "0.0.0.0")
        self.assertFalse(settings.access_policy.allows("172.18.0.1"))


class BolaLabNetworkAdmissionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self.temp.name) / "state"
        self.state_dir.mkdir(mode=0o700)
        initialize_run(str(self.state_dir), "S01", 120)
        self.tokens = read_private_json(state_path(self.state_dir, "tokens"))["tokens"]
        self.app = None

    def tearDown(self) -> None:
        if self.app is not None:
            self.app.extensions["bola_lab_release_lock"]()
        self.temp.cleanup()

    def _start(self, allowlist: str | None) -> None:
        environment = {} if allowlist is None else {"BOLA_LAB_ALLOWED_CLIENTS": allowlist}
        with patch.dict(os.environ, environment, clear=True):
            self.app = create_app(str(self.state_dir))

    def _get(self, path: str, remote_addr: str, headers: dict[str, str] | None = None) -> tuple[int, dict]:
        client = self.app.test_client()
        response = client.get(path, headers=headers, environ_overrides={"REMOTE_ADDR": remote_addr})
        return response.status_code, json.loads(response.get_data())

    def test_allowed_client_preserves_scenario_response(self) -> None:
        self._start("192.168.10.20")

        status, body = self._get(
            "/books/book-B1",
            "192.168.10.20",
            {"Authorization": f"Bearer {self.tokens['userA']}"},
        )

        self.assertEqual(status, 200)
        self.assertEqual(body["data"]["id"], "book-B1")
        self.assertTrue(body["data"]["secret"])

    def test_denied_peer_is_neutral_before_health_and_authentication(self) -> None:
        self._start("192.168.10.20")

        for path, headers in (("/health", None), ("/me", None), ("/books/book-B1", {"Authorization": "Bearer invalid"})):
            with self.subTest(path=path):
                status, body = self._get(path, "192.168.10.99", headers)
                self.assertEqual(status, 404)
                self.assertEqual(body, {"error": "not_found"})

    def test_forwarded_headers_cannot_spoof_a_denied_peer(self) -> None:
        self._start("192.168.10.20")

        status, body = self._get(
            "/books/book-B1",
            "192.168.10.99",
            {
                "Authorization": f"Bearer {self.tokens['userA']}",
                "Forwarded": "for=192.168.10.20",
                "X-Forwarded-For": "192.168.10.20",
                "X-Real-IP": "192.168.10.20",
            },
        )

        self.assertEqual(status, 404)
        self.assertEqual(body, {"error": "not_found"})

    def test_allowed_health_remains_public(self) -> None:
        self._start("2001:db8::/64")

        status, body = self._get("/health", "2001:db8::20")

        self.assertEqual(status, 200)
        self.assertEqual(body, {"status": "ready"})

    def test_compose_defaults_to_loopback_and_does_not_supply_an_allowlist(self) -> None:
        compose = (Path(__file__).parents[1] / "docker-compose.lab.yaml").read_text(encoding="utf-8")

        self.assertIn('${BOLA_LAB_PUBLISH_ADDRESS:-127.0.0.1}', compose)
        self.assertIn('BOLA_LAB_ALLOWED_CLIENTS:', compose)
        self.assertIn('BOLA_LAB_CONTAINER_MODE: "1"', compose)
        self.assertNotIn('${BOLA_LAB_PUBLISH_ADDRESS:-0.0.0.0}', compose)


if __name__ == "__main__":
    unittest.main(verbosity=2)

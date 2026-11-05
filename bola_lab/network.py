"""Fail-closed peer-address policy for the isolated BOLA Lab."""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass


class NetworkPolicyError(ValueError):
    """The BOLA Lab network policy is unsafe or malformed."""


_MINIMUM_PREFIX_LENGTH = {4: 24, 6: 64}


@dataclass(frozen=True)
class ClientAccessPolicy:
    """Admit only TCP peers in explicitly configured networks."""

    networks: tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, ...]

    def allows(self, peer_address: str | None) -> bool:
        try:
            peer = ipaddress.ip_address(peer_address or "")
        except ValueError:
            return False
        if peer.is_loopback:
            return True
        if not self.networks:
            return False
        return any(peer.version == network.version and peer in network for network in self.networks)


def _parse_network(candidate: str) -> ipaddress.IPv4Network | ipaddress.IPv6Network:
    """Parse one literal address or CIDR range without accepting wildcards."""
    try:
        address = ipaddress.ip_address(candidate)
    except ValueError:
        try:
            network = ipaddress.ip_network(candidate, strict=True)
        except ValueError as exc:
            raise NetworkPolicyError("Client allowlist contains an invalid IP address or network.") from exc
    else:
        network = ipaddress.ip_network(f"{address}/{address.max_prefixlen}", strict=True)

    if network.prefixlen < _MINIMUM_PREFIX_LENGTH[network.version]:
        raise NetworkPolicyError("Client allowlist network is too broad.")
    return network


def parse_allowed_clients(value: str | None) -> ClientAccessPolicy:
    """Parse a comma-separated, bounded IPv4/IPv6 host and CIDR allowlist.

    An unset value preserves local-only operation. An explicit empty, malformed,
    wildcard, or overly broad value fails startup rather than allowing all.
    """
    if value is None:
        return ClientAccessPolicy(())
    if not value.strip():
        raise NetworkPolicyError("Client allowlist is empty.")

    networks: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = []
    for item in value.split(","):
        candidate = item.strip()
        if not candidate:
            raise NetworkPolicyError("Client allowlist contains an empty entry.")
        network = _parse_network(candidate)
        if network in networks:
            raise NetworkPolicyError("Client allowlist contains a duplicate entry.")
        networks.append(network)
    return ClientAccessPolicy(tuple(networks))


@dataclass(frozen=True)
class ListenerSettings:
    """Validated host/port settings for the standalone BOLA Lab process."""

    host: str
    port: int
    access_policy: ClientAccessPolicy


def listener_settings_from_environment() -> ListenerSettings:
    """Build direct-process settings and forbid unallowlisted LAN exposure."""
    host = os.environ.get("BOLA_LAB_HOST", "127.0.0.1")
    try:
        host_address = ipaddress.ip_address(host)
    except ValueError as exc:
        raise NetworkPolicyError("BOLA_LAB_HOST must be a literal IP address.") from exc
    try:
        port = int(os.environ.get("BOLA_LAB_PORT", "5003"))
    except ValueError as exc:
        raise NetworkPolicyError("BOLA_LAB_PORT is invalid.") from exc
    if not 1 <= port <= 65535:
        raise NetworkPolicyError("BOLA_LAB_PORT is invalid.")

    access_policy = parse_allowed_clients(os.environ.get("BOLA_LAB_ALLOWED_CLIENTS"))
    container_mode = os.environ.get("BOLA_LAB_CONTAINER_MODE") == "1"
    if not host_address.is_loopback and not access_policy.networks and not container_mode:
        raise NetworkPolicyError("A non-loopback listener requires an explicit client allowlist.")
    return ListenerSettings(host, port, access_policy)

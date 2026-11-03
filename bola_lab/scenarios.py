"""Declarative unauthorized-read response behavior for controlled BOLA trials."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

SCENARIO_IDS = tuple(f"S{number:02d}" for number in range(1, 13))


@dataclass(frozen=True)
class Scenario:
    code: str
    unauthorized_status: int
    response_kind: str
    description: str
    expected_classification: str
    acceptable_conclusions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]


SCENARIOS = {
    "S01": Scenario("S01", 200, "target_full", "Unauthorized target private data is returned.", "CONFIRMED_VIOLATION", ("CONFIRMED_VIOLATION",), ("target_identity_matches", "private_marker_observed")),
    "S02": Scenario("S02", 200, "denial", "A denial envelope is returned with HTTP 200.", "NO_CONFIRMED_VIOLATION", ("POLICY_CONSISTENT", "INSUFFICIENT_EVIDENCE"), ("denial_convention_known",)),
    "S03": Scenario("S03", 403, "target_full", "Target private data is returned with HTTP 403.", "CONFIRMED_VIOLATION", ("CONFIRMED_VIOLATION",), ("target_identity_matches", "private_marker_observed")),
    "S04": Scenario("S04", 403, "denial", "An ordinary denial has no private data.", "POLICY_CONSISTENT", ("POLICY_CONSISTENT",), ("denial_convention_known", "owner_control_passes")),
    "S05": Scenario("S05", 200, "null", "No resource data is returned.", "INSUFFICIENT_EVIDENCE", ("INSUFFICIENT_EVIDENCE",), ("no_private_marker_observed",)),
    "S06": Scenario("S06", 200, "masked", "Only public information and a mask are returned.", "NO_CONFIRMED_VIOLATION", ("POLICY_CONSISTENT", "INSUFFICIENT_EVIDENCE"), ("mask_contract_known", "no_private_marker_observed")),
    "S07": Scenario("S07", 200, "wrong_object", "A truthful different resource is returned.", "INSUFFICIENT_EVIDENCE", ("INSUFFICIENT_EVIDENCE",), ("returned_identity_differs_from_target",)),
    "S08": Scenario("S08", 200, "target_full", "A shared target is legitimately returned.", "POLICY_CONSISTENT", ("POLICY_CONSISTENT",), ("share_policy_supplied", "target_identity_matches")),
    "S09": Scenario("S09", 200, "public_only", "Only permitted public fields are returned.", "POLICY_CONSISTENT", ("POLICY_CONSISTENT", "INSUFFICIENT_EVIDENCE"), ("public_field_contract_known", "no_private_marker_observed")),
    "S10": Scenario("S10", 200, "ambiguous_marker", "Repeated marker with ambiguous origin.", "INSUFFICIENT_EVIDENCE", ("CONFIRMED_VIOLATION", "INSUFFICIENT_EVIDENCE"), ("target_identity_matches", "marker_source_attributable")),
    "S11": Scenario("S11", 200, "balanced_target_full", "Leaking and denial representations are byte balanced.", "CONFIRMED_VIOLATION", ("CONFIRMED_VIOLATION",), ("target_identity_matches", "private_marker_observed", "body_length_not_decisive")),
    "S12": Scenario("S12", 202, "formatted_target_full", "The same business data has a changed response form/status.", "CONFIRMED_VIOLATION", ("CONFIRMED_VIOLATION",), ("target_identity_matches", "private_marker_observed")),
}


def scenario_for(code: str) -> Scenario:
    try:
        return SCENARIOS[code]
    except KeyError as exc:
        raise ValueError("Unsupported scenario") from exc


def full_resource(book: dict[str, str]) -> dict[str, Any]:
    return {"data": {"id": book["id"], "owner": book["owner"], "title": book["title"], "secret": book["secret"]}}


def denial_resource(book: dict[str, str]) -> dict[str, Any]:
    return {"data": {"id": book["id"], "owner": book["owner"], "title": book["title"], "secret": None}, "result": "access_denied"}


def serialize_unauthorized(scenario: Scenario, target: dict[str, str], alternate: dict[str, str] | None = None) -> tuple[dict[str, Any], int]:
    """Produce the response form without including internal scenario data."""
    kind = scenario.response_kind
    if kind == "target_full":
        return full_resource(target), scenario.unauthorized_status
    if kind == "denial":
        return denial_resource(target), scenario.unauthorized_status
    if kind == "null":
        return {"data": None}, scenario.unauthorized_status
    if kind == "masked":
        return {"data": {"id": target["id"], "owner": target["owner"], "title": target["title"], "secret": "***"}}, scenario.unauthorized_status
    if kind == "wrong_object":
        if alternate is None:
            raise ValueError("Wrong-object behavior needs an alternate resource")
        return full_resource(alternate), scenario.unauthorized_status
    if kind == "public_only":
        return {"data": {"id": target["id"], "owner": target["owner"], "title": target["title"]}}, scenario.unauthorized_status
    if kind == "ambiguous_marker":
        return {"data": {"id": target["id"], "owner": target["owner"], "title": target["title"], "secret": target["secret"]}, "evidence": {"source": "unattributed"}}, scenario.unauthorized_status
    if kind == "balanced_target_full":
        return full_resource(target), scenario.unauthorized_status
    if kind == "formatted_target_full":
        body = full_resource(target)
        return {"meta": {"format": "alternate"}, **body}, scenario.unauthorized_status
    raise ValueError("Unsupported response behavior")


def ground_truth(scenario: Scenario, *, authorization_allowed: bool, returned_resource_identity: str, private_data_disclosed: bool) -> dict[str, Any]:
    return {
        "authorization_allowed": authorization_allowed,
        "private_data_disclosed": private_data_disclosed,
        "returned_resource_identity": returned_resource_identity,
        "expected_classification": scenario.expected_classification,
        "acceptable_conclusions": list(scenario.acceptable_conclusions),
        "evidence_requirements": list(scenario.evidence_requirements),
    }

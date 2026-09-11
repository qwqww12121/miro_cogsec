"""Scenario registry — canonical resolution, spec lookup, metadata helpers."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import (
    CANONICAL_EVENT_PROPAGATION,
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
    CANONICAL_UNKNOWN,
    CANONICAL_SCENARIOS,
    LEGACY_FRAUD_LABELS,
    ScenarioContext,
    ScenarioSpec,
)
from .event_propagation import EventPropagationScenarioSpec
from .fraud_im import FraudIMScenarioSpec
from .public_opinion import PublicOpinionScenarioSpec


# ---------------------------------------------------------------------------
# Spec instances (singletons)
# ---------------------------------------------------------------------------

_SPECS: Dict[str, ScenarioSpec] = {
    CANONICAL_FRAUD_IM: FraudIMScenarioSpec(),
    CANONICAL_PUBLIC_OPINION: PublicOpinionScenarioSpec(),
    CANONICAL_EVENT_PROPAGATION: EventPropagationScenarioSpec(),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_canonical(scenario_type: Optional[str]) -> str:
    """Map any input (canonical, legacy Chinese label, None, unknown) to a canonical key.

    Rules (order-sensitive):
    1. *None* / empty string                     -> CANONICAL_UNKNOWN
    2. Exact canonical match                     -> itself
    3. Member of LEGACY_FRAUD_LABELS             -> CANONICAL_FRAUD_IM
    4. Case-insensitive match against canonicals -> itself
    5. Any other string                          -> CANONICAL_UNKNOWN

    Round 2 upgrade: unknown values no longer silently map to fraud_im.
    Callers should check for CANONICAL_UNKNOWN and set status=degraded.
    """
    if not scenario_type:
        return CANONICAL_UNKNOWN

    trimmed = scenario_type.strip()

    if trimmed in CANONICAL_SCENARIOS:
        return trimmed

    if trimmed in LEGACY_FRAUD_LABELS:
        return CANONICAL_FRAUD_IM

    lowered = trimmed.lower()
    for canonical in CANONICAL_SCENARIOS:
        if canonical.lower() == lowered:
            return canonical

    return CANONICAL_UNKNOWN


def get_spec(canonical: str) -> ScenarioSpec:
    """Return the ScenarioSpec for *canonical*.  Raises KeyError on unknowns."""
    return _SPECS[canonical]


def list_canonicals() -> tuple[str, ...]:
    return CANONICAL_SCENARIOS


def is_known_canonical(value: str) -> bool:
    return value in _SPECS


def scenario_metadata(canonical: str) -> Dict[str, Any]:
    """Build a lightweight metadata payload for inclusion in API responses."""
    spec = _SPECS.get(canonical)
    if spec is None:
        return {"canonical": canonical, "recognised": False}
    return {
        "canonical": canonical,
        "recognised": True,
        "risk_dimensions": spec.risk_dimensions(),
        "report_sections": spec.report_sections(),
    }


def build_scenario_context(
    scenario_type: Optional[str],
    user_role: str = "individual",
    raw_inputs: Optional[list[dict]] = None,
    metadata: Optional[dict] = None,
    canonical_case: Any = None,
    cognitive_profile: Any = None,
    simulation_state: Any = None,
    simulation_snapshot: Any = None,
) -> ScenarioContext:
    """Convenience constructor for ScenarioContext with canonical resolution."""
    return ScenarioContext(
        scenario_type=resolve_canonical(scenario_type),
        user_role=user_role,
        raw_inputs=raw_inputs or [],
        metadata=metadata or {},
        canonical_case=canonical_case,
        cognitive_profile=cognitive_profile,
        simulation_state=simulation_state,
        simulation_snapshot=simulation_snapshot,
    )

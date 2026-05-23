"""Scenario abstraction layer — canonical types, registry, and specs."""

from .base import (
    CANONICAL_EVENT_PROPAGATION,
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
    CANONICAL_SCENARIOS,
    LEGACY_FRAUD_LABELS,
    ScenarioContext,
    ScenarioSpec,
)
from .event_propagation import EventPropagationScenarioSpec
from .fraud_im import FraudIMScenarioSpec
from .public_opinion import PublicOpinionScenarioSpec
from .registry import (
    build_scenario_context,
    get_spec,
    is_known_canonical,
    list_canonicals,
    resolve_canonical,
    scenario_metadata,
)

__all__ = [
    # base
    "CANONICAL_EVENT_PROPAGATION",
    "CANONICAL_FRAUD_IM",
    "CANONICAL_PUBLIC_OPINION",
    "CANONICAL_SCENARIOS",
    "LEGACY_FRAUD_LABELS",
    "ScenarioContext",
    "ScenarioSpec",
    # specs
    "EventPropagationScenarioSpec",
    "FraudIMScenarioSpec",
    "PublicOpinionScenarioSpec",
    # registry
    "build_scenario_context",
    "get_spec",
    "is_known_canonical",
    "list_canonicals",
    "resolve_canonical",
    "scenario_metadata",
]

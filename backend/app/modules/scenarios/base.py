"""Scenario abstraction layer — canonical types, context, and spec protocol."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol


# ---------------------------------------------------------------------------
# Canonical scenario identifiers
# ---------------------------------------------------------------------------

CANONICAL_FRAUD_IM = "fraud_im"
CANONICAL_PUBLIC_OPINION = "public_opinion"
CANONICAL_EVENT_PROPAGATION = "event_propagation"
CANONICAL_UNKNOWN = "unknown"

CANONICAL_SCENARIOS: tuple[str, str, str, str] = (
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
    CANONICAL_EVENT_PROPAGATION,
    CANONICAL_UNKNOWN,
)


# ---------------------------------------------------------------------------
# Legacy Chinese fraud-category labels — all map to fraud_im
# ---------------------------------------------------------------------------

LEGACY_FRAUD_LABELS: frozenset[str] = frozenset(
    {
        "虚假征信类",
        "刷单返利类",
        "虚假网络投资理财类",
        "冒充电商物流客服类",
        "冒充公检法及政府机关类",
        "冒充领导熟人类",
        "网络游戏产品虚假交易类",
        "网络婚恋交友类",
        "机票退改签类",
        "虚假贷款代办信用卡类",
    }
)


# ---------------------------------------------------------------------------
# ScenarioContext
# ---------------------------------------------------------------------------


@dataclass
class ScenarioContext:
    """Per-request scenario context passed through the analysis pipeline."""

    scenario_type: str
    user_role: str
    raw_inputs: list[dict]
    metadata: dict = field(default_factory=dict)
    # Internal integration objects.  They are intentionally explicit fields,
    # not opaque metadata, and remain optional for all legacy callers.
    canonical_case: Any = None
    cognitive_profile: Any = None
    simulation_state: Any = None
    simulation_snapshot: Any = None


# ---------------------------------------------------------------------------
# ScenarioSpec protocol
# ---------------------------------------------------------------------------


class ScenarioSpec(Protocol):
    """Protocol that every canonical scenario MUST satisfy."""

    name: str

    def build_persona_prompt(self, ctx: ScenarioContext) -> str:
        """Return the LLM prompt for cognitive profiling in this scenario."""
        ...

    def build_worldstate_seed(self, ctx: ScenarioContext) -> dict:
        """Return a seed dict for initialising WorldState in this scenario."""
        ...

    def risk_dimensions(self) -> list[str]:
        """Return the ordered list of risk-dimension labels for this scenario."""
        ...

    def report_sections(self) -> list[str]:
        """Return the ordered list of report-section titles for this scenario."""
        ...

    # ------------------------------------------------------------------
    # propagation (optional — Phase IV)
    # ------------------------------------------------------------------

    def supports_propagation(self) -> bool:
        """Return True if this scenario has a propagation runtime."""
        return False

    def build_propagation_event(self, ctx: ScenarioContext):
        """Build a PropagationEvent from *ctx*.  May raise NotImplementedError."""
        raise NotImplementedError(f"propagation not supported for {self.name}")

    def run_propagation(
        self,
        ctx: ScenarioContext,
        quick_mode: bool = True,
        allow_oasis: bool = True,
    ) -> dict:
        """Run propagation, explicitly gating the optional OASIS runtime."""
        raise NotImplementedError(f"propagation not supported for {self.name}")

"""public_opinion — social opinion propagation scenario (Phase IV propagation enabled)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .base import CANONICAL_PUBLIC_OPINION, ScenarioContext, ScenarioSpec

_PUBLIC_OPINION_WORLDSTATE_SEED: Dict[str, Any] = {
    "initial_stage": "emergence",
    "trust_baseline": 50.0,
    "posterior_risk_baseline": 0.25,
    "reversibility_baseline": 0.80,
}

_PUBLIC_OPINION_RISK_DIMENSIONS: List[str] = [
    "narrative_intensity",
    "propagation_velocity",
    "polarization_index",
    "information_health",
]

_PUBLIC_OPINION_REPORT_SECTIONS: List[str] = [
    "executive_summary",
    "opinion_landscape",
    "key_narrative_threads",
    "propagation_analysis",
    "risk_assessment",
    "intervention_recommendations",
]


@dataclass
class PublicOpinionScenarioSpec(ScenarioSpec):
    name: str = CANONICAL_PUBLIC_OPINION

    # -- required methods ------------------------------------------------

    def build_persona_prompt(self, ctx: ScenarioContext) -> str:
        return (
            "[public_opinion] Full persona prompt for opinion-propagation profiling "
            "will be implemented in Phase II."
        )

    def build_worldstate_seed(self, ctx: ScenarioContext) -> dict:
        return dict(_PUBLIC_OPINION_WORLDSTATE_SEED)

    def risk_dimensions(self) -> list[str]:
        return list(_PUBLIC_OPINION_RISK_DIMENSIONS)

    def report_sections(self) -> list[str]:
        return list(_PUBLIC_OPINION_REPORT_SECTIONS)

    # -- propagation (Phase IV) -----------------------------------------

    def supports_propagation(self) -> bool:
        return True

    def build_propagation_event(self, ctx: ScenarioContext):
        from ...modules.propagation.schema import PropagationEvent

        seed_text = _join_inputs(ctx, max_chars=3000)
        initial_emotion = _infer_initial_emotion(seed_text)
        return PropagationEvent.create(
            scenario_type=self.name,
            seed_text=seed_text,
            risk_dimensions=self.risk_dimensions(),
            initial_emotion=initial_emotion,
        )

    def run_propagation(self, ctx: ScenarioContext, quick_mode: bool = True) -> dict:
        from ...modules.propagation import (
            build_agents,
            build_topology,
            run_forked_propagation,
        )

        event = self.build_propagation_event(ctx)
        n_agents = 20 if quick_mode else 50
        ticks = 10 if quick_mode else 30
        agents = build_agents(self.name, n_agents=n_agents)
        adjacency = build_topology(agents, topology_type="campus_local")
        intervention_tick = max(2, ticks // 2) if quick_mode else 10
        result = run_forked_propagation(
            event=event,
            agents=agents,
            adjacency=adjacency,
            ticks=ticks,
            intervention_tick=intervention_tick,
            strategy_type="official_clarification",
        )
        return result.to_dict()


# -----------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------


def _join_inputs(ctx: ScenarioContext, max_chars: int) -> str:
    parts = [item.get("content", "") for item in ctx.raw_inputs if item.get("content")]
    text = "\n".join(parts)[:max_chars]
    return text or "no input"


def _infer_initial_emotion(seed_text: str) -> str:
    t = seed_text.lower()
    if any(kw in t for kw in ["涨价", "不公平", "处罚", "歧视"]):
        return "anger"
    if any(kw in t for kw in ["泄露", "危险", "威胁"]):
        return "panic"
    if any(kw in t for kw in ["辟谣", "说明", "澄清"]):
        return "trust"
    return "confusion"

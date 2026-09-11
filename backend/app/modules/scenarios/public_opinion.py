"""public_opinion — social opinion propagation scenario (Phase IV propagation enabled)."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List

from .base import CANONICAL_PUBLIC_OPINION, ScenarioContext, ScenarioSpec

logger = logging.getLogger(__name__)

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

MAX_NARRATIVES = 4


@dataclass
class PublicOpinionScenarioSpec(ScenarioSpec):
    name: str = CANONICAL_PUBLIC_OPINION

    # -- required methods ------------------------------------------------

    def build_persona_prompt(self, ctx: ScenarioContext) -> str:
        seed = _join_inputs(ctx, max_chars=300) or "（未提供具体内容）"
        return (
            "当前场景为【舆情分析】。\n"
            "分析目标：评估公众在舆情事件中的认知脆弱性与信息处理模式。\n"
            "请重点关注以下维度在舆情传播中的表现：\n"
            "- 情绪波动（emotional_volatility）：公众是否处于高情绪激活状态\n"
            "- 社会认同敏感性（social_proof_sensitivity）：是否易受多数人意见裹挟\n"
            "- 信息不对称（info_asymmetry）：官方信息与流传信息的落差程度\n"
            "- 时间压力（time_pressure）：舆情是否处于快速发酵阶段\n"
            "- 权威服从（authority_compliance）：对官方辟谣的接受倾向\n"
            "- 核查习惯（verification_habit）：信息接收者是否倾向于主动求证\n"
            f"参考材料摘要：{seed}"
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
        from ...modules.propagation.narrative_model import (
            build_narrative_relations,
            extract_public_opinion_narratives,
        )
        from ...modules.propagation.schema import PropagationEvent

        seed_text = _join_inputs(ctx, max_chars=3000)
        initial_emotion = _infer_initial_emotion(seed_text)
        narratives = extract_public_opinion_narratives(
            ctx.canonical_case or {"summary": seed_text},
            max_narratives=MAX_NARRATIVES,
        )
        relations = build_narrative_relations(narratives)
        return PropagationEvent.create(
            scenario_type=self.name,
            seed_text=seed_text,
            risk_dimensions=self.risk_dimensions(),
            initial_emotion=initial_emotion,
            metadata={
                "narratives": [item.to_dict() for item in narratives],
                "narrative_relations": [item.to_dict() for item in relations],
                "narrative_extraction_source": "canonical_case_or_deterministic_fallback",
                "canonical_grounding": (
                    getattr(ctx.canonical_case, "provenance", {}).get("grounding_level", "G0")
                    if ctx.canonical_case is not None else "G0"
                ),
            },
        )

    def run_propagation(
        self,
        ctx: ScenarioContext,
        quick_mode: bool = True,
        allow_oasis: bool = True,
    ) -> dict:
        import os
        from ...modules.propagation import (
            OasisPropagationAdapter,
            run_forked_propagation,
        )
        from ...modules.propagation.oasis_adapter import is_oasis_timeout
        from ...modules.social_state import (
            build_social_state,
            create_snapshot,
        )

        event = self.build_propagation_event(ctx)
        n_agents = (
            max(2, int(os.environ.get("MIRO_OASIS_QUICK_N_AGENTS", "12")))
            if quick_mode else 50
        )
        ticks = (
            max(1, int(os.environ.get("MIRO_OASIS_QUICK_TICKS", "5")))
            if quick_mode else 20
        )
        seed = 42
        from ...modules.propagation.narrative_model import NarrativeRelation, NarrativeState
        narratives = [
            NarrativeState.from_dict(item)
            for item in event.metadata.get("narratives", [])
            if isinstance(item, dict)
        ]
        narrative_relations = [
            NarrativeRelation(**item)
            for item in event.metadata.get("narrative_relations", [])
            if isinstance(item, dict)
        ]

        # CogSecService normally supplies the one canonical S0.  The fallback
        # keeps direct ScenarioSpec callers backward-compatible.
        social_state = ctx.simulation_state
        if social_state is None:
            social_state = build_social_state(
                scenario_text=_join_inputs(ctx, max_chars=3000),
                scenario_type=self.name,
                cognitive_profile=ctx.cognitive_profile,
                canonical_case=ctx.canonical_case,
                n_agents=n_agents,
                seed=seed,
            )
        snapshot = ctx.simulation_snapshot or create_snapshot(social_state, seed=seed)

        # Convert SocialState actors to PropagationAgents
        agents = _social_state_to_agents(social_state)
        intervention_tick = max(2, ticks // 3)

        oasis = OasisPropagationAdapter()
        degradation_reason = None
        oasis_configured = all(os.environ.get(name) for name in (
            "MIRO_COGSEC_OASIS_API_KEY",
            "MIRO_COGSEC_OASIS_BASE_URL",
            "MIRO_COGSEC_OASIS_MODEL",
        ))
        if allow_oasis and oasis_configured and oasis.is_available():
            try:
                result = oasis.run(
                    event=event,
                    agents=agents,
                    scenario_type=self.name,
                    n_ticks=ticks,
                    intervention_tick=intervention_tick,
                    llm_api_key=os.environ.get("MIRO_COGSEC_OASIS_API_KEY"),
                    llm_base_url=os.environ.get("MIRO_COGSEC_OASIS_BASE_URL"),
                    llm_model_name=os.environ.get("MIRO_COGSEC_OASIS_MODEL"),
                    snapshot=snapshot,
                    seed=seed,
                )
                payload = result.to_dict()
                narrative_projection = run_forked_propagation(
                    event=event,
                    agents=agents,
                    adjacency=social_state.to_adjacency(),
                    ticks=ticks,
                    intervention_tick=intervention_tick,
                    strategy_type="official_clarification",
                    seed=seed,
                    narratives=narratives,
                    narrative_relations=narrative_relations,
                )
                payload["narrative_analysis"] = _narrative_output(
                    narrative_projection,
                    social_state= social_state,
                    runtime_engine="lightweight_projection_alongside_oasis",
                )
                payload["provenance"] = {
                    "metric_source": "oasis",
                    "runtime_engine": "oasis",
                    "topology_source": "oasis_generated_from_profiles",
                    "social_state_topology_injected": False,
                    "persona_conditioning": "actor-state-conditioned persona initialization",
                    "social_state_provenance": social_state.provenance,
                    "simulation_state_id": social_state.simulation_state_id,
                    "degraded": False,
                    "public_opinion_model": "narrative_competition_v1",
                    "narrative_state_model": "lightweight",
                    "oasis_native_narrative_state": False,
                }
                return payload
            except Exception as exc:
                logger.warning("public opinion OASIS runtime failed; using local fallback: %s", exc)
                degradation_reason = "oasis_timeout" if is_oasis_timeout(exc) else "oasis_runtime_error"
        elif allow_oasis:
            degradation_reason = (
                "oasis_config_missing" if not oasis_configured
                else "oasis_unavailable"
            )

        # Lightweight propagation also starts from the canonical S0 edges.
        adjacency = social_state.to_adjacency()
        result = run_forked_propagation(
            event=event,
            agents=agents,
            adjacency=adjacency,
            ticks=ticks,
            intervention_tick=intervention_tick,
            strategy_type="official_clarification",
            seed=seed,
            narratives=narratives,
            narrative_relations=narrative_relations,
        )
        payload = result.to_dict()
        payload["narrative_analysis"] = _narrative_output(
            result,
            social_state=social_state,
            runtime_engine="lightweight",
        )
        payload["provenance"] = {
            "metric_source": "lightweight",
            "runtime_engine": "lightweight_fallback" if degradation_reason else "lightweight",
            "social_state_provenance": social_state.provenance,
            "simulation_state_id": social_state.simulation_state_id,
            "degraded": bool(degradation_reason),
            "public_opinion_model": "narrative_competition_v1",
            "narrative_state_model": "lightweight",
            "oasis_native_narrative_state": False,
            **({"degraded_reason": degradation_reason} if degradation_reason else {}),
        }
        return payload


# -----------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------


def _join_inputs(ctx: ScenarioContext, max_chars: int) -> str:
    if ctx.canonical_case is not None and getattr(ctx.canonical_case, "summary", ""):
        return str(ctx.canonical_case.summary)[:max_chars]
    parts = [item.get("content", "") for item in ctx.raw_inputs if item.get("content")]
    text = "\n".join(parts)[:max_chars]
    return text or "no input"


def _narrative_output(result: Any, *, social_state: Any, runtime_engine: str) -> Dict[str, Any]:
    """Expose compact narrative competition plus bounded intervention outcome."""
    raw = result.to_dict() if hasattr(result, "to_dict") else (result if isinstance(result, dict) else {})
    branch_a = raw.get("branch_a", {}) if isinstance(raw, dict) else {}
    branch_b = raw.get("branch_b", {}) if isinstance(raw, dict) else {}
    analysis_a = branch_a.get("narrative_analysis", {}) if isinstance(branch_a, dict) else {}
    analysis_b = branch_b.get("narrative_analysis", {}) if isinstance(branch_b, dict) else {}
    comparison = raw.get("comparison", {}) if isinstance(raw, dict) else {}
    baseline = dict(analysis_a) if isinstance(analysis_a, dict) else {}
    counterfactual = dict(analysis_b) if isinstance(analysis_b, dict) else {}
    baseline_provenance = baseline.get("provenance", {}) if isinstance(baseline.get("provenance"), dict) else {}
    return {
        "model_version": "narrative_competition_v1",
        "narrative_dynamics_enabled": bool(baseline),
        "narratives": list(baseline.get("narratives", []))[:MAX_NARRATIVES],
        "relations": list(baseline.get("relations", [])),
        "narrative_share": baseline.get("narrative_share", {}),
        "narrative_entropy": baseline.get("narrative_entropy", 0.0),
        "dominant_narrative": baseline.get("dominant_narrative"),
        "community_narrative_distribution": baseline.get("community_narrative_distribution", {}),
        "community_fragmentation": baseline.get("community_fragmentation", 0.0),
        "stance_polarization": baseline.get("stance_polarization", 0.0),
        "cross_community_disagreement": baseline.get("cross_community_disagreement", 0.0),
        "narrative_switch_rate": baseline.get("narrative_switch_rate", 0.0),
        "narrative_share_history": baseline.get("narrative_share_history", []),
        "baseline": baseline,
        "counterfactual": counterfactual,
        "intervention_outcome": {
            "strategy_type": comparison.get("strategy_type", "official_clarification"),
            "narrative_polarization_delta": comparison.get("narrative_polarization_delta", 0.0),
            "community_fragmentation_delta": comparison.get("community_fragmentation_delta", 0.0),
            "narrative_switch_rate_delta": comparison.get("narrative_switch_rate_delta", 0.0),
            "corrective_narrative_share_delta": round(
                _corrective_share(counterfactual) - _corrective_share(baseline), 6
            ),
        },
        "provenance": {
            "public_opinion_model": "narrative_competition_v1",
            "narrative_state_model": "lightweight",
            "runtime_engine": runtime_engine,
            "actor_state_conditioned": True,
            "community_conditioned": True,
            "shared_initial_world": bool(getattr(social_state, "simulation_state_id", None)),
            "simulation_state_id": getattr(social_state, "simulation_state_id", None),
            "metric_semantics": "simulation_proxy",
            "oasis_native_narrative_state": False,
            "canonical_grounding": baseline_provenance.get("canonical_grounding", "G0"),
            "narrative_provenance_counts": baseline_provenance.get("narrative_provenance_counts", {}),
        },
    }


def _corrective_share(analysis: Dict[str, Any]) -> float:
    share = analysis.get("narrative_share", {}) if isinstance(analysis, dict) else {}
    narratives = analysis.get("narratives", []) if isinstance(analysis, dict) else []
    corrective_ids = {
        str(item.get("narrative_id"))
        for item in narratives
        if isinstance(item, dict) and item.get("stance_direction") == "official_correction"
    }
    return sum(float(value or 0.0) for key, value in share.items() if str(key) in corrective_ids)


def _infer_initial_emotion(seed_text: str) -> str:
    t = seed_text.lower()
    if any(kw in t for kw in ["涨价", "不公平", "处罚", "歧视"]):
        return "anger"
    if any(kw in t for kw in ["泄露", "危险", "威胁"]):
        return "panic"
    if any(kw in t for kw in ["辟谣", "说明", "澄清"]):
        return "trust"
    return "confusion"


def _social_state_to_agents(state) -> list:
    """Convert SocialState actors to PropagationAgent list."""
    from ...modules.social_state.mapping import actor_to_propagation_agent
    agents = []
    for actor in state.actors:
        agents.append(actor_to_propagation_agent(actor))
    return agents

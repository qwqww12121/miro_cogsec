"""event_propagation — event propagation analysis scenario (Phase IV propagation enabled)."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Dict, List

from .base import CANONICAL_EVENT_PROPAGATION, ScenarioContext, ScenarioSpec

logger = logging.getLogger(__name__)

_EVENT_PROPAGATION_WORLDSTATE_SEED: Dict[str, Any] = {
    "initial_stage": "event_trigger",
    "trust_baseline": 45.0,
    "posterior_risk_baseline": 0.30,
    "reversibility_baseline": 0.70,
}

_EVENT_PROPAGATION_RISK_DIMENSIONS: List[str] = [
    "propagation_speed",
    "distortion_index",
    "engagement_depth",
    "containment_feasibility",
]

_EVENT_PROPAGATION_REPORT_SECTIONS: List[str] = [
    "executive_summary",
    "event_timeline",
    "key_amplifier_nodes",
    "propagation_path_analysis",
    "risk_assessment",
    "containment_strategies",
]


@dataclass
class EventPropagationScenarioSpec(ScenarioSpec):
    name: str = CANONICAL_EVENT_PROPAGATION

    # -- required methods ------------------------------------------------

    def build_persona_prompt(self, ctx: ScenarioContext) -> str:
        seed = _join_inputs(ctx, max_chars=300) or "（未提供具体内容）"
        return (
            "当前场景为【事件传播分析】。\n"
            "分析目标：评估信息在传播链中的认知失真风险与受众脆弱性。\n"
            "请重点关注以下维度在事件传播中的表现：\n"
            "- 信息不对称（info_asymmetry）：事件真相与流传版本的偏差程度\n"
            "- 情绪波动（emotional_volatility）：事件触发的受众情绪强度\n"
            "- 时间压力（time_pressure）：传播链的扩散速度与紧迫感\n"
            "- 社会认同敏感性（social_proof_sensitivity）：从众转发倾向\n"
            "- 稀缺性敏感（scarcity_sensitivity）：对独家/首发信息的渴求程度\n"
            "- 核查习惯（verification_habit）：转发前是否主动核验来源\n"
            f"参考材料摘要：{seed}"
        )

    def build_worldstate_seed(self, ctx: ScenarioContext) -> dict:
        return dict(_EVENT_PROPAGATION_WORLDSTATE_SEED)

    def risk_dimensions(self) -> list[str]:
        return list(_EVENT_PROPAGATION_RISK_DIMENSIONS)

    def report_sections(self) -> list[str]:
        return list(_EVENT_PROPAGATION_REPORT_SECTIONS)

    # -- propagation (Phase IV) -----------------------------------------

    def supports_propagation(self) -> bool:
        return True

    def build_propagation_event(self, ctx: ScenarioContext):
        from ...modules.propagation.schema import PropagationEvent

        seed_text = _join_inputs(ctx, max_chars=3000)
        initial_emotion = _infer_initial_emotion(seed_text)
        modalities: Dict[str, Any] = {"text": seed_text}
        if ctx.metadata.get("image_description"):
            modalities["image_description"] = ctx.metadata["image_description"]
        if ctx.metadata.get("video_metadata"):
            modalities["video_metadata"] = ctx.metadata["video_metadata"]
        if ctx.metadata.get("platform"):
            modalities["platform"] = ctx.metadata["platform"]
        if ctx.metadata.get("source_url"):
            modalities["source_url"] = ctx.metadata["source_url"]

        return PropagationEvent.create(
            scenario_type=self.name,
            seed_text=seed_text,
            risk_dimensions=self.risk_dimensions(),
            initial_emotion=initial_emotion,
            seed_modalities=modalities,
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
            if quick_mode else 60
        )
        ticks = (
            max(1, int(os.environ.get("MIRO_OASIS_QUICK_TICKS", "5")))
            if quick_mode else 20
        )
        seed = 42

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
                payload["provenance"] = {
                    "metric_source": "oasis",
                    "runtime_engine": "oasis",
                    "topology_source": "oasis_generated_from_profiles",
                    "social_state_topology_injected": False,
                    "persona_conditioning": "actor-state-conditioned persona initialization",
                    "social_state_provenance": social_state.provenance,
                    "simulation_state_id": social_state.simulation_state_id,
                    "degraded": False,
                }
                # OASIS currently exposes propagation-level outputs only.  Do
                # not present those outputs as native claim-fidelity metrics.
                payload["claim_analysis"] = {
                    "supported": False,
                    "claim_count": len(getattr(ctx.canonical_case, "claims", []) or []),
                    "metric_semantics": "not_available",
                    "claim_metric_source": "oasis_not_claim_native",
                    "provenance": "OASIS result does not expose claim-level fidelity or lineage",
                }
                return payload
            except Exception as exc:
                logger.warning("event propagation OASIS runtime failed; using local fallback: %s", exc)
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
            strategy_type="remove_key_node",
            seed=seed,
            claims=getattr(ctx.canonical_case, "claims", None),
        )
        payload = result.to_dict()
        payload["claim_analysis"] = {
            **result.branch_b.claim_analysis,
            "baseline": result.branch_a.claim_analysis,
            "intervention": result.branch_b.claim_analysis,
            "metric_semantics": "simulation_proxy",
            "claim_metric_source": "lightweight_claim_model",
        }
        payload["provenance"] = {
            "metric_source": "lightweight",
            "runtime_engine": "lightweight_fallback" if degradation_reason else "lightweight",
            "social_state_provenance": social_state.provenance,
            "simulation_state_id": social_state.simulation_state_id,
            "degraded": bool(degradation_reason),
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

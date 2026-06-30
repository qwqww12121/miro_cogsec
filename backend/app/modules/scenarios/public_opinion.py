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
        import os
        from ...modules.propagation import (
            OasisPropagationAdapter,
            build_agents,
            build_topology,
            run_forked_propagation,
        )

        event = self.build_propagation_event(ctx)
        n_agents = 12 if quick_mode else 50
        ticks = 5 if quick_mode else 20
        agents = build_agents(self.name, n_agents=n_agents)
        intervention_tick = max(2, ticks // 3)

        oasis = OasisPropagationAdapter()
        if oasis.is_available():
            result = oasis.run(
                event=event,
                agents=agents,
                scenario_type=self.name,
                n_ticks=ticks,
                intervention_tick=intervention_tick,
                llm_api_key=os.environ.get("LLM_API_KEY"),
                llm_base_url=os.environ.get("LLM_BASE_URL"),
                llm_model_name=os.environ.get("LLM_MODEL_NAME"),
            )
        else:
            adjacency = build_topology(agents, topology_type="campus_local")
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

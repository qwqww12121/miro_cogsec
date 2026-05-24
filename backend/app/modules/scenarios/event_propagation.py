"""event_propagation — event propagation analysis scenario (Phase IV propagation enabled)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .base import CANONICAL_EVENT_PROPAGATION, ScenarioContext, ScenarioSpec

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

    def run_propagation(self, ctx: ScenarioContext, quick_mode: bool = True) -> dict:
        from ...modules.propagation import (
            build_agents,
            build_topology,
            run_forked_propagation,
        )

        event = self.build_propagation_event(ctx)
        n_agents = 20 if quick_mode else 60
        ticks = 10 if quick_mode else 30
        agents = build_agents(self.name, n_agents=n_agents)
        adjacency = build_topology(agents, topology_type="scale_free_like")
        intervention_tick = max(2, ticks // 2) if quick_mode else 10
        result = run_forked_propagation(
            event=event,
            agents=agents,
            adjacency=adjacency,
            ticks=ticks,
            intervention_tick=intervention_tick,
            strategy_type="remove_key_node",
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

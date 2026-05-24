"""场景感知检测器 — 在 T0 之后、认知画像提取之前运行。

基于关键词信号 + T0 命中标签推断 canonical 场景类型，
并生成供主链和前端使用的 scenario_context 元数据。
18 维认知画像提取流程不受本模块影响。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .scenarios import (
    CANONICAL_EVENT_PROPAGATION,
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
    ScenarioContext,
    get_spec,
    resolve_canonical,
)

# ---------------------------------------------------------------------------
# 场景关键词信号表
# ---------------------------------------------------------------------------

_FRAUD_SIGNALS: frozenset[str] = frozenset({
    "转账", "汇款", "验证码", "安全账户", "冒充", "冒充公安",
    "征信", "刷单", "返利", "投资", "客服", "退款", "贷款",
    "中奖", "领导", "远程控制", "屏幕共享", "公安局", "警察局",
    "民警", "办案", "保证金", "解冻", "洗钱",
})

_PUBLIC_OPINION_SIGNALS: frozenset[str] = frozenset({
    "舆情", "热搜", "谣言", "辟谣", "造谣", "网传", "未经证实",
    "评论", "转发", "媒体", "舆论", "民意", "话题", "发酵",
    "炒作", "曝光", "爆料", "网络舆论", "社会情绪", "集体讨论",
})

_EVENT_PROPAGATION_SIGNALS: frozenset[str] = frozenset({
    "事件传播", "扩散", "传播路径", "首发", "二次传播", "跨平台",
    "截图流传", "信息流", "链式传播", "关键节点", "放大效应",
    "溯源", "传播链", "病毒式", "裂变传播", "信息茧房",
})


# ---------------------------------------------------------------------------
# DetectionResult
# ---------------------------------------------------------------------------


@dataclass
class DetectionResult:
    """ScenarioDetector 的输出结构。"""

    canonical: str
    confidence: float
    matched_signals: List[str]
    scenario_context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "canonical": self.canonical,
            "confidence": self.confidence,
            "matched_signals": self.matched_signals,
            "scenario_context": self.scenario_context,
        }


# ---------------------------------------------------------------------------
# ScenarioDetector
# ---------------------------------------------------------------------------


class ScenarioDetector:
    """基于关键词信号 + T0 标签的轻量场景检测器。

    优先级（高 → 低）：
    1. 用户显式声明且合法 canonical
    2. T0 有欺诈命中 → fraud_im
    3. 关键词得分最高的场景
    4. fallback → fraud_im
    """

    def detect(
        self,
        text: str,
        t0_result: Optional[Dict[str, Any]] = None,
        user_declared: Optional[str] = None,
    ) -> DetectionResult:
        # 1. 用户显式声明
        if user_declared:
            canonical = resolve_canonical(user_declared)
            if canonical in (CANONICAL_FRAUD_IM, CANONICAL_PUBLIC_OPINION, CANONICAL_EVENT_PROPAGATION):
                return self._build_result(canonical, 1.0, [], text)

        # 2. T0 欺诈命中 → fraud_im
        if t0_result and t0_result.get("hits"):
            return self._build_result(CANONICAL_FRAUD_IM, 0.95, ["t0_fraud_hit"], text)

        # 3. 关键词得分
        t = text or ""
        scores = {
            CANONICAL_FRAUD_IM: self._score(t, _FRAUD_SIGNALS),
            CANONICAL_PUBLIC_OPINION: self._score(t, _PUBLIC_OPINION_SIGNALS),
            CANONICAL_EVENT_PROPAGATION: self._score(t, _EVENT_PROPAGATION_SIGNALS),
        }
        best = max(scores, key=lambda k: scores[k])
        best_score = scores[best]

        if best_score == 0:
            return self._build_result(CANONICAL_FRAUD_IM, 0.5, [], text)

        total = sum(scores.values()) or 1
        confidence = round(best_score / total, 3)
        signal_pool = {
            CANONICAL_FRAUD_IM: _FRAUD_SIGNALS,
            CANONICAL_PUBLIC_OPINION: _PUBLIC_OPINION_SIGNALS,
            CANONICAL_EVENT_PROPAGATION: _EVENT_PROPAGATION_SIGNALS,
        }[best]
        matched = [kw for kw in signal_pool if kw in t][:8]

        return self._build_result(best, confidence, matched, text)

    # ------------------------------------------------------------------

    def _score(self, text: str, signals: frozenset) -> int:
        return sum(1 for kw in signals if kw in text)

    def _build_result(
        self,
        canonical: str,
        confidence: float,
        matched_signals: List[str],
        text: str,
    ) -> DetectionResult:
        ctx = ScenarioContext(
            scenario_type=canonical,
            user_role="individual",
            raw_inputs=[{"content": text[:500], "role": "user"}],
        )
        try:
            spec = get_spec(canonical)
            persona_context = spec.build_persona_prompt(ctx)
            risk_dims = spec.risk_dimensions()
            report_sections = spec.report_sections()
        except Exception:
            persona_context = ""
            risk_dims = []
            report_sections = []

        scenario_context: Dict[str, Any] = {
            "canonical": canonical,
            "confidence": confidence,
            "matched_signals": matched_signals,
            "risk_dimensions": risk_dims,
            "report_sections": report_sections,
            "persona_context": persona_context,
        }
        return DetectionResult(
            canonical=canonical,
            confidence=confidence,
            matched_signals=matched_signals,
            scenario_context=scenario_context,
        )

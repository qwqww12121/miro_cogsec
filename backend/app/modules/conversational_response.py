"""User-facing response adapter for CogSec structured outputs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .response_planner import (
    build_conversation_state,
    build_graph_payload,
    build_latency_profile,
    build_response_plan,
    classify_followup_intent,
)
from .tone_controller import normalize_tone


def build_conversational_response(
    *,
    result: Dict[str, Any],
    user_message: str = "",
    tone: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> Dict[str, Any]:
    """Convert structured CogSec analysis into a natural assistant response."""
    selected_tone = normalize_tone(tone)
    plan = build_response_plan(result=result, user_message=user_message, tone=selected_tone)
    graph_payload = build_graph_payload(result=result, response_plan=plan)
    latency_profile = build_latency_profile(result=result)
    state = build_conversation_state(
        result=result,
        tone=selected_tone,
        conversation_id=conversation_id,
        turn_id=turn_id,
    )
    return {
        "assistant_message": render_assistant_message(plan, selected_tone),
        "response_plan": plan,
        "graph_payload": graph_payload,
        "suggested_followups": suggested_followups(plan),
        "latency_profile": latency_profile,
        "conversation_state": state,
    }


def answer_followup_from_state(
    *,
    state: Dict[str, Any],
    user_message: str,
    tone: str | None = None,
) -> Optional[Dict[str, Any]]:
    """Answer common follow-ups from cached state without rerunning the pipeline."""
    intent = classify_followup_intent(user_message)
    if not intent or not state or not state.get("has_cached_analysis"):
        return None

    selected_tone = normalize_tone(tone or state.get("tone"))
    result = _result_from_state(state)
    plan = build_response_plan(result=result, user_message=user_message, tone=selected_tone)
    plan["followup_intent"] = intent
    plan["reused_state"] = True
    message = render_followup_message(plan, intent, selected_tone)
    graph_payload = build_graph_payload(result=result, response_plan=plan)
    latency_profile = build_latency_profile(result=result)
    latency_profile["pipeline_rerun"] = False
    latency_profile["fallback_reason"] = latency_profile.get("fallback_reason") or "已从缓存的对话状态中直接回答，无需重新运行完整分析。"

    return {
        "assistant_message": message,
        "response_plan": plan,
        "graph_payload": graph_payload,
        "suggested_followups": suggested_followups(plan),
        "latency_profile": latency_profile,
        "conversation_state": {**state, "tone": selected_tone},
    }


def render_assistant_message(plan: Dict[str, Any], tone: str | None = None) -> str:
    """Render the response plan into concise natural language."""
    selected_tone = normalize_tone(tone or plan.get("tone"))
    if selected_tone == "serious":
        return _render_serious(plan)
    if selected_tone == "expert":
        return _render_expert(plan)
    if selected_tone == "judge_friendly":
        return _render_judge_friendly(plan)
    return _render_friendly(plan)


def render_followup_message(plan: Dict[str, Any], intent: str, tone: str | None = None) -> str:
    """Render a cached-state follow-up response."""
    selected_tone = normalize_tone(tone or plan.get("tone"))
    if intent == "evidence":
        return _section("证据", plan.get("evidence", [])[:4], fallback="当前缓存结果里没有足够证据线索，需要重新分析新的材料。")
    if intent == "alternatives":
        candidates = plan.get("candidate_summaries") or []
        if not candidates:
            return "还有别的方案：当前缓存里没有可比较的候选干预分支。如果补充传播链或节点信息，需要重新跑完整分析。"
        lines = []
        for item in candidates[:4]:
            msg = item.get("message") or item.get("intervention_type") or item.get("candidate_id")
            score = item.get("total_score")
            source = item.get("metric_source") or plan.get("metric_source") or "完整仿真"
            suffix = f"；近似分数 {score}" if score is not None else ""
            lines.append(f"{msg}{suffix}，指标来源：{source}。")
        return _section("备选方案", lines)
    if intent == "selected_reason":
        summary = plan.get("selected_branch_summary") or "当前缓存里没有 selected best branch。"
        extra = plan.get("mechanism", [])[:2]
        return _section("为什么选这个方案", [summary, *extra])
    # why
    if selected_tone == "judge_friendly":
        lines = [plan.get("conclusion", ""), *plan.get("evidence", [])[:3], *plan.get("mechanism", [])[:1]]
        return _section("原因", lines)
    return _section("为什么", [plan.get("conclusion", ""), *plan.get("evidence", [])[:3], *plan.get("mechanism", [])[:2]])


def suggested_followups(plan: Dict[str, Any]) -> List[str]:
    """Return short follow-up prompts appropriate for the scenario."""
    base = ["为什么这么判断？", "证据是什么？"]
    if plan.get("selected_branch") or plan.get("candidate_summaries"):
        base.extend(["还有别的方案吗？", "为什么选这个方案？"])
    elif plan.get("scenario") in {"public_opinion", "event_propagation"}:
        base.append("应该先在哪个窗口澄清？")
    else:
        base.append("现在最安全的操作是什么？")
    return base[:4]


def _render_friendly(plan: Dict[str, Any]) -> str:
    return "\n".join(
        [
            f"结论：{plan.get('conclusion', '需要进一步分析。')}",
            _section("为什么", plan.get("evidence", [])[:3]),
            _section("建议你这样做", plan.get("recommendations", [])[:3]),
        ]
    )


def _render_serious(plan: Dict[str, Any]) -> str:
    return "\n".join(
        [
            f"风险判断：{plan.get('conclusion', '需要进一步分析。')}",
            _section("关键依据", plan.get("evidence", [])[:4]),
            _section("处置建议", plan.get("recommendations", [])[:3]),
        ]
    )


def _render_expert(plan: Dict[str, Any]) -> str:
    branch_lines = []
    if plan.get("selected_branch_summary"):
        branch_lines.append(plan["selected_branch_summary"])
    for candidate in (plan.get("candidate_summaries") or [])[:4]:
        msg = candidate.get("message") or candidate.get("intervention_type") or candidate.get("candidate_id")
        score = candidate.get("total_score")
        source = candidate.get("metric_source") or plan.get("metric_source") or "完整仿真"
        suffix = f"；分支分数 {score}" if score is not None else ""
        branch_lines.append(f"{msg}{suffix}，指标来源：{source}。")
    if not branch_lines and plan.get("metric_source") in {"proxy", "heuristic", "llm_hypothesis", "代理仿真", "启发式估算", "LLM 假设推断"}:
        branch_lines.append(f"当前传播/分支指标来源为{plan.get('metric_source')}，不等同完整仿真结果。")

    return "\n".join(
        [
            f"系统判断：{plan.get('conclusion', '需要进一步分析。')}",
            _section("机制链路", plan.get("mechanism", [])[:4]),
            _section("干预分支比较", branch_lines, fallback="当前结果没有可比较的候选干预分支。"),
            _section("建议", plan.get("recommendations", [])[:3]),
        ]
    )


def _render_judge_friendly(plan: Dict[str, Any]) -> str:
    why = plan.get("mechanism", [])[:1]
    if plan.get("metric_source") in {"proxy", "heuristic", "llm_hypothesis"} and plan.get("selected_branch"):
        why.append("分支效果是近似评估，核心建议仍来自已识别的证据链和传播节点。")
    return "\n".join(
        [
            f"结论：{plan.get('conclusion', '需要进一步分析。')}",
            _section("关键依据", plan.get("evidence", [])[:3]),
            _section("建议动作", plan.get("recommendations", [])[:2]),
            _section("为什么这样做", why[:2]),
        ]
    )


def _section(title: str, items: Any, fallback: str = "暂无足够信息。") -> str:
    values = [str(item).strip() for item in _as_list(items) if str(item).strip()]
    if not values:
        return f"{title}：{fallback}"
    if len(values) == 1:
        return f"{title}：{values[0]}"
    joined = "\n".join(f"- {item}" for item in values)
    return f"{title}：\n{joined}"


def _result_from_state(state: Dict[str, Any]) -> Dict[str, Any]:
    cogsec = dict(state.get("last_cogsec_analysis") or {})
    intervention_search = dict(state.get("last_propagation_intervention_search") or {})
    graph = dict(state.get("last_risk_graph_bundle") or {})
    return {
        "scenario_metadata": {"canonical": state.get("scenario")},
        "profile": {"scenario_type": state.get("scenario")},
        "benchmark_prediction": dict(state.get("last_benchmark_prediction") or {}),
        "cogsec_analysis": cogsec,
        "risk_graph_bundle": graph,
        "graph": graph,
        "scenario_extension": {
            "detection": {"canonical": state.get("scenario")},
            "propagation_intervention_search": intervention_search,
        },
        "metrics": {},
    }


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]

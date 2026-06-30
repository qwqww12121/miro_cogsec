"""Plan compact, user-facing responses from structured CogSec results."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .tone_controller import evidence_limit, normalize_tone, section_titles


FOLLOWUP_INTENTS = {
    "why": ["为什么", "为啥", "原因", "依据是什么", "怎么判断"],
    "evidence": ["证据", "依据", "线索", "从哪看出", "哪几点"],
    "alternatives": ["还有别的方案", "其他方案", "备选", "别的干预", "还有其他"],
    "selected_reason": ["为什么选", "为什么选择", "为什么是这个方案", "为什么这个方案", "选这个"],
}


SCENARIO_LABELS = {
    "public_opinion": "舆论事件",
    "event_propagation": "事件传播",
    "fraud_im": "即时通讯风险",
}


def build_response_plan(
    *,
    result: Dict[str, Any],
    user_message: str = "",
    tone: str | None = None,
) -> Dict[str, Any]:
    """Build a compact response plan from existing backend outputs."""
    selected_tone = normalize_tone(tone)
    scenario = _resolve_scenario(result)
    prediction = _first_dict(result.get("benchmark_prediction"))
    cogsec = _first_dict(result.get("cogsec_analysis"))
    evidence_trace = _evidence_trace(prediction, cogsec)
    propagation_search = _propagation_search(result)
    selected_branch = _selected_branch(propagation_search, cogsec)
    metric_source = _metric_source(propagation_search, cogsec)

    if scenario == "public_opinion":
        plan = _plan_public_opinion(prediction, evidence_trace)
    elif scenario == "event_propagation":
        plan = _plan_event_propagation(prediction, evidence_trace)
    else:
        plan = _plan_fraud_im(prediction, evidence_trace)

    candidates = _candidate_summaries(propagation_search)
    if selected_branch:
        plan["selected_branch"] = selected_branch
        plan["selected_branch_summary"] = _selected_branch_summary(selected_branch)
        if candidates:
            plan["candidate_summaries"] = candidates
        action = selected_branch.get("best_intervention_action")
        if action and action not in plan["recommendations"]:
            plan["recommendations"].insert(0, str(action))
        plan["mechanism"].append(_selected_branch_summary(selected_branch))

    limit = evidence_limit(selected_tone)
    plan["evidence"] = _unique(plan["evidence"])[:limit]
    plan["recommendations"] = _unique(plan["recommendations"])[:3]
    plan["mechanism"] = _unique(plan["mechanism"])[:4]
    plan.update(
        {
            "scenario": scenario,
            "scenario_label": SCENARIO_LABELS.get(scenario, scenario),
            "tone": selected_tone,
            "sections": section_titles(selected_tone),
            "metric_source": metric_source,
            "user_message_preview": _clip(user_message, 180),
        }
    )
    return plan


def build_graph_payload(*, result: Dict[str, Any], response_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact graph payload for future frontend use."""
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    selected = _first_dict(response_plan.get("selected_branch"))
    scenario = response_plan.get("scenario") or _resolve_scenario(result)
    prediction = _first_dict(result.get("benchmark_prediction"))

    target_nodes = [str(item) for item in selected.get("target_nodes", []) if item]
    highlight_nodes = target_nodes[:]
    if scenario == "event_propagation":
        origin = _first_dict(prediction.get("origin_node"))
        if origin.get("id"):
            highlight_nodes.append(str(origin["id"]))
        for item in _as_list(prediction.get("amplifier_nodes"))[:3]:
            node = _first_dict(item)
            if node.get("id"):
                highlight_nodes.append(str(node["id"]))

    nodes = [_compact_node(item) for item in _as_list(graph.get("nodes"))[:24] if isinstance(item, dict)]
    edges = [_compact_edge(item) for item in _as_list(graph.get("links", graph.get("edges")))[:36] if isinstance(item, dict)]
    active_branch = selected.get("branch_id") or "baseline"
    evidence_links = []
    for item in _as_list(response_plan.get("evidence_trace"))[:8]:
        trace = _first_dict(item)
        if trace:
            evidence_links.append(
                {
                    "id": trace.get("id"),
                    "text": _clip(trace.get("text") or trace.get("span") or "", 120),
                    "source": trace.get("source"),
                }
            )

    return {
        "graph_mode": scenario,
        "highlight_nodes": _unique(highlight_nodes),
        "highlight_edges": [],
        "active_branch": active_branch,
        "display_step": "selected_intervention" if selected else "summary",
        "node_annotations": _node_annotations(selected, prediction),
        "edge_annotations": {},
        "evidence_links": evidence_links,
        "nodes": nodes,
        "edges": edges,
    }


def build_latency_profile(*, result: Dict[str, Any]) -> Dict[str, Any]:
    """Expose latency and metric provenance without inventing runtime data."""
    metrics = _first_dict(result.get("metrics"))
    propagation_search = _propagation_search(result)
    provenance = _first_dict(propagation_search.get("provenance"))
    diagnostics = _first_dict(propagation_search.get("diagnostics"))
    notes = _as_list(diagnostics.get("notes"))
    metric_source = provenance.get("metric_source") or diagnostics.get("metric_source")
    if metric_source is None:
        cogsec = _first_dict(result.get("cogsec_analysis"))
        metric_source = _first_dict(cogsec.get("provenance")).get("metric_source")

    fallback_reason = diagnostics.get("fallback_reason") or ""
    if not fallback_reason and metric_source in {"proxy", "heuristic", "llm_hypothesis"}:
        fallback_reason = str(notes[0]) if notes else "当前分支指标基于轻量代理仿真，非完整 OASIS 运行结果。"

    return {
        "quick_response_latency_ms": metrics.get("t0_latency_ms"),
        "full_response_latency_ms": metrics.get("end_to_end_ms"),
        "branch_execution_latency_ms": diagnostics.get("branch_execution_latency_ms"),
        "branch_count": provenance.get("branch_count") or _first_dict(propagation_search.get("branch_comparison")).get("branch_count") or 0,
        "metric_source": metric_source or "runtime",
        "fallback_reason": fallback_reason,
    }


def build_conversation_state(
    *,
    result: Dict[str, Any],
    tone: str | None = None,
    conversation_id: str | None = None,
    turn_id: str | None = None,
) -> Dict[str, Any]:
    """Build a reusable but bounded state snapshot for follow-up answers."""
    selected_tone = normalize_tone(tone)
    prediction = _first_dict(result.get("benchmark_prediction"))
    cogsec = _first_dict(result.get("cogsec_analysis"))
    propagation_search = _propagation_search(result)
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    evidence_trace = _evidence_trace(prediction, cogsec)
    selected = _selected_branch(propagation_search, cogsec)

    return {
        "conversation_id": conversation_id or "",
        "turn_id": turn_id or "",
        "scenario": _resolve_scenario(result),
        "tone": selected_tone,
        "last_benchmark_prediction": prediction,
        "last_cogsec_analysis": {
            "propagation_analysis": _first_dict(cogsec.get("propagation_analysis")),
            "counterfactual_analysis": _first_dict(cogsec.get("counterfactual_analysis")),
            "provenance": _first_dict(cogsec.get("provenance")),
            "evidence_trace": evidence_trace,
        },
        "last_risk_graph_bundle": {
            "nodes": [_compact_node(item) for item in _as_list(graph.get("nodes"))[:24] if isinstance(item, dict)],
            "links": [_compact_edge(item) for item in _as_list(graph.get("links", graph.get("edges")))[:36] if isinstance(item, dict)],
            "asset_targets": _as_list(graph.get("asset_targets"))[:8],
            "fork_points": _as_list(graph.get("fork_points"))[:8],
        },
        "last_evidence_trace": evidence_trace,
        "last_selected_best_branch": selected,
        "last_propagation_intervention_search": _compact_intervention_search(propagation_search),
        "cached_fields": [
            "benchmark_prediction",
            "cogsec_analysis",
            "risk_graph_bundle",
            "evidence_trace",
            "selected_best_branch",
            "propagation_intervention_search",
        ],
        "has_cached_analysis": True,
    }


def classify_followup_intent(text: str) -> Optional[str]:
    """Classify common follow-up questions that can reuse cached state."""
    normalized = (text or "").strip().lower()
    if not normalized:
        return None
    # Prefer selected_reason before the broad why bucket.
    for intent in ["selected_reason", "evidence", "alternatives", "why"]:
        if any(keyword.lower() in normalized for keyword in FOLLOWUP_INTENTS[intent]):
            return intent
    return None


def _plan_public_opinion(prediction: Dict[str, Any], evidence_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    risk = prediction.get("propagation_risk_level") or "medium"
    event = prediction.get("event_summary") or "该事件已经进入公共讨论场域。"
    emotion = _first_dict(prediction.get("emotion_signal"))
    gap = _first_dict(prediction.get("official_response_gap"))
    uncertainty = [_clip(_first_dict(item).get("description"), 120) for item in _as_list(prediction.get("uncertainty_points"))]
    conclusion = f"这是一个{_risk_zh(risk)}舆论扩散风险事件，重点不是立刻定性，而是防止未经确认的信息变成单一主叙事。"
    evidence = [
        f"事件线索：{_clip(event, 120)}",
    ]
    if emotion:
        evidence.append(
            f"情绪信号偏向{_label_zh(emotion.get('dominant_emotion'))}，放大等级为{_label_zh(emotion.get('amplification_level'))}。"
        )
    if gap:
        evidence.append(f"官方回应缺口：{_clip(gap.get('description'), 120)}")
    evidence.extend([item for item in uncertainty if item])
    evidence.extend(_span_evidence(evidence_trace))
    recommendations = [
        prediction.get("expected_intervention_action"),
        prediction.get("expected_safe_public_action"),
    ]
    mechanism = [
        "情绪放大、权威回应缺口和不确定事实会共同延长传播窗口。",
        "优先补足可核验事实，比直接压制讨论更能降低误解和对立。",
    ]
    return {
        "primary_risk": risk,
        "conclusion": conclusion,
        "evidence": [item for item in evidence if item],
        "recommendations": [str(item) for item in recommendations if item],
        "mechanism": mechanism,
        "evidence_trace": evidence_trace,
    }


def _plan_event_propagation(prediction: Dict[str, Any], evidence_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    risk = prediction.get("coverage_risk") or "medium"
    origin = _first_dict(prediction.get("origin_node"))
    amplifiers = [_first_dict(item) for item in _as_list(prediction.get("amplifier_nodes"))]
    distortions = [_first_dict(item) for item in _as_list(prediction.get("distortion_points"))]
    conclusion = f"这是一个{_risk_zh(risk)}传播风险事件，关键在于早期来源、放大节点和失真点是否被及时纠偏。"
    evidence = []
    if origin:
        evidence.append(f"起点：{_clip(origin.get('description') or origin.get('type'), 120)}")
    if amplifiers:
        names = "；".join(_clip(item.get("description") or item.get("type") or item.get("id"), 60).rstrip("。") for item in amplifiers[:3])
        evidence.append(f"放大节点：{names}")
    for item in distortions[:2]:
        evidence.append(f"失真点：{_clip(item.get('description'), 120)}")
    evidence.extend(_span_evidence(evidence_trace))
    recommendations = [prediction.get("expected_containment_action")]
    mechanism = [
        "传播风险主要来自早期信息被高影响力节点二次包装后继续扩散。",
        "把更正和核验状态绑定回原传播链，可以减少旧版本信息继续复制。",
    ]
    return {
        "primary_risk": risk,
        "conclusion": conclusion,
        "evidence": [item for item in evidence if item],
        "recommendations": [str(item) for item in recommendations if item],
        "mechanism": mechanism,
        "evidence_trace": evidence_trace,
    }


def _plan_fraud_im(prediction: Dict[str, Any], evidence_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    risk = prediction.get("risk_level") or "medium"
    is_fraud = prediction.get("is_fraud")
    label = "存在明显诈骗风险" if is_fraud else "需要进一步核验"
    fraud_type = prediction.get("fraud_type") or "可疑即时通讯场景"
    assets = [_first_dict(item) for item in _as_list(prediction.get("asset_targets"))]
    forks = [_first_dict(item) for item in _as_list(prediction.get("fork_points"))]
    conclusion = f"这段对话{label}，类型接近{fraud_type}，当前风险等级为{_risk_zh(risk)}。"
    evidence = []
    if assets:
        evidence.append("涉及资产：" + "、".join(str(item.get("label") or item.get("type")) for item in assets[:3]))
    for item in forks[:2]:
        evidence.append(f"关键转折点：{_clip(item.get('label') or item.get('type') or item.get('id'), 100)}")
    evidence.extend(_span_evidence(evidence_trace))
    recommendations = [prediction.get("expected_warning"), prediction.get("expected_safe_action")]
    mechanism = [
        "风险来自对敏感资产、转账动作或外部联系方式的连续推进。",
        "安全路径是暂停操作、换官方渠道核验，并保留原始聊天证据。",
    ]
    return {
        "primary_risk": risk,
        "conclusion": conclusion,
        "evidence": [item for item in evidence if item],
        "recommendations": [str(item) for item in recommendations if item],
        "mechanism": mechanism,
        "evidence_trace": evidence_trace,
    }


def _selected_branch_summary(selected: Dict[str, Any]) -> str:
    if not selected:
        return ""
    branch_id = selected.get("branch_id") or selected.get("candidate_id") or "最优分支"
    window = _first_dict(selected.get("best_intervention_window"))
    label = window.get("label") or window.get("open_stage") or window.get("open_step") or "早期窗口"
    reason = _selection_reason_zh(selected.get("selection_reason"))
    return f"已选 {branch_id}，介入窗口为{label}；选择原因是{_clip(reason, 160)}"


def _candidate_summaries(search: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = _as_list(search.get("intervention_candidates"))[:4]
    ranked = _as_list(_first_dict(search.get("branch_comparison")).get("ranked_branches"))
    score_by_candidate = {
        str(item.get("candidate_id")): item.get("total_score")
        for item in ranked
        if isinstance(item, dict) and item.get("candidate_id")
    }
    out = []
    for item in candidates:
        candidate = _first_dict(item)
        if not candidate:
            continue
        cid = str(candidate.get("candidate_id") or "")
        raw_source = _first_dict(search.get("provenance")).get("metric_source")
        out.append(
            {
                "candidate_id": cid,
                "intervention_type": candidate.get("intervention_type"),
                "target_stage": candidate.get("target_stage"),
                "message": candidate.get("message"),
                "metric_source": _metric_source_zh(raw_source),
                "total_score": score_by_candidate.get(cid),
            }
        )
    return out


def _compact_intervention_search(search: Dict[str, Any]) -> Dict[str, Any]:
    if not search:
        return {}
    return {
        "intervention_candidates": _as_list(search.get("intervention_candidates"))[:4],
        "branch_comparison": _first_dict(search.get("branch_comparison")),
        "selected_best_branch": _first_dict(search.get("selected_best_branch")),
        "provenance": _first_dict(search.get("provenance")),
        "diagnostics": _first_dict(search.get("diagnostics")),
    }


def _node_annotations(selected: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    annotations: Dict[str, Any] = {}
    for node_id in selected.get("target_nodes", []) if isinstance(selected.get("target_nodes"), list) else []:
        annotations[str(node_id)] = {"role": "intervention_target"}
    origin = _first_dict(prediction.get("origin_node"))
    if origin.get("id"):
        annotations[str(origin["id"])] = {"role": "origin_node", "description": origin.get("description")}
    for item in _as_list(prediction.get("amplifier_nodes")):
        node = _first_dict(item)
        if node.get("id"):
            annotations[str(node["id"])] = {"role": "amplifier", "description": node.get("description")}
    return annotations


def _resolve_scenario(result: Dict[str, Any]) -> str:
    meta = _first_dict(result.get("scenario_metadata"))
    detection = _first_dict(_scenario_extension(result).get("detection"))
    profile = _first_dict(result.get("profile"))
    for value in [meta.get("canonical"), detection.get("canonical"), profile.get("scenario_type")]:
        if value in SCENARIO_LABELS:
            return str(value)
    return "fraud_im"


def _propagation_search(result: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(_scenario_extension(result).get("propagation_intervention_search"))


def _scenario_extension(result: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(result.get("scenario_extension"))


def _selected_branch(search: Dict[str, Any], cogsec: Dict[str, Any]) -> Dict[str, Any]:
    selected = _first_dict(search.get("selected_best_branch"))
    if selected:
        return selected
    propagation = _first_dict(cogsec.get("propagation_analysis"))
    return _first_dict(propagation.get("selected_best_branch"))


def _metric_source(search: Dict[str, Any], cogsec: Dict[str, Any]) -> str:
    for value in [
        _first_dict(search.get("provenance")).get("metric_source"),
        _first_dict(search.get("diagnostics")).get("metric_source"),
        _first_dict(_first_dict(cogsec.get("provenance"))).get("metric_source"),
    ]:
        if value:
            return _metric_source_zh(value)
    return _metric_source_zh("runtime")


def _evidence_trace(prediction: Dict[str, Any], cogsec: Dict[str, Any]) -> List[Dict[str, Any]]:
    trace = _as_list(_first_dict(cogsec.get("provenance")))
    existing = _as_list(cogsec.get("evidence_trace"))
    if existing:
        return [_first_dict(item) for item in existing if isinstance(item, dict)]
    spans = _as_list(prediction.get("evidence_spans"))
    out = []
    for index, span in enumerate(spans[:8]):
        out.append({"id": f"ev:{index}", "text": str(span), "source": "prediction"})
    return out or [_first_dict(item) for item in trace if isinstance(item, dict)]


def _span_evidence(evidence_trace: List[Dict[str, Any]]) -> List[str]:
    out = []
    for item in evidence_trace[:3]:
        text = item.get("text") or item.get("span")
        if text:
            out.append(f"文本线索：{_clip(text, 120)}")
    return out


def _compact_node(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "label": item.get("label") or item.get("name") or item.get("type"),
        "category": item.get("category") or item.get("type"),
        "risk": item.get("risk") or item.get("severity") or item.get("value"),
        "description": _clip(item.get("description"), 160),
    }


def _compact_edge(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "source": item.get("source"),
        "target": item.get("target"),
        "label": item.get("label") or item.get("relation") or item.get("type"),
        "value": item.get("value") or item.get("weight"),
    }


def _selection_reason_zh(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "该方案在覆盖、失真、情绪和关键节点活跃度之间取得较好折中。"
    lowered = text.lower()
    if "best simulated reduction" in lowered:
        return "该方案在覆盖范围、情绪极化、误传强度和关键节点活跃度之间取得了当前最好的近似降幅，同时成本惩罚较低。"
    return text


def _label_zh(value: Any) -> str:
    text = str(value or "unclear").lower()
    return {
        "anger": "愤怒",
        "anxiety": "焦虑",
        "fear": "恐惧",
        "panic": "恐慌",
        "confusion": "困惑",
        "trust": "信任",
        "high": "高",
        "medium": "中",
        "low": "低",
        "unclear": "不明确",
    }.get(text, str(value or "不明确"))

def _risk_zh(value: Any) -> str:
    text = str(value or "medium").lower()
    return {
        "critical": "极高",
        "high": "较高",
        "medium": "中等",
        "low": "较低",
    }.get(text, str(value or "中等"))


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _unique(items: Iterable[Any]) -> List[Any]:
    out: List[Any] = []
    seen: set[str] = set()
    for item in items:
        key = str(item).strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _metric_source_zh(value: Any) -> str:
    text = str(value or "runtime").lower()
    return {
        "runtime": "完整仿真",
        "proxy": "代理仿真",
        "heuristic": "启发式估算",
        "llm_hypothesis": "LLM 假设推断",
    }.get(text, str(value or "完整仿真"))


def _clip(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"

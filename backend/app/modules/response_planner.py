"""Plan compact, user-facing responses from structured CogSec results."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .report_state import build_report_state
from .tone_controller import evidence_limit, normalize_tone, section_titles
from .opinion_shaping import looks_like_opinion_shaping, shaping_plan
from .platform_context import channel_lens, detect_platform, detect_time_window, fraud_platform_action, public_opinion_lens


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
    "unknown": "待澄清场景",
}

BENCHMARK_DISPLAY_FIELDS = {
    "event_summary", "origin_node", "amplifier_nodes", "propagation_path",
    "distortion_points", "coverage_risk", "containment_window",
    "expected_containment_action", "correction_status", "correction_binding",
    "narrative_threads", "uncertainty_points", "official_response_gap",
    "affected_communities", "emotion_signal", "narrative_analysis",
    "expected_intervention_action", "expected_safe_public_action",
}

FRAUD_TYPE_LABELS = {
    "fraud_im": "即时通讯诈骗",
    "identity_asset_trade": "实名身份资产交易诈骗",
    "unlicensed_financial_service": "信用卡代还/套现诈骗",
    "gambling_fraud": "博彩引流诈骗",
    "gambling_platform_fake_customer_service": "博彩平台虚假客服诈骗",
    "loan_recharge_withdrawal_fraud": "贷款充值提现诈骗",
    "fake_police_fraud": "冒充公检法诈骗",
    "impersonation_refund": "冒充客服退款诈骗",
    "phishing_credential_theft": "钓鱼链接窃取凭证诈骗",
    "loan_fraud": "虚假贷款诈骗",
    "document_forgery_fraud": "虚假证件/证明诈骗",
    "advance_fee_card_fraud": "办卡前置费用诈骗",
    "illegal_goods_fraud": "违法物品私下交易诈骗",
    "semantic_social_engineering": "社交工程诈骗",
}

FORK_LABELS = {
    "private_contact_lure": "对方要求离开公开或官方渠道，转到私人微信继续沟通",
    "identity_asset_exchange": "对方要求交易或交出实名身份资产",
    "unlicensed_financial_service": "对方要求接受未核验的信用卡或金融服务",
    "gambling_entry": "对方把用户引向博彩、充值或投注",
    "phishing_link_entry": "对方要求点击链接并输入账号凭证",
    "transfer_money": "对方要求付款、充值或转账",
    "screen_share": "对方要求开启屏幕共享或远程控制",
    "verification_code": "对方要求提供验证码或动态口令",
    "unknown_app_download": "对方要求下载或安装未知应用",
    "social_isolation": "对方要求保密并切断外部求助",
}


def build_response_plan(
    *,
    result: Dict[str, Any],
    user_message: str = "",
    tone: str | None = None,
) -> Dict[str, Any]:
    """Build a compact response plan from existing backend outputs."""
    selected_tone = normalize_tone(tone)
    # Reporter input is one canonical state.  The only permitted construction
    # fallback is this state builder, which is the explicit runtime boundary.
    # ``result.get("core_analysis")`` and ``benchmark_prediction`` are read
    # only inside build_report_state; this planner never selects between them.
    state = result.get("report_state") if isinstance(result.get("report_state"), dict) else build_report_state(result)
    scenario = str(state.get("scenario") or "unknown")
    prediction = _prediction_from_report_state(state)
    propagation_search = _search_from_report_state(state)
    cogsec: Dict[str, Any] = {}
    if prediction.get("is_direct_llm_baseline"):
        plan = _plan_direct_llm(prediction)
        plan["evidence"] = _unique(plan["evidence"])[:evidence_limit(selected_tone)]
        plan["recommendations"] = _unique(plan["recommendations"])[:3]
        plan["mechanism"] = _unique(plan["mechanism"])[:4]
        plan.update({
            "scenario": scenario,
            "scenario_label": SCENARIO_LABELS.get(scenario, scenario),
            "tone": selected_tone,
            "sections": section_titles(selected_tone),
            "metric_source": "direct_llm",
            "user_message_preview": _clip(user_message, 180),
        })
        return plan
    evidence_trace = _evidence_trace_from_state(state, prediction)
    selected_branch = _selected_branch(propagation_search, cogsec)
    metric_source = str(_first_dict(state.get("provenance")).get("metric_source") or _metric_source(propagation_search, cogsec))

    if scenario == "unknown":
        plan = _plan_unknown(prediction, evidence_trace)
    elif scenario == "public_opinion":
        plan = _plan_public_opinion(prediction, evidence_trace, user_message)
    elif scenario == "event_propagation":
        plan = _plan_event_propagation(prediction, evidence_trace, user_message)
    else:
        plan = _plan_fraud_im(prediction, evidence_trace, user_message)

    candidates = _candidate_summaries(propagation_search)
    if scenario == "public_opinion" and candidates:
        # Public-opinion cases need complementary actions, not only the
        # single selected score winner.  Candidate messages are runtime-derived
        # and are kept only when they are distinct and non-empty.
        for candidate in candidates:
            action = candidate.get("message")
            if action and action not in plan["recommendations"]:
                plan["recommendations"].append(str(action))
    if selected_branch:
        plan["selected_branch"] = selected_branch
        plan["selected_branch_summary"] = _selected_branch_summary(selected_branch)
        if candidates:
            plan["candidate_summaries"] = candidates
        action = selected_branch.get("best_intervention_action")
        if action and action not in plan["recommendations"]:
            plan["recommendations"].insert(0, str(action))
        plan["mechanism"].append(_selected_branch_summary(selected_branch))

    if (
        scenario == "fraud_im"
        and selected_tone == "expert"
        and plan.get("personalized_outcome_risk_level") not in {None, "", "unknown", plan.get("primary_risk")}
    ):
        plan["mechanism"].append(
            "个体后果风险来自画像与反事实分支差异；它与当前请求本身的威胁等级分开报告。"
        )

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


def _prediction_from_report_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """Compatibility view for existing plan templates, sourced only from state."""
    scenario = str(state.get("scenario") or "unknown")
    summary = _first_dict(state.get("summary"))
    prediction: Dict[str, Any] = {
        "scenario": scenario,
        "summary": summary.get("text"),
        "risk_level": summary.get("risk_level"),
        "propagation_risk_level": summary.get("risk_level"),
        "coverage_risk": summary.get("risk_level"),
        "evidence_spans": _as_list(state.get("evidence")),
        "is_direct_llm_baseline": bool(state.get("is_direct_llm_baseline")),
    }
    if scenario == "fraud_im":
        fraud = _first_dict(state.get("fraud"))
        prediction.update({
            "is_fraud": fraud.get("risk_type") not in {"unknown", "no_fraud_signal", ""},
            "fraud_type": fraud.get("risk_type"),
            "risk_level": summary.get("risk_level"),
            "personalized_outcome_risk_level": fraud.get("personalized_outcome_risk_level"),
            "attack_stage": fraud.get("current_stage") or fraud.get("attack_stage"),
            "asset_targets": _as_list(fraud.get("requested_assets") or fraud.get("target")),
            "fork_points": _as_list(fraud.get("critical_transitions") or fraud.get("critical_actions")),
            "expected_warning": _first_text(fraud.get("recommended_actions")),
            "expected_safe_action": _second_or_first_text(fraud.get("recommended_actions")),
            "intervention_window": _first_dict(fraud.get("recommended_timing")),
            "confidence": fraud.get("confidence"),
        })
    elif scenario == "public_opinion":
        public = _first_dict(state.get("public_opinion"))
        prediction.update({
            "event_summary": summary.get("text"),
            "narrative_threads": _as_list(public.get("narrative_threads") or public.get("core_claims")),
            "uncertainty_points": _as_list(public.get("uncertainty_points") or public.get("uncertainty")),
            "official_response_gap": _first_dict(public.get("source_status") or public.get("source_status_legacy")),
            "affected_communities": _as_list(public.get("affected_communities")),
            "emotion_signal": _first_dict(public.get("polarization_signal")),
            "narrative_analysis": {"fragmentation": public.get("fragmentation_signal")},
            "best_intervention_window": _first_dict(public.get("intervention_timing")),
            "expected_intervention_action": _selected_action(public) or public.get("recommended_intervention_action"),
            "expected_safe_public_action": public.get("recommended_public_action") or _selected_action(public),
            "confidence": public.get("confidence"),
        })
    elif scenario == "event_propagation":
        event = _first_dict(state.get("event_propagation"))
        prediction.update({
            "event_summary": event.get("original_claim") or summary.get("text"),
            "origin_node": _first_dict(_as_list(event.get("source_nodes"))[0] if _as_list(event.get("source_nodes")) else {}),
            "amplifier_nodes": _as_list(event.get("amplifier_nodes")),
            "propagation_path": _as_list(event.get("cross_platform_path") or event.get("mutation_steps")),
            "distortion_points": _as_list(event.get("lost_context")),
            "certainty_change": event.get("certainty_change"),
            "coverage_risk": summary.get("risk_level"),
            "containment_window": _first_dict(event.get("containment_timing")),
            "expected_containment_action": event.get("containment_action"),
            "correction_status": event.get("correction_status"),
            "correction_binding": event.get("correction_binding"),
            "confidence": event.get("confidence"),
        })
    if state.get("direct_llm"):
        prediction.update(_first_dict(state.get("direct_llm")))
        prediction["evidence"] = _as_list(_first_dict(state.get("direct_llm")).get("evidence"))
        prediction["is_direct_llm_baseline"] = True
    return prediction


def _search_from_report_state(state: Dict[str, Any]) -> Dict[str, Any]:
    candidates = []
    for item in _as_list(state.get("candidate_actions")):
        candidate = _first_dict(item)
        if not candidate:
            continue
        candidate = dict(candidate)
        candidate["message"] = candidate.get("action") or candidate.get("message")
        candidate["best_intervention_action"] = candidate.get("action")
        candidate["intervention_type"] = candidate.get("candidate_type") or candidate.get("intervention_type")
        candidate["best_intervention_window"] = candidate.get("timing") or candidate.get("best_intervention_window")
        candidate["final_metrics"] = candidate.get("expected_effect") or candidate.get("final_metrics") or {}
        candidates.append(candidate)
    selected = _first_dict(_as_list(state.get("selected_actions"))[0] if _as_list(state.get("selected_actions")) else {})
    if selected:
        selected = dict(selected)
        selected["message"] = selected.get("message") or selected.get("action")
        selected["best_intervention_action"] = selected.get("best_intervention_action") or selected.get("action")
    return {
        "intervention_candidates": candidates,
        "selected_best_branch": selected,
        "effective_selected_intervention": selected,
        "selection_source": _first_dict(state.get("provenance")).get("selection_source", "report_state"),
        "provenance": _first_dict(state.get("provenance")),
        "diagnostics": {"source": "report_state"},
    }


def _evidence_trace_from_state(state: Dict[str, Any], prediction: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        {"id": f"ev:{index}", "text": str(value), "source": "report_state"}
        for index, value in enumerate(_as_list(state.get("evidence"))[:8])
        if str(value).strip()
    ]


def _selected_action(public: Dict[str, Any]) -> str:
    selected = _as_list(public.get("selected_interventions"))
    if selected and isinstance(selected[0], dict):
        return str(selected[0].get("action") or selected[0].get("message") or selected[0].get("best_intervention_action") or "")
    return ""


def _first_text(value: Any) -> str:
    values = [str(item).strip() for item in _as_list(value) if str(item).strip()]
    return values[0] if values else ""


def _second_or_first_text(value: Any) -> str:
    values = [str(item).strip() for item in _as_list(value) if str(item).strip()]
    return values[1] if len(values) > 1 else (values[0] if values else "")


def build_graph_payload(*, result: Dict[str, Any], response_plan: Dict[str, Any]) -> Dict[str, Any]:
    """Build a compact graph payload for future frontend use."""
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    selected = _first_dict(response_plan.get("selected_branch"))
    state = result.get("report_state") if isinstance(result.get("report_state"), dict) else build_report_state(result)
    scenario = response_plan.get("scenario") or state.get("scenario") or "unknown"
    prediction = _prediction_from_report_state(state)

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
        fallback_reason = str(notes[0]) if notes else "当前分支指标基于轻量代理仿真。"
    if any(token in str(fallback_reason) for token in ("OASIS", "FORK", "未调用", "未接入")):
        fallback_reason = "当前分支指标基于轻量代理仿真。"

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
    state = result.get("report_state") if isinstance(result.get("report_state"), dict) else build_report_state(result)
    prediction = _prediction_from_report_state(state)
    cogsec: Dict[str, Any] = {}
    propagation_search = _search_from_report_state(state)
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    evidence_trace = _evidence_trace(prediction, cogsec)
    selected = _selected_branch(propagation_search, cogsec)

    return {
        "conversation_id": conversation_id or "",
        "turn_id": turn_id or "",
        "scenario": state.get("scenario") or "unknown",
        "tone": selected_tone,
        "last_benchmark_prediction": prediction,
        "last_report_state": state,
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
        "last_effective_selected_intervention": selected,
        "last_propagation_intervention_search": _compact_intervention_search(propagation_search),
        "cached_fields": [
            "benchmark_prediction",
            "cogsec_analysis",
            "risk_graph_bundle",
            "evidence_trace",
            "selected_best_branch",
            "effective_selected_intervention",
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


def _plan_public_opinion(
    prediction: Dict[str, Any],
    evidence_trace: List[Dict[str, Any]],
    user_message: str = "",
) -> Dict[str, Any]:
    shaping = looks_like_opinion_shaping(user_message)
    platform = detect_platform(user_message)
    window = detect_time_window(user_message)
    if shaping:
        plan = shaping_plan(platform)
        plan["evidence_trace"] = evidence_trace
        return plan
    risk = prediction.get("propagation_risk_level") or "medium"
    event = prediction.get("event_summary") or "该事件已经进入公共讨论场域。"
    emotion = _first_dict(prediction.get("emotion_signal"))
    gap = _first_dict(prediction.get("official_response_gap"))
    uncertainty = [_clip(_first_dict(item).get("description"), 120) for item in _as_list(prediction.get("uncertainty_points"))]
    threads = [_first_dict(item) for item in _as_list(prediction.get("narrative_threads"))]
    narrative = _first_dict(prediction.get("narrative_analysis"))
    platform_clause = f"，当前观察场是{platform}" if platform else ""
    window_clause = f"，时间窗口为{window}" if window else ""
    conclusion = (
        f"这是一个{_risk_zh(risk)}舆论扩散风险事件{platform_clause}{window_clause}，"
        "重点不是立刻定性，而是防止未经确认的信息变成单一主叙事。"
    )
    evidence = [
        f"事件线索：{_clip(event, 120)}",
    ]
    if platform:
        evidence.insert(0, f"平台：{platform}。{public_opinion_lens(platform)[0]}")
    if emotion:
        evidence.append(
            f"情绪信号偏向{_label_zh(emotion.get('dominant_emotion'))}，放大等级为{_label_zh(emotion.get('amplification_level'))}。"
        )
    if gap:
        evidence.append(f"官方回应缺口：{_clip(gap.get('description'), 120)}")
    for item in threads[:2]:
        claim = _clip(item.get("claim") or item.get("text") or item.get("summary"), 120)
        if claim:
            evidence.append(f"主要说法：{claim}")
    evidence.extend([item for item in uncertainty if item])
    evidence.extend(_span_evidence(evidence_trace))
    if narrative:
        dominant = narrative.get("dominant_narrative") or "暂无单一主导叙事"
        evidence.append(
            f"当前主导叙事：{dominant}；叙事熵为{narrative.get('narrative_entropy', 0.0)}，社区碎片化为{narrative.get('fragmentation', 0.0)}。"
        )
    lens, platform_recs = public_opinion_lens(platform)
    recommendations = [
        *platform_recs,
        prediction.get("expected_intervention_action"),
        prediction.get("expected_safe_public_action"),
    ]
    mechanism = [
        lens,
        "情绪化表达、权威回应不足和事实不确定会共同延长传播窗口。",
        "先补足可核验事实，再把更正放回该平台原来的传播位置。",
    ]
    if narrative:
        mechanism.append(
            "不同群体接收到的说法可能不一致，应分别核对来源并观察更正是否触达各群体。"
        )
    return {
        "primary_risk": risk,
        "conclusion": conclusion,
        "evidence": [item for item in evidence if item],
        "recommendations": [str(item) for item in recommendations if item],
        "mechanism": mechanism,
        "evidence_trace": evidence_trace,
    }


def _plan_event_propagation(
    prediction: Dict[str, Any],
    evidence_trace: List[Dict[str, Any]],
    user_message: str = "",
) -> Dict[str, Any]:
    risk = prediction.get("coverage_risk") or "medium"
    origin = _first_dict(prediction.get("origin_node"))
    amplifiers = [_first_dict(item) for item in _as_list(prediction.get("amplifier_nodes"))]
    distortions = [_first_dict(item) for item in _as_list(prediction.get("distortion_points"))]
    channel = detect_platform(user_message)
    lens, channel_recs = channel_lens(channel)
    channel_clause = f"，主要发酵渠道是{channel}" if channel else ""
    conclusion = f"这是一个{_risk_zh(risk)}传播风险事件{channel_clause}，关键在于早期来源、放大节点和失真点是否被及时纠偏。"
    evidence = []
    if origin:
        origin_text = _actor_node_text(origin, source=True)
        if origin_text:
            evidence.append(f"起点：{origin_text}")
    if amplifiers:
        names = [_actor_node_text(item) for item in amplifiers[:3]]
        names = [name for name in names if name]
        if names:
            evidence.append("放大节点：" + "；".join(names))
    for item in distortions[:2]:
        evidence.append(f"失真点：{_clip(item.get('description'), 120)}")
    if not distortions and len(evidence_trace) > 1:
        evidence.append(f"失真线索：{_clip(evidence_trace[1].get('text') or evidence_trace[1].get('span'), 120)}")
    evidence.extend(_span_evidence(evidence_trace))
    if channel:
        evidence.insert(0, f"渠道：{channel}。{lens}")
    recommendations = [
        *channel_recs,
        prediction.get("expected_containment_action"),
        "把官方更正同步回原帖、原截图和主要转发链，并注明仍待核实的细节。",
    ]
    mechanism = [
        lens,
        "传播风险主要来自早期信息被高影响力节点二次包装后继续扩散。",
        "如果更正没有回到原帖、原截图或主要转发链，错误版本仍可能继续被复制。",
    ]
    return {
        "primary_risk": risk,
        "conclusion": conclusion,
        "evidence": [item for item in evidence if item],
        "recommendations": [str(item) for item in recommendations if item],
        "mechanism": mechanism,
        "evidence_trace": evidence_trace,
    }


def _plan_fraud_im(
    prediction: Dict[str, Any],
    evidence_trace: List[Dict[str, Any]],
    user_message: str = "",
) -> Dict[str, Any]:
    risk = prediction.get("risk_level") or "medium"
    is_fraud = prediction.get("is_fraud")
    label = "存在明显诈骗风险" if is_fraud else "需要进一步核验"
    fraud_type = _fraud_type_label(prediction.get("fraud_type"))
    assets = [_first_dict(item) for item in _as_list(prediction.get("asset_targets"))]
    forks = [_first_dict(item) for item in _as_list(prediction.get("fork_points"))]
    type_clause = f"，类型接近{fraud_type}" if fraud_type else ""
    conclusion = f"这段对话{label}{type_clause}，当前风险等级为{_risk_zh(risk)}。"
    outcome_risk = prediction.get("personalized_outcome_risk_level")
    evidence = []
    if assets:
        evidence.append("涉及资产：" + "、".join(str(item.get("label") or item.get("type")) for item in assets[:3]))
    for item in forks[:2]:
        fork_type = str(item.get("type") or "")
        label = FORK_LABELS.get(fork_type, _clip(item.get("label") or fork_type or item.get("id"), 100))
        spans = _evidence_for_refs(item.get("evidence_refs"), evidence_trace)
        if spans:
            evidence.append(f"关键步骤：{label}（原文：“{spans[0]}”）")
        else:
            evidence.append(f"关键步骤：{label}")
    evidence.extend(_span_evidence(evidence_trace))
    platform = detect_platform(user_message)
    platform_action = fraud_platform_action(platform)
    recommendations = [
        platform_action,
        prediction.get("expected_warning"),
        prediction.get("expected_safe_action"),
    ]
    if platform:
        evidence.insert(0, f"对话平台：{platform}。")
        conclusion = f"这段对话发生在{platform}。{conclusion}"
    mechanism = _fraud_mechanisms(prediction, forks)
    return {
        "primary_risk": risk,
        "personalized_outcome_risk_level": outcome_risk,
        "conclusion": conclusion,
        "evidence": [item for item in evidence if item],
        "recommendations": [str(item) for item in recommendations if item],
        "mechanism": mechanism,
        "evidence_trace": evidence_trace,
    }


def _plan_unknown(prediction: Dict[str, Any], evidence_trace: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "primary_risk": "unknown",
        "conclusion": "当前材料缺少足够场景信号，暂不能可靠归类。",
        "evidence": _span_evidence(evidence_trace),
        "recommendations": ["请补充事件背景、涉及对象和希望判断的问题。"],
        "mechanism": ["系统未观察到足以支持三类场景路由的有效信号。"],
        "evidence_trace": evidence_trace,
    }


def _plan_direct_llm(prediction: Dict[str, Any]) -> Dict[str, Any]:
    evidence = prediction.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        evidence = []
    evidence = [str(item) for item in evidence if item]
    evidence_trace = [
        {"id": f"direct:{index}", "text": item, "source": "direct_llm"}
        for index, item in enumerate(evidence)
    ]
    summary = str(prediction.get("summary") or prediction.get("assessment") or "模型未提供摘要。")
    action = str(prediction.get("recommended_action") or "请通过独立渠道核验关键信息。")
    return {
        "primary_risk": prediction.get("risk_level") or "unknown",
        "conclusion": summary,
        "evidence": evidence,
        "recommendations": [action],
        "mechanism": ["以上内容直接整理自同一主模型的 baseline 输出。"],
        "evidence_trace": evidence_trace,
    }


def _selected_branch_summary(selected: Dict[str, Any]) -> str:
    if not selected:
        return ""
    action = selected.get("message") or selected.get("best_intervention_action") or "采取对应的风险控制措施"
    window = _first_dict(selected.get("best_intervention_window"))
    stage = str(window.get("open_stage") or "early")
    label = {
        "early": "早期传播阶段",
        "acceleration": "传播加速阶段",
        "peak": "传播高峰前",
    }.get(stage, "早期传播阶段")
    reason = _selection_reason_zh(selected.get("selection_reason"))
    return f"建议在{label}采取以下措施：{_clip(action, 100)} 原因是{_clip(reason, 160)}"


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
        "proxy_selected_intervention": _first_dict(search.get("proxy_selected_intervention")),
        "effective_selected_intervention": _first_dict(search.get("effective_selected_intervention")),
        "selection_source": search.get("selection_source", "proxy"),
        "selection_provenance": _first_dict(search.get("selection_provenance")),
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
    return "unknown"


def _propagation_search(result: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(_scenario_extension(result).get("propagation_intervention_search"))


def _scenario_extension(result: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(result.get("scenario_extension"))


def _selected_branch(search: Dict[str, Any], cogsec: Dict[str, Any]) -> Dict[str, Any]:
    selected = _first_dict(search.get("effective_selected_intervention"))
    if selected:
        return selected
    oasis_verification = _first_dict(search.get("oasis_verification"))
    selected = _first_dict(oasis_verification.get("selected"))
    if (
        selected.get("verification_status") == "executed"
        and selected.get("metric_source") == "oasis"
    ):
        return selected
    propagation = _first_dict(cogsec.get("propagation_analysis"))
    selected = _first_dict(propagation.get("effective_selected_intervention"))
    if selected:
        return selected
    selected = _first_dict(search.get("selected_best_branch"))
    if selected:
        return selected
    return _first_dict(propagation.get("selected_best_branch"))


def _metric_source(search: Dict[str, Any], cogsec: Dict[str, Any]) -> str:
    selected = _first_dict(search.get("effective_selected_intervention"))
    if selected.get("metric_source"):
        return _metric_source_zh(selected.get("metric_source"))
    propagation = _first_dict(cogsec.get("propagation_analysis"))
    selected = _first_dict(propagation.get("effective_selected_intervention"))
    if selected.get("metric_source"):
        return _metric_source_zh(selected.get("metric_source"))
    for value in [
        _first_dict(search.get("provenance")).get("metric_source"),
        _first_dict(search.get("diagnostics")).get("metric_source"),
        _first_dict(_first_dict(cogsec.get("provenance"))).get("metric_source"),
    ]:
        if value:
            return _metric_source_zh(value)
    return _metric_source_zh("runtime")


def _evidence_trace(prediction: Dict[str, Any], cogsec: Dict[str, Any]) -> List[Dict[str, Any]]:
    spans = _as_list(prediction.get("evidence_spans"))
    out: List[Dict[str, Any]] = []
    for index, span in enumerate(spans[:8]):
        if isinstance(span, (str, int, float)) and str(span).strip():
            out.append({"id": f"ev:{index}", "text": str(span), "source": "prediction"})
    if out:
        return _dedupe_trace(out)
    existing = _as_list(cogsec.get("evidence_trace"))
    if existing:
        return _dedupe_trace([_first_dict(item) for item in existing if isinstance(item, dict)])
    trace = _as_list(_first_dict(cogsec.get("provenance")))
    return _dedupe_trace([_first_dict(item) for item in trace if isinstance(item, dict)])


def _span_evidence(evidence_trace: List[Dict[str, Any]]) -> List[str]:
    out = []
    for item in evidence_trace[:3]:
        text = item.get("text") or item.get("span")
        if text:
            out.append(f"文本线索：{_clip(text, 120)}")
    return out


def _evidence_for_refs(refs: Any, evidence_trace: List[Dict[str, Any]]) -> List[str]:
    requested = {str(item).replace("ev:", "") for item in _as_list(refs) if item}
    exact = []
    matches = []
    for item in evidence_trace:
        text = str(item.get("text") or item.get("span") or "").strip()
        identifier = str(item.get("id") or "").replace("ev:", "")
        if not text:
            continue
        if identifier in requested or text in requested:
            exact.append(text)
        elif not requested or any(key in text for key in requested):
            matches.append(text)
    return _unique(exact or matches)


def _dedupe_trace(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in items:
        text = str(item.get("text") or item.get("span") or "").strip()
        if not text or text in seen:
            continue
        # Keep the minimum sufficient source span in the visible trace.
        if any(text in str(other.get("text") or other.get("span") or "") for other in output):
            continue
        output = [other for other in output if not str(other.get("text") or other.get("span") or "") in text]
        seen.add(text)
        output.append(item)
    return output


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
    if "best simulated claim-fidelity gain" in lowered:
        return "该方案对保留原始来源、减少内容失真和提高更正触达的近似效果最好，同时考虑了干预成本。"
    if " gives the best " in lowered:
        return "该方案在当前代理指标下的综合风险降低效果最好，同时考虑了干预成本。"
    return text


def _fraud_type_label(value: Any) -> str:
    """Convert machine-readable fraud types to normal Chinese wording."""
    raw = str(value or "").strip()
    if raw in FRAUD_TYPE_LABELS:
        return FRAUD_TYPE_LABELS[raw]
    if raw in {"unknown", "semantic_fraud_recognition", "social_engineering_fraud", ""}:
        return ""
    if raw.endswith("诈骗") or raw.endswith("诈骗类") or raw.endswith("类"):
        return raw
    # Avoid producing phrases such as “XXX诈骗风险风险”.
    if "诈骗风险" in raw or raw.endswith("风险"):
        return "存在明显诈骗风险"
    return raw


def _fraud_mechanisms(prediction: Dict[str, Any], forks: List[Dict[str, Any]]) -> List[str]:
    types = {str(item.get("type") or "") for item in forks}
    if "private_contact_lure" in types and "unlicensed_financial_service" in types:
        return [
            "对方先把沟通转到私人微信，再把信用卡代还、刷卡或低点位服务包装成交易机会。",
            "真正需要拦截的是添加微信、提供卡片资料或付款之前；后续费用和信息索取会让损失更难追回。",
        ]
    if "private_contact_lure" in types:
        return [
            "转到私人渠道后，平台原有的核验、举报和追责能力会下降，对方更容易继续施压或索取资料。",
            "应在添加联系人之前停下，并改用机构官网或官方客服电话核验。",
        ]
    assets = [str(_first_dict(item).get("label") or _first_dict(item).get("type") or "") for item in _as_list(prediction.get("asset_targets"))]
    asset_text = "、".join(item for item in assets if item) or "资金或账号资料"
    return [
        f"一旦按对方要求交付{asset_text}，控制权可能落到对方手里，之后很难撤回或追索。",
        "应暂停操作，保留原始聊天记录，并通过独立的官方渠道核验。",
    ]


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
        "unknown": "不明确",
    }.get(text, str(value or "不明确"))


def _actor_node_text(item: Dict[str, Any], *, source: bool = False) -> str:
    role_labels = {
        "source_agent": "早期来源节点",
        "original_poster": "首发账号",
        "repost_kol": "转发型高影响账号",
        "controversy_amplifier": "争议放大账号",
        "media_observer": "媒体观察账号",
        "ordinary_viewer": "普通浏览者",
        "agent": "传播节点",
    }
    description = _clip(item.get("description") or item.get("label") or item.get("name"), 60).rstrip("。")
    actor_id = str(item.get("agent_id") or item.get("id") or "").strip()
    role = str(item.get("role") or item.get("type") or "").strip()
    role_text = role_labels.get(role, "早期来源节点" if source else "")
    if description:
        return description
    if actor_id and role_text:
        return f"{actor_id}（{role_text}）"
    return actor_id or role_text

def _risk_zh(value: Any) -> str:
    text = str(value or "medium").lower()
    return {
        "critical": "极高",
        "high": "较高",
        "medium": "中等",
        "low": "较低",
        "unknown": "暂无法判断",
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

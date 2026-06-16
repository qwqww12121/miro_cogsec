"""Benchmark-facing adapters for Miro-CogSec runtime outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple


FRAUD_FIELDS = [
    "is_fraud",
    "fraud_type",
    "risk_level",
    "attack_stage",
    "asset_targets",
    "fork_points",
    "intervention_window",
    "expected_warning",
    "expected_safe_action",
    "counterfactual_paths",
    "evidence_spans",
    "confidence",
]

PUBLIC_OPINION_FIELDS = [
    "event_summary",
    "narrative_threads",
    "emotion_signal",
    "uncertainty_points",
    "official_response_gap",
    "propagation_risk_level",
    "best_intervention_window",
    "expected_intervention_action",
    "expected_safe_public_action",
    "evidence_spans",
    "confidence",
]

EVENT_PROPAGATION_FIELDS = [
    "event_summary",
    "origin_node",
    "amplifier_nodes",
    "propagation_path",
    "distortion_points",
    "coverage_risk",
    "containment_window",
    "expected_containment_action",
    "evidence_spans",
    "confidence",
]

REQUIRED_BY_SCENARIO = {
    "fraud_im": FRAUD_FIELDS,
    "public_opinion": PUBLIC_OPINION_FIELDS,
    "event_propagation": EVENT_PROPAGATION_FIELDS,
}

ASSET_KEYWORDS = {
    "funds": ["资金", "钱", "转账", "付款", "支付", "银行卡", "红包", "充值", "保证金", "购买", "价格", "退费"],
    "credentials": ["验证码", "密码", "口令", "登录", "短信码", "动态码", "credential"],
    "identity": ["实名", "身份", "身份证", "手机卡", "个人信息", "资料", "人脸", "姓名"],
    "device": ["下载", "安装", "链接", "APP", "屏幕共享", "远程", "设备", "木马", "插件"],
    "account": ["账号", "账户", "微信", "支付宝", "银行卡", "游戏账号", "社交账号"],
    "social_trust": ["亲友", "朋友", "老师", "客服", "公安", "领导", "熟人", "信誉", "多年老店"],
    "reputation": ["名誉", "曝光", "舆论", "评论", "声誉"],
    "public_safety": ["公共事件", "安全事件", "灾害", "救援", "危险", "执法"],
}

RISK_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def build_benchmark_payload(
    *,
    result: Dict[str, Any],
    scenario_text: str,
    scenario_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build benchmark prediction + CogSec mechanism output from runtime result."""
    scenario = _resolve_scenario(result, scenario_type)
    if scenario == "public_opinion":
        prediction = _build_public_opinion_prediction(result, scenario_text)
    elif scenario == "event_propagation":
        prediction = _build_event_propagation_prediction(result, scenario_text)
    else:
        scenario = "fraud_im"
        prediction = _build_fraud_prediction(result, scenario_text)

    cogsec_analysis = _build_cogsec_analysis(result, scenario_text, scenario)
    diagnostics = _diagnostics(result, scenario, prediction, cogsec_analysis)
    return {
        "scenario": scenario,
        "prediction": prediction,
        "cogsec_analysis": cogsec_analysis,
        "adapter_diagnostics": diagnostics,
    }


def build_llm_only_cogsec_analysis(
    *,
    prediction: Dict[str, Any],
    scenario_type: str,
) -> Dict[str, Any]:
    """Build an isomorphic, clearly hypothetical mechanism field for LLM baselines."""
    propagation_stub: Dict[str, Any] = {}
    if scenario_type in {"public_opinion", "event_propagation"}:
        selected = {}
        if scenario_type == "public_opinion":
            selected = {
                "best_intervention_window": prediction.get("best_intervention_window", {}),
                "best_intervention_action": prediction.get("expected_intervention_action", ""),
            }
        else:
            selected = {
                "best_intervention_window": prediction.get("containment_window", {}),
                "best_intervention_action": prediction.get("expected_containment_action", ""),
            }
        propagation_stub = {
            "intervention_candidates": [],
            "hypothetical_counterfactual_branches": [],
            "selected_best_branch": selected,
            "provenance": {
                "source": "llm_only",
                "has_oasis_counterfactual_branches": False,
                "metric_source": "llm_hypothesis",
            },
        }

    return {
        "risk_graph": {
            "nodes": [],
            "edges": [],
            "asset_targets": prediction.get("asset_targets", []),
            "fork_points": prediction.get("fork_points", []),
        },
        "counterfactual_analysis": {
            "risky_path": (prediction.get("counterfactual_paths") or {}).get("risky_path", []),
            "safe_path": (prediction.get("counterfactual_paths") or {}).get("safe_path", []),
            "trajectory_gap": 0.0,
            "irreversibility_loss": 0.0,
            "key_divergence": [],
        },
        "propagation_analysis": propagation_stub,
        "intervention_policy": [],
        "evidence_trace": _spans_to_trace(prediction.get("evidence_spans", []), ""),
        "provenance": {
            "source": "llm_only",
            "has_runtime_simulation": False,
            "has_oasis_simulation": False,
            "has_rag": False,
            "has_counterfactual_runtime": False,
            "has_oasis_counterfactual_branches": False,
            "branch_count": 0,
            "metric_source": "llm_hypothesis",
        },
    }


def _build_fraud_prediction(result: Dict[str, Any], text: str) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    fork_comp = _first_dict(result.get("fork_comparison"))
    report = _first_dict(result.get("counterfactual_report"))
    report_sections = _first_dict(report.get("report_sections"), report.get("structured_report"))
    counterfactual_expectation = _first_dict(report.get("counterfactual_expectation"), report_sections.get("counterfactual_expectation"))
    t0 = _first_dict(result.get("t0_fast_response"))

    risk_level = _risk_level(result)
    assets, asset_source = normalize_asset_targets(graph.get("asset_targets") or result.get("asset_targets") or [], text)
    if not assets:
        assets = _assets_from_text(text)
        asset_source = "text_fallback"

    fork_points = _normalize_fork_points(graph.get("fork_points"), fork_comp, assets)
    window = _fraud_window(report, fork_comp, counterfactual_expectation)
    evidence_spans = _extract_evidence_spans(text, graph, scenario="fraud_im")
    attack_stage = _infer_attack_stage(text, graph)

    risky_path, safe_path = _counterfactual_paths_from_runtime(result, counterfactual_expectation)
    prediction = {
        "is_fraud": risk_level in {"medium", "high", "critical"} or bool(t0.get("should_interrupt")) or bool(graph.get("attack_strategy_chain")),
        "fraud_type": _fraud_type(result, graph),
        "risk_level": risk_level,
        "attack_stage": attack_stage,
        "asset_targets": assets,
        "fork_points": fork_points,
        "intervention_window": window,
        "expected_warning": _fraud_warning(text, assets, t0, risk_level),
        "expected_safe_action": _fraud_safe_action(text, assets),
        "counterfactual_paths": {
            "risky_path": risky_path,
            "safe_path": safe_path,
            "trajectory_gap": _num(fork_comp.get("trajectory_gap")),
            "key_divergence": _key_divergence(fork_points, assets),
        },
        "evidence_spans": evidence_spans,
        "confidence": _confidence(result, prediction_hint_count=len(evidence_spans) + len(assets)),
    }
    prediction["_adapter_asset_type_source"] = asset_source
    return prediction


def _build_public_opinion_prediction(result: Dict[str, Any], text: str) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    propagation = _propagation_search(result) or _first_dict((_scenario_extension(result)).get("propagation"))
    selected = _first_dict(propagation.get("selected_best_branch"))
    baseline = _first_dict(propagation.get("baseline_branch"))
    evidence_spans = _extract_evidence_spans(text, graph, scenario="public_opinion")
    emotion = _emotion_signal(text, baseline)
    official_gap = _official_response_gap(text)
    risk_level = _scenario_risk_level(text, baseline, fallback=_risk_level(result), scenario="public_opinion")
    window = _public_window_from_selected(selected, text)

    return {
        "event_summary": _event_summary(text, "公共讨论"),
        "narrative_threads": _narrative_threads(text, evidence_spans),
        "emotion_signal": emotion,
        "uncertainty_points": _uncertainty_points(text),
        "official_response_gap": official_gap,
        "propagation_risk_level": risk_level,
        "best_intervention_window": window,
        "expected_intervention_action": _public_intervention_action(text, official_gap, selected.get("best_intervention_action")),
        "expected_safe_public_action": _safe_public_action(text),
        "evidence_spans": evidence_spans,
        "confidence": _confidence(result, prediction_hint_count=len(evidence_spans) + 3),
    }


def _build_event_propagation_prediction(result: Dict[str, Any], text: str) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    propagation = _propagation_search(result) or _first_dict((_scenario_extension(result)).get("propagation"))
    selected = _first_dict(propagation.get("selected_best_branch"))
    baseline = _first_dict(propagation.get("baseline_branch"))
    evidence_spans = _extract_evidence_spans(text, graph, scenario="event_propagation")
    origin = _origin_node(text)
    amplifiers = _amplifier_nodes(text)
    distortions = _distortion_points(text)
    window = _numeric_window_from_selected(selected, default_open=2, default_close=3)
    return {
        "event_summary": _event_summary(text, "事件传播"),
        "origin_node": origin,
        "amplifier_nodes": amplifiers,
        "propagation_path": _propagation_path(origin, amplifiers, distortions, text),
        "distortion_points": distortions,
        "coverage_risk": _scenario_risk_level(text, baseline, fallback=_risk_level(result), scenario="event_propagation"),
        "containment_window": window,
        "expected_containment_action": _containment_action(text, selected.get("best_intervention_action")),
        "evidence_spans": evidence_spans,
        "confidence": _confidence(result, prediction_hint_count=len(evidence_spans) + len(amplifiers)),
    }


def _build_cogsec_analysis(result: Dict[str, Any], text: str, scenario: str) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    fork_comp = _first_dict(result.get("fork_comparison"))
    report = _first_dict(result.get("counterfactual_report"))
    propagation = _first_dict((_scenario_extension(result)).get("propagation"))
    intervention_search = _propagation_search(result)
    risky_path, safe_path = _counterfactual_paths_from_runtime(result, _first_dict(report.get("counterfactual_expectation")))
    evidence_spans = _extract_evidence_spans(text, graph, scenario=scenario)

    propagation_analysis = {
        "origin_node": _origin_node(text) if scenario == "event_propagation" else {},
        "amplifier_nodes": _amplifier_nodes(text) if scenario == "event_propagation" else [],
        "propagation_path": [],
        "coverage_curve": _coverage_curve(propagation),
        "key_nodes": _key_nodes(propagation),
        "intervention_ticks": _intervention_ticks(propagation),
    }
    if intervention_search:
        propagation_analysis.update(
            {
                "baseline_branch": intervention_search.get("baseline_branch", {}),
                "intervention_candidates": intervention_search.get("intervention_candidates", []),
                "counterfactual_branches": intervention_search.get("counterfactual_branches", []),
                "branch_comparison": intervention_search.get("branch_comparison", {}),
                "selected_best_branch": intervention_search.get("selected_best_branch", {}),
                "selection_metrics": intervention_search.get("selection_metrics", {}),
            }
        )

    return {
        "risk_graph": {
            "nodes": graph.get("nodes", []),
            "edges": graph.get("links", graph.get("edges", [])),
            "asset_targets": graph.get("asset_targets", []),
            "fork_points": graph.get("fork_points", []),
        },
        "counterfactual_analysis": {
            "risky_path": risky_path,
            "safe_path": safe_path,
            "trajectory_gap": _num(fork_comp.get("trajectory_gap")),
            "irreversibility_loss": _num(fork_comp.get("irreversibility_loss")),
            "key_divergence": _key_divergence(graph.get("fork_points", []), graph.get("asset_targets", [])),
        },
        "propagation_analysis": propagation_analysis,
        "intervention_policy": (result.get("intervention_prescriptions") if isinstance(result.get("intervention_prescriptions"), list) else []),
        "evidence_trace": _spans_to_trace(evidence_spans, text),
        "provenance": {
            "source": "mirofish_pipeline",
            "has_runtime_simulation": bool(result.get("fork_comparison") or result.get("branch_a_log")),
            "has_oasis_simulation": _has_oasis_simulation(propagation),
            "has_rag": bool(graph.get("evidence_items") or graph.get("attack_strategy_chain")),
            "has_counterfactual_runtime": bool(result.get("counterfactual_report") or result.get("fork_comparison")),
            "has_oasis_counterfactual_branches": bool((_first_dict(intervention_search.get("provenance")) if intervention_search else {}).get("has_oasis_counterfactual_branches")),
            "branch_count": len(intervention_search.get("counterfactual_branches", [])) if intervention_search else 0,
            "candidate_generation_source": (_first_dict(intervention_search.get("provenance")).get("candidate_generation_source") if intervention_search else None),
            "metric_source": (_first_dict(intervention_search.get("provenance")).get("metric_source") if intervention_search else None),
        },
    }


def normalize_asset_targets(raw_assets: Any, text: str) -> Tuple[List[Dict[str, Any]], str]:
    assets: List[Dict[str, Any]] = []
    source = "fallback"
    for item in raw_assets if isinstance(raw_assets, list) else []:
        if not isinstance(item, dict):
            continue
        asset_type = item.get("type")
        local_source = "type"
        if not asset_type:
            joined = " ".join(
                str(part)
                for part in [
                    item.get("id", ""),
                    item.get("label", ""),
                    item.get("description", ""),
                    " ".join(str(term) for term in item.get("matched_terms", []) if term),
                ]
            )
            asset_type = _asset_type_from_text(joined)
            local_source = "label|id|matched_terms"
        if not asset_type:
            continue
        source = local_source
        assets.append(
            {
                "id": item.get("id") or f"asset:{asset_type}",
                "type": str(asset_type),
                "label": item.get("label") or _asset_label(str(asset_type)),
                "severity": round(_num(item.get("severity"), 0.65), 3),
                "evidence_refs": item.get("evidence_refs", []),
            }
        )
    existing = {asset["type"] for asset in assets}
    for asset in _assets_from_text(text):
        if asset["type"] not in existing:
            assets.append(asset)
            existing.add(asset["type"])
            if source == "fallback":
                source = "text"
    return assets, source


def _diagnostics(
    result: Dict[str, Any],
    scenario: str,
    prediction: Dict[str, Any],
    cogsec_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    scenario_extension = _scenario_extension(result)
    required = REQUIRED_BY_SCENARIO.get(scenario, [])
    missing_prediction = [field for field in required if field not in prediction]
    missing_cogsec = []
    for field in ["risk_graph", "counterfactual_analysis", "propagation_analysis", "intervention_policy", "evidence_trace", "provenance"]:
        if field not in cogsec_analysis:
            missing_cogsec.append(field)
    warnings: List[str] = []
    if not prediction.get("evidence_spans"):
        warnings.append("no evidence spans extracted from source text")
    if scenario in {"public_opinion", "event_propagation"} and not _propagation_search(result):
        warnings.append("no counterfactual intervention search found")
    return {
        "missing_prediction_fields": missing_prediction,
        "missing_cogsec_fields": missing_cogsec,
        "evidence_span_count": len(prediction.get("evidence_spans", [])) if isinstance(prediction.get("evidence_spans"), list) else 0,
        "asset_type_source": prediction.pop("_adapter_asset_type_source", None) or "not_applicable",
        "used_runtime_sources": {
            "risk_graph_bundle": bool(graph),
            "fork_comparison": bool(result.get("fork_comparison")),
            "counterfactual_report": bool(result.get("counterfactual_report")),
            "propagation": bool(scenario_extension.get("propagation")),
            "propagation_intervention_search": bool(scenario_extension.get("propagation_intervention_search")),
            "t0_fast_response": bool(result.get("t0_fast_response")),
        },
        "adapter_warnings": warnings,
    }


def _resolve_scenario(result: Dict[str, Any], scenario_type: Optional[str]) -> str:
    if scenario_type:
        return str(scenario_type)
    meta = _first_dict(result.get("scenario_metadata"))
    detection = _first_dict(_scenario_extension(result).get("detection"))
    profile = _first_dict(result.get("profile"))
    for value in [meta.get("canonical"), detection.get("canonical"), profile.get("scenario_type")]:
        if value in REQUIRED_BY_SCENARIO:
            return str(value)
    return "fraud_im"


def _scenario_extension(result: Dict[str, Any]) -> Dict[str, Any]:
    value = result.get("scenario_extension")
    return value if isinstance(value, dict) else {}


def _propagation_search(result: Dict[str, Any]) -> Dict[str, Any]:
    return _first_dict(_scenario_extension(result).get("propagation_intervention_search"))


def _risk_level(result: Dict[str, Any]) -> str:
    report = _first_dict(result.get("counterfactual_report"))
    score_comparison = _first_dict(report.get("score_comparison"))
    risk_breakdown = _first_dict(score_comparison.get("risk_breakdown"), _first_dict(result.get("metrics")).get("risk_breakdown"))
    raw = (
        report.get("risk_level")
        or risk_breakdown.get("risk_level")
        or _first_dict(result.get("t0_fast_response")).get("risk_level")
        or result.get("risk_level")
        or "medium"
    )
    text = str(raw).lower()
    if text in RISK_ORDER:
        return text
    score = _num(raw, -1.0)
    if score >= 0.85:
        return "critical"
    if score >= 0.65:
        return "high"
    if score >= 0.35:
        return "medium"
    if score >= 0:
        return "low"
    if any(term in text for term in ["critical", "严重", "极高"]):
        return "critical"
    if any(term in text for term in ["high", "高"]):
        return "high"
    if any(term in text for term in ["medium", "中"]):
        return "medium"
    return "low"


def _propagation_risk_level(baseline: Dict[str, Any], fallback: str = "medium") -> str:
    metrics = _first_dict(baseline.get("final_metrics"), baseline)
    coverage = _num(metrics.get("coverage_final"), None)
    peak = _num(metrics.get("peak_risk"), None)
    value = max(v for v in [coverage, peak] if v is not None) if any(v is not None for v in [coverage, peak]) else None
    if value is None:
        return fallback
    if value >= 0.75:
        return "critical"
    if value >= 0.45:
        return "high"
    if value >= 0.22:
        return "medium"
    return "low"


def _scenario_risk_level(text: str, baseline: Dict[str, Any], fallback: str, scenario: str) -> str:
    runtime_level = _propagation_risk_level(baseline, fallback=fallback)
    text_level = "low"
    if scenario == "public_opinion":
        if (
            ("迅速发酵" in text or "立即" in text or "大量" in text)
            and any(term in text for term in ["愤怒", "种族", "警民", "未经证实", "要求官方"])
        ):
            text_level = "high"
        elif any(term in text for term in ["焦虑", "求证", "互相指责", "未经临床验证", "亲友经验", "医学机构说明"]):
            text_level = "medium"
        elif any(term in text for term in ["网传", "未经证实", "讨论", "转发"]):
            text_level = "medium"
    else:
        if (
            any(term in text for term in ["多个新闻账号", "多个", "新闻账号", "个人账号"])
            and any(term in text for term in ["未经证实", "嫌疑人身份", "现场图片", "不准确", "更正"])
        ):
            text_level = "high"
        elif any(term in text for term in ["地方媒体", "救援信息汇总账号", "遗漏", "地点名称", "实时有效", "志愿者群组"]):
            text_level = "medium"
        elif any(term in text for term in ["转发", "首发", "传播"]):
            text_level = "medium"
    return max([runtime_level, fallback, text_level], key=lambda item: RISK_ORDER.get(item, 1))


def _fraud_type(result: Dict[str, Any], graph: Dict[str, Any]) -> str:
    profile = _first_dict(result.get("profile"))
    env = _first_dict(graph.get("environment_context"))
    for value in [profile.get("scenario_type"), env.get("scenario_type"), result.get("scenario_type")]:
        if value and str(value) not in {"fraud_im", "public_opinion", "event_propagation"}:
            return str(value)
    strategy_text = _json_text(graph.get("attack_strategy_chain", []))
    text = strategy_text.lower()
    if any(term in text for term in ["phone", "手机卡", "实名"]):
        return "identity_asset_trade"
    if any(term in text for term in ["客服", "退款", "征信"]):
        return "impersonation_refund"
    if any(term in text for term in ["投资", "理财", "收益"]):
        return "investment_fraud"
    return "social_engineering_fraud"


def _infer_attack_stage(text: str, graph: Dict[str, Any]) -> str:
    if any(term in text for term in ["验证码", "密码", "登录"]):
        return "credential_collection"
    if any(term in text for term in ["下载", "安装", "链接", "屏幕共享"]):
        return "malware_or_remote_control_lure"
    if any(term in text for term in ["转账", "付款", "保证金", "充值", "退款"]):
        return "payment_or_fund_transfer"
    if any(term in text for term in ["微信", "私下", "联系", "加好友"]):
        return "private_contact_lure"
    env = _first_dict(graph.get("environment_context"))
    if env.get("private_contact_lure"):
        return "private_contact_lure"
    return "early_lure"


def _normalize_fork_points(raw: Any, fork_comp: Dict[str, Any], assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        points.append(
            {
                "id": item.get("id") or "fork:runtime",
                "type": item.get("type") or fork_comp.get("fork_point_type") or "verify_legitimacy_vs_compliance",
                "severity": round(_num(item.get("severity"), 0.7), 3),
                "asset": item.get("asset") or (assets[0]["label"] if assets else "核心资产"),
                "reason": item.get("reason") or "该节点会将用户从核验路径推向高风险执行路径。",
                "evidence_refs": item.get("evidence_refs", []),
            }
        )
    if not points:
        points.append(
            {
                "id": "fork:runtime_primary",
                "type": fork_comp.get("fork_point_type") or "verify_legitimacy_vs_compliance",
                "severity": 0.7,
                "asset": assets[0]["label"] if assets else "核心资产",
                "reason": "运行时反事实分支显示需要在执行高风险动作前介入。",
                "evidence_refs": [],
            }
        )
    return points


def _fraud_window(report: Dict[str, Any], fork_comp: Dict[str, Any], cf: Dict[str, Any]) -> Dict[str, Any]:
    raw = _first_dict(
        cf.get("best_intervention_window"),
        report.get("best_intervention_window"),
        fork_comp.get("best_intervention_window"),
    )
    start = int(_num(raw.get("start_turn"), _num(raw.get("open_step"), 1)))
    end = int(_num(raw.get("end_turn"), _num(raw.get("close_step"), start)))
    return {
        "start_turn": max(1, start),
        "end_turn": max(1, end),
        "rationale": raw.get("rationale") or raw.get("label") or "在用户执行付款、交出凭证或进入私域沟通前介入。",
    }


def _counterfactual_paths_from_runtime(result: Dict[str, Any], cf: Dict[str, Any]) -> Tuple[List[Any], List[Any]]:
    risky = cf.get("branch_a_high_risk_path") or cf.get("risky_path")
    safe = cf.get("branch_b_safe_path") or cf.get("safe_path")
    if risky and safe:
        return _as_list(risky), _as_list(safe)
    branch_a = result.get("branch_a_log") if isinstance(result.get("branch_a_log"), list) else []
    branch_b = result.get("branch_b_log") if isinstance(result.get("branch_b_log"), list) else []
    risky_path = [
        {
            "step": item.get("step", index + 1),
            "action": item.get("action") or item.get("agent_action") or item.get("stage", "high-risk branch action"),
            "risk_state": item.get("stage") or item.get("cognitive_mode") or "risk_escalation",
        }
        for index, item in enumerate(branch_a[:4])
        if isinstance(item, dict)
    ]
    safe_path = [
        {
            "step": item.get("step", index + 1),
            "action": item.get("action") or item.get("agent_action") or item.get("stage", "safe branch action"),
            "risk_state": item.get("stage") or item.get("cognitive_mode") or "risk_reduction",
        }
        for index, item in enumerate(branch_b[:4])
        if isinstance(item, dict)
    ]
    if not risky_path:
        risky_path = [{"step": 1, "action": "继续相信并执行对方要求", "risk_state": "asset_exposure_increase"}]
    if not safe_path:
        safe_path = [{"step": 1, "action": "暂停操作并核验来源", "risk_state": "risk_reduction"}]
    return risky_path, safe_path


def _key_divergence(fork_points: Any, assets: Any) -> List[Dict[str, Any]]:
    first_fork = _as_list(fork_points)[0] if _as_list(fork_points) else {}
    first_asset = _as_list(assets)[0] if _as_list(assets) else {}
    if not isinstance(first_fork, dict):
        first_fork = {}
    if not isinstance(first_asset, dict):
        first_asset = {}
    return [
        {
            "fork_type": first_fork.get("type", "intervention_vs_compliance"),
            "asset": first_asset.get("type", first_asset.get("label", "core_asset")),
            "description": "安全路径要求暂停和核验，高风险路径继续执行对方诱导动作。",
        }
    ]


def _fraud_warning(text: str, assets: List[Dict[str, Any]], t0: Dict[str, Any], risk_level: str) -> str:
    if t0.get("warning"):
        return str(t0["warning"])
    asset_types = {item.get("type") for item in assets}
    if "credentials" in asset_types:
        return "不要向任何人提供验证码、密码或登录凭证。"
    if "device" in asset_types:
        return "不要点击陌生链接、下载未知应用或开启屏幕共享。"
    if "identity" in asset_types:
        return "不要通过私人渠道交易或交出实名身份资料。"
    if "funds" in asset_types:
        return "不要在未核验身份和官方渠道前转账或付款。"
    return f"当前内容存在{risk_level}风险，应在执行对方要求前暂停核验。"


def _fraud_safe_action(text: str, assets: List[Dict[str, Any]]) -> str:
    asset_types = {item.get("type") for item in assets}
    if "identity" in asset_types:
        return "停止私下联系，并通过运营商、公安或平台官方渠道核验合法性。"
    if "credentials" in asset_types:
        return "停止输入或转发验证码，改用官方 App 或客服电话核验账号状态。"
    if "device" in asset_types:
        return "停止下载和屏幕共享，关闭远程控制并联系官方客服核验。"
    if "funds" in asset_types:
        return "停止转账付款，通过官方渠道核验对方身份和业务真实性。"
    return "暂停操作，保留聊天记录，并通过官方渠道或可信第三方核验。"


def _event_summary(text: str, prefix: str) -> str:
    text = _clean_text(text)
    if len(text) <= 80:
        return f"{prefix}围绕{text}"
    return f"{prefix}围绕{text[:80]}..."


def _narrative_threads(text: str, evidence: List[str]) -> List[Dict[str, Any]]:
    primary = evidence[0] if evidence else "事件信息"
    threads = [
        {
            "id": "thread:public_accountability",
            "claim": f"讨论围绕{primary}形成公共问责或风险归因叙事。",
            "risk": "情绪化归因可能压过事实核验。",
            "evidence_refs": [f"ev:{primary}"] if primary else [],
        }
    ]
    if any(term in text for term in ["未经证实", "网传", "求证", "传言", "亲友经验"]):
        threads.append(
            {
                "id": "thread:uncertain_claim_spread",
                "claim": "未经证实或经验性说法推动讨论继续扩散。",
                "risk": "事实细节未稳定前容易被二次解读。",
                "evidence_refs": [f"ev:{item}" for item in evidence[:3]],
            }
        )
    else:
        threads.append(
            {
                "id": "thread:official_information_gap",
                "claim": "公众关注权威信息是否及时、具体和可验证。",
                "risk": "回应不足会延长传播窗口。",
                "evidence_refs": [f"ev:{item}" for item in evidence[:3]],
            }
        )
    return threads


def _emotion_signal(text: str, baseline: Dict[str, Any]) -> Dict[str, Any]:
    dominant = "confusion"
    if any(term in text for term in ["愤怒", "指责", "不公平", "处罚", "歧视"]):
        dominant = "anger"
    elif any(term in text for term in ["焦虑", "健康", "新冠", "求证"]):
        dominant = "anxiety"
    elif any(term in text for term in ["危险", "威胁", "泄露", "恐慌"]):
        dominant = "fear"
    coverage = _num(_first_dict(baseline.get("final_metrics")).get("coverage_final"), 0.0)
    if any(term in text for term in ["迅速发酵", "大量", "多个", "立即"]) or coverage >= 0.45:
        level = "high"
    elif any(term in text for term in ["部分", "一些", "争议", "讨论"]) or coverage >= 0.20:
        level = "medium"
    else:
        level = "low"
    return {
        "dominant_emotion": dominant,
        "amplification_level": level,
        "rationale": "由文本中的情绪词、传播速度和传播覆盖 proxy 综合判断。",
        "evidence": _extract_keyword_hits(text, ["愤怒", "焦虑", "求证", "指责", "迅速发酵", "大量", "多个"]),
    }


def _uncertainty_points(text: str) -> List[Dict[str, Any]]:
    rules = [
        ("uncertainty:unverified_claim", ["未经证实", "网传", "传言"], "流传说法仍缺少可复核证据。"),
        ("uncertainty:source_gap", ["来源不明", "首发", "个人账号", "亲友经验"], "来源和证据链需要进一步核验。"),
        ("uncertainty:official_details", ["要求官方", "官方", "权威", "公布", "说明"], "权威事实说明的完整性影响叙事稳定。"),
        ("uncertainty:time_place_context", ["时间", "地点", "简写", "遗漏"], "时间、地点或上下文可能在传播中丢失。"),
    ]
    points: List[Dict[str, Any]] = []
    for pid, terms, description in rules:
        hits = _extract_keyword_hits(text, terms)
        if hits:
            points.append({"id": pid, "description": description, "evidence_refs": [f"ev:{hit}" for hit in hits]})
    if not points:
        points.append({"id": "uncertainty:verification_needed", "description": "仍需多源信息确认事件细节。", "evidence_refs": []})
    return points


def _official_response_gap(text: str) -> Dict[str, Any]:
    if any(term in text for term in ["医学机构说明", "权威账号发布更正", "更正", "辟谣", "澄清"]):
        return {
            "status": "partially_available",
            "severity": 0.55,
            "description": "已有权威或专业信息参与纠偏，但仍需绑定原传播链并持续更新。",
            "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["医学机构说明", "权威账号发布更正", "更正", "辟谣", "澄清"])],
        }
    if any(term in text for term in ["要求官方", "立即公布", "尚未", "等待官方"]):
        return {
            "status": "delayed_or_incomplete",
            "severity": 0.78,
            "description": "讨论已经扩散，但权威事实说明尚不足以稳定叙事。",
            "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["要求官方", "立即公布", "官方"])],
        }
    return {
        "status": "unclear",
        "severity": 0.45,
        "description": "文本未呈现充分权威回应，需要继续核验回应状态。",
        "evidence_refs": [],
    }


def _public_window_from_selected(selected: Dict[str, Any], text: str) -> Dict[str, Any]:
    raw = _first_dict(selected.get("best_intervention_window"))
    branch_id = selected.get("branch_id")
    if any(term in text for term in ["未经证实", "要求官方", "迅速发酵", "愤怒"]):
        return {
            "open_stage": "early_discussion",
            "close_stage": "before_single_narrative_dominates",
            "label": "在未经证实叙事成为主导前介入",
            "selected_branch_id": branch_id,
        }
    if any(term in text for term in ["健康", "临床", "亲友经验", "医学机构说明"]):
        return {
            "open_stage": "claim_spreading",
            "close_stage": "before_health_behavior_adoption",
            "label": "在公众按误导性说法采取健康行为前介入",
            "selected_branch_id": branch_id,
        }
    return {
        "open_stage": raw.get("open_stage") or "early_discussion",
        "close_stage": raw.get("close_stage") or "before_single_narrative_dominates",
        "label": raw.get("label") or "在未经证实叙事成为主导前介入",
        "selected_branch_id": branch_id,
    }


def _public_intervention_action(text: str, gap: Dict[str, Any], selected_action: Any = None) -> str:
    selected_text = str(selected_action or "").strip()
    if gap.get("status") == "partially_available":
        base = "引用权威说明并绑定到原传播链，区分已证实、未证实和仍在核实的信息。"
    else:
        base = "发布时间线、证据状态和后续调查流程，明确哪些信息已确认、哪些仍在核实。"
    if selected_text and selected_text not in base:
        return f"{base}同时执行策略搜索选中的动作：{selected_text}"
    return base


def _safe_public_action(text: str) -> str:
    if any(term in text for term in ["健康", "新冠", "临床", "医学"]):
        return "不按未经验证说法改变健康行为，优先查看权威医学机构或本地卫生部门公开指引。"
    return "避免转发未经证实的信息、截图或目击叙述，保留来源链接并等待多源确认。"


def _origin_node(text: str) -> Dict[str, Any]:
    if "本地用户账号" in text:
        return {"id": "node:local_source", "type": "local_source", "description": "本地用户发出的初始信息。", "evidence_refs": ["ev:本地用户账号"]}
    if "首发帖" in text:
        return {"id": "node:origin_breaking_post", "type": "early_source_post", "description": "突发事件的首发帖或早期来源。", "evidence_refs": ["ev:首发帖"]}
    if any(term in text for term in ["首发", "早期"]):
        return {"id": "node:early_source", "type": "early_source_post", "description": "早期来源节点。", "evidence_refs": []}
    return {"id": "node:source", "type": "early_source_post", "description": "文本中的初始传播来源。", "evidence_refs": []}


def _amplifier_nodes(text: str) -> List[Dict[str, Any]]:
    specs = [
        ("新闻账号", "node:news_accounts", "media_amplifier", "新闻账号扩大初始信息覆盖面。"),
        ("个人账号", "node:personal_reposts", "grassroots_amplifier", "个人账号转发并推动二次传播。"),
        ("志愿者群组", "node:volunteer_group", "community_amplifier", "志愿者群组转发并扩大社区覆盖。"),
        ("地方媒体", "node:local_media", "public_information_amplifier", "地方媒体扩大公共覆盖面。"),
        ("救援信息汇总账号", "node:rescue_aggregator", "public_information_amplifier", "汇总账号继续放大传播。"),
    ]
    nodes: List[Dict[str, Any]] = []
    for term, node_id, node_type, desc in specs:
        if term in text:
            nodes.append({"id": node_id, "type": node_type, "description": desc, "evidence_refs": [f"ev:{term}"]})
    if not nodes:
        nodes.append({"id": "node:repost_amplifier", "type": "social_amplifier", "description": "转发节点扩大传播覆盖。", "evidence_refs": []})
    return nodes


def _distortion_points(text: str) -> List[Dict[str, Any]]:
    specs = [
        ("未经证实的嫌疑人身份", "distortion:suspect_identity", "未经证实的身份信息被补充并传播。", 0.86),
        ("现场图片单独传播", "distortion:image_context_loss", "现场图片被单独截取传播，可能脱离原始语境。", 0.66),
        ("地点名称被简写", "distortion:location_abbreviation", "地点名称被简写，可能影响定位准确性。", 0.58),
        ("遗漏了发布时间", "distortion:timestamp_loss", "发布时间遗漏导致信息时效性失真。", 0.84),
        ("不准确", "distortion:inaccurate_detail", "传播中的部分细节被权威更正为不准确。", 0.72),
        ("未经证实", "distortion:unverified_detail", "未经证实细节在二次传播中扩散。", 0.76),
    ]
    points: List[Dict[str, Any]] = []
    for term, did, desc, severity in specs:
        if term in text:
            points.append({"id": did, "description": desc, "severity": severity, "evidence_refs": [f"ev:{term}"]})
    if not points:
        points.append({"id": "distortion:context_gap", "description": "传播过程中存在上下文缺口或细节失真风险。", "severity": 0.55, "evidence_refs": []})
    return points


def _propagation_path(origin: Dict[str, Any], amplifiers: List[Dict[str, Any]], distortions: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
    path = [
        {"step": 1, "node": origin.get("id", "node:source"), "action": "发布或形成早期事件信息", "risk_state": "信息速度高但细节未稳定"}
    ]
    step = 2
    for node in amplifiers[:3]:
        path.append({"step": step, "node": node.get("id"), "action": "转发扩散", "risk_state": "覆盖面扩大"})
        step += 1
    if distortions:
        path.append({"step": step, "node": "node:distorted_repost", "action": "二次传播中出现失真或上下文丢失", "risk_state": "误传风险上升"})
    if any(term in text for term in ["更正", "澄清", "权威"]):
        path.append({"step": step + 1, "node": "node:official_correction", "action": "权威账号发布更正或说明", "risk_state": "进入纠偏窗口"})
    return path


def _containment_action(text: str, selected_action: Any = None) -> str:
    selected_text = str(selected_action or "").strip()
    if any(term in text for term in ["身份", "嫌疑人"]):
        base = "标注未确认身份信息，要求转发账号更新更正，并将权威更正与原传播链绑定展示。"
    elif any(term in text for term in ["地点", "时间", "求助"]):
        base = "转发时强制保留原始发布时间、地点全称和状态更新，对过期信息加醒目标记。"
    else:
        base = "对未核验内容加来源标签，优先要求高影响力转发节点同步更正。"
    if selected_text and selected_text not in base:
        return f"{base}策略搜索选中的补充动作：{selected_text}"
    return base


def _stage_window_from_selected(
    selected: Dict[str, Any],
    *,
    default_open: str,
    default_close: str,
    default_label: str,
) -> Dict[str, Any]:
    raw = _first_dict(selected.get("best_intervention_window"))
    return {
        "open_stage": raw.get("open_stage") or default_open,
        "close_stage": raw.get("close_stage") or default_close,
        "label": raw.get("label") or default_label,
    }


def _numeric_window_from_selected(selected: Dict[str, Any], *, default_open: int, default_close: int) -> Dict[str, Any]:
    raw = _first_dict(selected.get("best_intervention_window"))
    open_step = int(_num(raw.get("open_step"), default_open))
    close_step = int(_num(raw.get("close_step"), default_close))
    return {
        "open_step": open_step,
        "close_step": max(open_step, close_step),
        "label": raw.get("label") or "在放大节点继续扩散前介入",
    }


def _extract_evidence_spans(text: str, graph: Dict[str, Any], scenario: str) -> List[str]:
    candidates: List[str] = []
    for item in graph.get("evidence_items", []) if isinstance(graph.get("evidence_items"), list) else []:
        if not isinstance(item, dict):
            continue
        for key in ["span", "label", "typical_dialogue", "description"]:
            if item.get(key):
                candidates.append(str(item[key]))
        candidates.extend(str(term) for term in item.get("matched_terms", []) if term)
    for item in graph.get("attack_strategy_chain", []) if isinstance(graph.get("attack_strategy_chain"), list) else []:
        if isinstance(item, dict):
            candidates.extend(str(item.get(key)) for key in ["typical_dialogue", "description", "tactic_name"] if item.get(key))
    candidates.extend(_scenario_terms(text, scenario))
    direct = [candidate for candidate in candidates if candidate and candidate in text]

    spans = _unique(direct)
    for clause in _split_clauses(text):
        if any(term in clause for term in _scenario_terms(text, scenario)):
            spans.append(clause)
    if not spans and text:
        spans = _split_clauses(text)[:3]
    return _unique([span for span in spans if span and span in text])[:8]


def _scenario_terms(text: str, scenario: str) -> List[str]:
    common = ["未经证实", "要求官方", "官方", "权威", "更正", "转发", "迅速发酵", "愤怒", "焦虑"]
    if scenario == "fraud_im":
        common.extend(["实名", "手机卡", "微信", "验证码", "转账", "付款", "下载", "链接", "信誉", "客服", "银行卡"])
    elif scenario == "event_propagation":
        common.extend(["首发帖", "新闻账号", "个人账号", "嫌疑人身份", "现场图片", "本地用户账号", "志愿者群组", "地方媒体", "救援信息汇总账号", "地点名称被简写", "遗漏了发布时间", "实时有效", "不准确"])
    else:
        common.extend(["警民关系", "种族议题", "未经证实的目击叙述", "亲友经验", "医学机构说明", "临床验证", "预防或治疗", "互相指责"])
    return [term for term in common if term in text]


def _split_clauses(text: str) -> List[str]:
    parts = [part.strip() for part in re.split(r"[。！？；;，,]", text) if part.strip()]
    clauses: List[str] = []
    for part in parts:
        if len(part) <= 90:
            clauses.append(part)
        else:
            clauses.append(part[:90])
    return clauses


def _spans_to_trace(spans: Iterable[Any], text: str) -> List[Dict[str, Any]]:
    trace = []
    for index, span in enumerate(spans):
        value = str(span)
        start = text.find(value) if text else -1
        trace.append(
            {
                "id": f"ev:{value}" if value else f"ev:{index}",
                "text": value,
                "source": "input_text" if start >= 0 else "prediction",
                "start": start if start >= 0 else None,
                "end": start + len(value) if start >= 0 else None,
            }
        )
    return trace


def _assets_from_text(text: str) -> List[Dict[str, Any]]:
    assets: List[Dict[str, Any]] = []
    for asset_type, terms in ASSET_KEYWORDS.items():
        hits = [term for term in terms if term in text]
        if hits:
            assets.append(
                {
                    "id": f"asset:{asset_type}",
                    "type": asset_type,
                    "label": _asset_label(asset_type),
                    "severity": 0.7,
                    "evidence_refs": [f"ev:{hit}" for hit in hits[:3]],
                    "matched_terms": hits[:5],
                }
            )
    return assets


def _asset_type_from_text(text: str) -> Optional[str]:
    lower = text.lower()
    for asset_type, terms in ASSET_KEYWORDS.items():
        if asset_type in lower or f"asset:{asset_type}" in lower:
            return asset_type
        if any(term in text for term in terms):
            return asset_type
    if "credential" in lower:
        return "credentials"
    return None


def _asset_label(asset_type: str) -> str:
    return {
        "funds": "资金账户",
        "credentials": "登录凭证",
        "identity": "身份资料",
        "device": "设备控制权",
        "account": "账号资产",
        "social_trust": "社会信任关系",
        "reputation": "声誉资产",
        "public_safety": "公共安全",
    }.get(asset_type, asset_type)


def _coverage_curve(propagation: Dict[str, Any]) -> List[Any]:
    branch = _first_dict(propagation.get("branch_a"), propagation.get("baseline_branch"))
    return branch.get("coverage_curve", []) if isinstance(branch.get("coverage_curve"), list) else []


def _key_nodes(propagation: Dict[str, Any]) -> List[Any]:
    branch = _first_dict(propagation.get("branch_a"), propagation.get("baseline_branch"))
    return branch.get("key_nodes", []) if isinstance(branch.get("key_nodes"), list) else []


def _intervention_ticks(propagation: Dict[str, Any]) -> List[Any]:
    fork_point = _first_dict(propagation.get("fork_point"))
    ticks = []
    if fork_point.get("intervention_tick") is not None:
        ticks.append(fork_point.get("intervention_tick"))
    selected = _first_dict(propagation.get("selected_best_branch"))
    window = _first_dict(selected.get("best_intervention_window"))
    if window.get("open_step") is not None:
        ticks.append(window.get("open_step"))
    return _unique([str(tick) for tick in ticks])


def _has_oasis_simulation(propagation: Dict[str, Any]) -> bool:
    for branch_key in ["branch_a", "branch_b", "baseline_branch"]:
        branch = _first_dict(propagation.get(branch_key))
        metrics = _first_dict(branch.get("final_metrics"))
        if metrics.get("oasis_driven"):
            return True
    return False


def _confidence(result: Dict[str, Any], prediction_hint_count: int = 0) -> float:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    metrics = _first_dict(result.get("metrics"))
    risk_breakdown = _first_dict(metrics.get("risk_breakdown"))
    base = _num(graph.get("consistency_score"), None)
    if base is None:
        base = _num(risk_breakdown.get("evidence_consistency"), 0.55)
    confidence = float(base if base is not None else 0.55)
    if _first_dict(result.get("t0_fast_response")).get("should_interrupt"):
        confidence += 0.08
    if result.get("fork_comparison"):
        confidence += 0.06
    if result.get("counterfactual_report"):
        confidence += 0.06
    confidence += min(0.18, max(0, prediction_hint_count) * 0.015)
    return round(max(0.05, min(0.95, confidence)), 3)


def _extract_keyword_hits(text: str, terms: Iterable[str]) -> List[str]:
    return [term for term in terms if term and term in text]


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


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


def _num(value: Any, default: Optional[float] = 0.0) -> Optional[float]:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _json_text(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except TypeError:
        return str(value)


def _unique(items: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output

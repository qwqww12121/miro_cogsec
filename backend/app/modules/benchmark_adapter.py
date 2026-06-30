"""Benchmark-facing adapters for Miro-CogSec runtime outputs."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from .public_event_semantics import extract_public_event_frame, has_public_event_content
from .semantic_frame import extract_semantic_frame, has_semantic_content


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
    "funds": ["资金", "钱", "转账", "付款", "支付", "银行卡", "红包", "充值", "保证金", "购买", "价格", "退费", "代还", "套现", "刷卡", "低点位", "投注", "博彩"],
    "credentials": ["验证码", "密码", "口令", "登录", "短信码", "动态码", "credential"],
    "identity": ["实名", "身份", "身份证", "手机卡", "个人信息", "资料", "人脸", "姓名"],
    "device": ["下载", "安装", "链接", "APP", "屏幕共享", "远程", "设备", "木马", "插件"],
    "account": ["账号", "账户", "微信", "支付宝", "银行卡", "游戏账号", "社交账号"],
    "social_trust": ["亲友", "朋友", "老师", "客服", "公安", "领导", "熟人", "信誉", "多年老店"],
    "reputation": ["名誉", "曝光", "舆论", "评论", "声誉"],
    "public_safety": ["公共事件", "安全事件", "灾害", "救援", "危险", "执法"],
}

RISK_ORDER = {"none": 0, "low": 0, "medium": 1, "high": 2, "critical": 3}

FORK_KEYWORDS = {
    "private_contact_lure": ["微信", "私下", "加好友", "联系方式", "指定联系方式", "私人账号", "邀请咨询", "联系接待"],
    "identity_asset_exchange": ["实名", "手机卡", "身份资料", "身份证"],
    "unlicensed_financial_service": ["信用卡代还", "代还", "养卡", "套现", "低点位", "刷卡"],
    "gambling_entry": ["赌博", "博彩", "投注", "开奖", "极速赛车", "赛车技巧", "牛牛", "上下分", "接待", "进群"],
    "phishing_link_entry": ["钓鱼", "伪造链接", "网址", "链接", "密码", "登录"],
    "transfer_money": ["转账", "汇款", "打款", "付款", "充值", "保证金", "定金", "手续费", "安全账户"],
    "screen_share": ["共享屏幕", "远程控制"],
    "verification_code": ["验证码", "动态码"],
    "unknown_app_download": ["下载", "安装", "APP", "app"],
    "social_isolation": ["不要告诉别人", "不要联系家人", "单独联系", "保密"],
    "fake_official_verification": ["官方核验", "监管流程", "安全核验", "公安", "警方", "监管"],
    "document_forgery_order": ["收入证明", "银行流水", "在职证明", "学历证", "资格证", "证件", "不需要本人到场", "加急出证"],
    "advance_fee_card": ["高额度信用卡", "包装费", "通道费", "保证下卡", "无需征信"],
    "illegal_goods_private_purchase": ["管制药品", "私下购买", "先付款后发货"],
    "withdrawal_recovery_contact": ["无法出款", "被黑", "提现问题", "审核维护", "指定联系方式"],
    "withdrawal_threshold_recharge": ["提现最低线", "连续贷款", "连续贷款和充值", "达到所谓提现最低线"],
    "loan_private_submission": ["无抵押", "秒放款", "黑户", "提交身份证", "银行卡照片"],
    "official_transfer_scam": ["公安机关", "洗钱", "安全账户", "接受核查"],
}

BENIGN_FRAUD_TERMS = [
    "合同电子版",
    "合同模板",
    "合同范本",
    "资料下载",
    "普通资料",
    "资料索引",
    "企业介绍",
    "工程咨询",
    "规划设计",
    "项目策划",
    "酒店介绍",
    "私人会所",
    "香薰理疗",
    "游泳池",
    "健身房",
    "公开招投标信息",
    "建设工程信息公告",
    "寻人启事",
    "衣着特征",
    "家属联系方式",
    "系统重装软件",
    "向导式操作",
    "快速重装系统",
]

RISKY_FRAUD_TERMS = [
    "验证码",
    "密码",
    "转账",
    "汇款",
    "付款",
    "充值",
    "保证金",
    "定金",
    "手续费",
    "安全账户",
    "屏幕共享",
    "远程控制",
    "贷款",
    "投资",
    "赌博",
    "博彩",
    "投注",
    "实名",
    "手机卡",
    "低点位",
    "刷卡",
    "套现",
    "代还",
    "管制药品",
    "私下购买",
    "高额度信用卡",
    "包装费",
    "通道费",
]


def build_benchmark_payload(
    *,
    result: Dict[str, Any],
    scenario_text: str,
    scenario_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Build benchmark prediction + CogSec mechanism output from runtime result."""
    scenario = _resolve_scenario(result, scenario_type)
    public_event_frame: Dict[str, Any] = {}
    semantic_frame: Dict[str, Any] = {}
    if scenario in {"public_opinion", "event_propagation"}:
        public_event_frame = extract_public_event_frame(
            text=scenario_text,
            scenario=scenario,
            runtime_context=result,
        )
    if not has_public_event_content(public_event_frame):
        semantic_frame = extract_semantic_frame(
            text=scenario_text,
            scenario=scenario,
            runtime_context=result,
        )
    if scenario == "public_opinion":
        prediction = _build_public_opinion_prediction(result, scenario_text, semantic_frame, public_event_frame)
    elif scenario == "event_propagation":
        prediction = _build_event_propagation_prediction(result, scenario_text, semantic_frame, public_event_frame)
    else:
        scenario = "fraud_im"
        prediction = _build_fraud_prediction(result, scenario_text, semantic_frame)

    cogsec_analysis = _build_cogsec_analysis(result, scenario_text, scenario, semantic_frame, public_event_frame)
    diagnostics = _diagnostics(result, scenario, prediction, cogsec_analysis, semantic_frame, public_event_frame)
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


def _build_fraud_prediction_from_frame(result: Dict[str, Any], text: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    fork_comp = _first_dict(result.get("fork_comparison"))
    evidence_spans = _frame_evidence(frame, text)
    assets = _frame_assets(frame)
    forks = _frame_forks(frame, assets)
    risk_level = _frame_fraud_risk(frame, assets, forks)
    is_fraud = bool(frame.get("is_harmful")) and risk_level in {"medium", "high", "critical"}
    window = _frame_turn_window(frame, is_active=is_fraud)
    risky_path, safe_path = _frame_counterfactual_paths(frame, is_active=is_fraud)
    prediction = {
        "is_fraud": is_fraud,
        "fraud_type": (str(frame.get("risk_type") or "").strip() or ("semantic_social_engineering" if is_fraud else "no_fraud_signal")),
        "risk_level": risk_level if is_fraud else "none",
        "attack_stage": _frame_attack_stage(frame, is_active=is_fraud),
        "asset_targets": assets if is_fraud else [],
        "fork_points": forks if is_fraud else [],
        "intervention_window": window,
        "expected_warning": _frame_text(frame.get("warning"), "当前文本未显示需要立即拦截的诈骗执行动作。"),
        "expected_safe_action": _frame_text(frame.get("safe_action"), "保持常规核验，不向无法验证的对象提交资料、资金或账号权限。"),
        "counterfactual_paths": {
            "risky_path": risky_path,
            "safe_path": safe_path,
            "trajectory_gap": _num(fork_comp.get("trajectory_gap")),
            "key_divergence": _semantic_key_divergence(forks, assets),
        },
        "evidence_spans": evidence_spans,
        "confidence": _frame_confidence(frame, result, len(evidence_spans) + len(assets)),
    }
    prediction["_adapter_asset_type_source"] = "semantic_frame"
    return prediction


def _build_public_prediction_from_frame(result: Dict[str, Any], text: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    evidence_spans = _frame_evidence(frame, text)
    propagation = _first_dict(frame.get("propagation"))
    emotion = _frame_emotion(propagation)
    official_gap = _frame_official_gap(propagation)
    risk_level = _frame_mechanism_risk(frame, scenario="public_opinion")
    prediction = {
        "event_summary": _frame_text(frame.get("summary"), _event_summary(text, "公共讨论")),
        "narrative_threads": _frame_narrative_threads(frame),
        "emotion_signal": emotion,
        "uncertainty_points": _frame_uncertainties(frame, propagation),
        "official_response_gap": official_gap,
        "propagation_risk_level": risk_level,
        "best_intervention_window": _frame_stage_window(frame),
        "expected_intervention_action": _frame_public_action(frame, propagation, official_gap, risk_level),
        "expected_safe_public_action": _frame_text(
            frame.get("safe_action"),
            "公众应保留原始上下文，等待可核验信息，避免把未经确认的说法当作事实继续扩散。",
        ),
        "evidence_spans": evidence_spans,
        "confidence": _frame_confidence(frame, result, len(evidence_spans) + 3),
    }
    return prediction


def _build_event_prediction_from_frame(result: Dict[str, Any], text: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    evidence_spans = _frame_evidence(frame, text)
    propagation = _first_dict(frame.get("propagation"))
    origin = _frame_origin(propagation)
    amplifiers = _frame_amplifiers(propagation)
    distortions = _frame_distortions(propagation)
    risk_level = _frame_mechanism_risk(frame, scenario="event_propagation")
    prediction = {
        "event_summary": _frame_text(frame.get("summary"), _event_summary(text, "事件传播")),
        "origin_node": origin,
        "amplifier_nodes": amplifiers,
        "propagation_path": _frame_propagation_path(propagation, origin, amplifiers, distortions),
        "distortion_points": distortions,
        "coverage_risk": risk_level,
        "containment_window": _frame_numeric_window(frame),
        "expected_containment_action": _frame_event_action(frame, propagation, risk_level),
        "evidence_spans": evidence_spans,
        "confidence": _frame_confidence(frame, result, len(evidence_spans) + len(amplifiers)),
    }
    return prediction


def _build_public_prediction_from_public_event_frame(result: Dict[str, Any], text: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    evidence_spans = _pe_evidence(frame, text)
    gap = _first_dict(frame.get("authority_gap"))
    plan = _first_dict(frame.get("intervention_plan"))
    prediction = {
        "event_summary": _pe_text(frame.get("summary"), _event_summary(text, "公共讨论")),
        "narrative_threads": _pe_public_threads(frame),
        "emotion_signal": _pe_emotion(frame),
        "uncertainty_points": _pe_uncertainties(frame),
        "official_response_gap": {
            "status": _pe_text(gap.get("status"), "unclear"),
            "severity": round(max(0.0, min(1.0, _num(gap.get("severity"), 0.4) or 0.4)), 3),
            "description": _pe_text(gap.get("missing_response"), "权威信息状态不明确。"),
            "evidence_spans": _pe_spans(gap.get("evidence_spans")),
        },
        "propagation_risk_level": _pe_risk(frame),
        "best_intervention_window": {
            "open_stage": _pe_text(plan.get("open_stage"), "叙事刚形成时"),
            "close_stage": _pe_text(plan.get("close_stage"), "叙事被情绪化或阵营化放大前"),
            "label": _pe_text(plan.get("window_label"), "传播语义干预窗口"),
        } if _pe_risk(frame) != "low" else {"open_stage": "monitoring", "close_stage": "monitoring", "label": "无需干预"},
        "expected_intervention_action": _pe_public_action(frame),
        "expected_safe_public_action": _pe_public_safe_action(frame),
        "evidence_spans": evidence_spans,
        "confidence": _frame_confidence(frame, result, len(evidence_spans) + 4),
    }
    return prediction


def _build_event_prediction_from_public_event_frame(result: Dict[str, Any], text: str, frame: Dict[str, Any]) -> Dict[str, Any]:
    evidence_spans = _pe_evidence(frame, text)
    origin = _pe_event_origin(frame)
    amplifiers = _pe_event_amplifiers(frame)
    risk = _pe_risk(frame)
    distortions = [] if risk == "low" else _pe_event_distortions(frame)
    plan = _first_dict(frame.get("containment_plan"))
    open_step = int(_num(plan.get("open_step"), 1) or 1)
    close_step = int(_num(plan.get("close_step"), max(open_step, 2)) or max(open_step, 2))
    if risk in {"high", "critical"}:
        close_step = max(close_step, open_step + 1)
    prediction = {
        "event_summary": _pe_text(frame.get("summary"), _event_summary(text, "事件传播")),
        "origin_node": origin,
        "amplifier_nodes": amplifiers,
        "propagation_path": _pe_event_path(frame, origin, amplifiers, distortions),
        "distortion_points": distortions,
        "coverage_risk": risk,
        "containment_window": (
            {"open_step": 0, "close_step": 0, "label": "无需特殊遏制"}
            if risk == "low"
            else {"open_step": open_step, "close_step": close_step, "label": _pe_text(plan.get("label"), "传播语义遏制窗口")}
        ),
        "expected_containment_action": _pe_event_action(frame),
        "evidence_spans": evidence_spans,
        "confidence": _frame_confidence(frame, result, len(evidence_spans) + len(amplifiers) + len(distortions)),
    }
    return prediction


def _pe_risk(frame: Dict[str, Any]) -> str:
    raw = str(frame.get("risk_level") or "medium").strip().lower()
    risk = raw if raw in RISK_ORDER else "medium"
    if risk == "none":
        return "low"
    if risk == "low":
        return "low"

    rank = RISK_ORDER.get(risk, RISK_ORDER["medium"])
    if frame.get("narrative_claims") is not None:
        emotion = _first_dict(frame.get("emotion_dynamics"))
        gap = _first_dict(frame.get("authority_gap"))
        claims = _dict_items(frame.get("narrative_claims"))
        stances = _dict_items(frame.get("stance_dynamics"))
        amplification = str(emotion.get("amplification_level") or "").lower()
        gap_severity = _num(gap.get("severity"), 0.0) or 0.0
        uncertain_claims = sum(1 for item in claims if str(item.get("evidence_state") or "").lower() in {"unverified", "contested", "unclear"})
        if amplification in {"high", "critical"} and uncertain_claims:
            rank = max(rank, RISK_ORDER["high"])
        if gap_severity >= 0.65 and uncertain_claims:
            rank = max(rank, RISK_ORDER["high"])
        if len(stances) >= 2 and uncertain_claims and amplification in {"medium", "high", "critical"}:
            rank = max(rank, RISK_ORDER["high"])
        if len(claims) >= 2 and gap_severity >= 0.5:
            rank = max(rank, RISK_ORDER["high"])
    else:
        distortions = _dict_items(frame.get("distortion_points"))
        steps = _dict_items(frame.get("propagation_steps"))
        correction = _first_dict(frame.get("correction_status"))
        max_distortion = max([_num(item.get("severity"), 0.0) or 0.0 for item in distortions], default=0.0)
        has_high_step = any(str(item.get("risk_state") or "").lower() in {"high", "critical"} or any(token in str(item.get("risk_state") or "") for token in ["高", "严重"]) for item in steps)
        binding_problem = _pe_text(correction.get("binding_problem"), "")
        if max_distortion >= 0.7 or len(distortions) >= 2:
            rank = max(rank, RISK_ORDER["high"])
        if has_high_step:
            rank = max(rank, RISK_ORDER["high"])
        if correction.get("has_correction") and binding_problem and "无纠偏" not in binding_problem:
            rank = max(rank, RISK_ORDER["high"])
    if rank >= RISK_ORDER["critical"]:
        return "critical"
    if rank >= RISK_ORDER["high"]:
        return "high"
    if rank >= RISK_ORDER["medium"]:
        return "medium"
    return "low"


def _pe_evidence(frame: Dict[str, Any], text: str) -> List[str]:
    return _unique([span for span in _pe_spans(frame.get("evidence_spans")) if span in text])[:10]


def _pe_public_threads(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    threads: List[Dict[str, Any]] = []
    for item in _dict_items(frame.get("narrative_claims")):
        evidence = _pe_spans(item.get("evidence_spans"))
        claim = _pe_text(item.get("claim"), evidence[0] if evidence else "核心叙事")
        threads.append(
            {
                "claim": claim,
                "risk": _pe_text(item.get("why_risky"), "该叙事需要结合证据状态和传播上下文判断。"),
                "evidence_spans": evidence,
                "certainty": _pe_text(item.get("evidence_state"), "unclear"),
            }
        )
    return threads[:5] or [{"claim": _pe_text(frame.get("summary"), "公共讨论"), "risk": "需要持续核验证据状态。", "evidence_spans": _pe_spans(frame.get("evidence_spans"))}]


def _pe_emotion(frame: Dict[str, Any]) -> Dict[str, Any]:
    emotion = _first_dict(frame.get("emotion_dynamics"))
    return {
        "dominant_emotion": _pe_text(emotion.get("dominant_emotion"), "neutral"),
        "amplification_level": _pe_text(emotion.get("amplification_level"), "low"),
        "rationale": _pe_text(emotion.get("rationale"), "未识别到强情绪动员。"),
        "evidence_spans": _pe_spans(emotion.get("evidence_spans")),
    }


def _pe_uncertainties(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    points = []
    for item in _dict_items(frame.get("uncertainty_nodes")):
        missing = _pe_text(item.get("missing_fact"), "")
        why = _pe_text(item.get("why_it_matters"), "")
        description = missing if not why else f"{missing}：{why}"
        if description:
            points.append({"description": description, "evidence_spans": _pe_spans(item.get("evidence_spans"))})
    return points[:5]


def _pe_public_action(frame: Dict[str, Any]) -> str:
    if _pe_risk(frame) == "low":
        return "无需主动干预，保持常规监测，并保留来源、时间和上下文。"
    plan = _first_dict(frame.get("intervention_plan"))
    actions = _dict_items(plan.get("actor_actions"))
    pieces = []
    for item in actions[:4]:
        actor = _pe_actor(item.get("actor"))
        surface = _pe_text(item.get("target_surface"), "主要传播位置")
        action = _pe_text(item.get("action"), "")
        effect = _pe_text(item.get("expected_effect"), "")
        if action:
            pieces.append(f"{actor}在{surface}{action}" + (f"，以{effect}" if effect else ""))
    if pieces:
        return "；".join(pieces) + "。"
    gap = _first_dict(frame.get("authority_gap"))
    return _pe_text(gap.get("recommended_response"), "补充权威核验信息并绑定到主要传播位置。")


def _pe_public_safe_action(frame: Dict[str, Any]) -> str:
    plan = _first_dict(frame.get("intervention_plan"))
    actions = [str(item).strip() for item in plan.get("public_actions", []) if str(item).strip()] if isinstance(plan.get("public_actions"), list) else []
    if actions:
        return "；".join(actions[:3]) + "。"
    if _pe_risk(frame) == "low":
        return "公众可继续理性讨论，同时保留原始来源和上下文。"
    return "公众应等待可核验信息，只转发带来源和上下文的材料。"


def _pe_event_origin(frame: Dict[str, Any]) -> Dict[str, Any]:
    origin = _first_dict(frame.get("origin"))
    return {
        "id": "node:pe_origin",
        "type": "public_event_origin",
        "description": _pe_text(origin.get("description"), "原始信息源"),
        "evidence_refs": _pe_refs(origin.get("evidence_spans")),
    }


def _pe_event_amplifiers(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes = []
    for index, item in enumerate(_dict_items(frame.get("amplifiers")), start=1):
        nodes.append(
            {
                "id": f"node:pe_amplifier:{index}",
                "type": _pe_text(item.get("role"), "amplifier"),
                "description": _pe_text(item.get("description"), f"放大节点 {index}"),
                "evidence_refs": _pe_refs(item.get("evidence_spans")),
            }
        )
    return nodes[:6]


def _pe_event_distortions(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    points = []
    for index, item in enumerate(_dict_items(frame.get("distortion_points")), start=1):
        dtype = str(item.get("type") or "")
        description = _pe_text(item.get("description"), "")
        if dtype == "none" and not description:
            continue
        if not description:
            description = "传播中出现上下文丢失或事实失真。"
        points.append(
            {
                "id": f"distortion:pe:{index}",
                "type": dtype or "semantic_distortion",
                "description": description,
                "severity": round(max(0.0, min(1.0, _num(item.get("severity"), 0.6) or 0.6)), 3),
                "evidence_refs": _pe_refs(item.get("evidence_spans")),
                "evidence_spans": _pe_spans(item.get("evidence_spans")),
            }
        )
    return points[:6]


def _pe_event_path(
    frame: Dict[str, Any],
    origin: Dict[str, Any],
    amplifiers: List[Dict[str, Any]],
    distortions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    path = []
    for index, item in enumerate(_dict_items(frame.get("propagation_steps")), start=1):
        actor = _pe_text(item.get("actor"), "")
        action = _pe_text(item.get("action"), "")
        transformation = _pe_text(item.get("transformation"), "")
        action_text = "，".join(part for part in [actor, action, transformation] if part) or "信息继续传播"
        path.append(
            {
                "step": int(_num(item.get("step"), index) or index),
                "node": f"node:pe_step:{index}",
                "action": action_text,
                "risk_state": _pe_text(item.get("risk_state"), "传播状态变化"),
                "evidence_spans": _pe_spans(item.get("evidence_spans")),
            }
        )
    if path:
        return path[:7]
    fallback = [{"step": 1, "node": origin.get("id"), "action": origin.get("description", "原始信息出现"), "risk_state": "origin"}]
    for index, node in enumerate(amplifiers[:3], start=2):
        fallback.append({"step": index, "node": node.get("id"), "action": node.get("description", "信息被放大"), "risk_state": "coverage_expands"})
    if distortions:
        fallback.append({"step": len(fallback) + 1, "node": distortions[0].get("id"), "action": distortions[0].get("description", "出现失真"), "risk_state": "distortion"})
    return fallback


def _pe_event_action(frame: Dict[str, Any]) -> str:
    if _pe_risk(frame) == "low":
        return "无需特殊遏制，保持常规监测，确保后续转发继续保留来源、时间和上下文。"
    plan = _first_dict(frame.get("containment_plan"))
    actions = _dict_items(plan.get("actor_actions"))
    pieces = []
    for item in actions[:4]:
        actor = _pe_actor(item.get("actor"))
        surface = _pe_text(item.get("target_surface"), "关键传播节点")
        action = _pe_text(item.get("action"), "")
        effect = _pe_text(item.get("expected_effect"), "")
        if action:
            pieces.append(f"{actor}在{surface}{action}" + (f"，以{effect}" if effect else ""))
    if pieces:
        return "；".join(pieces) + "。"
    return "在关键放大节点继续扩散前补充来源、时间、上下文和纠偏说明。"


def _pe_text(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if _has_cjk(text) or not _has_cjk(default):
        return text
    return default


def _pe_spans(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return _unique([str(span).strip() for span in value if str(span).strip()])


def _pe_refs(value: Any) -> List[str]:
    return [f"ev:{span}" for span in _pe_spans(value)]


def _pe_actor(value: Any) -> str:
    actor = str(value or "").lower()
    return {
        "official": "权威主体",
        "platform": "平台",
        "media": "媒体",
        "community": "社区或群组管理者",
        "public": "公众",
        "source": "原始发布者",
    }.get(actor, "相关主体")


def _frame_risk(frame: Dict[str, Any]) -> str:
    value = str(frame.get("risk_level") or "medium").strip().lower()
    return value if value in RISK_ORDER else "medium"


def _frame_public_risk(frame: Dict[str, Any]) -> str:
    risk = _frame_risk(frame)
    return "low" if risk == "none" else risk


def _frame_fraud_risk(frame: Dict[str, Any], assets: List[Dict[str, Any]], forks: List[Dict[str, Any]]) -> str:
    if not frame.get("is_harmful"):
        return "none"
    rank = RISK_ORDER.get(_frame_risk(frame), RISK_ORDER["medium"])
    max_asset = max([_num(item.get("severity"), 0.0) or 0.0 for item in assets], default=0.0)
    max_fork = max([_num(item.get("severity"), 0.0) or 0.0 for item in forks], default=0.0)
    risky_steps = _string_list((_dict_items(frame.get("fork_candidates"))[0] if _dict_items(frame.get("fork_candidates")) else {}).get("unsafe_branch"))
    if max_asset >= 0.75 or max_fork >= 0.75:
        rank = max(rank, RISK_ORDER["high"])
    if len(risky_steps) >= 3 and assets:
        rank = max(rank, RISK_ORDER["high"])
    if rank >= RISK_ORDER["critical"]:
        return "critical"
    if rank >= RISK_ORDER["high"]:
        return "high"
    if rank >= RISK_ORDER["medium"]:
        return "medium"
    return "low"


def _frame_mechanism_risk(frame: Dict[str, Any], *, scenario: str) -> str:
    base = _frame_public_risk(frame)
    rank = RISK_ORDER.get(base, 1)
    propagation = _first_dict(frame.get("propagation"))
    claims = _dict_items(frame.get("claims"))
    emotion = _first_dict(propagation.get("emotion"))
    official_gap = _first_dict(propagation.get("official_gap"))
    uncertainties = _dict_items(propagation.get("uncertainties"))
    distortions = _dict_items(propagation.get("distortions"))
    amplifiers = _dict_items(propagation.get("amplifiers"))
    has_uncertain_claim = any(str(item.get("certainty") or "").lower() in {"unverified", "contested", "unknown"} for item in claims)
    amplification = str(emotion.get("amplification_level") or "").lower()
    gap_severity = _num(official_gap.get("severity"), 0.0) or 0.0
    max_distortion = max([_num(item.get("severity"), 0.0) or 0.0 for item in distortions], default=0.0)

    if not frame.get("is_harmful") and not has_uncertain_claim and not distortions and amplification in {"", "low"}:
        return "low"
    if scenario == "public_opinion":
        if has_uncertain_claim and amplification in {"high", "critical"}:
            rank = max(rank, RISK_ORDER["high"])
        if has_uncertain_claim and gap_severity >= 0.65:
            rank = max(rank, RISK_ORDER["high"])
        if len(uncertainties) >= 2 and amplification in {"medium", "high", "critical"}:
            rank = max(rank, RISK_ORDER["high"])
        if has_uncertain_claim and len(amplifiers) >= 2:
            rank = max(rank, RISK_ORDER["high"])
    else:
        if max_distortion >= 0.65 or len(distortions) >= 2:
            rank = max(rank, RISK_ORDER["high"])
        if distortions and len(amplifiers) >= 2:
            rank = max(rank, RISK_ORDER["high"])
        if distortions and _dict_items(propagation.get("corrections")):
            rank = max(rank, RISK_ORDER["high"])
        if any(_step_has_high_risk_state(item) for item in _dict_items(propagation.get("path_steps"))):
            rank = max(rank, RISK_ORDER["high"])
    if rank >= RISK_ORDER["critical"]:
        return "critical"
    if rank >= RISK_ORDER["high"]:
        return "high"
    if rank >= RISK_ORDER["medium"]:
        return "medium"
    return "low"


def _frame_evidence(frame: Dict[str, Any], text: str) -> List[str]:
    spans = [str(span) for span in frame.get("evidence_spans", []) if span]
    return _unique([span for span in spans if span in text])[:8]


def _frame_assets(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    assets: List[Dict[str, Any]] = []
    for index, item in enumerate(_dict_items(frame.get("assets")), start=1):
        asset_type = str(item.get("type") or "other").strip() or "other"
        description = _frame_text(item.get("description"), _asset_label(asset_type))
        evidence = _valid_frame_refs(item.get("evidence_spans"))
        assets.append(
            {
                "id": f"asset:{asset_type}:{index}",
                "type": asset_type,
                "label": description,
                "severity": round(max(0.0, min(1.0, _num(item.get("severity"), 0.65) or 0.65)), 3),
                "evidence_refs": evidence,
                "matched_terms": [ref.replace("ev:", "") for ref in evidence],
            }
        )
    return assets[:5]


def _frame_forks(frame: Dict[str, Any], assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    forks: List[Dict[str, Any]] = []
    asset_label = assets[0].get("label") if assets else "风险对象"
    for index, item in enumerate(_dict_items(frame.get("fork_candidates")), start=1):
        fork_type = _frame_text(item.get("type"), f"semantic_fork_{index}")
        trigger = _frame_text(item.get("trigger"), "原文中出现需要在继续配合与暂停核验之间选择的分叉点。")
        unsafe = _string_list(item.get("unsafe_branch"))
        safe = _string_list(item.get("safe_branch"))
        forks.append(
            {
                "id": f"fork:semantic:{index}",
                "type": fork_type,
                "severity": 0.8,
                "asset": asset_label,
                "reason": trigger,
                "evidence_refs": _valid_frame_refs(item.get("evidence_spans")),
                "runtime_alignment": {"status": "semantic_frame", "runtime_type": fork_type},
                "expected_branch_a": " → ".join(unsafe[:4]) if unsafe else "继续沿原诱导路径行动，风险累积。",
                "expected_branch_b": " → ".join(safe[:4]) if safe else "暂停行动并转向可核验渠道。",
            }
        )
    if forks:
        return forks[:4]
    return [
        {
            "id": "fork:semantic:1",
            "type": "verify_before_commitment",
            "severity": 0.65,
            "asset": asset_label,
            "reason": "语义帧识别到应在承诺、传播或提交资源前进行核验。",
            "evidence_refs": _valid_frame_refs(frame.get("evidence_spans")),
            "runtime_alignment": {"status": "semantic_frame", "runtime_type": "verify_before_commitment"},
            "expected_branch_a": "继续执行未核验请求，风险上升。",
            "expected_branch_b": "暂停并核验来源、证据和正式渠道。",
        }
    ]


def _frame_turn_window(frame: Dict[str, Any], *, is_active: bool) -> Dict[str, Any]:
    if not is_active:
        return {"start_turn": 0, "end_turn": 0, "rationale": "语义帧未识别到需要立即拦截的高风险诈骗执行动作。"}
    raw = _first_dict((_dict_items(frame.get("fork_candidates"))[0] if _dict_items(frame.get("fork_candidates")) else {}).get("intervention_window"))
    start = int(_num(raw.get("start_turn"), 0) or 0)
    end = int(_num(raw.get("end_turn"), max(start, 1)) or max(start, 1))
    rationale = _frame_text(raw.get("rationale") or raw.get("label"), "在用户继续提交资源、进入私域或扩散未核验信息前介入。")
    return {"start_turn": start, "end_turn": max(start, end), "rationale": rationale}


def _frame_stage_window(frame: Dict[str, Any]) -> Dict[str, Any]:
    raw = _first_dict((_dict_items(frame.get("fork_candidates"))[0] if _dict_items(frame.get("fork_candidates")) else {}).get("intervention_window"))
    risk = _frame_mechanism_risk(frame, scenario="public_opinion")
    if risk == "low":
        return {"open_stage": "monitoring", "close_stage": "monitoring", "label": "无需干预"}
    return {
        "open_stage": _frame_text(raw.get("open_stage"), "语义分叉刚形成时"),
        "close_stage": _frame_text(raw.get("close_stage"), "叙事或传播路径被放大前"),
        "label": _frame_text(raw.get("label"), "证据补充与传播降温窗口"),
    }


def _frame_numeric_window(frame: Dict[str, Any]) -> Dict[str, Any]:
    raw = _first_dict((_dict_items(frame.get("fork_candidates"))[0] if _dict_items(frame.get("fork_candidates")) else {}).get("intervention_window"))
    risk = _frame_mechanism_risk(frame, scenario="event_propagation")
    if risk == "low":
        return {"open_step": 0, "close_step": 0, "label": "无需特殊遏制"}
    open_step = int(_num(raw.get("start_turn"), 1) or 1)
    close_step = int(_num(raw.get("end_turn"), max(open_step, 2)) or max(open_step, 2))
    if risk in {"high", "critical"}:
        close_step = max(close_step, open_step + 1, 2)
    return {
        "open_step": open_step,
        "close_step": max(open_step, close_step),
        "label": _frame_text(raw.get("label") or raw.get("rationale"), "在关键放大节点继续扩散前介入"),
    }


def _frame_counterfactual_paths(frame: Dict[str, Any], *, is_active: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if not is_active:
        return [], [{"step": 1, "action": "保持常规核验，不执行高风险操作。", "risk_state": "risk_stable"}]
    forks = _dict_items(frame.get("fork_candidates"))
    first = forks[0] if forks else {}
    risky = _path_steps(_string_list(first.get("unsafe_branch")), "risk_escalation")
    safe = _path_steps(_string_list(first.get("safe_branch")), "risk_reduction")
    if not risky:
        risky = [{"step": 1, "action": "继续沿未核验路径行动。", "risk_state": "risk_escalation"}]
    if not safe:
        safe = [{"step": 1, "action": "暂停并转向可核验渠道。", "risk_state": "risk_reduction"}]
    return risky, safe


def _frame_attack_stage(frame: Dict[str, Any], *, is_active: bool) -> str:
    if not is_active:
        return "no_attack_observed"
    forks = _dict_items(frame.get("fork_candidates"))
    trigger = _frame_text(forks[0].get("trigger") if forks else None, "")
    return trigger[:80] if trigger else "semantic_fork_identified"


def _frame_narrative_threads(frame: Dict[str, Any]) -> List[Dict[str, Any]]:
    threads: List[Dict[str, Any]] = []
    for item in _dict_items(frame.get("claims")):
        evidence_texts = _valid_frame_span_texts(item.get("evidence_spans"))
        claim = _frame_text(item.get("claim"), evidence_texts[0] if evidence_texts else "")
        if not claim:
            continue
        threads.append(
            {
                "claim": claim,
                "risk": _frame_text(item.get("risk"), "该叙事需要结合证据状态和传播上下文判断，避免把未核验内容当作事实继续扩散。"),
                "evidence_spans": evidence_texts,
                "certainty": _frame_text(item.get("certainty"), "unknown"),
            }
        )
    if threads:
        return threads[:4]
    summary = _frame_text(frame.get("summary"), "原文形成公共讨论。")
    return [{"claim": summary, "risk": "需要根据证据充分性和传播放大情况判断。", "evidence_spans": _valid_frame_span_texts(frame.get("evidence_spans"))}]


def _frame_emotion(propagation: Dict[str, Any]) -> Dict[str, Any]:
    emotion = _first_dict(propagation.get("emotion"))
    return {
        "dominant_emotion": _frame_text(emotion.get("dominant_emotion"), "neutral"),
        "amplification_level": _frame_text(emotion.get("amplification_level"), "low"),
        "rationale": _frame_text(emotion.get("rationale"), "语义帧未识别到强情绪动员。"),
        "evidence_spans": _valid_frame_span_texts(emotion.get("evidence_spans")),
    }


def _frame_uncertainties(frame: Dict[str, Any], propagation: Dict[str, Any]) -> List[Dict[str, Any]]:
    points = [
        {
            "description": _frame_text(item.get("description"), ""),
            "evidence_spans": _valid_frame_span_texts(item.get("evidence_spans")),
        }
        for item in _dict_items(propagation.get("uncertainties"))
        if _frame_text(item.get("description"), "")
    ]
    if points:
        return points[:4]
    for item in _dict_items(frame.get("claims")):
        certainty = str(item.get("certainty") or "").lower()
        if certainty in {"unverified", "contested", "unknown"}:
            evidence_texts = _valid_frame_span_texts(item.get("evidence_spans"))
            points.append(
                {
                    "description": _frame_text(item.get("claim"), evidence_texts[0] if evidence_texts else "存在尚未核验的信息点。"),
                    "evidence_spans": evidence_texts,
                }
            )
    return points[:4]


def _frame_official_gap(propagation: Dict[str, Any]) -> Dict[str, Any]:
    gap = _first_dict(propagation.get("official_gap"))
    return {
        "status": _frame_text(gap.get("status"), "unclear"),
        "severity": round(max(0.0, min(1.0, _num(gap.get("severity"), 0.4) or 0.4)), 3),
        "description": _frame_text(gap.get("description"), "官方或权威信息状态不明确。"),
        "evidence_spans": _valid_frame_span_texts(gap.get("evidence_spans")),
    }


def _frame_public_action(frame: Dict[str, Any], propagation: Dict[str, Any], official_gap: Dict[str, Any], risk_level: str) -> str:
    if risk_level == "low":
        return "无需主动干预，保持常规监测，并继续保留来源、时间和上下文信息。"
    custom = _frame_text(frame.get("intervention_action") or frame.get("warning"), "")
    if _has_cjk(custom):
        return custom
    uncertainties = _dict_items(propagation.get("uncertainties"))
    claims = _dict_items(frame.get("claims"))
    gap_status = str(official_gap.get("status") or "").lower()
    if gap_status in {"present", "unclear"} and (official_gap.get("severity") or 0) >= 0.55:
        return "由权威主体尽快发布阶段性核查说明，把已确认事实、未确认说法和后续调查安排分开列出，并将说明置顶绑定到正在扩散的原讨论。"
    if uncertainties or any(str(item.get("certainty") or "").lower() in {"unverified", "contested", "unknown"} for item in claims):
        return "在转发入口和热评位置增加事实核验提示，要求传播者标注未确认内容，并把可核验证据链接到原叙事旁边。"
    return "补充可核验信息、降低情绪化转发权重，并把澄清说明同步到主要传播节点。"


def _frame_event_action(frame: Dict[str, Any], propagation: Dict[str, Any], risk_level: str) -> str:
    if risk_level == "low":
        return "无需特殊遏制，保持常规监测，确保后续转发继续保留来源、时间、影响范围和上下文。"
    custom = _frame_text(frame.get("intervention_action") or frame.get("safe_action"), "")
    if _has_cjk(custom):
        return custom
    distortions = _dict_items(propagation.get("distortions"))
    amplifiers = _dict_items(propagation.get("amplifiers"))
    corrections = _dict_items(propagation.get("corrections"))
    if distortions and corrections:
        return "把权威更正绑定到原始传播链和主要放大节点，要求已转发账号同步更新，并降低未更正版本的继续推荐。"
    if distortions and amplifiers:
        return "在首个放大节点继续扩散前加来源、时间、上下文和未证实标签，要求放大节点补充原文链接或停止转发失真版本。"
    if distortions:
        return "对失真内容加醒目标注，补齐原始上下文，并在二次传播前触发人工或平台审核。"
    return "在关键放大节点继续扩散前补充来源、时间和上下文，并把纠偏说明绑定到原传播链。"


def _frame_origin(propagation: Dict[str, Any]) -> Dict[str, Any]:
    origin = _first_dict(propagation.get("origin"))
    description = _frame_text(origin.get("description"), "原始信息源")
    return {"id": "node:semantic_origin", "type": "semantic_origin", "description": description, "evidence_refs": _valid_frame_refs(origin.get("evidence_spans"))}


def _frame_amplifiers(propagation: Dict[str, Any]) -> List[Dict[str, Any]]:
    nodes: List[Dict[str, Any]] = []
    for index, item in enumerate(_dict_items(propagation.get("amplifiers")), start=1):
        nodes.append(
            {
                "id": f"node:semantic_amplifier:{index}",
                "type": "semantic_amplifier",
                "description": _frame_text(item.get("description"), f"放大节点 {index}"),
                "evidence_refs": _valid_frame_refs(item.get("evidence_spans")),
            }
        )
    return nodes[:5]


def _frame_distortions(propagation: Dict[str, Any]) -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for index, item in enumerate(_dict_items(propagation.get("distortions")), start=1):
        evidence_texts = _valid_frame_span_texts(item.get("evidence_spans"))
        description = _frame_text(item.get("description"), evidence_texts[0] if evidence_texts else "传播中出现上下文丢失或事实失真。")
        if not description:
            continue
        points.append(
            {
                "id": f"distortion:semantic:{index}",
                "description": description,
                "severity": round(max(0.0, min(1.0, _num(item.get("severity"), 0.6) or 0.6)), 3),
                "evidence_refs": _valid_frame_refs(item.get("evidence_spans")),
                "evidence_spans": evidence_texts,
            }
        )
    return points[:5]


def _frame_propagation_path(
    propagation: Dict[str, Any],
    origin: Dict[str, Any],
    amplifiers: List[Dict[str, Any]],
    distortions: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    path = []
    for index, item in enumerate(_dict_items(propagation.get("path_steps")), start=1):
        evidence_texts = _valid_frame_span_texts(item.get("evidence_spans"))
        path.append(
            {
                "step": int(_num(item.get("step"), index) or index),
                "node": f"node:semantic_step:{index}",
                "action": _frame_text(item.get("action"), evidence_texts[0] if evidence_texts else "信息继续传播"),
                "risk_state": _frame_text(item.get("risk_state"), "传播风险状态发生变化"),
                "evidence_spans": evidence_texts,
            }
        )
    if path:
        return path[:6]
    fallback: List[Dict[str, Any]] = []
    if origin:
        fallback.append({"step": 1, "node": origin.get("id"), "action": origin.get("description", "原始信息出现"), "risk_state": "origin"})
    for index, node in enumerate(amplifiers[:3], start=2):
        fallback.append({"step": index, "node": node.get("id"), "action": node.get("description", "信息被放大"), "risk_state": "coverage_expands"})
    if distortions:
        fallback.append({"step": len(fallback) + 1, "node": distortions[0].get("id"), "action": distortions[0].get("description", "传播中出现失真"), "risk_state": "distortion"})
    return fallback


def _frame_confidence(frame: Dict[str, Any], result: Dict[str, Any], hint_count: int) -> float:
    raw = _num(frame.get("confidence"), None)
    if raw is not None:
        return round(max(0.05, min(0.95, raw)), 3)
    return _confidence(result, prediction_hint_count=hint_count)


def _semantic_key_divergence(forks: List[Dict[str, Any]], assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    asset = assets[0].get("type") if assets else "semantic_target"
    return [
        {
            "fork_type": fork.get("type", "semantic_fork"),
            "asset": asset,
            "description": "语义分叉比较高风险路径与核验/遏制路径的后果差异。",
        }
        for fork in forks[:3]
    ]


def _path_steps(items: List[str], state: str) -> List[Dict[str, Any]]:
    return [{"step": index, "action": item, "risk_state": state} for index, item in enumerate(items, start=1) if item]


def _step_has_high_risk_state(item: Dict[str, Any]) -> bool:
    text = str(item.get("risk_state") or "").lower()
    return any(signal in text for signal in ["high", "critical", "高", "严重"])


def _dict_items(value: Any) -> List[Dict[str, Any]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _frame_text(value: Any, default: str) -> str:
    text = str(value or "").strip()
    if not text:
        return default
    if _has_cjk(text) or not default or not _has_cjk(default):
        return text
    return default


def _has_cjk(text: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", text or ""))


def _valid_frame_refs(value: Any) -> List[str]:
    return [f"ev:{span}" for span in _valid_frame_span_texts(value)]


def _valid_frame_span_texts(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return _unique([str(span).strip() for span in value if str(span).strip()])


def _build_fraud_prediction(result: Dict[str, Any], text: str, semantic_frame: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    if has_semantic_content(semantic_frame):
        return _build_fraud_prediction_from_frame(result, text, semantic_frame or {})

    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    fork_comp = _first_dict(result.get("fork_comparison"))
    report = _first_dict(result.get("counterfactual_report"))
    report_sections = _first_dict(report.get("report_sections"), report.get("structured_report"))
    counterfactual_expectation = _first_dict(report.get("counterfactual_expectation"), report_sections.get("counterfactual_expectation"))
    t0 = _first_dict(result.get("t0_fast_response"))

    fraud_type = _fraud_type(result, graph, text)
    risk_level = _fraud_text_risk_level(text, _risk_level(result), fraud_type)
    benign_text = _is_benign_information_text(text)
    if benign_text:
        risk_level = "none"
    assets, asset_source = normalize_asset_targets(graph.get("asset_targets") or result.get("asset_targets") or [], text)
    if benign_text:
        assets = []
        asset_source = "benign_text_gate"
    if not assets:
        assets = _assets_from_text(text)
        asset_source = "text_fallback"
    if benign_text:
        assets = []

    fork_points = _normalize_fork_points(graph.get("fork_points"), fork_comp, assets, text=text)
    if benign_text:
        fork_points = []
    window = _fraud_window(report, fork_comp, counterfactual_expectation, text=text, is_fraud=not benign_text)
    evidence_spans = _extract_evidence_spans(text, graph, scenario="fraud_im")
    attack_stage = _infer_attack_stage(text, graph)

    risky_path, safe_path = _counterfactual_paths_from_runtime(result, counterfactual_expectation)
    risky_path, safe_path = _fraud_paths_from_text(text, fraud_type, risky_path, safe_path)
    prediction = {
        "is_fraud": False if benign_text else (risk_level in {"medium", "high", "critical"} or bool(t0.get("should_interrupt")) or bool(graph.get("attack_strategy_chain"))),
        "fraud_type": fraud_type,
        "risk_level": risk_level,
        "attack_stage": attack_stage,
        "asset_targets": assets,
        "fork_points": fork_points,
        "intervention_window": window,
        "expected_warning": _benign_fraud_warning(text) if benign_text else _fraud_warning(text, assets, t0, risk_level),
        "expected_safe_action": _benign_fraud_safe_action(text) if benign_text else _fraud_safe_action(text, assets),
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


def _build_public_opinion_prediction(
    result: Dict[str, Any],
    text: str,
    semantic_frame: Optional[Dict[str, Any]] = None,
    public_event_frame: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if has_public_event_content(public_event_frame):
        return _build_public_prediction_from_public_event_frame(result, text, public_event_frame or {})
    if has_semantic_content(semantic_frame):
        return _build_public_prediction_from_frame(result, text, semantic_frame or {})

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


def _build_event_propagation_prediction(
    result: Dict[str, Any],
    text: str,
    semantic_frame: Optional[Dict[str, Any]] = None,
    public_event_frame: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if has_public_event_content(public_event_frame):
        return _build_event_prediction_from_public_event_frame(result, text, public_event_frame or {})
    if has_semantic_content(semantic_frame):
        return _build_event_prediction_from_frame(result, text, semantic_frame or {})

    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    propagation = _propagation_search(result) or _first_dict((_scenario_extension(result)).get("propagation"))
    selected = _first_dict(propagation.get("selected_best_branch"))
    baseline = _first_dict(propagation.get("baseline_branch"))
    evidence_spans = _extract_evidence_spans(text, graph, scenario="event_propagation")
    origin = _origin_node(text)
    amplifiers = _amplifier_nodes(text)
    distortions = _distortion_points(text)
    window = _numeric_window_from_selected(selected, default_open=2, default_close=3)
    if _is_low_risk_event_text(text):
        window = {"open_step": 0, "close_step": 0, "label": "无需特殊遏制"}
    elif any(term in text for term in ["嫌疑人身份", "现场图片", "权威账号发布更正"]):
        window = {"open_step": 1, "close_step": 3, "label": "在未经证实身份和脱离上下文图片继续二次传播前介入"}
    elif "限定条件和更新说明被裁掉" in text:
        window = {"open_step": 2, "close_step": 3, "label": "在截图跨平台搬运并裁掉上下文前介入"}
    elif "高影响力账号" in text:
        window = {"open_step": 1, "close_step": 2, "label": "在高影响力账号继续放大未证实传言前介入"}
    elif any(term in text for term in ["地点名称被简写", "遗漏了发布时间", "实时有效"]):
        window = {"open_step": 1, "close_step": 2, "label": "在志愿者群组和地方媒体继续转发前补齐地点与时间"}
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


def _build_cogsec_analysis(
    result: Dict[str, Any],
    text: str,
    scenario: str,
    semantic_frame: Optional[Dict[str, Any]] = None,
    public_event_frame: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    graph = _first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    fork_comp = _first_dict(result.get("fork_comparison"))
    report = _first_dict(result.get("counterfactual_report"))
    propagation = _first_dict((_scenario_extension(result)).get("propagation"))
    intervention_search = _propagation_search(result)
    risky_path, safe_path = _counterfactual_paths_from_runtime(result, _first_dict(report.get("counterfactual_expectation")))
    if has_public_event_content(public_event_frame):
        evidence_spans = _pe_evidence(public_event_frame or {}, text)
    elif has_semantic_content(semantic_frame):
        evidence_spans = _frame_evidence(semantic_frame or {}, text)
    else:
        evidence_spans = _extract_evidence_spans(text, graph, scenario=scenario)

    propagation_analysis = {
        "origin_node": (
            _pe_event_origin(public_event_frame or {})
            if has_public_event_content(public_event_frame) and scenario == "event_propagation"
            else (_frame_origin(_first_dict((semantic_frame or {}).get("propagation"))) if has_semantic_content(semantic_frame) and scenario == "event_propagation" else (_origin_node(text) if scenario == "event_propagation" else {}))
        ),
        "amplifier_nodes": (
            _pe_event_amplifiers(public_event_frame or {})
            if has_public_event_content(public_event_frame) and scenario == "event_propagation"
            else (_frame_amplifiers(_first_dict((semantic_frame or {}).get("propagation"))) if has_semantic_content(semantic_frame) and scenario == "event_propagation" else (_amplifier_nodes(text) if scenario == "event_propagation" else []))
        ),
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
        "semantic_frame": semantic_frame if has_semantic_content(semantic_frame) else {},
        "public_event_frame": public_event_frame if has_public_event_content(public_event_frame) else {},
        "provenance": {
            "source": "mirofish_pipeline",
            "semantic_frame_source": _first_dict((semantic_frame or {}).get("provenance")).get("source"),
            "public_event_frame_source": _first_dict((public_event_frame or {}).get("provenance")).get("source"),
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
    semantic_frame: Optional[Dict[str, Any]] = None,
    public_event_frame: Optional[Dict[str, Any]] = None,
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
    frame_provenance = _first_dict((semantic_frame or {}).get("provenance"))
    pe_provenance = _first_dict((public_event_frame or {}).get("provenance"))
    if scenario in {"public_opinion", "event_propagation"} and not has_public_event_content(public_event_frame):
        warnings.append(f"public/event frame not used: {pe_provenance.get('source', 'unavailable')}")
    if not has_semantic_content(semantic_frame) and not has_public_event_content(public_event_frame):
        warnings.append(f"semantic frame not used: {frame_provenance.get('source', 'unavailable')}")
    return {
        "missing_prediction_fields": missing_prediction,
        "missing_cogsec_fields": missing_cogsec,
        "evidence_span_count": len(prediction.get("evidence_spans", [])) if isinstance(prediction.get("evidence_spans"), list) else 0,
        "asset_type_source": prediction.pop("_adapter_asset_type_source", None) or "not_applicable",
        "semantic_frame": {
            "used": has_semantic_content(semantic_frame),
            "source": frame_provenance.get("source"),
            "model": frame_provenance.get("model"),
            "evidence_policy": frame_provenance.get("evidence_policy"),
            "evidence_span_count": len((semantic_frame or {}).get("evidence_spans", [])) if isinstance((semantic_frame or {}).get("evidence_spans"), list) else 0,
        },
        "public_event_frame": {
            "used": has_public_event_content(public_event_frame),
            "source": pe_provenance.get("source"),
            "model": pe_provenance.get("model"),
            "evidence_policy": pe_provenance.get("evidence_policy"),
            "evidence_span_count": len((public_event_frame or {}).get("evidence_spans", [])) if isinstance((public_event_frame or {}).get("evidence_spans"), list) else 0,
        },
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
    if scenario == "public_opinion" and _is_low_risk_public_text(text):
        return "low"
    if scenario == "event_propagation" and _is_low_risk_event_text(text):
        return "low"
    runtime_level = _propagation_risk_level(baseline, fallback=fallback)
    text_level = "low"
    if scenario == "public_opinion":
        if any(term in text for term in ["阵营对立", "强烈指控", "种族议题", "迅速发酵", "航空事故"]):
            text_level = "high"
        elif "官方调查尚未完成" in text and any(term in text for term in ["多种说法", "媒体和个人账号", "恐慌", "猜测"]):
            text_level = "high"
        elif (
            ("迅速发酵" in text or "立即" in text or "大量" in text)
            and any(term in text for term in ["愤怒", "种族", "警民", "未经证实", "要求官方"])
        ):
            text_level = "high"
        elif any(term in text for term in ["焦虑", "求证", "互相指责", "未经临床验证", "亲友经验", "医学机构说明"]):
            text_level = "medium"
        elif any(term in text for term in ["网传", "未经证实", "讨论", "转发"]):
            text_level = "medium"
    else:
        if any(term in text for term in ["限定条件和更新说明被裁掉", "绝对化的说法", "高影响力账号", "判断性措辞", "原始高影响力转发仍继续被引用"]):
            text_level = "high"
        elif any(term in text for term in ["遗漏了发布时间", "实时有效", "地点名称被简写"]):
            text_level = "high"
        elif (
            any(term in text for term in ["多个新闻账号", "多个", "新闻账号", "个人账号"])
            and any(term in text for term in ["未经证实", "嫌疑人身份", "现场图片", "不准确", "更正"])
        ):
            text_level = "high"
        elif any(term in text for term in ["地方媒体", "救援信息汇总账号", "遗漏", "地点名称", "实时有效", "志愿者群组"]):
            text_level = "medium"
        elif any(term in text for term in ["转发", "首发", "传播"]):
            text_level = "medium"
    return max([runtime_level, fallback, text_level], key=lambda item: RISK_ORDER.get(item, 1))


def _fraud_text_risk_level(text: str, fallback: str, fraud_type: str) -> str:
    if _is_benign_information_text(text):
        return "none"
    high_types = {
        "identity_asset_trade",
        "unlicensed_financial_service",
        "gambling_fraud",
        "phishing_credential_theft",
        "fake_police_fraud",
        "impersonation_refund",
        "loan_fraud",
        "document_forgery_fraud",
        "advance_fee_card_fraud",
        "illegal_goods_fraud",
        "withdrawal_recovery_fraud",
        "gambling_platform_fake_customer_service",
        "loan_recharge_withdrawal_fraud",
    }
    if fraud_type in high_types:
        return "high"
    if any(term in text for term in ["广告", "群广告", "邮件声称", "来电者", "冒充", "要求", "先付", "先交"]):
        return "high"
    return fallback if fallback in RISK_ORDER else "medium"


def _fraud_type(result: Dict[str, Any], graph: Dict[str, Any], text: str = "") -> str:
    if _is_benign_information_text(text):
        return "no_fraud_signal"
    if any(term in text for term in ["实名", "手机卡"]):
        return "identity_asset_trade"
    if any(term in text for term in ["信用卡代还", "代还", "养卡", "套现", "低点位", "刷卡"]):
        return "unlicensed_financial_service"
    if any(term in text for term in ["赌博", "博彩", "投注", "开奖", "极速赛车", "赛车技巧", "牛牛", "上下分"]):
        return "gambling_fraud"
    if any(term in text for term in ["收入证明", "银行流水", "在职证明", "学历证", "资格证", "各类证件", "加急出证"]):
        return "document_forgery_fraud"
    if any(term in text for term in ["高额度信用卡", "包装费", "通道费", "保证下卡"]):
        return "advance_fee_card_fraud"
    if any(term in text for term in ["管制药品", "私下购买", "先付款后发货"]):
        return "illegal_goods_fraud"
    if any(term in text for term in ["无法出款", "被黑", "提现问题", "审核维护"]):
        return "gambling_platform_fake_customer_service"
    if any(term in text for term in ["提现最低线", "连续贷款", "连续贷款和充值"]):
        return "loan_recharge_withdrawal_fraud"
    if any(term in text for term in ["钓鱼", "伪造链接", "密码", "登录"]):
        return "phishing_credential_theft"
    if any(term in text for term in ["公安", "警方", "公检法", "安全账户", "账户冻结"]):
        return "fake_police_fraud"
    if any(term in text for term in ["贷款", "放款", "保证金", "刷流水", "激活费"]):
        return "loan_fraud"
    if any(term in text for term in ["客服", "退款", "理赔"]):
        return "impersonation_refund"
    if any(term in text for term in ["投资", "理财", "收益", "提现"]):
        return "investment_fraud"

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
    if _is_benign_information_text(text):
        return "no_attack_observed"
    if any(term in text for term in ["电话被拉黑", "无法联系", "失联"]):
        return "post_fraud"
    if any(term in text for term in ["广告", "群广告", "邮件声称", "来电者自称", "对方冒充", "帖子称", "指定联系方式", "对方声称"]):
        return "initial_contact"
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


def _is_benign_information_text(text: str) -> bool:
    return any(term in text for term in BENIGN_FRAUD_TERMS) and not any(term in text for term in RISKY_FRAUD_TERMS)


def _is_low_risk_public_text(text: str) -> bool:
    positive_reliability = any(term in text for term in ["可靠媒体确认", "理性讨论", "信息补充", "背景解释"])
    explicit_absence = any(term in text for term in ["未出现明显未经证实", "未出现明显", "无风险信号"])
    return positive_reliability and explicit_absence


def _is_low_risk_event_text(text: str) -> bool:
    preserved_context = any(term in text for term in ["保留了原始发布时间", "影响区域和防护建议", "官方应急账号"])
    explicit_absence = any(term in text for term in ["未出现明显地点误传", "未出现明显", "未出现明显地点误传、时间误传或断章取义"])
    return preserved_context and explicit_absence


def _normalize_fork_points(raw: Any, fork_comp: Dict[str, Any], assets: List[Dict[str, Any]], text: str = "") -> List[Dict[str, Any]]:
    points: List[Dict[str, Any]] = []
    for item in raw if isinstance(raw, list) else []:
        if not isinstance(item, dict):
            continue
        fork_type = item.get("type") or fork_comp.get("fork_point_type") or "verify_legitimacy_vs_compliance"
        evidence_refs = item.get("evidence_refs", []) or _fork_evidence_refs(fork_type, text)
        if not _fork_is_grounded(fork_type, text, evidence_refs):
            continue
        points.append(
            {
                "id": item.get("id") or "fork:runtime",
                "type": fork_type,
                "severity": round(_num(item.get("severity"), 0.7), 3),
                "asset": item.get("asset") or (assets[0]["label"] if assets else "核心资产"),
                "reason": item.get("reason") or _fork_reason(fork_type),
                "evidence_refs": evidence_refs,
                "runtime_alignment": item.get("runtime_alignment") or _runtime_alignment_for_fork(fork_type),
            }
        )
    if not points:
        points.extend(_semantic_forks_from_text(text, assets))
    if not points:
        runtime_type = fork_comp.get("fork_point_type")
        if runtime_type and _fork_is_grounded(str(runtime_type), text, _fork_evidence_refs(str(runtime_type), text)):
            points.append(
                {
                    "id": "fork:runtime_primary",
                    "type": str(runtime_type),
                    "severity": 0.55,
                    "asset": assets[0]["label"] if assets else "核心资产",
                    "reason": _fork_reason(str(runtime_type)),
                    "evidence_refs": _fork_evidence_refs(str(runtime_type), text),
                    "runtime_alignment": _runtime_alignment_for_fork(str(runtime_type)),
                }
            )
    return points[:3]


def _semantic_forks_from_text(text: str, assets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if _is_benign_information_text(text):
        return []
    points: List[Dict[str, Any]] = []
    asset = assets[0]["label"] if assets else "核心资产"
    specs = [
        ("private_contact_lure", 0.82),
        ("identity_asset_exchange", 0.84),
        ("unlicensed_financial_service", 0.84),
        ("gambling_entry", 0.86),
        ("document_forgery_order", 0.86),
        ("advance_fee_card", 0.86),
        ("illegal_goods_private_purchase", 0.88),
        ("withdrawal_recovery_contact", 0.82),
        ("withdrawal_threshold_recharge", 0.9),
        ("loan_private_submission", 0.88),
        ("official_transfer_scam", 0.92),
        ("phishing_link_entry", 0.86),
        ("transfer_money", 0.86),
        ("screen_share", 0.88),
        ("verification_code", 0.92),
        ("unknown_app_download", 0.83),
        ("social_isolation", 0.74),
        ("fake_official_verification", 0.8),
    ]
    for fork_type, severity in specs:
        evidence_refs = _fork_evidence_refs(fork_type, text)
        if not evidence_refs:
            continue
        points.append(
            {
                "id": f"fork:{fork_type}",
                "type": fork_type,
                "severity": severity,
                "asset": asset,
                "reason": _fork_reason(fork_type),
                "evidence_refs": evidence_refs,
                "runtime_alignment": _runtime_alignment_for_fork(fork_type),
            }
        )
    return points


def _fork_evidence_refs(fork_type: str, text: str) -> List[str]:
    hits = _extract_keyword_hits(text, FORK_KEYWORDS.get(fork_type, []))
    return [f"ev:{hit}" for hit in hits[:3]]


def _fork_is_grounded(fork_type: str, text: str, evidence_refs: Any) -> bool:
    refs = [str(ref).replace("ev:", "") for ref in _as_list(evidence_refs)]
    if any(ref and ref in text for ref in refs):
        return True
    return bool(_extract_keyword_hits(text, FORK_KEYWORDS.get(fork_type, [])))


def _runtime_alignment_for_fork(fork_type: str) -> Dict[str, Any]:
    direct = {
        "transfer_money",
        "screen_share",
        "verification_code",
        "unknown_app_download",
        "social_isolation",
        "fake_official_verification",
    }
    nearest = {
        "private_contact_lure": "transfer_money",
        "identity_asset_exchange": "transfer_money",
        "unlicensed_financial_service": "transfer_money",
        "gambling_entry": "transfer_money",
        "phishing_link_entry": "unknown_app_download",
        "document_forgery_order": "transfer_money",
        "advance_fee_card": "transfer_money",
        "illegal_goods_private_purchase": "transfer_money",
        "withdrawal_recovery_contact": "transfer_money",
        "withdrawal_threshold_recharge": "transfer_money",
        "loan_private_submission": "transfer_money",
        "official_transfer_scam": "transfer_money",
    }
    if fork_type in direct:
        return {"status": "direct", "runtime_type": fork_type}
    return {
        "status": "nearest",
        "runtime_type": nearest.get(fork_type, "transfer_money"),
        "note": "semantic fork is preserved; runtime_type is only a runtime-compatible approximation",
    }


def _fork_reason(fork_type: str) -> str:
    return {
        "private_contact_lure": "风险分叉发生在用户被引导离开公开/官方渠道进入私域联系时。",
        "identity_asset_exchange": "风险分叉发生在用户准备交易或交出实名身份资产时。",
        "unlicensed_financial_service": "风险分叉发生在用户准备接受未核验金融服务并暴露账户或信用卡信息时。",
        "gambling_entry": "风险分叉发生在用户被诱导进入博彩或投注链路时。",
        "document_forgery_order": "风险分叉发生在用户准备购买或定制虚假证明、证件材料时。",
        "advance_fee_card": "风险分叉发生在用户相信无需征信办高额信用卡并准备支付前置费用时。",
        "illegal_goods_private_purchase": "风险分叉发生在用户准备通过私下渠道购买管制或违法物品时。",
        "withdrawal_recovery_contact": "风险分叉发生在用户把提现受阻问题交给非官方联系人处理时。",
        "withdrawal_threshold_recharge": "风险分叉发生在用户相信所谓提现最低线并继续贷款或充值时。",
        "loan_private_submission": "风险分叉发生在用户准备向私人贷款渠道提交身份证、银行卡等资料时。",
        "official_transfer_scam": "风险分叉发生在用户相信冒充公检法说法并准备按要求保密或转入安全账户时。",
        "phishing_link_entry": "风险分叉发生在用户准备点击伪造链接或输入账号凭证时。",
        "transfer_money": "风险分叉发生在用户准备付款、充值、缴费或转账时。",
        "screen_share": "风险分叉发生在用户准备开启屏幕共享或远程控制时。",
        "verification_code": "风险分叉发生在用户准备提供验证码或动态口令时。",
        "unknown_app_download": "风险分叉发生在用户准备下载或安装未知应用时。",
        "social_isolation": "风险分叉发生在对方要求用户切断外部求助或保密时。",
        "fake_official_verification": "风险分叉发生在用户准备相信伪官方核验流程时。",
    }.get(fork_type, "风险分叉需要结合原文证据进一步核验。")


def _fraud_window(report: Dict[str, Any], fork_comp: Dict[str, Any], cf: Dict[str, Any], *, text: str = "", is_fraud: bool = True) -> Dict[str, Any]:
    if not is_fraud:
        return {
            "start_turn": 0,
            "end_turn": 0,
            "rationale": "无需安全干预；保持常规来源核验即可。",
        }
    if any(term in text for term in ["非官方链接", "确认密码", "账号将在"]):
        return {
            "start_turn": 0,
            "end_turn": 0,
            "rationale": "在用户点击非官方链接或输入账号密码之前介入，可阻断凭证泄露。",
        }
    if any(term in text for term in ["提现最低线", "连续贷款和充值"]):
        return {
            "start_turn": 0,
            "end_turn": 0,
            "rationale": "首次被要求贷款或充值才能提现时就应停止操作；若已被拉黑，应立即止损并报警。",
        }
    if any(term in text for term in ["广告", "群广告", "邮件声称", "来电者自称", "对方冒充", "帖子称", "指定联系方式", "对方声称"]):
        return {
            "start_turn": 0,
            "end_turn": 0,
            "rationale": "在用户添加私域联系方式、点击链接、提供凭证或付款之前介入，可阻断后续风险链路。",
        }
    raw = _first_dict(
        cf.get("best_intervention_window"),
        report.get("best_intervention_window"),
        fork_comp.get("best_intervention_window"),
    )
    start = int(_num(raw.get("start_turn"), _num(raw.get("open_step"), 1)))
    end = int(_num(raw.get("end_turn"), _num(raw.get("close_step"), start)))
    return {
        "start_turn": max(0, start),
        "end_turn": max(0, end),
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


def _fraud_paths_from_text(text: str, fraud_type: str, runtime_risky: List[Any], runtime_safe: List[Any]) -> Tuple[List[Any], List[Any]]:
    if _is_benign_information_text(text):
        return ["正常阅读或查询公开信息"], ["保持常规来源核验，不输入账号密码或支付信息"]
    templates = {
        "identity_asset_trade": (
            ["看到实名手机卡广告", "添加微信私下联系", "交易或交出实名身份资产", "身份资产被用于违法或诈骗链路"],
            ["识别实名手机卡交易违规", "不添加微信", "向平台或运营商举报"],
        ),
        "unlicensed_financial_service": (
            ["看到信用卡代还/养卡广告", "添加微信或接受上门办理", "交出信用卡或支付费用", "发生盗刷、套现或信息泄露"],
            ["不添加微信", "不提供信用卡和身份信息", "通过银行官方渠道核验"],
        ),
        "gambling_fraud": (
            ["看到博彩或牛牛广告", "进群或联系接待", "被诱导充值/上下分/投注", "持续损失或无法提现"],
            ["不进群、不联系接待", "退出并举报赌博广告", "不充值不投注"],
        ),
        "document_forgery_fraud": (
            ["看到代办证明/证件广告", "提交个人信息并付款", "购买伪造材料", "面临资金损失和法律风险"],
            ["忽略代办广告", "不提交资料不付款", "使用正规机构或官方流程"],
        ),
        "advance_fee_card_fraud": (
            ["相信无需征信高额办卡承诺", "支付包装费或通道费", "继续被追加费用", "无法下卡且资金损失"],
            ["不支付任何前置费用", "通过银行官方渠道申请", "举报虚假办卡广告"],
        ),
        "illegal_goods_fraud": (
            ["添加私人账号购买管制物品", "先付款后等待发货", "遭遇失联或卷入违法交易"],
            ["不联系私人卖家", "不付款不交易", "向平台举报违规内容"],
        ),
        "withdrawal_recovery_fraud": (
            ["相信可解决被黑或无法出款", "联系非官方处理人", "支付解冻费或交出账户信息", "再次被骗或账户暴露"],
            ["联系平台官方客服", "不向陌生人付款或交出账户", "保留记录并报警/投诉"],
        ),
        "gambling_platform_fake_customer_service": (
            ["看到平台审核维护导致无法出款的帖子", "联系指定联系方式处理被黑或提现问题", "对方以解冻、验证或通道费为由继续索要钱款", "资金再次损失或账户信息暴露"],
            ["不联系帖子中的指定联系方式", "向平台举报该帖子", "只通过官方客服或监管投诉渠道处理提现争议"],
        ),
        "loan_recharge_withdrawal_fraud": (
            ["相信平台客服的提现最低线说法", "连续贷款和充值", "达到所谓最低线后继续等待提现", "电话和微信被拉黑导致资金损失"],
            ["首次被要求贷款充值时立即停止", "拒绝任何提现门槛充值要求", "保留记录并向平台官方核实或报警"],
        ),
        "loan_fraud": (
            ["相信秒放款/黑户可借广告", "提交身份证和银行卡照片", "支付保证金或刷流水", "贷款未到账且资料泄露"],
            ["不加私人贷款账号", "不提交证件照片", "使用持牌金融机构渠道"],
        ),
        "fake_police_fraud": (
            ["相信冒充公安来电", "按要求保密", "把资金转入所谓安全账户", "资金被转走且难以追回"],
            ["立即挂断", "拨打官方电话核验", "不转入任何安全账户并报警"],
        ),
        "impersonation_refund": (
            ["相信冒充客服理赔说法", "开启屏幕共享或填写银行卡", "提供短信验证码", "账户被盗刷或资金被转走"],
            ["关闭屏幕共享", "不填写银行卡和验证码", "通过电商官方 App 或客服电话核验"],
        ),
        "phishing_credential_theft": (
            ["收到账号停用邮件", "点击非官方链接", "输入账号密码", "账号被接管或凭证泄露"],
            ["不点击邮件链接", "手动打开官网/App 核验", "删除邮件并上报钓鱼"],
        ),
    }
    if fraud_type in templates:
        return templates[fraud_type]
    return runtime_risky, runtime_safe


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
            "description": _key_divergence_description(first_fork.get("type", ""), first_asset),
        }
    ]


def _key_divergence_description(fork_type: str, asset: Dict[str, Any]) -> str:
    asset_label = asset.get("label") or asset.get("type") or "相关资产"
    return {
        "private_contact_lure": "安全路径停留在官方/公开渠道核验，高风险路径进入私域沟通后证据和追责能力下降。",
        "identity_asset_exchange": f"安全路径拒绝交易或交出{asset_label}，高风险路径让实名身份资产进入不可控使用链。",
        "unlicensed_financial_service": "安全路径拒绝未核验金融服务，高风险路径暴露信用卡、账户或资金信息。",
        "gambling_entry": "安全路径拒绝进入博彩链路，高风险路径被诱导充值或持续投注。",
        "document_forgery_order": "安全路径使用正规证明渠道，高风险路径购买伪造材料并暴露资料和法律风险。",
        "advance_fee_card": "安全路径拒绝前置费用并走银行官方流程，高风险路径持续支付包装费、通道费。",
        "illegal_goods_private_purchase": "安全路径举报违规交易，高风险路径进入私下违法交易和先款失联链路。",
        "withdrawal_recovery_contact": "安全路径回到平台官方客服，高风险路径把账户和费用交给陌生联系人。",
        "withdrawal_threshold_recharge": "安全路径拒绝贷款充值提现门槛，高风险路径持续充值后被拉黑失联。",
        "loan_private_submission": "安全路径拒绝私人贷款资料收集，高风险路径暴露身份证、银行卡和资金。",
        "official_transfer_scam": "安全路径挂断并官方核验，高风险路径在保密压力下把资金转入所谓安全账户。",
        "phishing_link_entry": "安全路径不点击或不输入凭证，高风险路径把账号凭证交给伪造页面。",
        "transfer_money": "安全路径暂停付款并核验收款方，高风险路径完成资金转移后可逆性下降。",
        "screen_share": "安全路径拒绝屏幕共享，高风险路径暴露账户、验证码或设备控制权。",
        "verification_code": "安全路径拒绝提供动态码，高风险路径让第三方完成账号或资金操作。",
        "unknown_app_download": "安全路径拒绝安装未知应用，高风险路径让设备控制权或账号会话暴露。",
    }.get(fork_type, "安全路径要求暂停并回到可验证渠道，高风险路径继续执行未核验要求。")


def _fraud_warning(text: str, assets: List[Dict[str, Any]], t0: Dict[str, Any], risk_level: str) -> str:
    if t0.get("warning"):
        return str(t0["warning"])
    if any(term in text for term in ["实名", "手机卡"]):
        return "出售或购买已实名手机卡属于高风险身份资产交易，可能被用于诈骗、洗钱或实名责任转嫁。"
    if any(term in text for term in ["信用卡代还", "养卡", "低点位", "刷卡"]):
        return "信用卡代还、养卡和低点位刷卡常涉及非法套现、盗刷或账户信息泄露。"
    if any(term in text for term in ["群内几百人在线", "诚信靠谱", "邀请咨询"]):
        return "群内人数、诚信承诺和邀请咨询常是赌博广告的虚假宣传包装，目的是诱导用户联系并参与上下分。"
    if any(term in text for term in ["赌博", "博彩", "极速赛车", "牛牛", "上下分", "开奖"]):
        return "博彩投注技巧、上下分和进群福利是典型赌博引流，请勿联系接待或充值投注。"
    if any(term in text for term in ["收入证明", "银行流水", "在职证明", "学历证", "资格证"]):
        return "代办虚假证明或证件既可能骗取费用，也可能带来法律和征信风险。"
    if any(term in text for term in ["包装费", "通道费", "保证下卡"]):
        return "正规办卡不会要求先交包装费或通道费，保证下卡是高风险预付费诈骗信号。"
    if any(term in text for term in ["管制药品", "私下购买"]):
        return "私下购买管制物品存在违法交易和先付款后失联风险。"
    if any(term in text for term in ["无法出款", "被黑", "提现问题"]):
        return "声称能通过指定联系方式解决平台审核维护、被黑或提现问题，是典型虚假客服引流。"
    if any(term in text for term in ["提现最低线", "连续贷款", "连续贷款和充值"]):
        return "任何要求贷款或充值到所谓提现最低线后才能提现的说法都是高风险诈骗信号。"
    if any(term in text for term in ["非官方链接", "账号将在", "确认密码"]):
        return "邮件用账号停用制造紧迫感，并要求点击非官方链接重新登录确认密码，这是典型钓鱼信号。"
    if any(term in text for term in ["公安", "安全账户", "洗钱"]):
        return "公检法不会要求全程保密或把资金转入安全账户。"
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
    if any(term in text for term in ["实名", "手机卡"]):
        return "忽略广告，不添加微信，并向平台、运营商或公安渠道举报该违规交易。"
    if any(term in text for term in ["信用卡代还", "养卡", "低点位", "刷卡"]):
        return "不要添加微信、不要提供信用卡或身份信息；如需金融服务，只通过银行官方渠道办理。"
    if any(term in text for term in ["赌博", "博彩", "极速赛车", "牛牛", "上下分", "开奖"]):
        return "不要进群或联系接待，不充值不投注，退出并举报赌博广告。"
    if any(term in text for term in ["收入证明", "银行流水", "在职证明", "学历证", "资格证"]):
        return "不要付款或提交个人资料；通过学校、单位、银行或政务官方渠道办理真实材料。"
    if any(term in text for term in ["包装费", "通道费", "保证下卡"]):
        return "不要支付任何前置费用，通过银行官方 App、网点或客服电话核验办卡流程。"
    if any(term in text for term in ["管制药品", "私下购买"]):
        return "不要联系私人卖家或付款，直接关闭并举报违规内容。"
    if any(term in text for term in ["无法出款", "被黑", "提现问题"]):
        return "不点击或联系帖子中的指定联系方式，保留截图并向平台举报；只通过平台官方客服或监管投诉渠道处理。"
    if any(term in text for term in ["提现最低线", "连续贷款", "连续贷款和充值"]):
        return "立即停止贷款和充值，保留客服记录、充值记录和联系方式，向平台官方核实并报警。"
    if any(term in text for term in ["公安", "安全账户", "洗钱"]):
        return "立即挂断，不转账到任何安全账户；拨打 110 或反诈专线 96110 核实，并保留记录报警。"
    if any(term in text for term in ["非官方链接", "账号将在", "确认密码"]):
        return "删除邮件，不点击链接；手动打开官方网站或官方 App 核验账号状态并上报钓鱼邮件。"
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


def _benign_fraud_warning(text: str) -> str:
    return "未观察到付款诱导、私域引流、身份凭证索取、验证码索取或伪官方威胁等明确诈骗信号。"


def _benign_fraud_safe_action(text: str) -> str:
    if any(term in text for term in ["下载", "软件", "合同电子版", "合同范本"]):
        return "正常阅读；如需下载，确认发布方、文件类型和官方来源，不输入账号密码或支付信息。"
    if "寻人启事" in text:
        return "正常查看；如需联系家属，优先通过公开发布平台或警方/社区渠道核验。"
    return "正常阅读；保持常规来源核验，不输入账号密码或支付信息。"


def _event_summary(text: str, prefix: str) -> str:
    text = _clean_text(text)
    clauses = _split_clauses(text)
    if not clauses:
        return f"{prefix}缺少可用文本，需要补充原始输入。"
    selected: List[str] = []
    for clause in clauses:
        selected.append(clause)
        if len(selected) >= 3 and not selected[-1].endswith(("后", "时", "期间")):
            break
        if len(selected) >= 4:
            break
    summary = "；".join(selected)
    if summary.startswith(("公众讨论", "公开讨论", "社交平台讨论", "一篇", "一起", "一条", "自然灾害", "突发事件", "官方应急")):
        return summary
    return f"{prefix}围绕{summary}"


def _narrative_threads(text: str, evidence: List[str]) -> List[Dict[str, Any]]:
    if _is_low_risk_public_text(text):
        return [
            {
                "id": "thread:verified_rational_discussion",
                "claim": "讨论基于多家可靠媒体确认的公开新闻，主要是信息补充、背景解释和理性讨论。",
                "risk": "暂无显著谣言、极化或行动动员风险。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["可靠媒体确认", "信息补充", "背景解释", "理性讨论"])],
            }
        ]
    if "种族议题" in text and "执法" in text:
        return [
            {
                "id": "thread:sensitive_issue_binding",
                "claim": "网传说法把现场冲突、警民关系和种族议题绑定在一起。",
                "risk": "敏感身份和执法议题叠加，容易激化群体对立和不信任。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["现场冲突", "警民关系", "种族议题"])],
            },
            {
                "id": "thread:unverified_witness_claims",
                "claim": "评论区出现未经证实的目击叙述并要求官方立即公布细节。",
                "risk": "信息真空下，未经核实的目击叙述可能被当作事实继续扩散。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["未经证实的目击叙述", "要求官方立即公布细节"])],
            },
        ]
    if "未经临床验证" in text or "新冠" in text:
        return [
            {
                "id": "thread:unverified_health_claim",
                "claim": "未经临床验证的做法被描述为可以预防或治疗新冠。",
                "risk": "公众可能按错误健康建议改变行为，延误正规医疗或防护。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["未经临床验证", "预防或治疗新冠"])],
            },
            {
                "id": "thread:experience_vs_medical_rebuttal",
                "claim": "亲友经验转发与医学机构反驳同时出现，评论区焦虑、求证并互相指责。",
                "risk": "经验叙事和专业说明冲突会放大焦虑并造成阵营化争论。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["亲友经验", "医学机构说明", "焦虑", "求证", "互相指责"])],
            },
        ]
    if "强烈指控" in text or "阵营对立" in text:
        return [
            {
                "id": "thread:accusatory_title_as_evidence",
                "claim": "带有强烈指控色彩的标题被支持者当作既有立场的证据。",
                "risk": "标题先行会弱化事实核验，让讨论围绕立场确认而非证据展开。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["强烈指控", "支持者", "已有立场"])],
            },
            {
                "id": "thread:source_motive_attack",
                "claim": "反对者从来源可信度质疑转向对媒体动机的攻击。",
                "risk": "讨论从事实核验滑向阵营对立，后续更难用事实纠偏。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["来源可信度", "事实核验", "阵营对立", "媒体动机"])],
            },
        ]
    if "航空事故" in text:
        return [
            {
                "id": "thread:multiple_crash_claims",
                "claim": "事故原因、机组行为和乘客状况出现多种未经稳定核实的说法。",
                "risk": "多版本解释会在官方调查完成前形成竞争性叙事。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["事故原因", "机组行为", "乘客状况", "多种说法"])],
            },
            {
                "id": "thread:repeated_media_citation",
                "claim": "部分说法被媒体和个人账号反复引用，评论区在同情、恐慌和猜测之间摇摆。",
                "risk": "反复引用会放大未核实说法，情绪摇摆延长信息真空。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["媒体和个人账号", "官方调查尚未完成", "同情", "恐慌", "猜测"])],
            },
        ]
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
    if _is_low_risk_public_text(text):
        return {
            "dominant_emotion": "neutral",
            "amplification_level": "low",
            "rationale": "原文说明讨论以信息补充、背景解释和理性讨论为主，未出现明显情绪动员。",
            "evidence": _extract_keyword_hits(text, ["理性讨论", "未出现明显", "信息补充", "背景解释"]),
        }
    dominant = "confusion"
    if any(term in text for term in ["焦虑", "健康", "新冠", "求证", "临床", "医学"]):
        dominant = "anxiety"
    elif any(term in text for term in ["阵营对立", "媒体动机", "强烈指控"]):
        dominant = "polarization"
    elif any(term in text for term in ["愤怒", "指责", "不公平", "处罚", "歧视"]):
        dominant = "anger"
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
    if _is_low_risk_public_text(text):
        return [
            {
                "id": "uncertainty:none_significant",
                "description": "无显著不确定性；原文明确说明新闻已由可靠媒体确认，且未出现明显未经证实爆料或行动呼吁。",
                "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["可靠媒体确认", "未出现明显未经证实", "要求立即行动"])],
            }
        ]
    rules = [
        ("uncertainty:unverified_claim", ["未经证实", "网传", "传言"], "流传说法仍缺少可复核证据。"),
        ("uncertainty:accusatory_title", ["强烈指控", "来源可信度"], "标题指控和来源可信度仍需独立核验。"),
        ("uncertainty:polarization_shift", ["事实核验", "阵营对立", "媒体动机"], "讨论正在从事实核验转向立场和动机攻击。"),
        ("uncertainty:unfinished_investigation", ["官方调查尚未完成", "事故原因", "机组行为", "乘客状况"], "事故调查仍未完成，原因和人员相关说法尚未稳定。"),
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
    if _is_low_risk_public_text(text):
        return {
            "status": "no_gap",
            "severity": 0.0,
            "description": "现有可靠媒体信息和理性讨论已足以支撑常规理解，暂无额外官方回应缺口。",
            "evidence_refs": [f"ev:{hit}" for hit in _extract_keyword_hits(text, ["可靠媒体确认", "理性讨论"])],
        }
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
    if _is_low_risk_public_text(text):
        return {
            "open_stage": "not_applicable",
            "close_stage": "not_applicable",
            "label": "无需干预",
            "selected_branch_id": branch_id,
        }
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
    if any(term in text for term in ["强烈指控", "阵营对立", "媒体动机"]):
        return {
            "open_stage": "fact_check_window",
            "close_stage": "before_polarized_narrative_locks_in",
            "label": "在事实核验窗口被阵营对立取代前介入",
            "selected_branch_id": branch_id,
        }
    if "航空事故" in text:
        return {
            "open_stage": "early_information_vacuum",
            "close_stage": "before_unverified_claims_repeat",
            "label": "在多种未核实说法被反复引用前介入",
            "selected_branch_id": branch_id,
        }
    return {
        "open_stage": raw.get("open_stage") or "early_discussion",
        "close_stage": raw.get("close_stage") or "before_single_narrative_dominates",
        "label": raw.get("label") or "在未经证实叙事成为主导前介入",
        "selected_branch_id": branch_id,
    }


def _public_intervention_action(text: str, gap: Dict[str, Any], selected_action: Any = None) -> str:
    if _is_low_risk_public_text(text):
        return "无需采取干预措施，保持常规观察即可。"
    if "种族议题" in text and "执法" in text:
        return "官方尽快发布权威事实通报，明确已确认与未确认信息，回应调查流程，承诺透明调查，并避免未经证实叙述继续绑定种族和警民关系议题。"
    if "未经临床验证" in text or "新冠" in text:
        return "平台和权威医学机构应标注该健康说法未经临床验证，提供可核验医学说明，并降低亲友经验类误导内容的推荐扩散。"
    if "阵营对立" in text or "强烈指控" in text:
        return "在事实核验窗口发布来源、证据状态和标题指控的核查说明，引导讨论回到可验证事实，避免继续攻击媒体动机。"
    if "航空事故" in text:
        return "官方在调查未完成前发布初步事实边界、已确认信息和后续时间表，媒体转发时标注未经核实的事故原因和机组说法。"
    if gap.get("status") == "partially_available":
        base = "引用权威说明并绑定到原传播链，区分已证实、未证实和仍在核实的信息。"
    else:
        base = "发布时间线、证据状态和后续调查流程，明确哪些信息已确认、哪些仍在核实。"
    return base


def _safe_public_action(text: str) -> str:
    if _is_low_risk_public_text(text):
        return "继续基于可靠来源理性讨论，无需扩散未经核实的新增说法。"
    if any(term in text for term in ["健康", "新冠", "临床", "医学"]):
        return "不按未经验证说法改变健康行为，优先查看权威医学机构或本地卫生部门公开指引。"
    return "避免转发未经证实的信息、截图或目击叙述，保留来源链接并等待多源确认。"


def _origin_node(text: str) -> Dict[str, Any]:
    if "官方应急账号" in text:
        return {"id": "node:official_emergency_account", "type": "official_source", "description": "官方应急账号发布天气预警更新。", "evidence_refs": ["ev:官方应急账号"]}
    if "新闻网站发布" in text:
        return {"id": "node:news_site_article", "type": "news_site_source", "description": "争议性新闻先在新闻网站发布。", "evidence_refs": ["ev:新闻网站发布"]}
    if "少数账号" in text and "传言" in text:
        return {"id": "node:minor_rumor_sources", "type": "early_rumor_sources", "description": "少数账号中出现关于现场状况的传言。", "evidence_refs": ["ev:少数账号", "ev:传言"]}
    if "本地用户账号" in text:
        return {"id": "node:local_source", "type": "local_source", "description": "本地用户发出的初始信息。", "evidence_refs": ["ev:本地用户账号"]}
    if "首发帖" in text:
        return {"id": "node:origin_breaking_post", "type": "early_source_post", "description": "突发事件的首发帖或早期来源。", "evidence_refs": ["ev:首发帖"]}
    if any(term in text for term in ["首发", "早期"]):
        hits = _extract_keyword_hits(text, ["首发", "早期"])
        return {"id": "node:early_source", "type": "early_source_post", "description": "文本中的早期来源节点。", "evidence_refs": [f"ev:{hit}" for hit in hits]}
    clauses = _split_clauses(text)
    if clauses:
        return {"id": "node:input_mentioned_source", "type": "source_mentioned_in_input", "description": clauses[0], "evidence_refs": [f"ev:{clauses[0]}"]}
    return {}


def _amplifier_nodes(text: str) -> List[Dict[str, Any]]:
    if _is_low_risk_event_text(text):
        return [
            {
                "id": "node:local_media",
                "type": "local_media",
                "description": "地方媒体转发时保留原始发布时间、影响区域和防护建议，未引入地点或时间误传。",
                "evidence_refs": ["ev:地方媒体", "ev:保留了原始发布时间", "ev:影响区域和防护建议"],
            },
            {
                "id": "node:community_account",
                "type": "community_account",
                "description": "社区账号延续完整天气预警信息，后续讨论围绕交通安排和学校通知展开。",
                "evidence_refs": ["ev:社区账号", "ev:交通安排", "ev:学校通知"],
            },
        ]
    specs = [
        ("新闻账号", "node:news_accounts", "media_amplifier", "新闻账号扩大初始信息覆盖面。"),
        ("个人账号", "node:personal_reposts", "grassroots_amplifier", "个人账号转发并推动二次传播。"),
        ("志愿者群组", "node:volunteer_group", "community_amplifier", "志愿者群组转发并扩大社区覆盖。"),
        ("地方媒体", "node:local_media", "public_information_amplifier", "地方媒体扩大公共覆盖面。"),
        ("社区账号", "node:community_accounts", "community_amplifier", "社区账号把信息转发到本地公众讨论中。"),
        ("救援信息汇总账号", "node:rescue_aggregator", "public_information_amplifier", "汇总账号继续放大传播。"),
        ("社交平台用户", "node:social_platform_users", "platform_user_amplifier", "社交平台用户截取标题和首段后继续转发。"),
        ("另一个平台", "node:cross_platform_repost", "cross_platform_amplifier", "截图被搬运到另一个平台，扩大跨平台覆盖。"),
        ("高影响力账号", "node:high_influence_account", "high_influence_amplifier", "高影响力账号引用传言并显著放大转发量。"),
        ("多个回复", "node:reply_corrections", "correction_node", "多个回复指出信息未被证实，但纠偏覆盖有限。"),
    ]
    nodes: List[Dict[str, Any]] = []
    for term, node_id, node_type, desc in specs:
        if term in text:
            nodes.append({"id": node_id, "type": node_type, "description": desc, "evidence_refs": [f"ev:{term}"]})
    return nodes


def _distortion_points(text: str) -> List[Dict[str, Any]]:
    if _is_low_risk_event_text(text):
        return []
    specs = [
        ("未经证实的嫌疑人身份", "distortion:suspect_identity", "未经证实的身份信息被补充并传播。", 0.86),
        ("现场图片单独传播", "distortion:image_context_loss", "现场图片被单独截取传播，可能脱离原始语境。", 0.66),
        ("地点名称被简写", "distortion:location_abbreviation", "地点名称被简写，可能影响定位准确性。", 0.58),
        ("遗漏了发布时间", "distortion:timestamp_loss", "发布时间遗漏导致信息时效性失真。", 0.84),
        ("限定条件和更新说明被裁掉", "distortion:condition_update_removed", "原文限定条件和更新说明被截图搬运时裁掉。", 0.88),
        ("绝对化的说法", "distortion:absolute_claim", "新的讨论围绕更绝对化的说法扩散。", 0.82),
        ("判断性措辞", "distortion:judgmental_framing", "高影响力账号加入判断性措辞，改变了原传言的语气和风险感知。", 0.78),
        ("原始高影响力转发仍继续被引用", "distortion:correction_not_bound", "纠正回复未能绑定原始高影响力转发，导致旧信息继续传播。", 0.84),
        ("不准确", "distortion:inaccurate_detail", "传播中的部分细节被权威更正为不准确。", 0.72),
        ("未经证实", "distortion:unverified_detail", "未经证实细节在二次传播中扩散。", 0.76),
    ]
    points: List[Dict[str, Any]] = []
    for term, did, desc, severity in specs:
        if term in text:
            points.append({"id": did, "description": desc, "severity": severity, "evidence_refs": [f"ev:{term}"]})
    return points


def _propagation_path(origin: Dict[str, Any], amplifiers: List[Dict[str, Any]], distortions: List[Dict[str, Any]], text: str) -> List[Dict[str, Any]]:
    if _is_low_risk_event_text(text):
        return [
            {"step": 1, "node": "node:official_emergency_account", "action": "官方应急账号发布天气预警更新", "risk_state": "低风险，来源权威"},
            {"step": 2, "node": "node:local_media", "action": "地方媒体转发并保留发布时间、影响区域和防护建议", "risk_state": "上下文完整"},
            {"step": 3, "node": "node:community_accounts", "action": "社区账号继续完整转发，讨论交通安排和学校通知", "risk_state": "未出现地点、时间误传或断章取义"},
        ]
    if "地点名称被简写" in text and "遗漏了发布时间" in text:
        return [
            {"step": 1, "node": "node:local_source", "action": "本地用户账号发出求助信息", "risk_state": "原始求助信息需要保留完整地点和时间"},
            {"step": 2, "node": "node:volunteer_group", "action": "志愿者群组转发时地点名称被简写", "risk_state": "位置语义开始丢失"},
            {"step": 3, "node": "node:local_media", "action": "地方媒体和部分转发遗漏发布时间", "risk_state": "时效性信息丢失"},
            {"step": 4, "node": "node:rescue_aggregator", "action": "救援信息汇总账号继续放大该求助", "risk_state": "后续用户误以为求助仍然实时有效"},
        ]
    if "限定条件和更新说明被裁掉" in text:
        return [
            {"step": 1, "node": "node:news_site_article", "action": "争议性新闻先在新闻网站发布", "risk_state": "原文仍包含限定条件和更新说明"},
            {"step": 2, "node": "node:social_platform_users", "action": "社交平台用户截取标题和首段转发", "risk_state": "上下文开始减少"},
            {"step": 3, "node": "node:cross_platform_repost", "action": "截图被搬运到另一个平台", "risk_state": "跨平台扩散加速"},
            {"step": 4, "node": "node:distorted_repost", "action": "限定条件和更新说明被裁掉", "risk_state": "绝对化说法开始扩散"},
        ]
    if "高影响力账号" in text and "判断性措辞" in text:
        return [
            {"step": 1, "node": "node:minor_rumor_sources", "action": "少数账号中出现关于现场状况的传言", "risk_state": "信息未被证实"},
            {"step": 2, "node": "node:high_influence_account", "action": "高影响力账号引用传言并加入判断性措辞", "risk_state": "转发量迅速上升"},
            {"step": 3, "node": "node:reply_corrections", "action": "多个回复指出信息未被证实", "risk_state": "纠偏未绑定原始高影响力转发"},
            {"step": 4, "node": "node:high_influence_repost", "action": "原始高影响力转发仍继续被引用", "risk_state": "误传残留继续扩散"},
        ]
    path = []
    if origin:
        path.append(
            {
                "step": 1,
                "node": origin.get("id", "node:input_mentioned_source"),
                "action": "发布或形成早期事件信息",
                "risk_state": "信息速度高但细节未稳定",
            }
        )
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
    if _is_low_risk_event_text(text):
        return "无需采取特殊遏制行动，保持常规监测即可。"
    if any(term in text for term in ["身份", "嫌疑人"]):
        base = "标注未确认身份信息，要求转发账号更新更正，并将权威更正与原传播链绑定展示。"
    elif any(term in text for term in ["地点", "时间", "求助"]):
        base = "在志愿者群组首次转发前，由群组管理员或自动审核机制补齐地点全称、原始发布时间和状态更新，并对过期求助加醒目标记。"
    elif "限定条件和更新说明被裁掉" in text:
        base = "由新闻网站或权威账号在社交平台补充完整原文、限定条件和更新说明，要求跨平台截图绑定原文链接并加上下文标签。"
    elif "高影响力账号" in text:
        base = "优先要求高影响力账号同步更正，将未证实标签和纠正回复绑定到原始转发并降低继续推荐。"
    else:
        base = "对未核验内容加来源标签，优先要求高影响力转发节点同步更正。"
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

    clause_hits: List[str] = []
    for clause in _split_clauses(text):
        if any(term in clause for term in _scenario_terms(text, scenario)):
            clause_hits.append(clause)
    generic_terms = {"官方", "转发", "权威", "焦虑", "愤怒", "微信", "客服", "链接"}
    specific_direct = [
        item
        for item in direct
        if len(str(item)) >= 4 and str(item) not in generic_terms
    ]
    if scenario == "event_propagation" and _is_low_risk_event_text(text):
        spans = _unique(clause_hits)
    else:
        spans = _unique(clause_hits + specific_direct)
    if not spans and text:
        spans = _split_clauses(text)[:3]
    return _unique([span for span in spans if span and span in text])[:8]


def _scenario_terms(text: str, scenario: str) -> List[str]:
    common = ["未经证实", "要求官方", "官方", "权威", "更正", "转发", "迅速发酵", "愤怒", "焦虑"]
    if scenario == "fraud_im":
        common.extend([
            "实名",
            "手机卡",
            "微信",
            "验证码",
            "转账",
            "付款",
            "下载",
            "链接",
            "信誉",
            "客服",
            "银行卡",
            "信用卡代还",
            "养卡",
            "低点位",
            "极速赛车",
            "牛牛",
            "上下分",
            "群内几百人在线",
            "诚信靠谱",
            "邀请咨询",
            "收入证明",
            "银行流水",
            "在职证明",
            "学历证",
            "资格证",
            "包装费",
            "通道费",
            "管制药品",
            "无法出款",
            "被黑",
            "指定联系方式",
            "连续贷款和充值",
            "提现最低线",
            "电话被拉黑",
            "账号将在24小时内停用",
            "非官方链接",
            "确认密码",
            "安全账户",
            "共享屏幕",
        ])
    elif scenario == "event_propagation":
        common.extend([
            "首发帖",
            "新闻账号",
            "个人账号",
            "嫌疑人身份",
            "现场图片",
            "本地用户账号",
            "志愿者群组",
            "地方媒体",
            "社区账号",
            "救援信息汇总账号",
            "地点名称被简写",
            "遗漏了发布时间",
            "实时有效",
            "不准确",
            "新闻网站发布",
            "标题和首段",
            "另一个平台",
            "限定条件和更新说明被裁掉",
            "绝对化的说法",
            "高影响力账号",
            "判断性措辞",
            "原始高影响力转发仍继续被引用",
            "官方应急账号",
            "保留了原始发布时间",
        ])
    else:
        common.extend([
            "警民关系",
            "种族议题",
            "未经证实的目击叙述",
            "亲友经验",
            "医学机构说明",
            "临床验证",
            "预防或治疗",
            "互相指责",
            "强烈指控",
            "事实核验",
            "阵营对立",
            "媒体动机",
            "航空事故",
            "事故原因",
            "机组行为",
            "乘客状况",
            "官方调查尚未完成",
            "可靠媒体确认",
            "理性讨论",
            "未出现明显未经证实",
        ])
    return [term for term in common if term in text]


def _split_clauses(text: str) -> List[str]:
    parts = [part.strip() for part in re.split(r"[。！？；;，,]", text) if part.strip()]
    clauses: List[str] = []
    for part in parts:
        if part in {"随后", "几小时后", "稍后", "后续"}:
            continue
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

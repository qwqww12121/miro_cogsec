import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark"

SCENARIOS = {
    "fraud_im": {
        "gold": BENCHMARK_ROOT / "data" / "cogsec_v0.1.jsonl",
        "llm": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "fraud_im_llm_baseline_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_fraud_im_after_adapter_v0.1.jsonl",
    },
    "public_opinion": {
        "gold": BENCHMARK_ROOT / "data" / "public_opinion_v0.1.jsonl",
        "llm": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "public_opinion_llm_baseline_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_public_opinion_after_adapter_v0.1.jsonl",
    },
    "event_propagation": {
        "gold": BENCHMARK_ROOT / "data" / "event_propagation_v0.1.jsonl",
        "llm": BENCHMARK_ROOT / "outputs" / "llm_baseline" / "event_propagation_llm_baseline_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_event_propagation_after_adapter_v0.1.jsonl",
    },
}

DEFAULT_OUTPUT = BENCHMARK_ROOT / "outputs" / "closed_model_judge" / "judge_requests_v0.1.jsonl"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} invalid JSON: {exc}") from exc
    return rows


def by_id(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row.get("id")): row for row in rows if row.get("id")}


def prediction_from(row: Dict[str, Any]) -> Dict[str, Any]:
    prediction = row.get("benchmark_prediction")
    if isinstance(prediction, dict) and prediction:
        return prediction
    prediction = row.get("prediction")
    if isinstance(prediction, dict):
        return prediction
    return {}


def _fraud_im_llm_text(bp: Dict[str, Any]) -> str:
    parts: List[str] = []
    is_fraud = bp.get("is_fraud", False)
    fraud_type = _readable_fraud_type(bp.get("fraud_type", ""))
    risk_level = _risk_label_text(bp.get("risk_level", ""))
    attack_stage = bp.get("attack_stage", "")
    if is_fraud:
        parts.append(f"结论：检测到{fraud_type or '疑似'}诈骗行为。风险等级：{risk_level}。当前阶段：{attack_stage or '初期接触'}。")
    else:
        parts.append(f"结论：当前场景风险等级 {risk_level or 'LOW'}，暂未确认诈骗行为。")
    fps = bp.get("fork_points", [])
    if fps:
        lines = []
        for fp in fps[:3]:
            if isinstance(fp, dict):
                spans = fp.get("evidence_spans", [])
                ev = "、".join(spans[:3]) if spans else ""
                lines.append(f"- [{fp.get('type','')}] {fp.get('reason','')}" + (f"（原文：{ev}）" if ev else ""))
        if lines:
            parts.append("关键分叉点：\n" + "\n".join(lines))
    ev_spans = bp.get("evidence_spans", [])
    if ev_spans:
        parts.append("原文证据片段：" + "、".join(f"「{s}」" for s in ev_spans[:6]))
    iw = bp.get("intervention_window", {})
    if isinstance(iw, dict) and iw:
        parts.append(f"干预窗口：步骤 {iw.get('start_turn','?')}–{iw.get('end_turn','?')}。{iw.get('rationale','')}")
    warn = bp.get("expected_warning", "")
    safe_act = bp.get("expected_safe_action", "")
    if warn:
        parts.append(f"预警提示：{warn}")
    if safe_act:
        parts.append(f"安全操作建议：{safe_act}")
    cf = bp.get("counterfactual_paths", {})
    if isinstance(cf, dict):
        hrp = cf.get("high_risk_path", [])
        sp = cf.get("safe_path", [])
        if hrp:
            parts.append("高风险路径：" + " → ".join(str(s) for s in hrp[:4]))
        if sp:
            parts.append("安全路径：" + " → ".join(str(s) for s in sp[:4]))
    return "\n\n".join(parts)


def _fraud_im_miro_text(bp: Dict[str, Any], ca: Dict[str, Any]) -> str:
    parts: List[str] = []
    is_fraud = bp.get("is_fraud", False)
    fraud_type = _readable_fraud_type(bp.get("fraud_type", ""))
    risk_level = _risk_label_text(bp.get("risk_level", ""))
    attack_stage = bp.get("attack_stage", "")
    if is_fraud:
        parts.append(f"结论：检测到{fraud_type or '疑似'}诈骗行为。风险等级：{risk_level}。当前阶段：{attack_stage or '初期接触'}。")
    else:
        parts.append(f"结论：当前场景风险等级 {risk_level or 'LOW'}，暂未确认诈骗行为。")

    fps = bp.get("fork_points", [])
    if fps:
        lines = []
        for fp in fps[:3]:
            if isinstance(fp, dict):
                refs = fp.get("evidence_refs", [])
                evidence = "、".join(str(ref).replace("ev:", "") for ref in refs[:3])
                line = f"- [{_readable_fork_type(fp.get('type',''))}] {fp.get('reason','')}"
                if evidence:
                    line += f"（原文：{evidence}）"
                lines.append(line)
        if lines:
            parts.append("关键分叉点：\n" + "\n".join(lines))

    ev_spans = bp.get("evidence_spans", [])
    if ev_spans:
        parts.append("原文证据片段：" + "、".join(f"「{s}」" for s in ev_spans[:6]))
    iw = bp.get("intervention_window", {})
    if isinstance(iw, dict) and iw:
        parts.append(f"干预窗口：步骤 {iw.get('start_turn','?')}–{iw.get('end_turn','?')}。{iw.get('rationale','')}")
    warning = bp.get("expected_warning", "")
    safe_action = bp.get("expected_safe_action", "")
    if warning:
        parts.append(f"预警提示：{warning}")
    if safe_action:
        parts.append(f"安全操作建议：{safe_action}")
    direct_actions = _fraud_direct_actions_text(bp)
    if direct_actions:
        parts.append(direct_actions)
    cf = bp.get("counterfactual_paths", {})
    if isinstance(cf, dict):
        risky = cf.get("risky_path") or cf.get("high_risk_path") or []
        safe = cf.get("safe_path") or []
        if risky:
            parts.append("高风险路径：" + " → ".join(_path_step_text(step) for step in risky[:4]))
        if safe:
            parts.append("安全路径：" + " → ".join(_path_step_text(step) for step in safe[:4]))
    if is_fraud:
        parts.append(_fraud_mechanism_text(bp))
    return "\n\n".join(parts)


def _path_step_text(step: Any) -> str:
    if isinstance(step, dict):
        return str(step.get("action") or step.get("risk_state") or step.get("stage") or step)
    return str(step)


def _risk_label_text(value: Any) -> str:
    mapping = {
        "none": "无风险",
        "low": "低",
        "medium": "中",
        "high": "高",
        "critical": "极高",
    }
    text = str(value or "")
    return mapping.get(text.lower(), text)


def _readable_fraud_type(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return text
    return "语义识别的诈骗风险"


def _readable_fork_type(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if any("\u4e00" <= ch <= "\u9fff" for ch in text):
        return text
    if "fork" in text.lower() or "_" in text:
        return "关键决策分叉"
    return text


def _fraud_mechanism_text(bp: Dict[str, Any]) -> str:
    fps = [fp for fp in bp.get("fork_points", []) if isinstance(fp, dict)]
    assets = [a for a in bp.get("asset_targets", []) if isinstance(a, dict)]
    asset_text = "、".join(str(a.get("label") or a.get("type")) for a in assets[:3] if a.get("label") or a.get("type"))
    fork_text = fps[0].get("reason", "") if fps else ""
    if asset_text and fork_text:
        return f"机制解释：风险集中在“{fork_text}”这个分叉点；一旦用户继续配合，{asset_text}会从可核验状态转入暴露状态，安全路径则要求在提交资料、资金或账号权限前暂停并改走官方核验。"
    if fork_text:
        return f"机制解释：关键风险不是单个词，而是用户在“{fork_text}”处从观察转向配合；最佳防线是在执行前切断该分支。"
    return "机制解释：该场景的高危分支来自未核验对象推动用户继续配合，安全分支来自暂停、核验和举报。"


def _fraud_direct_actions_text(bp: Dict[str, Any]) -> str:
    forks = [item for item in bp.get("fork_points", []) if isinstance(item, dict)]
    lines: List[str] = []
    if forks:
        fork = forks[0]
        unsafe = _clean_phrase(fork.get("expected_branch_a") or fork.get("unsafe_branch") or "")
        safe = _clean_phrase(fork.get("expected_branch_b") or fork.get("safe_branch") or "")
        reason = _clean_phrase(fork.get("reason") or "")
        if reason:
            lines.append(f"- 最早阻断点：在“{reason}”之前暂停，不进入对方设计的下一步。")
        if unsafe:
            lines.append(f"- 不执行高风险分支：{unsafe}。")
        if safe:
            lines.append(f"- 改走安全分支：{safe}。")
    assets = [item for item in bp.get("asset_targets", []) if isinstance(item, dict)]
    asset_text = "、".join(str(item.get("label") or item.get("type")) for item in assets[:3] if item.get("label") or item.get("type"))
    if asset_text:
        lines.append(f"- 在{asset_text}被提交、转移或授权前，通过官方渠道核验并保留证据。")
    if str(bp.get("risk_level") or "").lower() in {"high", "critical"}:
        lines.append("- 如果已经转账、泄露身份信息或授权账号，立即联系平台/银行止付，并拨打 96110 或当地反诈渠道。")
    return "直接安全动作：\n" + "\n".join(lines) if lines else ""


def _emotion_label_text(value: Any) -> str:
    mapping = {
        "neutral": "中性",
        "anger": "愤怒",
        "anxiety": "焦虑",
        "fear": "恐慌",
        "confusion": "困惑",
        "polarization": "对立",
    }
    text = str(value or "")
    return mapping.get(text.lower(), text)


def _amplification_label_text(value: Any) -> str:
    mapping = {
        "low": "低",
        "medium": "中",
        "high": "高",
        "critical": "极高",
    }
    text = str(value or "")
    return mapping.get(text.lower(), text)


def _propagation_text(bp: Dict[str, Any], ca: Dict[str, Any], scenario: str) -> str:
    """Shared builder for event_propagation and public_opinion (both LLM and Miro)."""
    parts: List[str] = []
    event_summary = bp.get("event_summary", "")
    if event_summary:
        parts.append(f"事件概述：{event_summary}")

    if scenario == "event_propagation":
        risk_label = bp.get("coverage_risk", "")
        if risk_label:
            risk_context = _event_frame_risk_context(ca)
            parts.append(f"传播风险：{_risk_label_text(risk_label)}" + (f"。{risk_context}" if risk_context else ""))
        origin = bp.get("origin_node", {})
        if isinstance(origin, dict) and origin:
            parts.append(f"传播起点：{origin.get('description','')}")
        amps = bp.get("amplifier_nodes", [])
        if amps:
            lines = [f"- {a.get('description','')}" for a in amps[:3] if isinstance(a, dict)]
            if lines:
                parts.append("放大节点：\n" + "\n".join(lines))
        problem_text = _event_frame_problem_text(ca)
        if problem_text:
            parts.append(problem_text)
        path = bp.get("propagation_path", [])
        if path:
            steps = [
                f"{s.get('step', i+1)}. {s.get('action','')}（{s.get('risk_state','')}）"
                for i, s in enumerate(path[:5]) if isinstance(s, dict)
            ]
            if steps:
                parts.append("传播路径：\n" + "\n".join(steps))
        dp = bp.get("distortion_points", [])
        if dp:
            lines = []
            for d in dp[:3]:
                if isinstance(d, dict):
                    spans = d.get("evidence_spans", [])
                    ev = "、".join(f"「{s}」" for s in spans[:3]) if spans else ""
                    lines.append(f"- {d.get('description','')}（严重度 {d.get('severity','')}）" + (f" 原文：{ev}" if ev else ""))
            lines.extend(_event_frame_correction_distortion_lines(ca))
            if lines:
                parts.append("失真点：\n" + "\n".join(lines))
        targeted_actions = _event_frame_targeted_actions(ca)
        if targeted_actions:
            parts.append(targeted_actions)
        correction_text = _event_frame_correction_text(ca)
        if correction_text:
            parts.append(correction_text)
        ev_spans = bp.get("evidence_spans", [])
        if ev_spans:
            parts.append("原文证据片段：" + "、".join(f"「{s}」" for s in ev_spans[:6]))
        cw = bp.get("containment_window", {})
        if isinstance(cw, dict) and cw:
            parts.append(f"遏制窗口：{cw.get('label','')}（步骤 {cw.get('open_step','?')}–{cw.get('close_step','?')}）")
        action = _event_frame_expected_action(ca) or bp.get("expected_containment_action", "")
        if action:
            parts.append(f"建议遏制行动：{action}")
        parts.append(_event_execution_steps(bp))
        frame_mechanism = _frame_mechanism_text(ca, "传播语义机制")
        if frame_mechanism:
            parts.append(frame_mechanism)
        parts.append(_event_mechanism_text(bp))

    else:  # public_opinion
        risk_label = bp.get("propagation_risk_level", "")
        if risk_label:
            parts.append(f"传播风险等级：{_risk_label_text(risk_label)}")
        es = bp.get("emotion_signal", {})
        if isinstance(es, dict) and es:
            parts.append(f"情绪信号：主情绪={_emotion_label_text(es.get('dominant_emotion',''))}，放大={_amplification_label_text(es.get('amplification_level',''))}。{es.get('rationale','')}")
        nt = bp.get("narrative_threads", [])
        if nt:
            lines = [f"- {t.get('claim','')}（风险：{t.get('risk','')}）" for t in nt[:3] if isinstance(t, dict)]
            if lines:
                parts.append("叙事线程：\n" + "\n".join(lines))
        stance_text = _public_frame_stance_text(ca)
        if stance_text:
            parts.append(stance_text)
        up = bp.get("uncertainty_points", [])
        if up:
            lines = [f"- {u.get('description','')}" for u in up[:3] if isinstance(u, dict)]
            if lines:
                parts.append("不确定性节点：\n" + "\n".join(lines))
        org = bp.get("official_response_gap", {})
        if isinstance(org, dict) and org:
            parts.append(f"官方回应缺口：{org.get('description','')}（严重度 {org.get('severity','')}）")
        authority_text = _public_frame_authority_text(ca)
        if authority_text:
            parts.append(authority_text)
        ev_spans = bp.get("evidence_spans", [])
        if ev_spans:
            parts.append("原文证据片段：" + "、".join(f"「{s}」" for s in ev_spans[:6]))
        biw = bp.get("best_intervention_window", {})
        if isinstance(biw, dict) and biw:
            parts.append(f"最佳干预窗口：{biw.get('label','')}（{biw.get('open_stage','')} → {biw.get('close_stage','')}）")
        action = _public_frame_expected_action(ca) or bp.get("expected_intervention_action", "")
        safe = bp.get("expected_safe_public_action", "")
        if action:
            parts.append(f"干预行动：{action}")
        if safe:
            parts.append(f"公众安全行动：{safe}")
        actor_plan = _public_frame_actor_plan_text(ca)
        if actor_plan:
            parts.append(actor_plan)
        stance_actions = _public_frame_stance_action_text(ca)
        if stance_actions:
            parts.append(stance_actions)
        parts.append(_public_execution_steps(bp))
        frame_mechanism = _frame_mechanism_text(ca, "语义机制")
        if frame_mechanism:
            parts.append(frame_mechanism)
        parts.append(_public_mechanism_text(bp))

    return "\n\n".join(parts)


def _public_event_frame_from(ca: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(ca, dict):
        return {}
    frame = ca.get("public_event_frame")
    if isinstance(frame, dict) and (frame.get("available") or frame.get("scenario")):
        return frame
    return {}


def _span_suffix(item: Dict[str, Any], limit: int = 2) -> str:
    spans = item.get("evidence_spans", []) if isinstance(item, dict) else []
    if not isinstance(spans, list):
        return ""
    cleaned = [str(span).strip() for span in spans if str(span).strip()]
    if not cleaned:
        return ""
    return "（原文：" + "、".join(f"「{span}」" for span in cleaned[:limit]) + "）"


def _frame_mechanism_text(ca: Dict[str, Any], label: str) -> str:
    frame = _public_event_frame_from(ca)
    summary = str(frame.get("mechanism_summary") or "").strip()
    if not summary:
        return ""
    return f"{label}：{summary}"


def _public_frame_stance_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    stances = frame.get("stance_dynamics", [])
    if not isinstance(stances, list):
        return ""
    lines: List[str] = []
    for item in stances[:3]:
        if not isinstance(item, dict):
            continue
        group = str(item.get("group") or "传播参与者").strip()
        interpretation = str(item.get("interpretation") or "").strip()
        reaction = str(item.get("reaction") or "").strip()
        details = []
        if interpretation:
            details.append(interpretation)
        if reaction:
            details.append(f"反应：{reaction}")
        if details:
            lines.append(f"- {group}：" + "；".join(details) + _span_suffix(item))
    return "立场动态：\n" + "\n".join(lines) if lines else ""


def _public_frame_stance_risk_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    stances = frame.get("stance_dynamics", [])
    if not isinstance(stances, list):
        return ""
    lines: List[str] = []
    for item in stances[:3]:
        if not isinstance(item, dict):
            continue
        group = str(item.get("group") or "传播参与者").strip()
        interpretation = _clean_phrase(item.get("interpretation") or "相关判断")
        reaction = _clean_phrase(item.get("reaction") or "相关传播行为")
        lines.append(
            f"- {group}风险：把“{interpretation}”当作传播依据，并通过“{reaction}”推动讨论偏离事实核验。"
            + _span_suffix(item)
        )
    return "具体风险定位：\n" + "\n".join(lines) if lines else ""


def _public_frame_authority_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    gap = frame.get("authority_gap", {})
    if not isinstance(gap, dict) or not gap:
        return ""
    status = _official_gap_status_text(gap.get("status"))
    severity = gap.get("severity", "")
    missing = str(gap.get("missing_response") or gap.get("description") or "").strip()
    recommended = str(gap.get("recommended_response") or "").strip()
    details = []
    if missing:
        details.append(f"缺口：{missing}")
    if recommended:
        details.append(f"建议回应：{recommended}")
    suffix = "；".join(details)
    if suffix:
        suffix = "。" + suffix
    return f"权威回应校准：{status}（严重度 {severity}）{suffix}" + _span_suffix(gap)


def _public_frame_actor_plan_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    plan = frame.get("intervention_plan", {})
    lines: List[str] = []
    if isinstance(plan, dict):
        actions = plan.get("actor_actions", [])
        if isinstance(actions, list):
            for item in actions[:4]:
                if not isinstance(item, dict):
                    continue
                actor = _actor_label(item.get("actor") or "执行方")
                target = str(item.get("target_surface") or "传播界面").strip()
                action = str(item.get("action") or "").strip()
                effect = str(item.get("expected_effect") or "").strip()
                if not action:
                    continue
                line = f"- {actor} 在{target}：{action}"
                if effect:
                    line += f"；预期效果：{effect}"
                lines.append(line + _span_suffix(item))
    gap = frame.get("authority_gap", {})
    if isinstance(gap, dict):
        recommended = str(gap.get("recommended_response") or "").strip()
        if recommended:
            lines.append(f"- official 在官方账号、发布会或权威信息入口：{recommended}" + _span_suffix(gap))
    return "分角色干预计划：\n" + "\n".join(lines) if lines else ""


def _public_frame_expected_action(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    pieces: List[str] = []
    plan = frame.get("intervention_plan", {})
    if isinstance(plan, dict):
        actions = plan.get("actor_actions", [])
        if isinstance(actions, list):
            for item in actions[:2]:
                if not isinstance(item, dict):
                    continue
                actor = _actor_label(item.get("actor") or "执行方")
                target = str(item.get("target_surface") or "传播界面").strip()
                action = _clean_phrase(item.get("action") or "")
                if action:
                    pieces.append(f"{actor}在{target}：{action}")
    gap = frame.get("authority_gap", {})
    if isinstance(gap, dict):
        recommended = str(gap.get("recommended_response") or "").strip().rstrip("。")
        if recommended:
            pieces.append(f"权威主体：{recommended}")
    if not pieces:
        return ""
    return "；".join(pieces) + "。"


def _public_frame_stance_action_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    stances = frame.get("stance_dynamics", [])
    if not isinstance(stances, list):
        return ""
    lines: List[str] = []
    for item in stances[:3]:
        if not isinstance(item, dict):
            continue
        group = str(item.get("group") or "传播参与者").strip()
        interpretation = _clean_phrase(item.get("interpretation") or "相关判断")
        reaction = _clean_phrase(item.get("reaction") or "相关传播行为")
        lines.append(
            f"- 面向{group}：把“{interpretation}”拆成可核验命题，在其“{reaction}”的转发、热评或二创入口旁标注证据状态，并引导回到来源核验而不是立场动员。"
            + _span_suffix(item)
        )
    return "阵营/立场治理动作：\n" + "\n".join(lines) if lines else ""


def _actor_label(value: Any) -> str:
    mapping = {
        "platform": "平台",
        "official": "权威主体",
        "public": "公众",
        "media": "媒体",
    }
    text = str(value or "").strip()
    return mapping.get(text.lower(), text or "执行方")


def _clean_phrase(value: Any) -> str:
    return str(value or "").strip().rstrip("。；;，, ")


def _event_frame_correction_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    correction = frame.get("correction_status", {})
    if not isinstance(correction, dict) or not correction:
        return ""
    has_correction = correction.get("has_correction")
    state = "已有纠偏信号" if has_correction else "未见有效纠偏"
    binding = str(correction.get("binding_problem") or "").strip()
    text = f"纠偏绑定状态：{state}"
    if binding:
        text += f"。绑定问题：{binding}"
    return text + _span_suffix(correction)


def _event_frame_problem_text(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    lines: List[str] = []
    amplifiers = frame.get("amplifiers", [])
    if isinstance(amplifiers, list):
        for item in amplifiers[:2]:
            if not isinstance(item, dict):
                continue
            desc = _clean_phrase(item.get("description") or item.get("node") or "")
            if desc:
                lines.append(f"- 放大转折：{desc}" + _span_suffix(item))
    distortions = frame.get("distortion_points", [])
    if isinstance(distortions, list):
        for item in distortions[:2]:
            if not isinstance(item, dict):
                continue
            desc = _clean_phrase(item.get("description") or "传播失真")
            dtype = _distortion_type_text(item.get("type"))
            lines.append(f"- 失真机制：{desc}（类型：{dtype}）" + _span_suffix(item))
    correction = frame.get("correction_status", {})
    if isinstance(correction, dict):
        binding = _clean_phrase(correction.get("binding_problem") or "")
        if binding and "无纠偏" not in binding:
            lines.append(f"- 纠偏失败：{binding}" + _span_suffix(correction))
    return "传播问题定位：\n" + "\n".join(lines) if lines else ""


def _event_frame_risk_context(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    distortions = frame.get("distortion_points", [])
    distortion_items = [item for item in distortions if isinstance(item, dict)] if isinstance(distortions, list) else []
    correction = frame.get("correction_status", {})
    pieces: List[str] = []
    if distortion_items:
        max_severity = max(_safe_float(item.get("severity")) for item in distortion_items)
        types = "、".join(_distortion_type_text(item.get("type")) for item in distortion_items[:3])
        pieces.append(f"风险来自{len(distortion_items)}个传播失真点（{types}），最高严重度 {max_severity:g}")
    if isinstance(correction, dict):
        binding = str(correction.get("binding_problem") or "").strip()
        if binding:
            pieces.append(f"纠偏状态：{binding}")
    return "；".join(pieces)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _event_frame_correction_distortion_lines(ca: Dict[str, Any]) -> List[str]:
    frame = _public_event_frame_from(ca)
    correction = frame.get("correction_status", {})
    if not isinstance(correction, dict) or not correction.get("has_correction"):
        return []
    binding = str(correction.get("binding_problem") or "").strip()
    if not binding or "无纠偏" in binding:
        return []
    return [f"- 纠偏未能绑定原始高影响传播链，导致旧版本继续被引用（严重度 0.8）" + _span_suffix(correction)]


def _event_frame_targeted_actions(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    distortions = frame.get("distortion_points", [])
    actions: List[str] = []
    has_distortion_actions = False
    if isinstance(distortions, list):
        for item in distortions[:3]:
            if not isinstance(item, dict):
                continue
            dtype = str(item.get("type") or "").strip()
            desc = str(item.get("description") or "传播失真点").strip()
            severity = item.get("severity", "")
            action = _distortion_action_text(dtype)
            actions.append(
                f"- {desc}（类型：{_distortion_type_text(dtype)}，严重度 {severity}）：{action}"
                + _span_suffix(item)
            )
            has_distortion_actions = True
    plan = frame.get("containment_plan", {})
    if isinstance(plan, dict) and not has_distortion_actions:
        actor_actions = plan.get("actor_actions", [])
        if isinstance(actor_actions, list):
            for item in actor_actions[:3]:
                if not isinstance(item, dict):
                    continue
                actor = str(item.get("actor") or "执行方").strip()
                target = str(item.get("target_surface") or "传播界面").strip()
                action = str(item.get("action") or "").strip()
                effect = str(item.get("expected_effect") or "").strip()
                if not action:
                    continue
                line = f"- {actor} 在{target}：{action}"
                if effect:
                    line += f"；预期效果：{effect}"
                actions.append(line + _span_suffix(item))
    return "按失真类型的遏制动作：\n" + "\n".join(actions) if actions else ""


def _event_frame_expected_action(ca: Dict[str, Any]) -> str:
    frame = _public_event_frame_from(ca)
    distortions = frame.get("distortion_points", [])
    distortion_items = [item for item in distortions if isinstance(item, dict)] if isinstance(distortions, list) else []
    if not distortion_items:
        return ""
    target = _event_frame_primary_target(frame)
    actions = []
    for item in distortion_items[:2]:
        dtype = str(item.get("type") or "").strip()
        desc = str(item.get("description") or "该失真点").strip()
        action = _distortion_action_text(dtype).rstrip("。")
        actions.append(f"对“{desc}”：{action}")
    correction = frame.get("correction_status", {})
    bind_correction = ""
    if isinstance(correction, dict) and correction.get("has_correction"):
        bind_correction = "；同时把纠偏说明绑定到原帖、截图版本和主要转发节点"
    return f"在{target}执行：" + "；".join(actions) + bind_correction + "。"


def _event_frame_primary_target(frame: Dict[str, Any]) -> str:
    amplifiers = frame.get("amplifiers", [])
    if isinstance(amplifiers, list):
        for item in amplifiers:
            if isinstance(item, dict):
                desc = str(item.get("description") or item.get("node") or "").strip()
                if desc:
                    return _clean_phrase(desc)
    plan = frame.get("containment_plan", {})
    if isinstance(plan, dict):
        actor_actions = plan.get("actor_actions", [])
        if isinstance(actor_actions, list):
            for item in actor_actions:
                if isinstance(item, dict):
                    target = str(item.get("target_surface") or "").strip()
                    if target:
                        return _clean_phrase(target)
    return "主要传播节点"


def _distortion_type_text(value: Any) -> str:
    mapping = {
        "identity_error": "身份误认",
        "time_loss": "时间丢失",
        "location_loss": "地点丢失",
        "context_loss": "上下文丢失",
        "judgmental_framing": "判断性措辞放大",
        "overgeneralization": "过度泛化",
        "correction_not_bound": "纠偏未绑定",
        "image_context_loss": "图片脱离上下文",
        "source_uncertainty": "来源不确定",
    }
    text = str(value or "").strip()
    return mapping.get(text, text or "语义失真")


def _distortion_action_text(value: Any) -> str:
    mapping = {
        "identity_error": "把身份信息标为未证实，禁止未核验版本自动补全姓名、照片或嫌疑人标签，并把权威更正绑定到旧转发。",
        "time_loss": "对转发卡片自动检查发布时间和更新时间字段；缺失时阻断汇总账号继续分发或加时效性高敏提示，避免旧信息被当作最新事实。",
        "location_loss": "对转发卡片自动检查完整地点层级；地点缺失或缩写时要求补全、醒目标注可能造成资源误配，并引导查看原始发布。",
        "context_loss": "把原文链接、限定条件和更新说明固定在转发卡片中，裁剪截图版本进入人工复核或降推荐。",
        "judgmental_framing": "自动分离事实句和评价句，要求高影响节点保留“未证实”状态和中性表述；评价性改写继续传播前触发复核并绑定纠偏入口。",
        "overgeneralization": "补回限定范围和适用条件，提示该结论不能外推到未覆盖人群、地点或时间段。",
        "correction_not_bound": "把更正直接挂到原帖、截图版本和高影响节点，旧版本继续传播时显示已更正状态。",
        "image_context_loss": "要求图片和原始说明一起展示；单独图片转发时补上下文提示并限制继续截取扩散。",
        "source_uncertainty": "标注来源未核验，要求补充一手来源或权威说明后再扩大推荐。",
    }
    text = str(value or "").strip()
    return mapping.get(text, "标注证据状态，补回来源、时间和上下文，并把纠偏入口绑定到正在传播的版本。")


def _public_mechanism_text(bp: Dict[str, Any]) -> str:
    if str(bp.get("propagation_risk_level") or "").lower() == "low":
        return "机制解释：该讨论建立在已确认来源和理性补充之上，没有明显未核实爆料、情绪动员或行动号召。系统只需保持来源、时间和上下文完整，防止后续转发时发生断章取义。"
    threads = [item for item in bp.get("narrative_threads", []) if isinstance(item, dict)]
    uncertainties = [item for item in bp.get("uncertainty_points", []) if isinstance(item, dict)]
    gap = bp.get("official_response_gap", {}) if isinstance(bp.get("official_response_gap"), dict) else {}
    emotion = bp.get("emotion_signal", {}) if isinstance(bp.get("emotion_signal"), dict) else {}
    first_claim = threads[0].get("claim", "核心叙事") if threads else "核心叙事"
    uncertainty_text = "；".join(str(item.get("description", "")) for item in uncertainties[:2] if item.get("description"))
    if not uncertainty_text:
        uncertainty_text = "证据充分性和传播上下文需要持续核验"
    return (
        "机制解释：讨论先围绕“"
        + str(first_claim)
        + "”形成叙事，再受到情绪放大和信息缺口影响。"
        + f"当前主情绪为{_emotion_label_text(emotion.get('dominant_emotion',''))}，权威信息状态为{_official_gap_status_text(gap.get('status'))}；"
        + f"因此干预重点是同时处理不确定性（{uncertainty_text}）和传播位置，把澄清、核验入口或阶段性说明绑定到正在扩散的叙事上。"
    )


def _public_execution_steps(bp: Dict[str, Any]) -> str:
    risk = str(bp.get("propagation_risk_level") or "").lower()
    if risk == "low":
        return "执行步骤：1. 保留原始来源、发布时间和上下文；2. 继续常规监测转发是否出现断章取义；3. 不进行额外降权或强干预，避免过度治理。"
    gap = bp.get("official_response_gap", {}) if isinstance(bp.get("official_response_gap"), dict) else {}
    threads = [item for item in bp.get("narrative_threads", []) if isinstance(item, dict)]
    uncertainties = [item for item in bp.get("uncertainty_points", []) if isinstance(item, dict)]
    target = threads[0].get("claim", "核心争议叙事") if threads else "核心争议叙事"
    uncertain = uncertainties[0].get("description", "未确认信息") if uncertainties else "未确认信息"
    if str(gap.get("status") or "").lower() in {"present", "unclear"}:
        first = "权威主体发布阶段性通报，明确已确认事实、未确认部分和下一次更新时间"
    else:
        first = "补充事实核验入口，把可靠来源和原始上下文放到争议叙事旁边"
    return (
        "执行步骤：1. "
        + first
        + f"；2. 在“{target}”相关转发、热评和二创内容旁标注证据状态，特别提示“{uncertain}”；"
        + "3. 要求主要放大账号同步更新说明，减少只转述情绪结论的二次传播；4. 公众侧只转发带来源和上下文的材料，避免把未经核验内容当作事实。"
    )


def _event_execution_steps(bp: Dict[str, Any]) -> str:
    risk = str(bp.get("coverage_risk") or "").lower()
    if risk == "low":
        return "执行步骤：1. 保留原始发布时间、来源和影响范围；2. 常规监测后续转发是否裁剪上下文；3. 无需限流或强制更正。"
    distortions = [item for item in bp.get("distortion_points", []) if isinstance(item, dict)]
    amps = [item for item in bp.get("amplifier_nodes", []) if isinstance(item, dict)]
    distortion = distortions[0].get("description", "失真内容") if distortions else "失真内容"
    dtype = distortions[0].get("type", "") if distortions else ""
    distortion_actions = []
    for item in distortions[:2]:
        desc = str(item.get("description") or distortion).strip()
        item_type = item.get("type", dtype)
        action = _distortion_action_text(item_type).rstrip("。") if item_type else "标注证据状态并绑定原始传播链和纠偏入口"
        distortion_actions.append(f"针对“{desc}”执行：{action}")
    type_action = "；".join(distortion_actions) if distortion_actions else "标注证据状态并绑定原始传播链和纠偏入口"
    amplifier = amps[0].get("description", "主要放大节点") if amps else "主要放大节点"
    precheck = _event_precheck_text(distortions)
    return (
        "执行步骤：1. 在“"
        + str(amplifier)
        + f"”继续转发前{precheck}；2. {type_action}；"
        + "3. 若已有更正信息，将更正绑定到原帖、截图版本和主要转发节点；4. 对未同步更正的旧版本降低推荐，并保留用户查看完整原文的入口。"
    )


def _event_precheck_text(distortions: List[Dict[str, Any]]) -> str:
    types = {str(item.get("type") or "") for item in distortions if isinstance(item, dict)}
    checks: List[str] = []
    if "location_loss" in types:
        checks.append("自动检查地点层级是否完整")
    if "time_loss" in types:
        checks.append("自动检查发布时间和更新时间是否保留")
    if "context_loss" in types:
        checks.append("自动检查原文链接、限定条件和更新说明是否被裁剪")
    if "judgmental_framing" in types:
        checks.append("自动检测事实句是否被评价性措辞改写")
    if "identity_error" in types:
        checks.append("自动检查身份标签是否已有权威核验")
    if checks:
        return "，".join(checks) + "，缺失或改写时先标注/限流再放大"
    return "提示信息未证实，并展示原始证据状态"


def _official_gap_status_text(value: Any) -> str:
    status = str(value or "").lower()
    if status == "present":
        return "存在回应缺口"
    if status == "unclear":
        return "回应状态不明确"
    if status == "none":
        return "无明显回应缺口"
    return "需要继续核验"


def _event_mechanism_text(bp: Dict[str, Any]) -> str:
    origin = bp.get("origin_node", {}) if isinstance(bp.get("origin_node"), dict) else {}
    amps = [item for item in bp.get("amplifier_nodes", []) if isinstance(item, dict)]
    distortions = [item for item in bp.get("distortion_points", []) if isinstance(item, dict)]
    origin_text = origin.get("description") or "原始信息源"
    amp_text = "、".join(str(item.get("description", "")) for item in amps[:2] if item.get("description")) or "后续转发节点"
    if distortions:
        distortion_text = "；".join(str(item.get("description", "")) for item in distortions[:2] if item.get("description"))
        return f"机制解释：信息从“{origin_text}”进入“{amp_text}”后，风险集中在失真点：{distortion_text}。遏制动作需要绑定原传播链和主要放大节点，否则更正信息容易覆盖不到旧版本。"
    return f"机制解释：信息从“{origin_text}”经由“{amp_text}”扩散；当前没有显著失真点，重点是保持来源、时间和上下文不被后续转发破坏。"


def llm_text_from(row: Dict[str, Any], scenario: str = "fraud_im") -> str:
    """Convert LLM-only output to natural language, scenario-aware."""
    bp = prediction_from(row)
    if scenario == "event_propagation":
        return _propagation_text(bp, {}, scenario)
    if scenario == "public_opinion":
        return _propagation_text(bp, {}, scenario)
    return _fraud_im_llm_text(bp)


def miro_text_from(row: Dict[str, Any], scenario: str = "fraud_im") -> str:
    """Convert Miro-CogSec output to natural language, scenario-aware."""
    bp = prediction_from(row)
    ca = row.get("cogsec_analysis", {}) if isinstance(row.get("cogsec_analysis"), dict) else {}
    if scenario == "event_propagation":
        return _propagation_text(bp, ca, scenario)
    if scenario == "public_opinion":
        return _propagation_text(bp, ca, scenario)
    return _fraud_im_miro_text(bp, ca)


def runtime_summary_from(row: Dict[str, Any]) -> Dict[str, Any]:
    propagation_summary = row.get("propagation_summary") if isinstance(row.get("propagation_summary"), dict) else {}
    metrics = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
    return {
        "ok": row.get("ok"),
        "latency_ms": row.get("latency_ms"),
        "scenario_match": row.get("scenario_match"),
        "has_propagation": row.get("has_propagation"),
        "has_intervention_search": row.get("has_intervention_search"),
        "propagation_summary": {
            "present": propagation_summary.get("present"),
            "branch_a_final_metrics": propagation_summary.get("branch_a_final_metrics"),
            "branch_b_final_metrics": propagation_summary.get("branch_b_final_metrics"),
            "comparison": propagation_summary.get("comparison"),
            "counterfactual_branch_count": propagation_summary.get("counterfactual_branch_count"),
            "selected_best_branch": propagation_summary.get("selected_best_branch"),
        },
        "runtime_metrics": {
            "t0_latency_ms": metrics.get("t0_latency_ms"),
            "end_to_end_ms": metrics.get("end_to_end_ms"),
            "benchmarks": metrics.get("benchmarks"),
        },
    }


def stable_shuffle_seed(row_id: str, seed: int) -> int:
    digest = hashlib.sha256(f"{seed}:{row_id}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def build_request(
    *,
    scenario: str,
    truth: Dict[str, Any],
    llm_row: Dict[str, Any],
    miro_row: Dict[str, Any],
    seed: int,
    include_gold: bool,
    structured: bool = False,
) -> Dict[str, Any]:
    row_id = str(truth.get("id"))
    if structured:
        answers = [
            {
                "slot": "A",
                "system": "llm_only",
                "prediction": prediction_from(llm_row),
                "runtime_summary": None,
            },
            {
                "slot": "B",
                "system": "miro_cogsec",
                "prediction": prediction_from(miro_row),
                "runtime_summary": None,
            },
        ]
    else:
        answers = [
            {
                "slot": "A",
                "system": "llm_only",
                "text": llm_text_from(llm_row, scenario),
                "runtime_summary": None,
            },
            {
                "slot": "B",
                "system": "miro_cogsec",
                "text": miro_text_from(miro_row, scenario),
                "runtime_summary": None,
            },
        ]
    rng = random.Random(stable_shuffle_seed(row_id, seed))
    rng.shuffle(answers)
    for index, item in enumerate(answers):
        item["slot"] = "A" if index == 0 else "B"

    if include_gold:
        reference_gold = truth.get("answer", {})
        judge_instruction = (
            "Gold is a reference annotation, not an absolute truth. Prefer the answer that is better grounded in "
            "the original input, offers more useful safety intervention, and gives stronger evidence. Do not "
            "penalize reasonable alternative interpretations merely because they differ from gold wording."
        ) if structured else (
            "Gold is a reference annotation, not an absolute truth. "
            "Each answer is presented as a natural-language analysis report. "
            "Prefer the answer that better identifies the real risk in the original input, "
            "cites concrete evidence from the input text, and gives actionable safety intervention. "
            "Do not penalize reasonable alternative interpretations merely because they differ from gold wording."
        )
    else:
        reference_gold = None
        judge_instruction = (
            "No gold/reference answer is provided. Judge only from the original input, the two candidate answers, "
            "and their evidence grounding. Prefer the answer that is more useful "
            "for real safety work, even if it uses a different structure or terminology."
        ) if structured else (
            "No gold/reference answer is provided. "
            "Each answer is presented as a natural-language analysis report. "
            "Judge only from the original input and the two candidate reports. "
            "Prefer the answer that more clearly locates the problem, cites evidence from the input, "
            "and gives specific actionable safety intervention."
        )

    answer_key = "prediction" if structured else "text"
    return {
        "id": row_id,
        "scenario_type": scenario,
        "input": truth.get("input", {}),
        "reference_gold": reference_gold,
        "judge_instruction": judge_instruction,
        "answer_a": {
            answer_key: answers[0][answer_key],
            "runtime_summary": answers[0]["runtime_summary"],
        },
        "answer_b": {
            answer_key: answers[1][answer_key],
            "runtime_summary": answers[1]["runtime_summary"],
        },
        "private_answer_key": {
            "A": answers[0]["system"],
            "B": answers[1]["system"],
        },
    }


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create blind closed-model judge requests.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--miro-fraud", type=Path, default=None, help="Override Miro fraud_im JSONL")
    parser.add_argument("--miro-public", type=Path, default=None, help="Override Miro public_opinion JSONL")
    parser.add_argument("--miro-event", type=Path, default=None, help="Override Miro event_propagation JSONL")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-gold", action="store_true", help="Do not include reference_gold in judge requests")
    parser.add_argument("--structured", action="store_true", help="Use structured prediction dict instead of natural-language text")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configs = {name: dict(config) for name, config in SCENARIOS.items()}
    if args.miro_fraud:
        configs["fraud_im"]["miro"] = args.miro_fraud
    if args.miro_public:
        configs["public_opinion"]["miro"] = args.miro_public
    if args.miro_event:
        configs["event_propagation"]["miro"] = args.miro_event
    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    requests: List[Dict[str, Any]] = []
    for scenario in scenarios:
        config = configs[scenario]
        truth_rows = load_jsonl(config["gold"])
        llm_rows = by_id(load_jsonl(config["llm"]))
        miro_rows = by_id(load_jsonl(config["miro"]))
        if args.limit is not None:
            truth_rows = truth_rows[: args.limit]
        for truth in truth_rows:
            row_id = str(truth.get("id"))
            if row_id not in llm_rows:
                raise ValueError(f"missing LLM-only prediction for {row_id}")
            if row_id not in miro_rows:
                raise ValueError(f"missing Miro-CogSec prediction for {row_id}")
            requests.append(
                build_request(
                    scenario=scenario,
                    truth=truth,
                    llm_row=llm_rows[row_id],
                    miro_row=miro_rows[row_id],
                    seed=args.seed,
                    include_gold=not args.no_gold,
                    structured=args.structured,
                )
            )
    write_jsonl(args.output, requests)
    print(f"closed-model judge requests: {args.output} ({len(requests)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

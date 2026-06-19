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
    fraud_type = bp.get("fraud_type", "")
    risk_level = str(bp.get("risk_level", "")).upper()
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
    fraud_type = bp.get("fraud_type", "")
    risk_level = str(bp.get("risk_level", "")).upper()
    attack_stage = bp.get("attack_stage", "")
    if is_fraud:
        parts.append(f"结论：检测到{fraud_type or '疑似'}诈骗行为。风险等级：{risk_level}。当前阶段：{attack_stage or '初期接触'}。")
    else:
        parts.append(f"结论：当前场景风险等级 {risk_level or 'LOW'}，暂未确认诈骗行为。")
    cf = ca.get("counterfactual_analysis", {}) if isinstance(ca.get("counterfactual_analysis"), dict) else {}
    key_div = cf.get("key_divergence", [])
    if key_div:
        lines = []
        for d in key_div[:3]:
            if isinstance(d, dict):
                lines.append(f"- [{d.get('fork_type','')} / {d.get('asset','')}] {d.get('description','')}")
        if lines:
            parts.append("关键分叉点：\n" + "\n".join(lines))
    traj_gap = cf.get("trajectory_gap")
    irrev = cf.get("irreversibility_loss")
    if traj_gap is not None:
        irrev_str = f"{irrev:.1f}" if irrev is not None else "?"
        parts.append(f"双路径偏差度：{traj_gap:.3f}，不可逆损失：{irrev_str}")
    risky = cf.get("risky_path", [])
    safe = cf.get("safe_path", [])
    if risky:
        steps = [f"{s.get('step', i+1)}. {s.get('action','')}" for i, s in enumerate(risky[:4]) if isinstance(s, dict)]
        parts.append("高风险路径（顺从攻击者）：\n" + "\n".join(steps))
    if safe:
        steps = [f"{s.get('step', i+1)}. {s.get('action','')}" for i, s in enumerate(safe[:4]) if isinstance(s, dict)]
        parts.append("干预后安全路径：\n" + "\n".join(steps))
    ip = ca.get("intervention_policy", [])
    if isinstance(ip, list) and ip:
        iv_lines = []
        for policy in ip[:3]:
            if not isinstance(policy, dict):
                continue
            wo = policy.get("window_open_step")
            wc = policy.get("window_close_step")
            line = f"[优先级{policy.get('priority','')}] {policy.get('title','')}\n  理由：{policy.get('rationale','')}"
            if wo is not None and wc is not None:
                line += f"\n  干预窗口：步骤 {wo}–{wc}"
            recs = policy.get("recommended_actions", [])
            if recs:
                line += "\n  建议行动：" + " / ".join(str(r) for r in recs[:3])
            iv_lines.append(line)
        if iv_lines:
            parts.append("干预建议：\n" + "\n".join(iv_lines))
    et = ca.get("evidence_trace", [])
    if isinstance(et, list) and et:
        items = [f"「{e['text']}」({e.get('type','')})" for e in et[:6] if isinstance(e, dict) and e.get("text")]
        if items:
            parts.append("原文证据片段：" + "、".join(items))
    return "\n\n".join(parts)


def _propagation_text(bp: Dict[str, Any], ca: Dict[str, Any], scenario: str) -> str:
    """Shared builder for event_propagation and public_opinion (both LLM and Miro)."""
    parts: List[str] = []
    event_summary = bp.get("event_summary", "")
    if event_summary:
        parts.append(f"事件概述：{event_summary[:250]}")

    if scenario == "event_propagation":
        risk_label = bp.get("coverage_risk", "")
        if risk_label:
            parts.append(f"传播风险：{risk_label}")
        origin = bp.get("origin_node", {})
        if isinstance(origin, dict) and origin:
            parts.append(f"传播起点：[{origin.get('type','')}] {origin.get('description','')}")
        amps = bp.get("amplifier_nodes", [])
        if amps:
            lines = [f"- [{a.get('type','')}] {a.get('description','')}" for a in amps[:3] if isinstance(a, dict)]
            if lines:
                parts.append("放大节点：\n" + "\n".join(lines))
        path = bp.get("propagation_path", [])
        if path:
            steps = [
                f"{s.get('step', i+1)}. [{s.get('node','')}] {s.get('action','')}（{s.get('risk_state','')}）"
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
            if lines:
                parts.append("失真点：\n" + "\n".join(lines))
        ev_spans = bp.get("evidence_spans", [])
        if ev_spans:
            parts.append("原文证据片段：" + "、".join(f"「{s}」" for s in ev_spans[:6]))
        cw = bp.get("containment_window", {})
        if isinstance(cw, dict) and cw:
            parts.append(f"遏制窗口：{cw.get('label','')}（步骤 {cw.get('open_step','?')}–{cw.get('close_step','?')}）")
        action = bp.get("expected_containment_action", "")
        if action:
            parts.append(f"建议遏制行动：{action}")

    else:  # public_opinion
        risk_label = bp.get("propagation_risk_level", "")
        if risk_label:
            parts.append(f"传播风险等级：{risk_label}")
        es = bp.get("emotion_signal", {})
        if isinstance(es, dict) and es:
            parts.append(f"情绪信号：主情绪={es.get('dominant_emotion','')}，放大={es.get('amplification_level','')}。{es.get('rationale','')}")
        nt = bp.get("narrative_threads", [])
        if nt:
            lines = [f"- {t.get('claim','')}（风险：{t.get('risk','')}）" for t in nt[:3] if isinstance(t, dict)]
            if lines:
                parts.append("叙事线程：\n" + "\n".join(lines))
        up = bp.get("uncertainty_points", [])
        if up:
            lines = [f"- {u.get('description','')}" for u in up[:3] if isinstance(u, dict)]
            if lines:
                parts.append("不确定性节点：\n" + "\n".join(lines))
        org = bp.get("official_response_gap", {})
        if isinstance(org, dict) and org:
            parts.append(f"官方回应缺口：{org.get('description','')}（严重度 {org.get('severity','')}）")
        ev_spans = bp.get("evidence_spans", [])
        if ev_spans:
            parts.append("原文证据片段：" + "、".join(f"「{s}」" for s in ev_spans[:6]))
        biw = bp.get("best_intervention_window", {})
        if isinstance(biw, dict) and biw:
            parts.append(f"最佳干预窗口：{biw.get('label','')}（{biw.get('open_stage','')} → {biw.get('close_stage','')}）")
        action = bp.get("expected_intervention_action", "")
        safe = bp.get("expected_safe_public_action", "")
        if action:
            parts.append(f"干预行动：{action}")
        if safe:
            parts.append(f"公众安全行动：{safe}")

    # Miro-only: OASIS simulation results from cogsec_analysis
    if ca:
        ps = ca.get("propagation_analysis", {})
        if isinstance(ps, dict):
            best = ps.get("selected_best_branch", {})
            if isinstance(best, dict) and best:
                fm = best.get("final_metrics", {})
                cov = fm.get("coverage_final", "?")
                pol = fm.get("polarization_final", "?")
                parts.append(f"OASIS多Agent仿真——最优干预方案：{best.get('branch_id','')}，干预后覆盖率 {cov}，极化度 {pol}")
            kn = ps.get("key_nodes", [])
            if kn:
                kn_text = "、".join(
                    f"{n.get('role','')}({n.get('agent_id','')})" for n in kn[:4] if isinstance(n, dict)
                )
                parts.append(f"仿真关键传播节点：{kn_text}")
        ip = ca.get("intervention_policy", [])
        if isinstance(ip, list) and ip:
            iv_lines = []
            for policy in ip[:2]:
                if not isinstance(policy, dict):
                    continue
                recs = policy.get("recommended_actions", [])
                line = f"[{policy.get('title','')}] {policy.get('rationale','')}"
                if recs:
                    line += " 建议：" + " / ".join(str(r) for r in recs[:2])
                iv_lines.append(line)
            if iv_lines:
                parts.append("干预建议（仿真驱动）：\n" + "\n".join(iv_lines))

    return "\n\n".join(parts)


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
                "runtime_summary": runtime_summary_from(miro_row),
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
                "runtime_summary": runtime_summary_from(miro_row),
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
            "their evidence grounding, and any runtime trace summary shown. Prefer the answer that is more useful "
            "for real safety work, even if it uses a different structure or terminology."
        ) if structured else (
            "No gold/reference answer is provided. "
            "Each answer is presented as a natural-language analysis report. "
            "Judge only from the original input, the two candidate reports, and any runtime trace summary shown. "
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
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-gold", action="store_true", help="Do not include reference_gold in judge requests")
    parser.add_argument("--structured", action="store_true", help="Use structured prediction dict instead of natural-language text")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    scenarios = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    requests: List[Dict[str, Any]] = []
    for scenario in scenarios:
        config = SCENARIOS[scenario]
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

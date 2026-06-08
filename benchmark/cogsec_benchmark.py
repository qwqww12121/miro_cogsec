"""Miro-CogSec benchmark v0.1 pipeline.

This script intentionally uses only the Python standard library so the benchmark
folder can travel independently with the GitHub repo.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import statistics
import sys
import time
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


BENCHMARK_ROOT = Path(__file__).resolve().parent
REPO_ROOT = BENCHMARK_ROOT.parent
RAW_PATH = BENCHMARK_ROOT / "data" / "raw_seed_v0.1.jsonl"
ANNOTATED_PATH = BENCHMARK_ROOT / "data" / "cogsec_v0.1.jsonl"
REVIEW_REQUEST_PATH = BENCHMARK_ROOT / "data" / "review_request_v0.1.jsonl"
REVIEW_STUB_PATH = BENCHMARK_ROOT / "data" / "review_stub_v0.1.jsonl"
REVIEW_PATH = BENCHMARK_ROOT / "data" / "review_v0.1.jsonl"
RUN_OUTPUT_PATH = BENCHMARK_ROOT / "outputs" / "run_v0.1.jsonl"
METRICS_PATH = BENCHMARK_ROOT / "outputs" / "metrics_v0.1.json"
REPORT_PATH = BENCHMARK_ROOT / "reports" / "human_review_v0.1.md"
PUBLIC_OPINION_PATH = BENCHMARK_ROOT / "data" / "public_opinion_v0.1.jsonl"
EVENT_PROPAGATION_PATH = BENCHMARK_ROOT / "data" / "event_propagation_v0.1.jsonl"
LLM_BASELINE_OUTPUT_ROOT = BENCHMARK_ROOT / "outputs" / "llm_baseline"

REQUIRED_ANSWER_FIELDS = {
    "is_fraud",
    "fraud_type",
    "risk_level",
    "attack_stage",
    "cognitive_pressure",
    "expected_fork",
    "intervention_window",
    "evidence_spans",
    "evidence_keywords",
    "scenario_frame",
    "evidence_pack",
    "attack_strategy_chain",
    "persona_weakness_candidates",
    "asset_targets",
    "environment_context",
    "fork_points",
    "counterfactual_expectation",
    "uncertainty",
}

RICH_ANSWER_FIELDS = {
    "scenario_frame",
    "evidence_pack",
    "attack_strategy_chain",
    "persona_weakness_candidates",
    "asset_targets",
    "environment_context",
    "fork_points",
    "counterfactual_expectation",
    "uncertainty",
}

RUNTIME_FORK_TYPES = {
    "transfer_money",
    "screen_share",
    "verification_code",
    "unknown_app_download",
    "social_isolation",
    "fake_official_verification",
    "no_fork_needed",
}

BENCHMARK_FORK_TYPES = RUNTIME_FORK_TYPES | {
    "private_contact_lure",
    "identity_asset_exchange",
    "group_or_platform_join",
    "gambling_entry",
    "unlicensed_financial_service",
    "illicit_or_regulated_service",
    "phishing_link_entry",
}

RISK_VALUE = {
    "low": 0.0,
    "medium": 0.5,
    "high": 1.0,
    "critical": 1.0,
    "LOW": 0.0,
    "MEDIUM": 0.5,
    "HIGH": 1.0,
    "CRITICAL": 1.0,
}

RISK_BASE = {
    "low": 0.12,
    "medium": 0.42,
    "high": 0.68,
    "critical": 0.88,
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            try:
                rows.append(json.loads(stripped))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number} is not valid JSON: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def normalize_space(value: str) -> str:
    return " ".join(value.replace("\t", " ").split())


def text_hash(value: str) -> str:
    return hashlib.sha256(normalize_space(value).encode("utf-8")).hexdigest()[:16]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def evidence_slug(span: str, index: int) -> str:
    normalized = normalize_space(span)
    safe = "".join(char if char.isalnum() else "_" for char in normalized[:28]).strip("_")
    return safe or f"span_{index}"


def evidence_refs_for_terms(
    evidence_pack: List[Dict[str, Any]],
    terms: Iterable[str],
    fallback_count: int = 2,
) -> List[str]:
    refs: List[str] = []
    normalized_terms = [normalize_space(str(term)).lower() for term in terms if normalize_space(str(term))]
    for evidence in evidence_pack:
        span = normalize_space(str(evidence.get("span", ""))).lower()
        if not span:
            continue
        if any(term in span or span in term for term in normalized_terms):
            refs.append(str(evidence.get("id")))
    if not refs:
        refs = [str(item.get("id")) for item in evidence_pack[:fallback_count]]
    return [ref for index, ref in enumerate(refs) if ref and ref not in refs[:index]]


def evidence_confidence(span: str, answer: Dict[str, Any], supports: List[str]) -> float:
    base = 0.66 if answer.get("is_fraud") else 0.61
    base += min(0.10, len(normalize_space(span)) / 120)
    base += min(0.10, len(set(supports)) * 0.025)
    if any(keyword in span for keyword in answer.get("evidence_keywords", [])):
        base += 0.04
    return round(clamp(base, 0.5, 0.92), 2)


def infer_asset_targets(text: str, answer: Dict[str, Any], evidence_pack: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lowered = text.lower()
    specs = [
        ("asset:funds", "funds", "资金账户", 0.95, ["转账", "汇款", "付款", "充值", "提现", "定金", "费用", "银行卡", "信用卡"]),
        ("asset:credential", "credential", "身份凭证", 0.92, ["验证码", "动态码", "密码", "登录", "银行卡号"]),
        ("asset:device", "device_control", "设备控制权", 0.86, ["共享屏幕", "远程", "下载", "安装", "app", "链接"]),
        ("asset:identity", "identity", "身份资料", 0.88, ["实名", "身份证", "手机卡", "证件", "银行卡照片"]),
        ("asset:social", "social_support", "社会支持系统", 0.72, ["保密", "不要告诉别人", "不要联系家人", "单独联系"]),
    ]
    evidence_keywords = answer.get("evidence_keywords", [])
    targets = []
    for asset_id, asset_type, label, severity, keywords in specs:
        hits = [keyword for keyword in keywords if keyword.lower() in lowered]
        if hits:
            targets.append(
                {
                    "id": asset_id,
                    "type": asset_type,
                    "label": label,
                    "severity": severity,
                    "evidence_refs": evidence_refs_for_terms(evidence_pack, hits, fallback_count=3),
                    "matched_terms": hits[:4],
                }
            )
    if answer.get("is_fraud") and not targets:
        targets.append(
            {
                "id": "asset:funds",
                "type": "funds",
                "label": "资金账户",
                "severity": 0.78,
                "evidence_refs": evidence_refs_for_terms(evidence_pack, evidence_keywords, fallback_count=2),
                "matched_terms": evidence_keywords[:3],
            }
        )
    return targets


def infer_fork_points(
    text: str,
    answer: Dict[str, Any],
    asset_targets: List[Dict[str, Any]],
    evidence_pack: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if not answer.get("is_fraud"):
        return [
            {
                "id": "fork:no_fork_needed",
                "type": "no_fork_needed",
                "severity": 0.0,
                "asset": "none",
                "reason": "样本未要求付款、凭据暴露或私下高风险操作。",
                "evidence_refs": [],
                "runtime_alignment": {"status": "direct", "runtime_type": "no_fork_needed"},
                "expected_branch_a": "正常浏览或忽略信息。",
                "expected_branch_b": "无需干预。",
            }
        ]

    lowered = text.lower()
    specs = [
        ("transfer_money", "direct", "transfer_money", ["转账", "汇款", "打款", "付款", "充值", "定金", "费用", "安全账户"], 0.96),
        ("verification_code", "direct", "verification_code", ["验证码", "动态码", "密码", "重新登录", "确认密码", "银行卡号", "短信验证码"], 0.94),
        ("screen_share", "direct", "screen_share", ["共享屏幕", "远程控制", "远程", "会议软件"], 0.88),
        ("unknown_app_download", "direct", "unknown_app_download", ["下载", "安装", "app", "二维码"], 0.84),
        ("phishing_link_entry", "nearest", "unknown_app_download", ["链接", "非官方链接", "重新登录"], 0.82),
        ("fake_official_verification", "direct", "fake_official_verification", ["官方", "客服", "公安", "监管", "核验", "证明"], 0.80),
        ("social_isolation", "direct", "social_isolation", ["保密", "不要告诉别人", "不要联系家人", "单独联系"], 0.74),
        ("identity_asset_exchange", "unsupported", None, ["实名", "手机卡", "身份证", "证件"], 0.84),
        ("private_contact_lure", "unsupported", None, ["微信", "私人", "私下", "联系", "账号", "接待"], 0.70),
        ("group_or_platform_join", "unsupported", None, ["进群", "群", "社区", "会员"], 0.68),
        ("gambling_entry", "unsupported", None, ["博彩", "赌博", "投注", "开奖", "赛车", "牛牛"], 0.78),
        ("unlicensed_financial_service", "unsupported", None, ["代还", "刷卡", "养卡", "套现", "低点位"], 0.78),
        ("illicit_or_regulated_service", "unsupported", None, ["办证", "证明", "黑户", "贷款"], 0.72),
    ]
    asset_label = asset_targets[0]["label"] if asset_targets else "核心资产"
    forks = []
    for fork_type, alignment_status, runtime_type, keywords, severity in specs:
        hits = [keyword for keyword in keywords if keyword.lower() in lowered]
        if not hits:
            continue
        alignment_note = "可被当前 runtime 直接消费" if alignment_status == "direct" else (
            f"当前 runtime 无精确 Fork 类型，评测运行时近似映射为 {runtime_type}" if runtime_type else "当前 runtime 无精确 Fork 类型，仅作为 benchmark 语义标准答案"
        )
        forks.append(
            {
                "id": f"fork:{fork_type}",
                "type": fork_type,
                "severity": severity,
                "asset": asset_label,
                "reason": f"文本命中 {', '.join(hits[:3])}，对应 benchmark Fork 类型 {fork_type}；{alignment_note}。",
                "evidence_refs": evidence_refs_for_terms(evidence_pack, hits, fallback_count=3),
                "matched_terms": hits[:4],
                "runtime_alignment": {"status": alignment_status, "runtime_type": runtime_type},
                "expected_branch_a": "用户继续服从高风险指令，资产暴露和后验风险上升。",
                "expected_branch_b": "用户暂停操作并进行官方核验，资产暴露下降、可逆性回升。",
            }
        )
    if not forks:
        fallback_terms = answer.get("evidence_keywords", [])[:3]
        forks.append(
            {
                "id": "fork:private_contact_lure",
                "type": "private_contact_lure",
                "severity": 0.55,
                "asset": asset_label,
                "reason": "文本显示可疑诱导但未出现付款、凭据、下载或屏幕共享等精确 Fork；以私下联系诱导作为 benchmark 语义标准答案，并要求二审复核。",
                "evidence_refs": evidence_refs_for_terms(evidence_pack, fallback_terms, fallback_count=2),
                "matched_terms": fallback_terms,
                "runtime_alignment": {"status": "unsupported", "runtime_type": None},
                "expected_branch_a": "用户进入私下沟通或后续高风险链路。",
                "expected_branch_b": "用户停止私下联系并通过官方渠道核验。",
            }
        )
    forks.sort(key=lambda item: item.get("severity", 0.0), reverse=True)
    return forks


def infer_environment_context(text: str, source: Dict[str, Any], answer: Dict[str, Any]) -> Dict[str, Any]:
    lowered = text.lower()
    channel = "text"
    if any(token in lowered for token in ["电话", "来电", "客服热线"]):
        channel = "voice"
    if any(token in lowered for token in ["链接", "网址", "二维码", "app"]):
        channel = "mixed"
    return {
        "channel": channel,
        "source_channel": source.get("split", ""),
        "time_pressure": any(token in lowered for token in ["马上", "立即", "今天", "24小时", "限时", "加急", "秒"]),
        "social_isolation": any(token in lowered for token in ["保密", "不要告诉别人", "不要联系家人", "单独联系"]),
        "official_masking": any(token in lowered for token in ["官方", "客服", "公安", "监管", "银行", "平台"]),
        "private_contact_lure": any(token in lowered for token in ["微信", "私人", "私下", "联系", "账号"]),
        "scenario_type": answer.get("fraud_type", "unknown"),
    }


def pressure_to_dimension(pressure: str) -> str:
    mapping = {
        "authority": "authority_compliance",
        "urgency": "time_pressure_sensitivity",
        "scarcity": "fomo_susceptibility",
        "fear": "emotional_volatility",
        "greed": "financial_stress",
        "social_proof": "fomo_susceptibility",
        "commitment": "loss_aversion",
        "trust_transfer": "digital_trust_boundary",
        "confusion": "analytic_control_gap",
        "isolation": "help_seeking_gap",
        "convenience": "analytic_control_gap",
    }
    return mapping.get(pressure, "unknown")


def build_evidence_pack(answer: Dict[str, Any]) -> List[Dict[str, Any]]:
    spans = answer.get("evidence_spans", [])
    pack = []
    used_ids = set()
    for index, span in enumerate(spans, start=1):
        supports = ["risk_level", "fraud_type"]
        if any(keyword in span for keyword in ["验证码", "密码", "银行卡", "身份证", "共享屏幕", "转账", "安全账户"]):
            supports.append("asset_targets")
        if any(keyword in span for keyword in ["客服", "公安", "官方", "信誉", "几百人", "老师"]):
            supports.append("persona_pressure")
        base_id = f"ev:{evidence_slug(str(span), index)}"
        evidence_id = base_id
        suffix = 2
        while evidence_id in used_ids:
            evidence_id = f"{base_id}_{suffix}"
            suffix += 1
        used_ids.add(evidence_id)
        pack.append(
            {
                "id": evidence_id,
                "span": span,
                "evidence_type": "direct_text",
                "supports": sorted(set(supports)),
                "confidence": evidence_confidence(str(span), answer, supports),
            }
        )
    return pack


def compute_case_scores(
    answer: Dict[str, Any],
    evidence_pack: List[Dict[str, Any]],
    asset_targets: List[Dict[str, Any]],
    fork_points: List[Dict[str, Any]],
    environment: Dict[str, Any],
) -> Dict[str, float]:
    is_fraud = bool(answer.get("is_fraud"))
    risk_level = str(answer.get("risk_level", "low")).lower()
    risk = RISK_BASE.get(risk_level, 0.35 if is_fraud else 0.12)
    pressure_score = min(0.14, len(answer.get("cognitive_pressure", [])) * 0.035)
    evidence_score = min(0.14, len(evidence_pack) * 0.035)
    primary_severity = max([float(item.get("severity", 0.0)) for item in fork_points] or [0.0])
    environment_score = sum(
        0.025
        for key in ("time_pressure", "social_isolation", "official_masking", "private_contact_lure")
        if environment.get(key)
    )
    unsupported_runtime = any(
        (item.get("runtime_alignment") or {}).get("status") == "unsupported"
        for item in fork_points
    )

    if is_fraud:
        trajectory_gap = clamp(0.18 + risk * 0.36 + primary_severity * 0.22 + pressure_score + environment_score, 0.22, 0.92)
    else:
        trajectory_gap = clamp(0.02 + evidence_score * 0.3, 0.02, 0.12)

    asset_loss = {
        "funds": 0.70,
        "credential": 0.74,
        "device_control": 0.58,
        "identity": 0.56,
        "social_support": 0.34,
    }
    strongest_asset = max(
        (asset_loss.get(str(item.get("type")), 0.48) * float(item.get("severity", 0.5)) for item in asset_targets),
        default=0.18 if is_fraud else 0.0,
    )
    irreversibility_loss = clamp(strongest_asset * (0.55 + risk * 0.45), 0.0, 0.88) if is_fraud else 0.0

    confidence = 0.56 + evidence_score + min(0.12, primary_severity * 0.10)
    confidence += 0.06 if answer.get("evidence_spans") else 0.0
    confidence += 0.04 if answer.get("fraud_type") not in {"", "unknown", "none"} else 0.0
    if unsupported_runtime:
        confidence -= 0.08
    if not is_fraud:
        confidence -= 0.03
    return {
        "expected_trajectory_gap": round(trajectory_gap, 2),
        "expected_irreversibility_loss": round(irreversibility_loss, 2),
        "confidence": round(clamp(confidence, 0.52, 0.88), 2),
    }


def enrich_case(row: Dict[str, Any]) -> Dict[str, Any]:
    answer = row.setdefault("answer", {})
    text = row.get("input", {}).get("text", "")
    source = row.get("source", {})
    evidence_pack = build_evidence_pack(answer)
    asset_targets = infer_asset_targets(text, answer, evidence_pack)
    fork_points = infer_fork_points(text, answer, asset_targets, evidence_pack)
    environment = infer_environment_context(text, source, answer)
    is_fraud = bool(answer.get("is_fraud"))
    primary_fork = fork_points[0]
    evidence_refs = [item["id"] for item in evidence_pack[:3]]
    evidence_ref_set = set(evidence_refs)
    for item in asset_targets + fork_points:
        refs = item.get("evidence_refs", [])
        if not refs or any(ref not in {evidence["id"] for evidence in evidence_pack} for ref in refs):
            terms = item.get("matched_terms", []) or answer.get("evidence_keywords", [])
            item["evidence_refs"] = evidence_refs_for_terms(evidence_pack, terms, fallback_count=3)
    dynamic_scores = compute_case_scores(answer, evidence_pack, asset_targets, fork_points, environment)

    answer["scenario_frame"] = {
        "summary": text,
        "language": row.get("input", {}).get("language", "zh-CN"),
        "channel": row.get("input", {}).get("channel", environment["channel"]),
        "source_label": source.get("label_name"),
        "adversary_role": "unknown_or_not_applicable" if not is_fraud else answer.get("fraud_type", "unknown"),
        "target_user_action": answer.get("expected_safe_action", ""),
        "observed_attack_surface": environment["channel"],
        "turns": [
            {
                "turn_id": 1,
                "speaker": "source_text",
                "text": text,
                "risk_function": "seed_case",
            }
        ],
    }
    answer["evidence_pack"] = evidence_pack
    answer["attack_strategy_chain"] = [] if not is_fraud else [
        {
            "id": f"strategy:{row.get('id')}:{index + 1}",
            "tactic_name": answer.get("fraud_type", "unknown"),
            "cialdini_principle": pressure,
            "description": f"利用 {pressure} 压力推进用户进入 {answer.get('attack_stage', 'unknown')} 阶段。",
            "typical_dialogue": evidence_pack[min(index, len(evidence_pack) - 1)]["span"] if evidence_pack else text[:32],
            "escalation_condition": "用户未进行官方核验或继续私下沟通。",
            "intensity_level": 3 if answer.get("risk_level") in {"high", "critical"} else 2,
            "evidence_refs": evidence_refs,
        }
        for index, pressure in enumerate(answer.get("cognitive_pressure", [])[:3])
    ]
    if is_fraud and not answer["attack_strategy_chain"]:
        answer["attack_strategy_chain"] = [
            {
                "id": f"strategy:{row.get('id')}:primary",
                "tactic_name": answer.get("fraud_type", "unknown"),
                "cialdini_principle": "trust_transfer",
                "description": "通过私下联系或非官方承诺推动用户进入高风险流程。",
                "typical_dialogue": evidence_pack[0]["span"] if evidence_pack else text[:32],
                "escalation_condition": "用户继续私下沟通。",
                "intensity_level": 2,
                "evidence_refs": evidence_refs,
            }
        ]
    answer["persona_weakness_candidates"] = [
        {
            "dimension": pressure_to_dimension(pressure),
            "pressure": pressure,
            "score_hint": 7.5 if is_fraud else 2.0,
            "evidence_refs": evidence_refs,
            "caution": "这是文本可见的认知压力，不等于真实用户人格画像。",
        }
        for pressure in answer.get("cognitive_pressure", [])
    ]
    answer["asset_targets"] = asset_targets
    answer["environment_context"] = environment
    answer["fork_points"] = fork_points
    answer["counterfactual_expectation"] = {
        "branch_a_high_risk_path": [] if not is_fraud else [
            {"step": 1, "action": "继续响应攻击者要求", "expected_world_state_change": "trust_score 上升，intervention_window 缩短"},
            {"step": 2, "action": primary_fork.get("expected_branch_a", "进入高风险路径"), "expected_world_state_change": "asset_exposure 与 posterior_risk 上升"},
            {"step": 3, "action": "损失或凭据暴露开始变得不可逆", "expected_world_state_change": "reversibility 明显下降"},
        ],
        "branch_b_safe_path": [
            {"step": 1, "action": "暂停操作并延迟决策", "expected_world_state_change": "system2_control 回升"},
            {"step": 2, "action": primary_fork.get("expected_branch_b", "通过官方渠道核验"), "expected_world_state_change": "posterior_risk 下降，reversibility 回升"},
        ],
        "irreversible_nodes": [] if not is_fraud else [
            {
                "step": max(2, int(answer.get("intervention_window", {}).get("end_turn", 1)) + 1),
                "node_type": primary_fork.get("type"),
                "asset": primary_fork.get("asset"),
                "reason": "超过干预窗口后，付款、凭据或身份资料暴露将更难逆转。",
            }
        ],
        "best_intervention_window": {
            "open_step": answer.get("intervention_window", {}).get("start_turn", 0),
            "close_step": answer.get("intervention_window", {}).get("end_turn", 0),
            "label": answer.get("intervention_window", {}).get("rationale", ""),
        },
        "expected_trajectory_gap": dynamic_scores["expected_trajectory_gap"],
        "expected_irreversibility_loss": dynamic_scores["expected_irreversibility_loss"],
    }
    unsupported_forks = [
        item.get("type")
        for item in fork_points
        if (item.get("runtime_alignment") or {}).get("status") == "unsupported"
    ]
    answer["uncertainty"] = {
        "confidence": dynamic_scores["confidence"],
        "needs_human_review": True,
        "unsupported_inferences": [
            "公开短文本无法证明真实用户长期人格，只能标注文本诱发的认知压力。"
        ],
        "runtime_alignment_notes": [
            "fork_points.type 使用 benchmark 语义标准答案；runtime_alignment.runtime_type 记录当前 MiroFishRuntime 可直接消费或近似映射的类型。",
            f"当前 runtime 暂无精确映射的 Fork 类型: {', '.join(unsupported_forks)}。" if unsupported_forks else "所有主要 Fork 类型均可被当前 runtime 直接消费或近似映射。",
        ],
    }
    return row


def dedupe_rows(rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for row in rows:
        text = row.get("input", {}).get("text", "")
        key = text_hash(text)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped


def read_tabular_source(path: Path) -> List[Dict[str, Any]]:
    content = path.read_text(encoding="utf-8-sig", errors="replace")
    sample = content[:2048]
    delimiter = "\t" if "\t" in sample else ","
    reader = csv.DictReader(content.splitlines(), delimiter=delimiter)
    rows: List[Dict[str, Any]] = []
    for index, item in enumerate(reader, start=1):
        text = item.get("Text") or item.get("text") or item.get("scenario") or item.get("content") or ""
        label = item.get("Label_id") or item.get("label_id") or item.get("label") or None
        if not normalize_space(text):
            continue
        rows.append(
            {
                "id": f"imported-{index:04d}",
                "source": {
                    "dataset": path.stem,
                    "url": "",
                    "license": "unknown",
                    "split": path.name,
                    "label_id": label,
                    "label_name": None,
                    "relation": "imported_raw_text",
                },
                "input": {
                    "language": "zh-CN",
                    "channel": "imported_text",
                    "text": normalize_space(text),
                    "sanitization": [],
                },
                "sampling": {
                    "version": "custom",
                    "source_hash": text_hash(text),
                },
            }
        )
    return rows


def read_source(path: Path) -> List[Dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        return load_jsonl(path)
    if path.suffix.lower() in {".csv", ".tsv", ".txt"}:
        return read_tabular_source(path)
    raise ValueError(f"Unsupported source format: {path}")


def build_sample(args: argparse.Namespace) -> int:
    rows = read_source(args.input)
    rows = dedupe_rows(rows)
    rows = rows[: args.limit]
    write_jsonl(args.output, rows)
    print(f"built sample: {args.output} ({len(rows)} rows)")
    return 0


def enrich_annotations(args: argparse.Namespace) -> int:
    rows = [enrich_case(row) for row in load_jsonl(args.input)]
    write_jsonl(args.output, rows)
    print(f"enriched annotations: {args.output} ({len(rows)} rows)")
    return 0


def validate_case(row: Dict[str, Any], raw: bool = False) -> List[str]:
    errors: List[str] = []
    prefix = row.get("id", "<missing-id>")
    for key in ("id", "source", "input"):
        if key not in row:
            errors.append(f"{prefix}: missing {key}")
    text = row.get("input", {}).get("text", "")
    if not isinstance(text, str) or not text.strip():
        errors.append(f"{prefix}: input.text is empty")
    if raw:
        return errors

    answer = row.get("answer")
    if not isinstance(answer, dict):
        errors.append(f"{prefix}: missing answer object")
        return errors
    missing = REQUIRED_ANSWER_FIELDS - set(answer)
    if missing:
        errors.append(f"{prefix}: missing answer fields {sorted(missing)}")
    for key in RICH_ANSWER_FIELDS:
        if key not in answer:
            continue
        if key in {"evidence_pack", "attack_strategy_chain", "persona_weakness_candidates", "asset_targets", "fork_points"}:
            if not isinstance(answer.get(key), list):
                errors.append(f"{prefix}: answer.{key} must be a list")
        elif key in {"scenario_frame", "environment_context", "counterfactual_expectation", "uncertainty"}:
            if not isinstance(answer.get(key), dict):
                errors.append(f"{prefix}: answer.{key} must be an object")
    fork_points = answer.get("fork_points", [])
    if isinstance(fork_points, list):
        for fork in fork_points:
            fork_type = fork.get("type") if isinstance(fork, dict) else None
            if fork_type not in BENCHMARK_FORK_TYPES:
                errors.append(f"{prefix}: unsupported fork_points.type {fork_type!r}")
            runtime_alignment = fork.get("runtime_alignment", {}) if isinstance(fork, dict) else {}
            runtime_type = runtime_alignment.get("runtime_type") if isinstance(runtime_alignment, dict) else None
            if runtime_type is not None and runtime_type not in RUNTIME_FORK_TYPES:
                errors.append(f"{prefix}: unsupported runtime_alignment.runtime_type {runtime_type!r}")
    evidence_ids = {
        item.get("id")
        for item in answer.get("evidence_pack", [])
        if isinstance(item, dict) and item.get("id")
    }
    if evidence_ids:
        for node_key in ("attack_strategy_chain", "persona_weakness_candidates", "asset_targets", "fork_points"):
            for index, node in enumerate(answer.get(node_key, []) or []):
                if not isinstance(node, dict):
                    continue
                for ref in node.get("evidence_refs", []) or []:
                    if ref not in evidence_ids:
                        errors.append(f"{prefix}: {node_key}[{index}] has unknown evidence_ref {ref!r}")
    risk = answer.get("risk_level")
    if risk not in {"low", "medium", "high", "critical"}:
        errors.append(f"{prefix}: invalid risk_level {risk!r}")
    window = answer.get("intervention_window", {})
    if not isinstance(window, dict):
        errors.append(f"{prefix}: intervention_window must be an object")
    else:
        start = window.get("start_turn")
        end = window.get("end_turn")
        if not isinstance(start, int) or not isinstance(end, int) or start > end:
            errors.append(f"{prefix}: invalid intervention_window start/end")
    annotation = row.get("annotation", {})
    if annotation.get("review_status") not in {
        "silver_pending_review",
        "silver_reviewed",
        "gold_reviewed",
        "rejected",
    }:
        errors.append(f"{prefix}: invalid annotation.review_status")
    return errors


def validate(args: argparse.Namespace) -> int:
    raw_rows = load_jsonl(args.raw)
    annotated_rows = load_jsonl(args.annotated)
    errors: List[str] = []
    for row in raw_rows:
        errors.extend(validate_case(row, raw=True))
    for row in annotated_rows:
        errors.extend(validate_case(row, raw=False))

    raw_ids = {row.get("id") for row in raw_rows}
    annotated_ids = {row.get("id") for row in annotated_rows}
    if raw_ids != annotated_ids:
        errors.append(
            "raw/annotated id mismatch: "
            f"missing_in_annotated={sorted(raw_ids - annotated_ids)}, "
            f"extra_in_annotated={sorted(annotated_ids - raw_ids)}"
        )

    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print(f"PASS raw={len(raw_rows)} annotated={len(annotated_rows)}")
    return 0


def make_review_input(args: argparse.Namespace) -> int:
    raw_by_id = {row["id"]: row for row in load_jsonl(args.raw)}
    annotated = load_jsonl(args.annotated)
    review_rows = []
    stub_rows = []
    for row in annotated:
        case_id = row["id"]
        review_rows.append(
            {
                "id": case_id,
                "raw_case": raw_by_id.get(case_id),
                "stage1_annotation": row,
                "review_questions": [
                    "Is every fraud, risk, and graph claim grounded in raw_case text or source label?",
                    "Do evidence_pack items support the attack_strategy_chain, asset_targets, and fork_points?",
                    "Are fork_points.type values aligned with MiroFishRuntime.FORK_RULES?",
                    "Does counterfactual_expectation form a real Branch A / Branch B divergence?",
                    "Is the intervention window before the irreversible node?",
                    "Are persona_weakness_candidates framed as text-induced pressure rather than invented user personality?",
                    "Are source license, sanitization, and redistribution risks handled conservatively?",
                    "Should this case be approved, revised, rejected, or sent to human review?",
                ],
                "review_output_schema": {
                    "id": case_id,
                    "reviewer": "claudecode+deepseek-v4-pro",
                    "decision": "approve|revise|reject|needs_human",
                    "confidence": "0.0-1.0",
                    "issues": [{"severity": "low|medium|high", "field": "answer.risk_level", "comment": "..."}],
                    "suggested_patch": None,
                    "human_review": {"decision": "", "notes": "", "reviewer": ""},
                },
            }
        )
        stub_rows.append(
            {
                "id": case_id,
                "reviewer": "",
                "decision": "needs_human",
                "confidence": 0.0,
                "issues": [],
                "suggested_patch": None,
                "human_review": {"decision": "", "notes": "", "reviewer": ""},
            }
        )

    write_jsonl(args.output, review_rows)
    write_jsonl(args.stub_output, stub_rows)
    print(f"review input: {args.output} ({len(review_rows)} rows)")
    print(f"review stub: {args.stub_output} ({len(stub_rows)} rows)")
    return 0


def review_by_id(path: Path) -> Dict[str, Dict[str, Any]]:
    return {row["id"]: row for row in load_jsonl(path) if row.get("id")}


def compact_list(values: Iterable[Any]) -> str:
    items = [str(item) for item in values if str(item)]
    return ", ".join(items) if items else "-"


def make_report(args: argparse.Namespace) -> int:
    annotated = load_jsonl(args.annotated)
    review_path = args.review
    if not review_path.exists() and review_path == REVIEW_PATH and REVIEW_STUB_PATH.exists():
        review_path = REVIEW_STUB_PATH
    reviews = review_by_id(review_path) if review_path.exists() else {}
    review_label = "未找到二审文件"
    if review_path.exists():
        try:
            review_label = review_path.relative_to(BENCHMARK_ROOT).as_posix()
        except ValueError:
            review_label = str(review_path)
    lines: List[str] = [
        "# Miro-CogSec Benchmark v0.1 人工审核报告",
        "",
        "每条样本分为三部分：第一层 CogSec 抽取结果、第二层模型审查意见、人工审核留白。",
        f"审查输入: {review_label}",
        "",
    ]

    for index, row in enumerate(annotated, start=1):
        answer = row["answer"]
        source = row["source"]
        review = reviews.get(row["id"], {})
        issues = review.get("issues") or []
        issue_text = "无" if not issues else "; ".join(
            f"{item.get('severity', '?')}:{item.get('field', '?')} - {item.get('comment', '')}"
            for item in issues
        )
        lines.extend(
            [
                f"## {index:02d}. {row['id']}",
                "",
                "### 1. GPT 抽取结果",
                "",
                f"- 来源: {source.get('dataset')} / {source.get('label_name')} / {source.get('relation')}",
                f"- 输入文本: {row['input']['text']}",
                f"- is_fraud: {answer['is_fraud']}",
                f"- fraud_type: {answer['fraud_type']}",
                f"- risk_level: {answer['risk_level']}",
                f"- expected_fork: {answer['expected_fork']}",
                f"- 干预窗口: 第 {answer['intervention_window'].get('start_turn')} 到第 {answer['intervention_window'].get('end_turn')} 步 - {answer['intervention_window'].get('rationale')}",
                f"- cognitive_pressure: {compact_list(answer.get('cognitive_pressure', []))}",
                f"- 证据片段: {compact_list(answer.get('evidence_spans', []))}",
                f"- 建议安全动作: {answer.get('expected_safe_action', '-')}",
                "",
                "#### 图谱支撑材料",
                "",
                f"- 场景框架: {json.dumps(answer.get('scenario_frame', {}), ensure_ascii=False)}",
                f"- 证据包: {json.dumps(answer.get('evidence_pack', []), ensure_ascii=False)}",
                f"- 攻击策略链: {json.dumps(answer.get('attack_strategy_chain', []), ensure_ascii=False)}",
                f"- 认知压力候选: {json.dumps(answer.get('persona_weakness_candidates', []), ensure_ascii=False)}",
                f"- 资产目标: {json.dumps(answer.get('asset_targets', []), ensure_ascii=False)}",
                f"- 环境上下文: {json.dumps(answer.get('environment_context', {}), ensure_ascii=False)}",
                f"- Fork 节点: {json.dumps(answer.get('fork_points', []), ensure_ascii=False)}",
                f"- 反事实预期: {json.dumps(answer.get('counterfactual_expectation', {}), ensure_ascii=False)}",
                f"- 不确定性: {json.dumps(answer.get('uncertainty', {}), ensure_ascii=False)}",
                "",
                "### 2. DS 审查意见",
                "",
                f"- 审查模型: {review.get('reviewer', '')}",
                f"- 审查结论: {review.get('decision', '')}",
                f"- 置信度: {review.get('confidence', '')}",
                f"- 问题: {issue_text}",
                f"- 建议修订: {json.dumps(review.get('suggested_patch'), ensure_ascii=False) if review else ''}",
                "",
                "### 3. 人工审核",
                "",
                "- 人工结论:",
                "- 审核人:",
                "- 审核备注:",
                "- 最终修订:",
                "",
            ]
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"human review report: {args.output} ({len(annotated)} cases)")
    return 0


def risk_bin(value: str) -> str:
    value = str(value or "").lower()
    if value in {"critical", "high"}:
        return "high"
    if value == "medium":
        return "medium"
    return "low"


def as_number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def runtime_prediction(result: Dict[str, Any]) -> Dict[str, Any]:
    report = first_dict(result.get("counterfactual_report"))
    report_sections = first_dict(report.get("report_sections"), report.get("structured_report"))
    score_comparison = first_dict(report.get("score_comparison"))
    risk_breakdown = first_dict(score_comparison.get("risk_breakdown"))
    branch_contrast = first_dict(report.get("branch_contrast"), report_sections.get("branch_contrast"))
    fork_comp = first_dict(result.get("fork_comparison"))
    graph = first_dict(result.get("risk_graph_bundle"), result.get("graph"))
    risk_level = (
        report.get("risk_level")
        or risk_breakdown.get("risk_level")
        or result.get("risk_level")
        or "LOW"
    )
    t0 = result.get("t0_fast_response", {})
    t0_alert = bool(
        t0.get("should_interrupt")
        or t0.get("alert")
        or str(t0.get("risk_level", "")).lower() in {"high", "critical"}
        or t0.get("matched_patterns")
    )
    strategies = result.get("strategies", [])
    strategy_text = " ".join(
        " ".join(
            str(strategy.get(key, ""))
            for key in ("tactic_name", "description", "typical_dialogue", "cialdini_principle")
        )
        for strategy in strategies
    )
    evidence_text = " ".join(
        [
            strategy_text,
            str(report.get("critical_bifurcation_reason", "")),
            str(report.get("related_case_summary", "")),
            json.dumps(graph.get("evidence_items", []), ensure_ascii=False),
            json.dumps(graph.get("attack_strategy_chain", []), ensure_ascii=False),
            json.dumps(t0, ensure_ascii=False),
        ]
    )
    # Extract asset types from risk_graph_bundle or fork_comparison
    predicted_asset_types: List[str] = []
    raw_assets = graph.get("asset_targets") or result.get("asset_targets") or []
    for item in (raw_assets if isinstance(raw_assets, list) else []):
        asset_type = item.get("type") if isinstance(item, dict) else None
        if asset_type and asset_type not in predicted_asset_types:
            predicted_asset_types.append(str(asset_type))
    predicted_fork_type = (
        fork_comp.get("fork_point_type")
        or branch_contrast.get("fork_point_type")
        or risk_breakdown.get("fork_point_type")
        or report.get("expected_fork")
        or ""
    )
    predicted_fork_binary = "no_fork_needed" if risk_bin(risk_level) == "low" else "intervention_vs_compliance"
    trajectory_gap = (
        fork_comp.get("trajectory_gap")
        if fork_comp.get("trajectory_gap") is not None
        else branch_contrast.get("trajectory_gap")
    )
    if trajectory_gap is None:
        trajectory_gap = risk_breakdown.get("trajectory_gap")
    irreversibility_loss = (
        fork_comp.get("irreversibility_loss")
        if fork_comp.get("irreversibility_loss") is not None
        else risk_breakdown.get("irreversibility_loss")
    )
    branch_a_final = first_dict(score_comparison.get("branch_a_final"))
    branch_b_final = first_dict(score_comparison.get("branch_b_final"))
    if trajectory_gap is None and branch_a_final and branch_b_final:
        trajectory_gap = abs(
            as_number(branch_a_final.get("risk_score"))
            - as_number(branch_b_final.get("risk_score"))
        ) / 100.0
    if irreversibility_loss is None and branch_a_final and branch_b_final:
        irreversibility_loss = max(
            0.0,
            as_number(branch_b_final.get("reversibility"), 1.0)
            - as_number(branch_a_final.get("reversibility"), 1.0),
        )
    bifurcation_step = (
        report.get("critical_bifurcation_step")
        or first_dict(fork_comp.get("best_intervention_window")).get("open_step")
        or first_dict(report.get("best_intervention_window")).get("open_step")
        or 0
    )

    return {
        "risk_level": risk_level,
        "risk_bin": risk_bin(risk_level),
        "critical_bifurcation_step": as_int(bifurcation_step),
        "t0_alert": t0_alert,
        "predicted_fork_family": predicted_fork_binary,
        "predicted_fork_type": predicted_fork_type,
        "trajectory_gap": as_number(trajectory_gap),
        "irreversibility_loss": as_number(irreversibility_loss),
        "predicted_asset_types": predicted_asset_types,
        "evidence_text": evidence_text,
    }


def run_runtime(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(REPO_ROOT))
    rows = load_jsonl(args.annotated)
    try:
        from backend.app.cogsec_minimal_runtime import run_minimal_cogsec_analysis
    except Exception as exc:  # pragma: no cover - environment dependency guard
        outputs = [
            {
                "id": row["id"],
                "ok": False,
                "latency_ms": None,
                "prediction": {},
                "error": f"runtime_import_failed: {exc.__class__.__name__}: {exc}",
            }
            for row in rows
        ]
        write_jsonl(args.output, outputs)
        print(f"runtime import failed; wrote error output: {args.output} ({len(outputs)} rows)")
        print(f"error: {exc.__class__.__name__}: {exc}")
        return 0

    outputs = []
    for row in rows:
        started = time.perf_counter()
        try:
            result = run_minimal_cogsec_analysis(
                scenario_text=row["input"]["text"],
                scenario_type=row["answer"].get("fraud_type"),
            )
            latency_ms = (time.perf_counter() - started) * 1000
            outputs.append(
                {
                    "id": row["id"],
                    "ok": True,
                    "latency_ms": round(latency_ms, 3),
                    "prediction": runtime_prediction(result),
                    "error": None,
                }
            )
        except Exception as exc:  # pragma: no cover - runtime dependency guard
            latency_ms = (time.perf_counter() - started) * 1000
            outputs.append(
                {
                    "id": row["id"],
                    "ok": False,
                    "latency_ms": round(latency_ms, 3),
                    "prediction": {},
                    "error": f"{exc.__class__.__name__}: {exc}",
                }
            )
    write_jsonl(args.output, outputs)
    print(f"runtime output: {args.output} ({len(outputs)} rows)")
    return 0


def contains_any(text: str, keywords: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if str(keyword).lower() in lowered)


# ---------------------------------------------------------------------------
# Layer 1 scoring: Annotation Quality Score (no runtime needed)
# ---------------------------------------------------------------------------

def compute_annotation_quality(annotated_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Evaluate the quality and completeness of the benchmark annotations themselves."""
    per_case: List[Dict[str, Any]] = []
    for row in annotated_rows:
        cid = row["id"]
        answer = row.get("answer", {})
        text = row.get("input", {}).get("text", "")
        source = row.get("source", {})
        annotation = row.get("annotation", {})

        # ECR: Evidence Coverage Rate — spans in text, IDs valid, supports meaningful
        evidence_pack = answer.get("evidence_pack", []) if isinstance(answer.get("evidence_pack"), list) else []
        ecr_items = []
        for ev in evidence_pack:
            if not isinstance(ev, dict):
                continue
            span_ok = isinstance(ev.get("span"), str) and ev["span"] in text
            id_ok = isinstance(ev.get("id"), str) and ev["id"].startswith("ev:")
            supports_ok = isinstance(ev.get("supports"), list) and len(ev.get("supports", [])) > 0
            ecr_items.append({"id": ev.get("id", ""), "span_ok": span_ok, "id_ok": id_ok, "supports_ok": supports_ok})
        if not evidence_pack and not answer.get("is_fraud"):
            ecr = 1.0  # benign cases correctly have no evidence
        else:
            ecr = round(sum(1 for item in ecr_items if item["span_ok"] and item["id_ok"]) / max(1, len(ecr_items)), 3)

        # FVS: Fork Validity Score — benchmark type is valid and runtime alignment is explicit.
        fork_points = answer.get("fork_points", []) if isinstance(answer.get("fork_points"), list) else []
        fvs_items = []
        for fp in fork_points:
            if not isinstance(fp, dict):
                continue
            alignment = fp.get("runtime_alignment") or {}
            type_ok = fp.get("type") in BENCHMARK_FORK_TYPES
            status_ok = alignment.get("status") in {"direct", "nearest", "unsupported"}
            runtime_type = alignment.get("runtime_type")
            runtime_type_ok = runtime_type is None or runtime_type in RUNTIME_FORK_TYPES
            alignment_ok = status_ok and runtime_type_ok
            fvs_items.append({
                "type": fp.get("type", ""),
                "type_ok": type_ok,
                "alignment_ok": alignment_ok,
            })
        fvs = round(sum(1 for item in fvs_items if item["type_ok"] and item["alignment_ok"]) / max(1, len(fvs_items)), 3)

        # WCS: Window Consistency Score — window closes before irreversible node
        iw = answer.get("intervention_window", {}) if isinstance(answer.get("intervention_window"), dict) else {}
        cf = answer.get("counterfactual_expectation", {}) if isinstance(answer.get("counterfactual_expectation"), dict) else {}
        ir_nodes = cf.get("irreversible_nodes", []) if isinstance(cf.get("irreversible_nodes"), list) else []
        wcs = 1.0
        if ir_nodes:
            end_turn = int(iw.get("end_turn", 0))
            irrev_steps = [int(n.get("step", 999)) for n in ir_nodes if isinstance(n, dict)]
            if irrev_steps and end_turn >= min(irrev_steps):
                wcs = 0.0

        # TRS: Traceability Score — evidence_refs point to valid evidence IDs
        ev_ids = {ev["id"] for ev in evidence_pack if isinstance(ev, dict) and ev.get("id")}
        ref_sources = [
            ("attack_strategy_chain", answer.get("attack_strategy_chain", [])),
            ("persona_weakness_candidates", answer.get("persona_weakness_candidates", [])),
            ("asset_targets", answer.get("asset_targets", [])),
            ("fork_points", fork_points),
        ]
        total_refs = 0
        dangling_refs = 0
        for _source_name, chain in ref_sources:
            for item in (chain if isinstance(chain, list) else []):
                if not isinstance(item, dict):
                    continue
                for ref in item.get("evidence_refs", []):
                    total_refs += 1
                    if ref not in ev_ids:
                        dangling_refs += 1
        trs = round(1.0 - (dangling_refs / max(1, total_refs)), 3)

        # RFS: Rich Field Score — all required rich fields present
        rich_present = 0
        for key in RICH_ANSWER_FIELDS:
            if isinstance(answer.get(key), (dict, list)):
                value = answer[key]
                if isinstance(value, list) or (isinstance(value, dict) and len(value) > 0):
                    rich_present += 1
                elif isinstance(value, dict) and len(value) == 0 and not answer.get("is_fraud"):
                    rich_present += 1  # benign cases can have empty lists
        rfs = round(rich_present / max(1, len(RICH_ANSWER_FIELDS)), 3)

        annotation_quality = round((ecr * 0.25 + fvs * 0.25 + wcs * 0.15 + trs * 0.20 + rfs * 0.15), 3)

        per_case.append({
            "id": cid, "ECR": ecr, "FVS": fvs, "WCS": wcs, "TRS": trs, "RFS": rfs,
            "annotation_quality": annotation_quality,
            "evidence_count": len(ecr_items), "fork_count": len(fvs_items),
            "source_license": source.get("license", "unknown"),
            "review_status": annotation.get("review_status", "unknown"),
        })

    def mean(values: Iterable[float]) -> float:
        values = list(values)
        return round(sum(values) / max(1, len(values)), 3)

    return {
        "layer": "annotation_quality",
        "benchmark_version": "v0.1",
        "case_count": len(per_case),
        "ECR": mean(item["ECR"] for item in per_case),
        "FVS": mean(item["FVS"] for item in per_case),
        "WCS": mean(item["WCS"] for item in per_case),
        "TRS": mean(item["TRS"] for item in per_case),
        "RFS": mean(item["RFS"] for item in per_case),
        "AQI": mean(item["annotation_quality"] for item in per_case),
        "per_case": per_case,
    }


def score_annotation_quality(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.annotated)
    metrics = compute_annotation_quality(rows)
    write_json(args.output, metrics)
    summary = {k: v for k, v in metrics.items() if k != "per_case"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"annotation quality: {args.output}")
    return 0


# ---------------------------------------------------------------------------
# Scenario-extension scoring: public_opinion / event_propagation AQS
# ---------------------------------------------------------------------------

SCENARIO_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "public_opinion": [
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
        "evidence_pack",
    ],
    "event_propagation": [
        "event_summary",
        "origin_node",
        "amplifier_nodes",
        "propagation_path",
        "distortion_points",
        "coverage_risk",
        "containment_window",
        "expected_containment_action",
        "evidence_spans",
        "evidence_pack",
    ],
}


def _truthy_field(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def _walk_evidence_refs(value: Any) -> Iterable[str]:
    if isinstance(value, dict):
        refs = value.get("evidence_refs")
        if isinstance(refs, list):
            for ref in refs:
                if isinstance(ref, str):
                    yield ref
        for child in value.values():
            yield from _walk_evidence_refs(child)
    elif isinstance(value, list):
        for item in value:
            yield from _walk_evidence_refs(item)


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return round(sum(values) / max(1, len(values)), 3)


def compute_scenario_annotation_quality(rows: List[Dict[str, Any]], scenario_type: Optional[str] = None) -> Dict[str, Any]:
    """Score seed gold annotations for non-fraud scenario extensions."""
    per_case: List[Dict[str, Any]] = []
    for row in rows:
        cid = row.get("id", "unknown")
        scenario = scenario_type or row.get("scenario_type") or row.get("source", {}).get("scenario_type")
        answer = row.get("answer", {}) if isinstance(row.get("answer"), dict) else {}
        text = row.get("input", {}).get("text", "")
        annotation = row.get("annotation", {}) if isinstance(row.get("annotation"), dict) else {}

        required = SCENARIO_REQUIRED_FIELDS.get(str(scenario), [])
        present = 0
        for key in required:
            if _truthy_field(answer.get(key)):
                present += 1
            elif scenario == "event_propagation" and key == "distortion_points" and answer.get("coverage_risk") == "low":
                present += 1
        rfs = round(present / max(1, len(required)), 3)

        evidence_pack = answer.get("evidence_pack", []) if isinstance(answer.get("evidence_pack"), list) else []
        evidence_items = []
        for ev in evidence_pack:
            if not isinstance(ev, dict):
                continue
            evidence_items.append(
                {
                    "span_ok": isinstance(ev.get("span"), str) and ev["span"] in text,
                    "id_ok": isinstance(ev.get("id"), str) and ev["id"].startswith("ev:"),
                    "supports_ok": isinstance(ev.get("supports"), list) and bool(ev.get("supports")),
                }
            )
        ecr = round(
            sum(1 for item in evidence_items if item["span_ok"] and item["id_ok"] and item["supports_ok"])
            / max(1, len(evidence_items)),
            3,
        )

        evidence_spans = answer.get("evidence_spans", []) if isinstance(answer.get("evidence_spans"), list) else []
        span_coverage = round(
            sum(1 for span in evidence_spans if isinstance(span, str) and span in text)
            / max(1, len(evidence_spans)),
            3,
        )

        ev_ids = {ev.get("id") for ev in evidence_pack if isinstance(ev, dict) and ev.get("id")}
        refs = list(_walk_evidence_refs(answer))
        trs = round(sum(1 for ref in refs if ref in ev_ids) / max(1, len(refs)), 3)

        review_status = annotation.get("review_status")
        review_status_ok = review_status in {"silver_pending_review", "gold_reviewed"}
        gold_reviewed = review_status == "gold_reviewed"
        rss = 1.0 if review_status_ok else 0.0

        metrics: Dict[str, float] = {
            "ECR": ecr,
            "SCS": span_coverage,
            "TRS": trs,
            "RFS": rfs,
            "RSS": rss,
        }

        if scenario == "public_opinion":
            narrative_threads = answer.get("narrative_threads", [])
            uncertainty_points = answer.get("uncertainty_points", [])
            emotion_signal = answer.get("emotion_signal", {})
            intervention = answer.get("expected_intervention_action", "")
            safe_action = answer.get("expected_safe_public_action", "")
            official_gap = answer.get("official_response_gap", {})

            metrics.update(
                {
                    "NCS": 1.0 if isinstance(narrative_threads, list) and bool(narrative_threads) else 0.0,
                    "EAS": 1.0 if isinstance(emotion_signal, dict) and _truthy_field(emotion_signal.get("dominant_emotion")) and _truthy_field(emotion_signal.get("amplification_level")) else 0.0,
                    "UGS": 1.0 if isinstance(uncertainty_points, list) and bool(uncertainty_points) else 0.0,
                    "OGS": 1.0 if isinstance(official_gap, dict) and _truthy_field(official_gap.get("status")) else 0.0,
                    "IAS": 1.0 if _truthy_field(intervention) and _truthy_field(safe_action) else 0.0,
                }
            )
            aqi_keys = ["ECR", "SCS", "TRS", "RFS", "RSS", "NCS", "EAS", "UGS", "OGS", "IAS"]
        elif scenario == "event_propagation":
            origin = answer.get("origin_node", {})
            amplifiers = answer.get("amplifier_nodes", [])
            path = answer.get("propagation_path", [])
            distortions = answer.get("distortion_points", [])
            containment = answer.get("containment_window", {})
            action = answer.get("expected_containment_action", "")
            low_risk = answer.get("coverage_risk") == "low"

            metrics.update(
                {
                    "OVS": 1.0 if isinstance(origin, dict) and _truthy_field(origin.get("id")) else 0.0,
                    "ANS": 1.0 if isinstance(amplifiers, list) and bool(amplifiers) else 0.0,
                    "PCS": 1.0 if isinstance(path, list) and len(path) >= 2 else 0.0,
                    "DCS": 1.0 if low_risk or (isinstance(distortions, list) and bool(distortions)) else 0.0,
                    "CWS": 1.0 if isinstance(containment, dict) and _truthy_field(containment.get("label")) and _truthy_field(action) else 0.0,
                }
            )
            aqi_keys = ["ECR", "SCS", "TRS", "RFS", "RSS", "OVS", "ANS", "PCS", "DCS", "CWS"]
        else:
            aqi_keys = ["ECR", "SCS", "TRS", "RFS", "RSS"]

        annotation_quality = _mean(metrics[key] for key in aqi_keys)
        per_case.append(
            {
                "id": cid,
                "scenario_type": scenario,
                **metrics,
                "annotation_quality": annotation_quality,
                "evidence_count": len(evidence_items),
                "evidence_ref_count": len(refs),
                "review_status": review_status or "unknown",
                "gold_reviewed": gold_reviewed,
                "source_dataset": row.get("source", {}).get("dataset", "unknown"),
                "source_license": row.get("source", {}).get("license", "unknown"),
            }
        )

    metric_names = sorted({key for item in per_case for key, value in item.items() if isinstance(value, float) and key != "annotation_quality"})
    return {
        "layer": "scenario_annotation_quality",
        "benchmark_version": "v0.1",
        "scenario_type": scenario_type or "mixed",
        "case_count": len(per_case),
        **{name: _mean(item.get(name, 0.0) for item in per_case) for name in metric_names},
        "AQI": _mean(item["annotation_quality"] for item in per_case),
        "per_case": per_case,
    }


def score_scenario_annotation_quality(args: argparse.Namespace) -> int:
    rows = load_jsonl(args.input)
    metrics = compute_scenario_annotation_quality(rows, args.scenario_type)
    write_json(args.output, metrics)
    summary = {k: v for k, v in metrics.items() if k != "per_case"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"scenario annotation quality: {args.output}")
    return 0


def make_baseline_input(args: argparse.Namespace) -> int:
    """Create answer-free JSONL for LLM-only baseline prompting."""
    rows = load_jsonl(args.input)
    outputs: List[Dict[str, Any]] = []
    for row in rows:
        item = {
            "id": row.get("id"),
            "source": row.get("source", {}),
            "input": row.get("input", {}),
        }
        scenario_type = args.scenario_type or row.get("scenario_type")
        if scenario_type:
            item["scenario_type"] = scenario_type
        outputs.append(item)
    write_jsonl(args.output, outputs)
    print(f"baseline input: {args.output} ({len(outputs)} rows)")
    return 0


LLM_BASELINE_REQUIRED_PREDICTION_FIELDS: Dict[str, List[str]] = {
    "fraud_im": [
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
    ],
    "public_opinion": [
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
    ],
    "event_propagation": [
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
    ],
}


def validate_llm_baseline(args: argparse.Namespace) -> int:
    """Validate LLM-only baseline JSONL format before scoring."""
    input_rows = load_jsonl(args.input)
    output_rows = load_jsonl(args.output)
    expected_ids = [row.get("id") for row in input_rows]
    output_by_id = {row.get("id"): row for row in output_rows if row.get("id")}
    required = LLM_BASELINE_REQUIRED_PREDICTION_FIELDS.get(args.scenario_type, [])

    errors: List[str] = []
    if len(output_rows) != len(input_rows):
        errors.append(f"row count mismatch: input={len(input_rows)} output={len(output_rows)}")

    for expected_id in expected_ids:
        row = output_by_id.get(expected_id)
        if row is None:
            errors.append(f"{expected_id}: missing output row")
            continue
        if row.get("scenario_type") != args.scenario_type:
            errors.append(f"{expected_id}: scenario_type={row.get('scenario_type')!r}, expected {args.scenario_type!r}")
        prediction = row.get("prediction")
        if not isinstance(prediction, dict):
            errors.append(f"{expected_id}: prediction must be an object")
            continue
        missing = [key for key in required if key not in prediction]
        if missing:
            errors.append(f"{expected_id}: missing prediction fields {missing}")
        if "answer" in row:
            errors.append(f"{expected_id}: output row must not contain gold answer")

    extra_ids = sorted(set(output_by_id) - set(expected_ids))
    for extra_id in extra_ids:
        errors.append(f"{extra_id}: unexpected output id")

    if errors:
        print("FAIL llm baseline validation")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "scenario_type": args.scenario_type,
                "case_count": len(input_rows),
                "required_prediction_fields": required,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return normalize_space(value)
    return normalize_space(json.dumps(value, ensure_ascii=False, sort_keys=True))


def _sequence_similarity(left: Any, right: Any) -> float:
    left_text = _stringify(left)
    right_text = _stringify(right)
    if not left_text and not right_text:
        return 1.0
    if not left_text or not right_text:
        return 0.0
    if left_text in right_text or right_text in left_text:
        return 1.0
    return round(SequenceMatcher(None, left_text, right_text).ratio(), 3)


def _text_collection_similarity(expected: Iterable[Any], predicted: Iterable[Any]) -> float:
    expected_items = [_stringify(item) for item in expected if _stringify(item)]
    predicted_items = [_stringify(item) for item in predicted if _stringify(item)]
    if not expected_items and not predicted_items:
        return 1.0
    if not expected_items or not predicted_items:
        return 0.0
    scores = []
    for expected in expected_items:
        scores.append(max(_sequence_similarity(expected, predicted) for predicted in predicted_items))
    return round(sum(scores) / max(1, len(scores)), 3)


def _field_texts(items: Iterable[Any], keys: Iterable[str]) -> List[str]:
    texts: List[str] = []
    for item in items:
        if isinstance(item, dict):
            parts = [_stringify(item.get(key)) for key in keys if _stringify(item.get(key))]
            if parts:
                texts.append(" ".join(parts))
        else:
            text = _stringify(item)
            if text:
                texts.append(text)
    return texts


def _risk_score_match(expected: Any, predicted: Any) -> float:
    expected_bin = risk_bin(str(expected or "low"))
    predicted_bin = risk_bin(str(predicted or "low"))
    if expected_bin == predicted_bin:
        return 1.0
    adjacent = {
        ("low", "medium"),
        ("medium", "low"),
        ("medium", "high"),
        ("high", "medium"),
    }
    return 0.5 if (expected_bin, predicted_bin) in adjacent else 0.0


def _evidence_span_score(answer: Dict[str, Any], prediction: Dict[str, Any], text: str) -> float:
    expected = [str(item) for item in _as_list(answer.get("evidence_spans")) if isinstance(item, str)]
    predicted = [str(item) for item in _as_list(prediction.get("evidence_spans")) if isinstance(item, str)]
    if not expected:
        expected = [
            str(item.get("span"))
            for item in _as_list(answer.get("evidence_pack"))
            if isinstance(item, dict) and item.get("span")
        ]
    if not expected and not predicted:
        return 1.0
    if not predicted:
        return 0.0
    grounded_predicted = [span for span in predicted if span in text]
    grounding = len(grounded_predicted) / max(1, len(predicted))
    coverage = _text_collection_similarity(expected, predicted)
    return round(coverage * 0.7 + grounding * 0.3, 3)


def _numeric_window_score(expected: Dict[str, Any], predicted: Dict[str, Any], start_key: str, end_key: str) -> float:
    if not isinstance(expected, dict) or not isinstance(predicted, dict):
        return 0.0
    try:
        expected_start = int(expected.get(start_key, 0))
        expected_end = int(expected.get(end_key, expected_start))
        predicted_start = int(predicted.get(start_key, 0))
        predicted_end = int(predicted.get(end_key, predicted_start))
    except (TypeError, ValueError):
        return 0.0
    if predicted_start <= expected_end and predicted_end >= expected_start:
        return 1.0
    if abs(predicted_start - expected_start) <= 1 or abs(predicted_end - expected_end) <= 1:
        return 0.5
    return 0.0


def _stage_window_score(expected: Dict[str, Any], predicted: Dict[str, Any]) -> float:
    if not isinstance(expected, dict) or not isinstance(predicted, dict):
        return 0.0
    scores = [
        _sequence_similarity(expected.get("open_stage"), predicted.get("open_stage")),
        _sequence_similarity(expected.get("close_stage"), predicted.get("close_stage")),
        _sequence_similarity(expected.get("label"), predicted.get("label")),
    ]
    return round(sum(scores) / max(1, len(scores)), 3)


def _score_fraud_prediction(truth: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    answer = truth.get("answer", {}) if isinstance(truth.get("answer"), dict) else {}
    text = truth.get("input", {}).get("text", "")
    expected_fork = (
        answer.get("fork_points", [{}])[0].get("type")
        if isinstance(answer.get("fork_points"), list) and answer.get("fork_points")
        else answer.get("expected_fork", "no_fork_needed")
    )
    predicted_fork = (
        prediction.get("fork_points", [{}])[0].get("type")
        if isinstance(prediction.get("fork_points"), list) and prediction.get("fork_points")
        else "missing"
    )
    fpa = 1.0 if (expected_fork in FORK_FAMILY_BINARY) == (predicted_fork in FORK_FAMILY_BINARY) else 0.0

    expected_assets = [
        item.get("type") for item in _as_list(answer.get("asset_targets"))
        if isinstance(item, dict) and item.get("type")
    ]
    predicted_assets = [
        item.get("type") for item in _as_list(prediction.get("asset_targets"))
        if isinstance(item, dict) and item.get("type")
    ]
    expected_set = set(expected_assets)
    predicted_set = set(predicted_assets)
    ata = round(len(expected_set & predicted_set) / max(1, len(expected_set)), 3) if expected_set else 1.0
    rca = _risk_score_match(answer.get("risk_level"), prediction.get("risk_level"))
    iwa = _numeric_window_score(
        answer.get("intervention_window", {}),
        prediction.get("intervention_window", {}),
        "start_turn",
        "end_turn",
    )
    ear = _evidence_span_score(answer, prediction, text)
    action_score = _sequence_similarity(answer.get("expected_safe_action"), prediction.get("expected_safe_action"))
    warning_score = _sequence_similarity(answer.get("expected_warning"), prediction.get("expected_warning"))
    res = round(fpa * 0.20 + ata * 0.16 + rca * 0.16 + iwa * 0.14 + ear * 0.18 + action_score * 0.10 + warning_score * 0.06, 3)
    return {
        "FPA": fpa,
        "ATA": ata,
        "RCA": rca,
        "IWA": iwa,
        "EAR": ear,
        "ASA": action_score,
        "WSA": warning_score,
        "RES": res,
        "expected_fork": expected_fork,
        "predicted_fork": predicted_fork,
        "expected_risk": risk_bin(str(answer.get("risk_level", "low"))),
        "predicted_risk": risk_bin(str(prediction.get("risk_level", "low"))),
        "expected_assets": expected_assets,
        "predicted_assets": predicted_assets,
    }


def _score_public_opinion_prediction(truth: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    answer = truth.get("answer", {}) if isinstance(truth.get("answer"), dict) else {}
    text = truth.get("input", {}).get("text", "")
    nss = _text_collection_similarity(
        _field_texts(_as_list(answer.get("narrative_threads")), ["claim", "risk"]),
        _field_texts(_as_list(prediction.get("narrative_threads")), ["claim", "risk"]),
    )
    eas_emotion = 1.0 if (answer.get("emotion_signal", {}) or {}).get("dominant_emotion") == (prediction.get("emotion_signal", {}) or {}).get("dominant_emotion") else 0.0
    eas_level = 1.0 if (answer.get("emotion_signal", {}) or {}).get("amplification_level") == (prediction.get("emotion_signal", {}) or {}).get("amplification_level") else 0.0
    eas = round(eas_emotion * 0.55 + eas_level * 0.45, 3)
    ugs = _text_collection_similarity(
        _field_texts(_as_list(answer.get("uncertainty_points")), ["description"]),
        _field_texts(_as_list(prediction.get("uncertainty_points")), ["description"]),
    )
    ogs_status = 1.0 if (answer.get("official_response_gap", {}) or {}).get("status") == (prediction.get("official_response_gap", {}) or {}).get("status") else 0.0
    ogs_desc = _sequence_similarity(
        (answer.get("official_response_gap", {}) or {}).get("description"),
        (prediction.get("official_response_gap", {}) or {}).get("description"),
    )
    ogs = round(ogs_status * 0.6 + ogs_desc * 0.4, 3)
    rca = _risk_score_match(answer.get("propagation_risk_level"), prediction.get("propagation_risk_level"))
    iwa = _stage_window_score(answer.get("best_intervention_window", {}), prediction.get("best_intervention_window", {}))
    ias = _sequence_similarity(answer.get("expected_intervention_action"), prediction.get("expected_intervention_action"))
    sps = _sequence_similarity(answer.get("expected_safe_public_action"), prediction.get("expected_safe_public_action"))
    ear = _evidence_span_score(answer, prediction, text)
    res = round(nss * 0.16 + eas * 0.12 + ugs * 0.14 + ogs * 0.12 + rca * 0.12 + iwa * 0.10 + ias * 0.10 + sps * 0.06 + ear * 0.08, 3)
    return {
        "NSS": nss,
        "EAS": eas,
        "UGS": ugs,
        "OGS": ogs,
        "RCA": rca,
        "IWA": iwa,
        "IAS": ias,
        "SPS": sps,
        "EAR": ear,
        "RES": res,
        "expected_risk": risk_bin(str(answer.get("propagation_risk_level", "low"))),
        "predicted_risk": risk_bin(str(prediction.get("propagation_risk_level", "low"))),
    }


def _score_event_propagation_prediction(truth: Dict[str, Any], prediction: Dict[str, Any]) -> Dict[str, Any]:
    answer = truth.get("answer", {}) if isinstance(truth.get("answer"), dict) else {}
    text = truth.get("input", {}).get("text", "")
    ovs_type = 1.0 if (answer.get("origin_node", {}) or {}).get("type") == (prediction.get("origin_node", {}) or {}).get("type") else 0.0
    ovs_desc = _sequence_similarity(
        (answer.get("origin_node", {}) or {}).get("description"),
        (prediction.get("origin_node", {}) or {}).get("description"),
    )
    ovs = round(ovs_type * 0.6 + ovs_desc * 0.4, 3)
    ans = _text_collection_similarity(
        _field_texts(_as_list(answer.get("amplifier_nodes")), ["type", "description"]),
        _field_texts(_as_list(prediction.get("amplifier_nodes")), ["type", "description"]),
    )
    pcs = _text_collection_similarity(
        _field_texts(_as_list(answer.get("propagation_path")), ["node", "action", "risk_state"]),
        _field_texts(_as_list(prediction.get("propagation_path")), ["node", "action", "risk_state"]),
    )
    dcs = _text_collection_similarity(
        _field_texts(_as_list(answer.get("distortion_points")), ["description"]),
        _field_texts(_as_list(prediction.get("distortion_points")), ["description"]),
    )
    rca = _risk_score_match(answer.get("coverage_risk"), prediction.get("coverage_risk"))
    cws = _numeric_window_score(
        answer.get("containment_window", {}),
        prediction.get("containment_window", {}),
        "open_step",
        "close_step",
    )
    cas = _sequence_similarity(answer.get("expected_containment_action"), prediction.get("expected_containment_action"))
    ear = _evidence_span_score(answer, prediction, text)
    res = round(ovs * 0.14 + ans * 0.14 + pcs * 0.16 + dcs * 0.12 + rca * 0.12 + cws * 0.12 + cas * 0.10 + ear * 0.10, 3)
    return {
        "OVS": ovs,
        "ANS": ans,
        "PCS": pcs,
        "DCS": dcs,
        "RCA": rca,
        "CWS": cws,
        "CAS": cas,
        "EAR": ear,
        "RES": res,
        "expected_risk": risk_bin(str(answer.get("coverage_risk", "low"))),
        "predicted_risk": risk_bin(str(prediction.get("coverage_risk", "low"))),
    }


SCENARIO_SCORE_FUNCTIONS = {
    "fraud_im": _score_fraud_prediction,
    "public_opinion": _score_public_opinion_prediction,
    "event_propagation": _score_event_propagation_prediction,
}


def compute_prediction_scores(
    truth_rows: List[Dict[str, Any]],
    prediction_rows: List[Dict[str, Any]],
    scenario_type: str,
    layer: str,
) -> Dict[str, Any]:
    predictions = {row.get("id"): row for row in prediction_rows if row.get("id")}
    score_fn = SCENARIO_SCORE_FUNCTIONS[scenario_type]
    required = LLM_BASELINE_REQUIRED_PREDICTION_FIELDS.get(scenario_type, [])
    per_case: List[Dict[str, Any]] = []

    for truth in truth_rows:
        row_id = truth.get("id")
        output = predictions.get(row_id)
        if not output:
            per_case.append({"id": row_id, "ok": False, "missing": True, "RES": 0.0})
            continue
        prediction = output.get("prediction") if isinstance(output.get("prediction"), dict) else {}
        missing_fields = [key for key in required if key not in prediction]
        scores = score_fn(truth, prediction)
        per_case.append(
            {
                "id": row_id,
                "ok": True,
                "confidence": prediction.get("confidence"),
                "missing_prediction_fields": missing_fields,
                **scores,
            }
        )

    metric_names = sorted(
        {
            key
            for item in per_case
            for key, value in item.items()
            if isinstance(value, (int, float)) and key not in {"confidence"} and key.isupper()
        }
    )
    ok_cases = [item for item in per_case if item.get("ok")]
    return {
        "layer": layer,
        "benchmark_version": "v0.1",
        "scenario_type": scenario_type,
        "case_count": len(per_case),
        "scored_case_count": len(ok_cases),
        "format_success_rate": round((len(ok_cases) / max(1, len(per_case))) * 100, 2),
        "complete_schema_rate": round(
            (
                sum(1 for item in ok_cases if not item.get("missing_prediction_fields"))
                / max(1, len(per_case))
            ) * 100,
            2,
        ),
        **{name: round((_mean(item.get(name, 0.0) for item in ok_cases)) * 100, 2) for name in metric_names if name != "RES"},
        "RES": _mean(item.get("RES", 0.0) for item in ok_cases),
        "per_case": per_case,
    }


def score_predictions(args: argparse.Namespace) -> int:
    truth_rows = load_jsonl(args.annotated)
    prediction_rows = load_jsonl(args.predictions)
    metrics = compute_prediction_scores(
        truth_rows=truth_rows,
        prediction_rows=prediction_rows,
        scenario_type=args.scenario_type,
        layer=args.layer,
    )
    write_json(args.output, metrics)
    summary = {key: value for key, value in metrics.items() if key != "per_case"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"prediction scores: {args.output}")
    return 0


# ---------------------------------------------------------------------------
# Layer 2 scoring: Runtime Evaluation Score
# ---------------------------------------------------------------------------

ASSET_TYPE_MAP = {
    "funds": "asset:funds", "credential": "asset:credential",
    "device_control": "asset:device", "identity": "asset:identity",
    "social_support": "asset:social",
}

FORK_FAMILY_BINARY = {"no_fork_needed"}  # fork types treated as "no intervention needed"


def evaluate_runtime(args: argparse.Namespace) -> int:
    """Full runtime evaluation against graph-support benchmark truth."""
    truth_rows = load_jsonl(args.annotated)
    run_rows = load_jsonl(args.run_output)
    predictions = {row["id"]: row for row in run_rows if row.get("id")}
    per_case: List[Dict[str, Any]] = []

    for truth in truth_rows:
        row_id = truth["id"]
        answer = truth.get("answer", {})
        run_row = predictions.get(row_id, {})
        prediction = run_row.get("prediction", {})
        runtime_ok = bool(run_row.get("ok"))

        expected_fork = (
            answer.get("fork_points", [{}])[0].get("type")
            if isinstance(answer.get("fork_points"), list) and answer.get("fork_points")
            else answer.get("expected_fork", "no_fork_needed")
        )
        expected_risk = answer.get("risk_level", "low")
        expected_is_fraud = bool(answer.get("is_fraud"))
        expected_assets = [
            item.get("type") for item in (answer.get("asset_targets") if isinstance(answer.get("asset_targets"), list) else [])
            if isinstance(item, dict)
        ]
        expected_trajectory_gap = float(
            (answer.get("counterfactual_expectation") or {}).get("expected_trajectory_gap", 0.1)
        )
        expected_irreversibility_loss = float(
            (answer.get("counterfactual_expectation") or {}).get("expected_irreversibility_loss", 0.0)
        )
        expected_window_end = int((answer.get("intervention_window") or {}).get("end_turn", 0))

        if not runtime_ok:
            per_case.append({
                "id": row_id, "runtime_ok": False,
                "FPA": 0.0, "ATA": 0.0, "CPA": 0.0, "IWA": 0.0, "RCA": 0.0, "EAR": 0.0,
                "expected_fork": expected_fork, "predicted_fork": "missing",
                "expected_risk": expected_risk, "predicted_risk": "missing",
                "expected_assets": expected_assets, "predicted_assets": [],
                "anomaly": "runtime_failed",
            })
            continue

        # FPA: Fork Point Accuracy — binary "fork needed" vs "no fork needed"
        predicted_fork_binary = prediction.get("predicted_fork_family", "missing")
        expected_no_fork = expected_fork in FORK_FAMILY_BINARY
        predicted_no_fork = predicted_fork_binary == "no_fork_needed"
        fpa = 1.0 if expected_no_fork == predicted_no_fork else 0.0

        # ATA: Asset Target Accuracy — overlap of predicted vs expected asset types
        predicted_assets_raw = prediction.get("predicted_asset_types", [])
        if not predicted_assets_raw:
            predicted_bin = prediction.get("risk_bin", "low")
            if predicted_bin in {"high", "medium"} and expected_is_fraud:
                predicted_assets_raw = ["funds"]
            else:
                predicted_assets_raw = []
        expected_set = set(expected_assets)
        predicted_set = set(predicted_assets_raw)
        ata = round(len(expected_set & predicted_set) / max(1, len(expected_set)), 2) if expected_set else 1.0

        # CPA: Counterfactual Path Accuracy — trajectory gap within tolerance
        predicted_gap = float(prediction.get("trajectory_gap", 0.0))
        cpa = 1.0 if abs(predicted_gap - expected_trajectory_gap) <= 0.20 else (
            0.5 if abs(predicted_gap - expected_trajectory_gap) <= 0.35 else 0.0)

        # IWA: Intervention Window Accuracy — predicted window captures the expected window
        predicted_step = int(prediction.get("critical_bifurcation_step", 0))
        window_start = int((answer.get("intervention_window") or {}).get("start_turn", 0))
        iwa = 1.0 if window_start <= 1 and predicted_step <= expected_window_end + 1 else (
            0.5 if predicted_step <= expected_window_end + 2 else 0.0)

        # RCA: Risk Calibration Accuracy — risk bin match
        predicted_risk = prediction.get("risk_bin", "low")
        expected_risk_bin = risk_bin(expected_risk)
        rca = 1.0 if predicted_risk == expected_risk_bin else (
            0.5 if (expected_risk_bin == "high" and predicted_risk == "medium") or
                   (expected_risk_bin == "medium" and predicted_risk in {"high", "low"}) else 0.0)

        # EAR: Evidence Attribution Rate — keyword overlap
        expected_keywords = answer.get("evidence_keywords", [])
        predicted_evidence = prediction.get("evidence_text", "")
        keyword_hits = contains_any(predicted_evidence, expected_keywords)
        ear = round(keyword_hits / max(1, len(expected_keywords)), 2)

        per_case.append({
            "id": row_id, "runtime_ok": True,
            "FPA": fpa, "ATA": ata, "CPA": cpa, "IWA": iwa, "RCA": rca, "EAR": ear,
            "expected_fork": expected_fork, "predicted_fork_family": predicted_fork_binary,
            "expected_risk": expected_risk_bin, "predicted_risk": predicted_risk,
            "expected_assets": expected_assets, "predicted_assets": list(predicted_set),
            "expected_trajectory_gap": expected_trajectory_gap,
            "predicted_trajectory_gap": predicted_gap,
            "anomaly": None,
        })

    def pct(values: Iterable[float]) -> float:
        values = list(values)
        return round((sum(values) / max(1, len(values))) * 100, 2)

    def mean(values: Iterable[float]) -> float:
        values = list(values)
        return round(sum(values) / max(1, len(values)), 3)

    latencies = [float(item.get("latency_ms", 0)) for item in run_rows if item.get("latency_ms") is not None]
    runtime_ok_cases = [item for item in per_case if item["runtime_ok"]]

    metrics = {
        "layer": "runtime_evaluation",
        "benchmark_version": "v0.1",
        "case_count": len(per_case),
        "runtime_success_rate": pct(1.0 if item["runtime_ok"] else 0.0 for item in per_case) if per_case else 0.0,
        "FPA": pct(item["FPA"] for item in runtime_ok_cases) if runtime_ok_cases else 0.0,
        "ATA": pct(item["ATA"] for item in runtime_ok_cases) if runtime_ok_cases else 0.0,
        "CPA": pct(item["CPA"] for item in runtime_ok_cases) if runtime_ok_cases else 0.0,
        "IWA": pct(item["IWA"] for item in runtime_ok_cases) if runtime_ok_cases else 0.0,
        "RCA": pct(item["RCA"] for item in runtime_ok_cases) if runtime_ok_cases else 0.0,
        "EAR": pct(item["EAR"] for item in runtime_ok_cases) if runtime_ok_cases else 0.0,
        "RES": mean(
            (item["FPA"] * 0.20 + item["ATA"] * 0.18 + item["CPA"] * 0.18 +
             item["IWA"] * 0.14 + item["RCA"] * 0.15 + item["EAR"] * 0.15)
            for item in runtime_ok_cases
        ) if runtime_ok_cases else 0.0,
        "end_to_end_ms_p50": round(statistics.median(latencies), 3) if len(latencies) >= 2 else None,
        "end_to_end_ms_p95": round(statistics.quantiles(latencies, n=20)[18], 3) if len(latencies) >= 20 else None,
        "per_case": per_case,
    }
    write_json(args.output, metrics)
    summary = {k: v for k, v in metrics.items() if k != "per_case"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"runtime evaluation: {args.output}")
    return 0


def all_local(args: argparse.Namespace) -> int:
    steps = [
        ("validate", validate(argparse.Namespace(raw=RAW_PATH, annotated=ANNOTATED_PATH))),
        ("aqs", score_annotation_quality(argparse.Namespace(
            annotated=ANNOTATED_PATH, output=BENCHMARK_ROOT / "outputs" / "aqs_v0.1.json"))),
        (
            "make-review-input",
            make_review_input(
                argparse.Namespace(
                    raw=RAW_PATH,
                    annotated=ANNOTATED_PATH,
                    output=REVIEW_REQUEST_PATH,
                    stub_output=REVIEW_STUB_PATH,
                )
            ),
        ),
        (
            "report",
            make_report(
                argparse.Namespace(
                    annotated=ANNOTATED_PATH,
                    review=REVIEW_PATH,
                    output=REPORT_PATH,
                )
            ),
        ),
    ]
    failed = [name for name, code in steps if code != 0]
    if failed:
        print(f"all-local stopped, failed steps: {failed}")
        return 1
    if args.with_runtime:
        run_code = run_runtime(argparse.Namespace(annotated=ANNOTATED_PATH, output=RUN_OUTPUT_PATH))
        if run_code != 0:
            return run_code
        return evaluate_runtime(argparse.Namespace(annotated=ANNOTATED_PATH, run_output=RUN_OUTPUT_PATH, output=METRICS_PATH))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Miro-CogSec benchmark v0.1 pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_cmd = subparsers.add_parser("build", help="Clean, dedupe, and sample a JSONL/CSV/TSV source")
    build_cmd.add_argument("--input", type=Path, default=RAW_PATH)
    build_cmd.add_argument("--output", type=Path, default=RAW_PATH)
    build_cmd.add_argument("--limit", type=int, default=20)
    build_cmd.set_defaults(func=build_sample)

    enrich_cmd = subparsers.add_parser("enrich", help="Upgrade first-pass annotations into graph-support annotations")
    enrich_cmd.add_argument("--input", type=Path, default=ANNOTATED_PATH)
    enrich_cmd.add_argument("--output", type=Path, default=ANNOTATED_PATH)
    enrich_cmd.set_defaults(func=enrich_annotations)

    validate_cmd = subparsers.add_parser("validate", help="Validate raw and annotated JSONL files")
    validate_cmd.add_argument("--raw", type=Path, default=RAW_PATH)
    validate_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    validate_cmd.set_defaults(func=validate)

    aqs_cmd = subparsers.add_parser("aqs", help="Score annotation quality (ECR/FVS/WCS/TRS/RFS) without runtime")
    aqs_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    aqs_cmd.add_argument("--output", type=Path, default=BENCHMARK_ROOT / "outputs" / "aqs_v0.1.json")
    aqs_cmd.set_defaults(func=score_annotation_quality)

    scenario_aqs_cmd = subparsers.add_parser(
        "scenario-aqs",
        help="Score public_opinion/event_propagation seed-gold annotation quality",
    )
    scenario_aqs_cmd.add_argument("--input", type=Path, required=True)
    scenario_aqs_cmd.add_argument("--scenario-type", choices=["public_opinion", "event_propagation"], default=None)
    scenario_aqs_cmd.add_argument("--output", type=Path, required=True)
    scenario_aqs_cmd.set_defaults(func=score_scenario_annotation_quality)

    baseline_input_cmd = subparsers.add_parser("make-baseline-input", help="Create answer-free JSONL for LLM-only baselines")
    baseline_input_cmd.add_argument("--input", type=Path, required=True)
    baseline_input_cmd.add_argument("--output", type=Path, required=True)
    baseline_input_cmd.add_argument("--scenario-type", default=None)
    baseline_input_cmd.set_defaults(func=make_baseline_input)

    baseline_validate_cmd = subparsers.add_parser("validate-llm-baseline", help="Validate LLM-only baseline output JSONL")
    baseline_validate_cmd.add_argument("--input", type=Path, required=True, help="Answer-free baseline input JSONL")
    baseline_validate_cmd.add_argument("--output", type=Path, required=True, help="LLM baseline output JSONL")
    baseline_validate_cmd.add_argument(
        "--scenario-type",
        choices=["fraud_im", "public_opinion", "event_propagation"],
        required=True,
    )
    baseline_validate_cmd.set_defaults(func=validate_llm_baseline)

    baseline_score_cmd = subparsers.add_parser("score-llm-baseline", help="Score LLM-only baseline predictions against gold answers")
    baseline_score_cmd.add_argument("--annotated", type=Path, required=True, help="Gold annotated JSONL")
    baseline_score_cmd.add_argument("--predictions", type=Path, required=True, help="LLM baseline output JSONL")
    baseline_score_cmd.add_argument("--output", type=Path, required=True, help="Metrics JSON output")
    baseline_score_cmd.add_argument(
        "--scenario-type",
        choices=["fraud_im", "public_opinion", "event_propagation"],
        required=True,
    )
    baseline_score_cmd.set_defaults(func=score_predictions, layer="llm_baseline_evaluation")

    scenario_score_cmd = subparsers.add_parser("score-scenario-predictions", help="Score scenario prediction JSONL against gold answers")
    scenario_score_cmd.add_argument("--annotated", type=Path, required=True, help="Gold annotated JSONL")
    scenario_score_cmd.add_argument("--predictions", type=Path, required=True, help="Prediction JSONL with id and prediction object")
    scenario_score_cmd.add_argument("--output", type=Path, required=True, help="Metrics JSON output")
    scenario_score_cmd.add_argument(
        "--scenario-type",
        choices=["fraud_im", "public_opinion", "event_propagation"],
        required=True,
    )
    scenario_score_cmd.add_argument("--layer", default="scenario_prediction_evaluation")
    scenario_score_cmd.set_defaults(func=score_predictions)

    review_cmd = subparsers.add_parser("make-review-input", help="Create second-model review JSONL and empty review stub")
    review_cmd.add_argument("--raw", type=Path, default=RAW_PATH)
    review_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    review_cmd.add_argument("--output", type=Path, default=REVIEW_REQUEST_PATH)
    review_cmd.add_argument("--stub-output", type=Path, default=REVIEW_STUB_PATH)
    review_cmd.set_defaults(func=make_review_input)

    report_cmd = subparsers.add_parser("report", help="Create human-readable review Markdown")
    report_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    report_cmd.add_argument("--review", type=Path, default=REVIEW_PATH)
    report_cmd.add_argument("--output", type=Path, default=REPORT_PATH)
    report_cmd.set_defaults(func=make_report)

    run_cmd = subparsers.add_parser("run", help="Run local Miro-CogSec runtime on the benchmark")
    run_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    run_cmd.add_argument("--output", type=Path, default=RUN_OUTPUT_PATH)
    run_cmd.set_defaults(func=run_runtime)

    eval_cmd = subparsers.add_parser("evaluate", help="Full runtime evaluation (FPA/ATA/CPA/IWA/RCA/EAR)")
    eval_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    eval_cmd.add_argument("--run-output", type=Path, default=RUN_OUTPUT_PATH)
    eval_cmd.add_argument("--output", type=Path, default=METRICS_PATH)
    eval_cmd.set_defaults(func=evaluate_runtime)

    score_cmd = subparsers.add_parser("score", help="[deprecated] Alias for evaluate")
    score_cmd.add_argument("--annotated", type=Path, default=ANNOTATED_PATH)
    score_cmd.add_argument("--run-output", type=Path, default=RUN_OUTPUT_PATH)
    score_cmd.add_argument("--output", type=Path, default=METRICS_PATH)
    score_cmd.set_defaults(func=evaluate_runtime)

    all_cmd = subparsers.add_parser("all-local", help="Run validate, aqs, review-input, report; --with-runtime adds run+evaluate")
    all_cmd.add_argument("--with-runtime", action="store_true")
    all_cmd.set_defaults(func=all_local)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())

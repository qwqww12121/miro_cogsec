"""Build a legacy-compatible CogSec benchmark JSONL.

This script keeps the original scripts/ entrypoint alive while using the richer
benchmark v0.1 annotations as the source of truth.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, Iterable, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ANNOTATED = PROJECT_ROOT / "benchmark" / "data" / "cogsec_v0.1.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "benchmark" / "cogsec_eval_sample.jsonl"


FALLBACK_ROWS: List[Dict[str, Any]] = [
    {
        "id": "cogsec-legacy-0001",
        "scenario": "客服称快递丢失，要求共享屏幕并填写银行卡信息。",
        "label": "refund_impersonation",
        "expected_risk_level": "critical",
        "expected_fork_type": "verification_code",
        "expected_alert": True,
        "expected_min_warning_step": 1,
        "expected_evidence_keywords": ["客服", "共享屏幕", "银行卡"],
    },
    {
        "id": "cogsec-legacy-0002",
        "scenario": "陌生人推荐稳赚理财群，催促今天内转账。",
        "label": "investment_fraud",
        "expected_risk_level": "high",
        "expected_fork_type": "transfer_money",
        "expected_alert": True,
        "expected_min_warning_step": 1,
        "expected_evidence_keywords": ["稳赚", "理财群", "转账"],
    },
    {
        "id": "cogsec-legacy-0003",
        "scenario": "用户通过官方客服电话回拨确认，拒绝提供验证码。",
        "label": "benign_verified_behavior",
        "expected_risk_level": "low",
        "expected_fork_type": "no_fork_needed",
        "expected_alert": False,
        "expected_min_warning_step": 0,
        "expected_evidence_keywords": ["官方", "拒绝", "验证码"],
    },
]


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped:
                rows.append(json.loads(stripped))
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def risk_label(answer: Dict[str, Any]) -> str:
    risk_level = str(answer.get("risk_level", "low")).lower()
    fraud_type = answer.get("fraud_type") or "unknown"
    return f"{risk_level}_{fraud_type}"


def convert_annotation(row: Dict[str, Any]) -> Dict[str, Any]:
    answer = row.get("answer", {})
    fork_points = answer.get("fork_points") if isinstance(answer.get("fork_points"), list) else []
    primary_fork = fork_points[0] if fork_points and isinstance(fork_points[0], dict) else {}
    window = answer.get("intervention_window") if isinstance(answer.get("intervention_window"), dict) else {}
    cf = answer.get("counterfactual_expectation") if isinstance(answer.get("counterfactual_expectation"), dict) else {}
    assets = answer.get("asset_targets") if isinstance(answer.get("asset_targets"), list) else []

    return {
        "id": row.get("id"),
        "scenario": row.get("input", {}).get("text", ""),
        "label": risk_label(answer),
        "expected_risk_level": answer.get("risk_level", "low"),
        "expected_fork_type": primary_fork.get("type", answer.get("expected_fork", "no_fork_needed")),
        "expected_runtime_fork_type": (primary_fork.get("runtime_alignment") or {}).get("runtime_type"),
        "expected_alert": bool(answer.get("is_fraud")),
        "expected_min_warning_step": int(window.get("start_turn", 0) or 0),
        "expected_window_end": int(window.get("end_turn", 0) or 0),
        "expected_evidence_keywords": answer.get("evidence_keywords", []),
        "expected_asset_types": [item.get("type") for item in assets if isinstance(item, dict) and item.get("type")],
        "expected_trajectory_gap": cf.get("expected_trajectory_gap", 0.0),
        "expected_irreversibility_loss": cf.get("expected_irreversibility_loss", 0.0),
        "source": row.get("source", {}),
    }


def build_dataset(input_path: Path, sample_size: int, seed: int) -> List[Dict[str, Any]]:
    annotated_rows = load_jsonl(input_path)
    if not annotated_rows:
        return FALLBACK_ROWS[:sample_size]

    rows = [convert_annotation(row) for row in annotated_rows]
    if sample_size and sample_size < len(rows):
        rng = random.Random(seed)
        rows = rng.sample(rows, sample_size)
        rows.sort(key=lambda item: item.get("id", ""))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a CogSec evaluation JSONL from benchmark v0.1 annotations")
    parser.add_argument("--input", type=Path, default=DEFAULT_ANNOTATED, help="source annotated JSONL")
    parser.add_argument("--size", type=int, default=20, help="maximum number of rows to export")
    parser.add_argument("--seed", type=int, default=42, help="sampling seed")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="output JSONL")
    args = parser.parse_args()

    rows = build_dataset(args.input, args.size, args.seed)
    write_jsonl(args.output, rows)
    print(f"dataset built: {args.output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

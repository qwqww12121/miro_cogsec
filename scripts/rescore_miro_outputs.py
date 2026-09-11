"""重新用 benchmark_prediction 字段打分（修正 prediction 字段读取错误）。

问题：compute_prediction_scores 读 prediction 字段（runtime 通用字段），
     但场景专属内容（event_summary / narrative_threads / origin_node 等）在 benchmark_prediction 里。
解法：把每行的 benchmark_prediction 注入为 prediction，再跑打分函数。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from benchmark.cogsec_benchmark import compute_prediction_scores  # noqa: E402

BENCHMARK_ROOT = ROOT / "benchmark"

SCENARIOS = {
    "fraud_im": {
        "gold": BENCHMARK_ROOT / "data" / "cogsec_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_fraud_im_after_adapter_v0.1.jsonl",
        "output": BENCHMARK_ROOT / "outputs" / "api_fraud_im_answer_scores_after_adapter_v0.1.json",
    },
    "public_opinion": {
        "gold": BENCHMARK_ROOT / "data" / "public_opinion_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_public_opinion_after_adapter_v0.1.jsonl",
        "output": BENCHMARK_ROOT / "outputs" / "api_public_opinion_answer_scores_after_adapter_v0.1.json",
    },
    "event_propagation": {
        "gold": BENCHMARK_ROOT / "data" / "event_propagation_v0.1.jsonl",
        "miro": BENCHMARK_ROOT / "outputs" / "api_event_propagation_after_adapter_v0.1.jsonl",
        "output": BENCHMARK_ROOT / "outputs" / "api_event_propagation_answer_scores_after_adapter_v0.1.json",
    },
}


def load_jsonl(path: Path):
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["all"] + list(SCENARIOS), default="all")
    args = parser.parse_args()

    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    for scenario in selected:
        cfg = SCENARIOS[scenario]
        truth_rows = load_jsonl(cfg["gold"])
        miro_rows = load_jsonl(cfg["miro"])

        # 把每行的 benchmark_prediction 注入为 prediction
        patched = []
        for row in miro_rows:
            bp = row.get("benchmark_prediction")
            if isinstance(bp, dict) and bp:
                patched.append({**row, "prediction": bp})
            else:
                patched.append(row)

        scores = compute_prediction_scores(
            truth_rows=truth_rows,
            prediction_rows=patched,
            scenario_type=scenario,
            layer="api_answer_score_after_adapter",
        )
        cfg["output"].write_text(json.dumps(scores, ensure_ascii=False, indent=2), encoding="utf-8")
        summary = {k: v for k, v in scores.items() if k != "per_case"}
        print(f"[{scenario}] RES={scores.get('RES')}  {summary}")


if __name__ == "__main__":
    main()

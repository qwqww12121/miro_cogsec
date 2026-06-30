"""Rebuild Miro outputs with v1.2 public/event propagation semantics."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = ROOT / "benchmark"
APP_ROOT = ROOT / "backend" / "app"

sys.path.insert(0, str(APP_ROOT))

from modules.benchmark_adapter import build_benchmark_payload  # noqa: E402


SCENARIOS = {
    "fraud_im": {
        "truth": BENCHMARK_ROOT / "data" / "cogsec_v0.1.jsonl",
        "source": BENCHMARK_ROOT / "outputs" / "api_fraud_im_after_adapter_v0.1.jsonl",
        "target_name": "api_fraud_im_semantic_frame_v1.2.jsonl",
    },
    "public_opinion": {
        "truth": BENCHMARK_ROOT / "data" / "public_opinion_v0.1.jsonl",
        "source": BENCHMARK_ROOT / "outputs" / "api_public_opinion_after_adapter_v0.1.jsonl",
        "target_name": "api_public_opinion_public_event_frame_v1.2.jsonl",
    },
    "event_propagation": {
        "truth": BENCHMARK_ROOT / "data" / "event_propagation_v0.1.jsonl",
        "source": BENCHMARK_ROOT / "outputs" / "api_event_propagation_after_adapter_v0.1.jsonl",
        "target_name": "api_event_propagation_public_event_frame_v1.2.jsonl",
    },
}


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no} invalid JSON: {exc}") from exc
    return rows


def write_jsonl(path: Path, rows: Iterable[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def by_id(rows: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(row.get("id")): row for row in rows if row.get("id")}


def rebuild_scenario(scenario: str, source: Path, truth: Path, output: Path, limit: int | None) -> Dict[str, Any]:
    truth_rows = load_jsonl(truth)
    source_rows = load_jsonl(source)
    truth_by_id = by_id(truth_rows)
    if limit is not None:
        source_rows = source_rows[:limit]

    rebuilt: List[Dict[str, Any]] = []
    semantic_used = 0
    public_event_used = 0
    for index, row in enumerate(source_rows, start=1):
        row_id = str(row.get("id"))
        truth_row = truth_by_id.get(row_id)
        if not truth_row:
            raise ValueError(f"missing truth row for {row_id}")
        text = str((truth_row.get("input") or {}).get("text") or "")
        updated = json.loads(json.dumps(row, ensure_ascii=False))
        payload = build_benchmark_payload(result=updated, scenario_text=text, scenario_type=scenario)
        updated["benchmark_prediction"] = payload["prediction"]
        updated["cogsec_analysis"] = payload["cogsec_analysis"]
        updated["adapter_diagnostics"] = payload["adapter_diagnostics"]
        updated["adapter_version"] = "v1.2_public_event_semantics"
        semantic_diag = payload["adapter_diagnostics"].get("semantic_frame", {})
        public_event_diag = payload["adapter_diagnostics"].get("public_event_frame", {})
        semantic_used += 1 if semantic_diag.get("used") else 0
        public_event_used += 1 if public_event_diag.get("used") else 0
        print(
            f"[v1.2 {scenario} {index}/{len(source_rows)}] {row_id} "
            f"semantic={bool(semantic_diag.get('used'))} public_event={bool(public_event_diag.get('used'))}",
            flush=True,
        )
        rebuilt.append(updated)

    write_jsonl(output, rebuilt)
    return {
        "scenario": scenario,
        "rows": len(rebuilt),
        "semantic_used": semantic_used,
        "public_event_used": public_event_used,
        "output": str(output),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild Miro outputs with v1.2 public/event semantics.")
    parser.add_argument("--scenario", choices=["all", *SCENARIOS.keys()], default="all")
    parser.add_argument("--output-dir", type=Path, default=BENCHMARK_ROOT / "outputs" / "v1.2")
    parser.add_argument("--source-dir", type=Path, default=None, help="Reuse previously rebuilt v1.2 files as source rows when present")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--offline", action="store_true", help="Do not enable LLM extraction")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.offline:
        os.environ["MIRO_SEMANTIC_FRAME_ENABLED"] = "1"
        os.environ["MIRO_PUBLIC_EVENT_FRAME_ENABLED"] = "1"
    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    summaries = []
    for scenario in selected:
        config = SCENARIOS[scenario]
        source = config["source"]
        if args.source_dir:
            candidate = args.source_dir / config["target_name"]
            if candidate.exists():
                source = candidate
        summaries.append(
            rebuild_scenario(
                scenario=scenario,
                source=source,
                truth=config["truth"],
                output=args.output_dir / config["target_name"],
                limit=args.limit,
            )
        )
    print(json.dumps({"layer": "v1.2_public_event_semantics_rebuild", "summaries": summaries}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

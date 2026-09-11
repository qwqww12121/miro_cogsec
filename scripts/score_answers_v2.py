"""Score any system's natural-language answers with Semantic Scorer v2."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from benchmark.semantic_scorer_v2 import (  # noqa: E402
    SemanticScorerConfig,
    SemanticScorerV2,
    evaluate_records,
    load_jsonl,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--system-name", required=True)
    parser.add_argument("--source-field", default="input")
    parser.add_argument("--answer-field", default="assistant_message")
    parser.add_argument("--scenario-field", default="scenario_type")
    parser.add_argument("--source-jsonl", help="Optional case JSONL joined by id")
    parser.add_argument("--record-id-field", default="id")
    parser.add_argument("--source-id-field", default="id")
    parser.add_argument("--embedding-model")
    parser.add_argument("--nli-model")
    parser.add_argument("--allow-model-download", action="store_true")
    args = parser.parse_args()

    scorer = SemanticScorerV2(SemanticScorerConfig(
        embedding_model=args.embedding_model,
        nli_model=args.nli_model,
        allow_model_download=args.allow_model_download,
    ))
    records = load_jsonl(args.input)
    if args.source_jsonl:
        source_rows = load_jsonl(args.source_jsonl)
        source_by_id = {str(item.get(args.source_id_field)): item for item in source_rows}
        merged = []
        for record in records:
            source = source_by_id.get(str(record.get(args.record_id_field)), {})
            source_value = source.get(args.source_field, source.get("input", ""))
            merged.append({**record, args.source_field: source_value})
        records = merged
    result = evaluate_records(
        records,
        scorer=scorer,
        system_name=args.system_name,
        source_field=args.source_field,
        answer_field=args.answer_field,
        scenario_field=args.scenario_field,
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "per_case"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

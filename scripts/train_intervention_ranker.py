"""Train and gate the inspectable single-step intervention ranker."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.modules.propagation.intervention_ranker import train_ranker_with_holdout  # noqa: E402


def _load(path: Path):
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Pairwise preference JSONL")
    parser.add_argument("--artifact", required=True, help="Published artifact path")
    parser.add_argument("--report", required=True)
    parser.add_argument("--validation-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--minimum-records", type=int, default=20)
    parser.add_argument("--minimum-validation-records", type=int, default=4)
    parser.add_argument("--minimum-accuracy-gain", type=float, default=0.02)
    args = parser.parse_args()
    result = train_ranker_with_holdout(
        _load(Path(args.input)),
        artifact_path=args.artifact,
        validation_ratio=args.validation_ratio,
        seed=args.seed,
        epochs=args.epochs,
        minimum_records=args.minimum_records,
        minimum_validation_records=args.minimum_validation_records,
        minimum_accuracy_gain=args.minimum_accuracy_gain,
    )
    report = Path(args.report)
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key not in {"training", "artifact"}}, ensure_ascii=False, indent=2))
    return 0 if result["promoted"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Run opt-in PPO training with a user-supplied environment factory."""

from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from training.ppo import DiscretePPOBackend, InterventionEnvironment, InterventionReward, PPOTrainer  # noqa: E402


def _load_jsonl(path: str):
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _factory(spec: str, cases):
    module_name, function_name = spec.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name)
    return function(cases=cases)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", required=True)
    parser.add_argument("--environment-factory", required=True, help="module:function")
    parser.add_argument("--output", required=True)
    parser.add_argument("--steps", type=int, default=1000)
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()
    cases = _load_jsonl(args.cases)
    if not args.execute:
        print(json.dumps({
            "status": "validated",
            "cases": len(cases),
            "steps": args.steps,
            "environment_factory": args.environment_factory,
            "training_started": False,
        }, ensure_ascii=False, indent=2))
        return 0
    if os.environ.get("ENABLE_PPO_TRAINING", "false").lower() != "true":
        raise RuntimeError("set ENABLE_PPO_TRAINING=true to execute PPO updates")
    environment = InterventionEnvironment(_factory(args.environment_factory, cases))
    backend = DiscretePPOBackend(cases=cases)
    trainer = PPOTrainer(backend)
    result = trainer.train(environment, InterventionReward(), enabled=True, steps=args.steps)
    result = {**result, "save": backend.save(args.output)}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

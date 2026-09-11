"""Validate or execute local Reporter SFT/DPO training."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from training.dpo import DPOConfig, DPOPipeline  # noqa: E402
from training.hf_backends import (  # noqa: E402
    HFCausalLMDPOBackend,
    HFCausalLMSFTBackend,
    training_stack_status,
)
from training.sft import SFTConfig, SFTPipeline  # noqa: E402


def _load(path: str):
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("sft", "dpo"), required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument("--base-model", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--qlora", action="store_true")
    parser.add_argument("--epochs", type=int, default=1)
    args = parser.parse_args()
    records = _load(args.input)
    if args.stage == "sft":
        config = SFTConfig(
            task="reporter", base_model=args.base_model, output_dir=args.output_dir,
            use_lora=True, use_qlora=args.qlora, epochs=args.epochs,
        )
        pipeline = SFTPipeline(config, backend=HFCausalLMSFTBackend())
    else:
        config = DPOConfig(
            base_model=args.base_model, output_dir=args.output_dir,
            use_lora=True, use_qlora=args.qlora, epochs=args.epochs,
        )
        pipeline = DPOPipeline(config, backend=HFCausalLMDPOBackend())
    if not args.execute:
        result = {**pipeline.validate_records(records), "stack": training_stack_status()}
    else:
        if os.environ.get("ENABLE_REPORTER_TRAINING", "false").lower() != "true":
            raise RuntimeError("set ENABLE_REPORTER_TRAINING=true to execute optimiser updates")
        result = pipeline.train(records, enabled=True)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

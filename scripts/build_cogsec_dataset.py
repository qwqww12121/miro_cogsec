"""构建 CogSec 训练/评估样本。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
from typing import Dict, List


SCENARIO_TEMPLATES: List[Dict[str, str]] = [
    {
        "scenario": "客服称快递丢失，要求共享屏幕并填写银行卡信息。",
        "label": "high_risk_social_engineering",
    },
    {
        "scenario": "陌生人推荐稳赚理财群，催促今天内转账。",
        "label": "high_risk_investment_fraud",
    },
    {
        "scenario": "用户通过官方客服电话回拨确认，拒绝提供验证码。",
        "label": "low_risk_verified_behavior",
    },
]


def build_dataset(sample_size: int, seed: int) -> List[Dict[str, str]]:
    random.seed(seed)
    rows: List[Dict[str, str]] = []
    for index in range(sample_size):
        template = random.choice(SCENARIO_TEMPLATES)
        rows.append(
            {
                "id": f"cogsec-{index + 1:04d}",
                "scenario": template["scenario"],
                "label": template["label"],
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CogSec labeled dataset")
    parser.add_argument("--size", type=int, default=120, help="sample size")
    parser.add_argument("--seed", type=int, default=42, help="random seed")
    parser.add_argument("--output", type=Path, default=Path("data/cogsec_dataset.jsonl"), help="output jsonl")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    rows = build_dataset(args.size, args.seed)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"dataset built: {args.output} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Run a real OASIS multi-candidate and multi-seed experiment.

The current adapter honestly supports official-response broadcasts. This
script compares three official-response timing/message candidates under three
seeds without relabeling unsupported platform actions as OASIS results.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
load_dotenv(ROOT / ".env", override=False)

from app.modules.propagation.oasis_experiment import (  # noqa: E402
    OasisExperimentConfig,
    oasis_environment_status,
    run_multiseed_oasis_experiment,
)
from app.modules.propagation.schema import PropagationAgent  # noqa: E402


SCENARIOS = {
    "public_opinion": {
        "seed_text": "网传某地饮用水受到严重污染，相关说法正在社交平台扩散，但权威检测结果尚未公布。",
        "messages": [
            ("official_immediate", 0, "请暂停传播未经确认的信息，权威检测结果和取样过程将在官方渠道公开。"),
            ("official_evidence", 1, "现公布检测机构、取样时间和可核验来源；请依据原始报告判断，不转发无来源截图。"),
            ("official_action", 1, "如发现异常请通过公开热线提交位置和证据，后续信息以连续更新的官方通报为准。"),
        ],
    },
    "event_propagation": {
        "seed_text": "一段高校冲突视频先在短视频平台传播，随后出现多个互相矛盾的时间地点与身份说法。",
        "messages": [
            ("official_immediate", 0, "相关视频正在核验，请暂缓传播未经确认的身份、地点和事件经过。"),
            ("official_evidence", 1, "现发布原始时间线、视频来源和已确认事实，并逐项标注仍待核验的内容。"),
            ("official_correction", 1, "已确认部分流传细节不准确，请删除旧版本并转发附有来源的更正说明。"),
        ],
    },
}


def build_agents() -> list[PropagationAgent]:
    return [
        PropagationAgent(
            agent_id="source", role="content_creator", stance="supportive",
            influence=0.85, susceptibility=0.35, activity=0.9,
            trust_in_official=0.25,
        ),
        PropagationAgent(
            agent_id="viewer", role="ordinary_viewer", stance="neutral",
            influence=0.4, susceptibility=0.75, activity=0.65,
            trust_in_official=0.55,
        ),
        PropagationAgent(
            agent_id="amplifier", role="media_amplifier", stance="supportive",
            influence=0.72, susceptibility=0.58, activity=0.82,
            trust_in_official=0.4,
        ),
        PropagationAgent(
            agent_id="official", role="official_responder", stance="neutral",
            influence=0.9, susceptibility=0.15, activity=0.8,
            trust_in_official=0.95,
        ),
    ]


def build_proxy_result(scenario: str) -> dict[str, Any]:
    ranked = []
    for rank, (candidate_id, tick, message) in enumerate(
        SCENARIOS[scenario]["messages"], start=1
    ):
        ranked.append({
            "candidate_id": candidate_id,
            "intervention_type": "official_response",
            "target_nodes": [],
            "target_stage": "immediate" if tick == 0 else "early",
            "intervention_tick": tick,
            "message": message,
            "evidence_basis": ["formal_multiseed_fixed_case"],
            "total_score": round(1.0 - (rank - 1) * 0.05, 3),
        })
    return {
        "branch_comparison": {"ranked_branches": ranked},
        "selected_best_branch": ranked[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", choices=["all", *SCENARIOS], default="all")
    parser.add_argument("--seeds", default="42,43,44")
    parser.add_argument("--agents", type=int, default=4)
    parser.add_argument("--ticks", type=int, default=2)
    parser.add_argument(
        "--output-dir", type=Path,
        default=ROOT / "benchmark" / "outputs" / "oasis_multiseed_formal_2026-08-09",
    )
    args = parser.parse_args()

    seeds = tuple(int(item.strip()) for item in args.seeds.split(",") if item.strip())
    if len(seeds) < 2 or len(set(seeds)) != len(seeds):
        raise SystemExit("at least two distinct seeds are required")
    os.environ["MIRO_OASIS_QUICK_MULTI_CANDIDATE"] = "true"
    os.environ["MIRO_OASIS_QUICK_N_AGENTS"] = str(max(4, args.agents))
    os.environ["MIRO_OASIS_QUICK_TICKS"] = str(max(2, args.ticks))

    status = oasis_environment_status()
    if not status.get("ready"):
        raise SystemExit("OASIS environment is not ready: " + json.dumps(status, ensure_ascii=False))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected = list(SCENARIOS) if args.scenario == "all" else [args.scenario]
    exit_code = 0
    for scenario in selected:
        result = run_multiseed_oasis_experiment(
            scenario_type=scenario,
            seed_text=SCENARIOS[scenario]["seed_text"],
            agents=build_agents(),
            proxy_result=build_proxy_result(scenario),
            simulation_state_id=f"formal-{scenario}-20260809",
            config=OasisExperimentConfig(
                seeds=seeds,
                top_k=3,
                quick_mode=True,
                require_shared_initial_world=True,
                require_oasis_metrics=True,
            ),
        )
        output = args.output_dir / f"{scenario}_multiseed.json"
        output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "scenario": scenario,
            "accepted": result.get("accepted"),
            "completed_seeds": result.get("completed_seeds"),
            "candidate_utility": result.get("candidate_utility"),
            "winner_frequency": result.get("winner_frequency"),
            "output": str(output),
        }, ensure_ascii=False), flush=True)
        if not result.get("accepted"):
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

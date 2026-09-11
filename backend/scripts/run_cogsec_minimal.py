"""CogSec 最小链路验证脚本。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_BACKEND_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_BACKEND_ROOT))

from app.cogsec_minimal_runtime import run_minimal_cogsec_analysis  # noqa: E402


DEFAULT_SCENARIO = (
    "我接到自称电商平台客服的电话，对方说我的快递丢失了，要马上操作退款。"
    "他让我不要告诉别人，直接加QQ，发来一个链接让我填写银行卡和验证码。"
    "我当时有点着急，因为他说今天不处理就会过期。"
)


def parse_args() -> argparse.Namespace:
    """解析命令行参数。"""
    parser = argparse.ArgumentParser(description="运行 CogSec 最小链路验证")
    parser.add_argument("--scenario", default=DEFAULT_SCENARIO, help="待分析的中文场景文本")
    parser.add_argument("--scenario-type", default=None, help="可选，手动指定诈骗类别")
    return parser.parse_args()


def main() -> None:
    """CLI 入口。"""
    args = parse_args()
    full_result = run_minimal_cogsec_analysis(args.scenario, scenario_type=args.scenario_type)
    result = {
        "scenario_type": full_result["profile"]["scenario_type"],
        "overall_vulnerability_score": full_result["profile"]["overall_vulnerability_score"],
        "loaded_case_count": full_result["meta"]["loaded_case_count"],
        "strategy_names": [item["tactic_name"] for item in full_result["strategies"]],
        "final_scores_a": full_result["counterfactual_report"]["score_comparison"]["branch_a_final"],
        "final_scores_b": full_result["counterfactual_report"]["score_comparison"]["branch_b_final"],
        "risk_level": full_result["counterfactual_report"]["risk_level"],
        "critical_bifurcation_step": full_result["counterfactual_report"]["critical_bifurcation_step"],
        "critical_bifurcation_reason": full_result["counterfactual_report"]["critical_bifurcation_reason"],
        "recommendations": full_result["counterfactual_report"]["recommendations"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""反事实报告模块测试。"""

from modules.cf_reporter import CounterfactualReporter
from modules.cognitive_profiler import CognitiveProfile
from modules.risk_scorer import RiskScorer


def test_counterfactual_report_contains_bifurcation_and_recommendations():
    profile = CognitiveProfile(
        verification_habit=3.0,
        decision_delay=3.0,
        help_seeking=2.5,
        authority_compliance=8.0,
    )

    branch_a = [
        {
            "step": 1,
            "agent_action": "攻击者冒充官方要求转账",
            "victim_response": "立即配合",
            "triggered_principles": ["authority"],
            "asset_exposure_coefficient": 0.12,
            "is_protection_action": False,
        },
        {
            "step": 2,
            "agent_action": "攻击者继续制造紧迫感",
            "victim_response": "继续操作",
            "triggered_principles": ["authority", "scarcity"],
            "asset_exposure_coefficient": 0.20,
            "is_protection_action": False,
        },
    ]
    branch_b = [
        {
            "step": 1,
            "agent_action": "用户回拨官方渠道核验",
            "victim_response": "暂停操作",
            "triggered_principles": [],
            "asset_exposure_coefficient": 0.0,
            "is_protection_action": True,
        },
        {
            "step": 2,
            "agent_action": "用户向家人求助",
            "victim_response": "终止会话",
            "triggered_principles": [],
            "asset_exposure_coefficient": 0.0,
            "is_protection_action": True,
        },
    ]

    scorer_a = RiskScorer(profile)
    scorer_b = RiskScorer(profile)
    for item in branch_a:
        updated = scorer_a.update_scores(
            item["agent_action"],
            item["triggered_principles"],
            item["is_protection_action"],
            item["asset_exposure_coefficient"],
        )
        item["score_delta"] = {"ASS": updated.ASS - 100, "CHS": updated.CHS - 100}
    for item in branch_b:
        updated = scorer_b.update_scores(
            item["agent_action"],
            item["triggered_principles"],
            item["is_protection_action"],
            item["asset_exposure_coefficient"],
        )
        item["score_delta"] = {"ASS": updated.ASS - 100, "CHS": updated.CHS - 100}

    report = CounterfactualReporter().generate_report(
        branch_a_log=branch_a,
        branch_b_log=branch_b,
        scorer_a=scorer_a,
        scorer_b=scorer_b,
        cognitive_profile=profile,
        case_evidence="测试案例",
    )

    assert report.critical_bifurcation_step >= 1
    assert report.recommendations
    assert report.score_comparison["branch_a_final"]["ASS"] < report.score_comparison["branch_b_final"]["ASS"]
    assert "overview" in report.structured_report
    assert "trigger_analysis" in report.structured_report
    assert "recommendations" in report.structured_report

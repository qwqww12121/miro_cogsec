"""反事实报告模块测试。"""

from app.modules.cf_reporter import CounterfactualReporter
from app.modules.cognitive_profiler import CognitiveProfile
from app.modules.risk_scorer import RiskScorer


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


def test_propagation_prescriptions_include_executable_actions():
    reporter = CounterfactualReporter()
    for scenario in ("public_opinion", "event_propagation"):
        items = reporter._generate_propagation_prescriptions(scenario)
        assert items
        for item in items:
            assert "已存档" not in item["title"]
            assert item["recommended_actions"]
            assert all(str(action).strip() for action in item["recommended_actions"])


def test_fraud_prescriptions_use_readable_node_name():
    class _Fork:
        best_intervention_window = {"open_step": 2, "close_step": 3}
        fork_point_type = "transfer_money"

    profile = CognitiveProfile(
        scenario_type="fraud_im",
        verification_habit=3.0,
        help_seeking=2.5,
    )
    items = CounterfactualReporter()._generate_mainline_prescriptions(
        profile=profile,
        fork_comparison=_Fork(),
        persona_state_vector=None,
    )
    assert items
    assert "转账" in items[0]["title"]
    assert "transfer_money" not in items[0]["title"]
    assert items[0]["recommended_actions"]
    assert "Fork" not in items[0]["expected_effect"]
    assert "System" not in items[0]["expected_effect"]


def test_fraud_prescriptions_translate_phishing_link_entry():
    class _Fork:
        best_intervention_window = {"open_step": 2, "close_step": 3}
        fork_point_type = "phishing_link_entry"

    profile = CognitiveProfile(scenario_type="fraud_im", verification_habit=6.0, help_seeking=6.0)
    items = CounterfactualReporter()._generate_mainline_prescriptions(
        profile=profile,
        fork_comparison=_Fork(),
        persona_state_vector=None,
    )
    assert items
    assert "钓鱼" in items[0]["title"]
    assert "phishing_link_entry" not in items[0]["title"]
    assert "节点前" not in items[0]["title"]

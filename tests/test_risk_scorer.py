"""风险评分模块测试。"""

from modules.cognitive_profiler import CognitiveProfile
from modules.risk_scorer import RiskScorer


def test_risk_scores_drop_on_attack_and_recover_on_protection():
    profile = CognitiveProfile(
        authority_compliance=8.0,
        scarcity_sensitivity=7.0,
        decision_delay=8.0,
        verification_habit=9.0,
        help_seeking=8.0,
    )
    scorer = RiskScorer(profile)

    attack_scores = scorer.update_scores(
        agent_action="攻击者要求立即转账",
        triggered_principles=["authority", "scarcity"],
        asset_exposure_coefficient=0.2,
    )
    protected_scores = scorer.update_scores(
        agent_action="用户通过官方渠道核实并求助",
        triggered_principles=[],
        is_protection_action=True,
        asset_exposure_coefficient=0.0,
    )

    assert attack_scores.CHS < 100
    assert attack_scores.ASS < 100
    assert protected_scores.SSS > attack_scores.SSS
    assert protected_scores.EES <= attack_scores.EES
    assert attack_scores.posterior_probability >= 0.2
    assert attack_scores.cognitive_mode in {"SYSTEM_1", "SYSTEM_2"}
    assert 0.0 <= attack_scores.reversibility <= 1.0
    assert len(scorer.get_score_timeline()) == 3

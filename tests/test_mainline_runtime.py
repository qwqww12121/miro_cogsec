"""CogSec-MIROFISH mainline runtime tests."""

from modules.cognitive_profiler import CognitiveProfile
from modules.mainline_runtime import MiroFishRuntime
from modules.privacy_sanitizer import PrivacySanitizer
from modules.risk_scorer import RiskScorer
from modules.threat_rag import AttackStrategy, FraudCase, ThreatKnowledgeRAG


def build_case(case_id, category, principle, tactic):
    return FraudCase(
        id=case_id,
        category=category,
        attack_role="tester",
        target_info=["资金账户", "验证码"],
        attack_strategies=[
            AttackStrategy(
                id=f"{case_id}:{principle}",
                cialdini_principle=principle,
                tactic_name=tactic,
                description=f"{tactic} 的详细描述",
                typical_dialogue="请马上转账并完成核验",
                escalation_condition="受害者犹豫时",
                intensity_level=3,
            )
        ],
        dialogue_examples=[{"attacker": "请配合", "victim": "好的"}],
        risk_keywords=[category, tactic, "转账", "验证码"],
        red_flags=["要求转账", "要求验证码"],
    )


def build_profile():
    return CognitiveProfile(
        scenario_type="虚假征信类",
        authority_compliance=9.0,
        time_pressure=8.5,
        financial_pressure=7.8,
        emotional_volatility=8.4,
        scarcity_sensitivity=7.5,
        social_proof_sensitivity=6.8,
        verification_habit=3.2,
        help_seeking=3.0,
        link_check_ability=4.0,
        transaction_review=3.5,
        prior_experience=3.0,
    )


def test_persona_vector_switches_to_system1_when_pressure_and_emotion_high():
    vector = build_profile().to_persona_state_vector()

    assert vector.cognitive_mode == "SYSTEM_1"
    assert vector.storage_policy["default"] == "session_only"
    assert vector.switch_policy["force_system1_if"]["time_pressure_gt"] == 7


def test_threat_graph_bundle_contains_required_relations():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([build_case("case_a", "虚假征信类", "authority", "权威施压")])
    profile = build_profile()
    bundle = rag.build_risk_graph_bundle(
        scenario_text="官方客服说征信异常，要求马上转账到安全账户并提供验证码，不要告诉家人。",
        scenario_type=profile.scenario_type,
        cognitive_profile=profile,
        persona_state_vector=profile.to_persona_state_vector(),
    )

    relations = {item["relation"] for item in bundle.to_dict()["links"]}
    assert {
        "TRUST_IN",
        "PRESSURED_BY",
        "MATCHES_WEAKNESS",
        "ESCALATES_TO",
        "THREATENS_ASSET",
        "MITIGATED_BY",
        "FORK_AT",
    }.issubset(relations)


def test_hallucination_low_consistency_triggers_rollback():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    profile = build_profile()
    bundle = rag.build_risk_graph_bundle(
        scenario_text="模糊样本，没有足够证据。",
        scenario_type=profile.scenario_type,
        cognitive_profile=profile,
        persona_state_vector=profile.to_persona_state_vector(),
    )

    assert bundle.hallucination_rollback is True


def test_runtime_timeout_degrades_result():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([build_case("case_a", "虚假征信类", "authority", "权威施压")])
    profile = build_profile()
    bundle = rag.build_risk_graph_bundle(
        scenario_text="官方客服说征信异常，要求马上转账到安全账户并提供验证码。",
        scenario_type=profile.scenario_type,
        cognitive_profile=profile,
        persona_state_vector=profile.to_persona_state_vector(),
    )

    result = MiroFishRuntime().run(
        persona_state_vector=profile.to_persona_state_vector(),
        risk_graph_bundle=bundle,
        current_input="官方客服说征信异常，要求马上转账到安全账户并提供验证码。",
        deadline_sec=0,
    )

    assert result.degraded is True
    assert "timeout_degraded" in result.fork_comparison.anomaly_flags


def test_privacy_sanitizer_retries_and_marks_pii_leak(monkeypatch):
    sanitizer = PrivacySanitizer(enabled=False)
    monkeypatch.setattr(sanitizer, "contains_sensitive_data", lambda text: True)

    result = sanitizer.sanitize_with_retry(
        "我的手机号是13800138000，银行卡6222021234567890123。",
        max_retries=1,
    )

    assert result.retry_count == 1
    assert result.pii_leak_detected is True


def test_runtime_flags_audit_when_score_jump_exceeds_threshold():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([build_case("case_a", "虚假征信类", "authority", "权威施压")])
    profile = build_profile()
    bundle = rag.build_risk_graph_bundle(
        scenario_text="官方客服说征信异常，要求马上转账到安全账户并提供验证码。",
        scenario_type=profile.scenario_type,
        cognitive_profile=profile,
        persona_state_vector=profile.to_persona_state_vector(),
    )

    result = MiroFishRuntime().run(
        persona_state_vector=profile.to_persona_state_vector(),
        risk_graph_bundle=bundle,
        current_input="官方客服说征信异常，要求马上转账到安全账户并提供验证码。",
        deadline_sec=15,
    )

    assert any(step.audit_flag for step in result.fork_comparison.branch_a_state_trace)


def test_counterfactual_risk_marks_low_discriminability_for_similar_branches():
    profile = build_profile()
    trace = [
        {
            "world_state": {
                "posterior_risk": 0.42,
                "asset_exposure": 0.18,
                "reversibility": 0.82,
                "trust_score": 52,
            }
        },
        {
            "world_state": {
                "posterior_risk": 0.45,
                "asset_exposure": 0.2,
                "reversibility": 0.79,
                "trust_score": 54,
            }
        },
    ]
    breakdown = RiskScorer(profile).evaluate_counterfactual(
        branch_a_state_trace=trace,
        branch_b_state_trace=trace,
        fork_point_type="transfer_money",
        posterior_updates=[],
        reversibility_curve=[],
        persona_hit_chain=["authority_compliance"],
        evidence_graph_consistency=0.8,
    )

    assert breakdown.low_discriminability is True
    assert "branch_divergence_too_small" in breakdown.anomaly_flags


def test_counterfactual_risk_uses_five_factor_geometric_mean():
    profile = build_profile()
    risky = [{"world_state": {"posterior_risk": 0.9, "asset_exposure": 1.0,
                              "reversibility": 0.1, "trust_score": 90}}]
    safe = [{"world_state": {"posterior_risk": 0.1, "asset_exposure": 0.0,
                             "reversibility": 0.9, "trust_score": 10}}]

    breakdown = RiskScorer(profile).evaluate_counterfactual(
        branch_a_state_trace=risky,
        branch_b_state_trace=safe,
        fork_point_type="transfer_money",
        posterior_updates=[],
        reversibility_curve=[],
        persona_hit_chain=["authority", "urgency", "transfer_money"],
        evidence_graph_consistency=0.8,
    )

    assert breakdown.final_risk >= 50.0
    assert breakdown.risk_level in {"HIGH", "CRITICAL"}


def test_branch_b_closing_step_points_to_visible_prescription():
    runtime = MiroFishRuntime()
    for fork_type in (
        "transfer_money",
        "info_propagation_risk",
        "misinformation_risk",
        "screen_share",
    ):
        labels = runtime._fork_specific_labels(fork_type)
        assert "已存档" not in labels["b_prescription"]
        assert "干预处方" in labels["b_prescription"]
        templates = runtime._build_action_templates("B", {"type": fork_type})
        assert templates[-1]["action_type"] == "prescription"
        assert "已存档" not in templates[-1]["action"]

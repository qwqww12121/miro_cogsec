"""ThreatKnowledgeRAG 测试。"""

from app.modules.cognitive_profiler import CognitiveProfile
from app.modules.threat_rag import AttackStrategy, FraudCase, ThreatKnowledgeRAG


def build_case(case_id, category, principle, tactic):
    return FraudCase(
        id=case_id,
        category=category,
        attack_role="tester",
        target_info=["账户"],
        attack_strategies=[
            AttackStrategy(
                id=f"{case_id}:{principle}",
                cialdini_principle=principle,
                tactic_name=tactic,
                description=f"{tactic} 的详细描述",
                typical_dialogue="请立即配合操作",
                escalation_condition="受害者犹豫时",
                intensity_level=3,
            )
        ],
        dialogue_examples=[{"attacker": "请配合", "victim": "好的"}],
        risk_keywords=[category, tactic],
        red_flags=["要求转账"],
    )


def test_retrieve_attack_strategies_prefers_profile_aligned_results():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([
        build_case("case_a", "虚假征信类", "authority", "权威施压"),
        build_case("case_b", "刷单返利类", "scarcity", "名额稀缺"),
    ])

    profile = CognitiveProfile(
        scenario_type="虚假征信类",
        authority_compliance=9.0,
        scarcity_sensitivity=4.0,
    )
    strategies = rag.retrieve_attack_strategies("虚假征信类", profile, n_results=1)

    assert len(strategies) == 1
    assert strategies[0].cialdini_principle == "authority"


def test_verify_strategy_legitimacy_distinguishes_unknown_strategy():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    legit_strategy = AttackStrategy(
        id="case_a:authority",
        cialdini_principle="authority",
        tactic_name="权威施压",
        description="权威施压 的详细描述",
        typical_dialogue="请立即配合操作",
        escalation_condition="受害者犹豫时",
        intensity_level=3,
    )
    rag.ingest_cases([build_case("case_a", "虚假征信类", "authority", "权威施压")])

    legit, legit_score = rag.verify_strategy_legitimacy(legit_strategy)
    fake, fake_score = rag.verify_strategy_legitimacy(
        AttackStrategy(
            id="fake",
            cialdini_principle="unity",
            tactic_name="完全无关策略",
            description="与案例库没有关系",
            typical_dialogue="你好",
            escalation_condition="无",
            intensity_level=1,
        )
    )

    assert legit is True
    assert legit_score > fake_score
    assert fake is False


def test_assert_operation_allowed_blocks_unknown_operation():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([build_case("case_a", "虚假征信类", "authority", "权威施压")])

    assert rag.assert_operation_allowed("攻击者执行权威施压并要求继续操作") is True
    assert rag.assert_operation_allowed("攻击者突然要求去线下见面交现金") is False


def test_retrieve_keeps_inferred_candidates_for_fraud_im():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([
        build_case("case_loan", "虚假贷款代办信用卡类", "authority", "信用卡代还诱导"),
    ])
    profile = CognitiveProfile(scenario_type="虚假贷款代办信用卡类")
    strategies = rag.retrieve_attack_strategies(
        "fraud_im",
        profile,
        n_results=1,
        scenario_text="广告称本地信用卡代还，我同意了",
    )
    assert len(strategies) == 1
    assert getattr(strategies[0], "grounding_status", None) in {"observed", "inferred"}


def test_identity_asset_text_uses_semantic_forks_without_transfer_fallback():
    rag = ThreatKnowledgeRAG("unused", enable_chroma=False)
    rag.ingest_cases([
        build_case("case_credit", "虚假征信类", "authority", "安全账户限时转移"),
    ])
    profile = CognitiveProfile(scenario_type="fraud_im")

    bundle = rag.build_risk_graph_bundle(
        "广告称可以买到已实名激活手机卡，留下微信联系，强调多年老店和信誉第一。",
        "fraud_im",
        profile,
        profile,
    )

    fork_types = {item["type"] for item in bundle.fork_points}
    assert "identity_asset_exchange" in fork_types
    assert "private_contact_lure" in fork_types
    assert "transfer_money" not in fork_types

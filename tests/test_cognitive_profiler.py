"""认知画像模块测试。"""

from modules.cognitive_profiler import CognitiveProfileExtractor, FEATURE_KEYS


class FakeLLM:
    """返回固定 JSON 的假 LLM。"""

    def chat_json(self, messages, temperature=0.1, max_tokens=4096):
        features = {key: 4.0 for key in FEATURE_KEYS}
        confidence = {key: 0.9 for key in FEATURE_KEYS}
        confidence["authority_intensity"] = 0.2
        confidence["authority_compliance"] = 0.2
        reasoning = {key: "测试依据" for key in FEATURE_KEYS}
        return {
            "scenario_type": "虚假征信类",
            "features": features,
            "confidence": confidence,
            "reasoning": reasoning,
        }


def test_low_confidence_fields_fallback_to_defaults_and_questionnaire_override():
    extractor = CognitiveProfileExtractor(FakeLLM())
    profile = extractor.extract(
        "陌生客服说我的征信异常，需要马上处理。",
        questionnaire={"verification_habit": 9.0},
    )

    assert profile.scenario_type == "虚假征信类"
    assert profile.authority_intensity == 8.5
    assert profile.authority_compliance == 7.5
    assert profile.verification_habit == 9.0
    assert profile.confidence_scores["verification_habit"] == 0.95


def test_heuristic_mode_detects_scenario_and_outputs_reasonable_score():
    extractor = CognitiveProfileExtractor(llm_client=None)
    profile = extractor.extract(
        "客服说包裹丢失可以退款，但要我立即下载会议软件共享屏幕并提供验证码。"
    )

    assert profile.scenario_type == "冒充电商物流客服类"
    assert profile.time_pressure >= 6
    assert profile.cognitive_load >= 6
    assert 0 <= profile.overall_vulnerability_score() <= 100


def test_victim_context_from_questionnaire_connects_protection_factors():
    extractor = CognitiveProfileExtractor(FakeLLM())
    profile = extractor.extract(
        "广告称本地信用卡代还，我同意了",
        questionnaire={
            "platform": "微信",
            "attacker_role": "冒充客服",
            "victim_context": "50岁，独居，缺少反诈科普",
            "scenario_category": "虚假贷款代办信用卡类",
        },
        scenario_type="虚假贷款代办信用卡类",
        canonical_scenario="fraud_im",
    )

    assert profile.help_seeking <= 2.0
    assert profile.verification_habit <= 2.0
    assert profile.prior_experience <= 2.0
    assert profile.protection_score() < 4.5
    assert profile.overall_vulnerability_score() > 40
    assert "受害人背景" in profile.reasoning["help_seeking"]


def test_heuristic_victim_context_works_without_tagged_section():
    extractor = CognitiveProfileExtractor(llm_client=None)
    profile = extractor.extract(
        "广告称本地信用卡代还，我同意了",
        questionnaire={"victim_context": "65岁，独居，缺少反诈科普"},
        scenario_type="虚假贷款代办信用卡类",
        canonical_scenario="fraud_im",
    )

    assert profile.scenario_type == "虚假贷款代办信用卡类"
    assert profile.help_seeking == 2.0
    assert profile.link_check_ability <= 2.0
    assert profile.protection_score() < 4.0


def test_victim_agreeing_updates_protection_and_cognitive_mode():
    extractor = CognitiveProfileExtractor(llm_client=None)
    baseline = extractor.extract(
        "教务处老师通知张同学奖学金到账，请去支付宝认证，不要告诉辅导员。",
        questionnaire={"victim_context": "在校学生，收到奖学金或教务类通知，缺少当面核验条件"},
        scenario_type="冒充领导熟人类",
        canonical_scenario="fraud_im",
    )
    complied = extractor.extract(
        "教务处老师通知张同学奖学金到账，请去支付宝认证，不要告诉辅导员。\n受害人：我答应了",
        questionnaire={"victim_context": "在校学生，收到奖学金或教务类通知，缺少当面核验条件"},
        scenario_type="冒充领导熟人类",
        canonical_scenario="fraud_im",
    )
    assert complied.protection_score() < baseline.protection_score()
    assert complied.resolve_cognitive_mode() == "SYSTEM_1"
    assert complied.time_pressure >= 8.0
    assert "对话进展" in complied.reasoning["decision_delay"]

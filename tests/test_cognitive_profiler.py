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

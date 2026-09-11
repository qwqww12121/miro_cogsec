"""Local scenario classifier guards."""

from app.modules.llm_scenario_classifier import LLMScenarioClassifier
from app.modules.scenarios import CANONICAL_FRAUD_IM


class BoomLLM:
    def chat_json(self, *args, **kwargs):
        raise AssertionError("remote LLM should not be used for classic openings")


def test_qin_shi_huang_is_recognized_as_fraud_without_llm():
    classifier = LLMScenarioClassifier(client=BoomLLM())
    result = classifier.classify("我是秦始皇")

    assert result.scenario_type == CANONICAL_FRAUD_IM
    assert result.confidence >= 0.75
    assert result.model == "deterministic_pattern"
    assert "秦始皇" in result.extracted_summary


def test_greeting_is_unknown_without_llm():
    result = LLMScenarioClassifier.classify_without_llm("你好")
    assert result is not None
    assert result.scenario_type == "unknown"
    assert result.model == "deterministic_guard"


def test_casebook_is_out_of_scope_without_llm():
    text = """# 107 Agent Hackathon Casebook 2024-2026
## 3. 从 300+ 案例里反复出现的 10 个成熟模式
Agent Workspace、OpenHands、Agent Zero 的规划案。
"""
    result = LLMScenarioClassifier.classify_without_llm(text)
    assert result is not None
    assert result.scenario_type == "unknown"
    assert result.model == "deterministic_out_of_scope"
    assert result.confidence < 0.3


def test_illegal_llm_label_does_not_fallback_to_fraud():
    classifier = LLMScenarioClassifier(client=BoomLLM())
    built = classifier._build_result({"scenario_type": "not_a_scene", "confidence": 0.9, "reason": "x", "extracted_summary": "y"})
    assert built.scenario_type == "unknown"


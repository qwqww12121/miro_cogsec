from __future__ import annotations

from benchmark.semantic_scorer_v2 import SemanticScorerV2, evaluate_records


class FakeEmbedder:
    name = "fake-embedding"

    def similarity(self, left: str, right: str) -> float:
        return 0.8


class FakeNLI:
    name = "fake-nli"

    def predict(self, premise: str, hypothesis: str):
        return {"entailment": 0.9, "contradiction": 0.05, "neutral": 0.05}


def test_pair_score_records_model_provenance() -> None:
    result = SemanticScorerV2(embedder=FakeEmbedder(), nli=FakeNLI()).score_pair(
        "官方已经发布澄清", "权威渠道已作出澄清"
    )
    assert result.score > 0.5
    assert result.provenance["mode"] == "model_augmented"
    assert result.provenance["embedding_backend"] == "fake-embedding"


def test_negation_and_hallucination_are_penalised() -> None:
    scorer = SemanticScorerV2()
    pair = scorer.score_pair("信息尚未证实", "信息已经证实")
    assert pair.score <= 0.25

    safe = scorer.score_response(source="普通商品宣传，没有付款要求。", answer="建议先核验商品来源。")
    invented = scorer.score_response(
        source="普通商品宣传，没有付款要求。",
        answer="对方要求转账并索取验证码，应立即冻结账户。",
    )
    assert invented["hallucination_penalty"] > safe["hallucination_penalty"]
    assert invented["over_intervention_penalty"] > safe["over_intervention_penalty"]


def test_same_evaluator_contract_applies_to_any_system() -> None:
    rows = [{"case_id": "1", "input": "有人要求转账", "assistant_message": "暂停转账并向银行核验", "scenario_type": "fraud_im"}]
    scorer = SemanticScorerV2()
    miro = evaluate_records(rows, scorer=scorer, system_name="miro")
    baseline = evaluate_records(rows, scorer=scorer, system_name="llm_only")
    assert miro["summary"] == baseline["summary"]
    assert miro["per_case"][0]["system"] == "miro"
    assert baseline["per_case"][0]["system"] == "llm_only"

from __future__ import annotations

from app.modules.benchmark_adapter import (
    EVENT_PROPAGATION_FIELDS,
    FRAUD_FIELDS,
    PUBLIC_OPINION_FIELDS,
    build_benchmark_payload,
    build_llm_only_cogsec_analysis,
    normalize_asset_targets,
)
from app.modules.propagation.intervention_search import run_oasis_counterfactual_intervention_search


def _base_result(scenario: str) -> dict:
    return {
        "profile": {"scenario_type": scenario},
        "risk_graph_bundle": {
            "nodes": [{"id": "risk:1", "label": "risk"}],
            "links": [{"source": "risk:1", "target": "asset:identity", "relation": "targets"}],
            "asset_targets": [
                {"id": "asset:identity", "label": "身份资料", "severity": 0.82},
            ],
            "fork_points": [{"id": "fork:1", "type": "transfer_money", "severity": 0.6}],
            "evidence_items": [{"label": "实名手机卡", "matched_terms": ["实名", "手机卡"]}],
            "attack_strategy_chain": [{"typical_dialogue": "留下微信联系"}],
        },
        "fork_comparison": {
            "fork_point_type": "transfer_money",
            "best_intervention_window": {"open_step": 1, "close_step": 1, "label": "添加微信前阻断"},
            "trajectory_gap": 0.4,
            "irreversibility_loss": 0.3,
        },
        "counterfactual_report": {
            "score_comparison": {"risk_breakdown": {"risk_level": "high"}},
        },
        "intervention_prescriptions": [{"action": "stop_and_verify"}],
        "t0_fast_response": {"should_interrupt": True, "risk_level": "high"},
        "scenario_metadata": {"canonical": scenario},
        "scenario_extension": {"detection": {"canonical": scenario}},
    }


def test_fraud_adapter_complete_schema_and_asset_mapping() -> None:
    text = "广告称可以买到已实名激活手机卡，留下微信联系，强调多年老店和信誉第一。"
    result = _base_result("fraud_im")
    payload = build_benchmark_payload(result=result, scenario_text=text, scenario_type="fraud_im")
    prediction = payload["prediction"]

    assert all(field in prediction for field in FRAUD_FIELDS)
    assert {item["type"] for item in prediction["asset_targets"]} >= {"identity", "account", "social_trust"}
    assert prediction["evidence_spans"]
    assert all(span in text for span in prediction["evidence_spans"])
    assert payload["cogsec_analysis"]["provenance"]["source"] == "mirofish_pipeline"


def test_asset_targets_map_without_type() -> None:
    assets, source = normalize_asset_targets(
        [{"id": "asset:credential", "label": "验证码和登录密码", "severity": 0.9}],
        "客服要求提供验证码和登录密码。",
    )
    assert source == "label|id|matched_terms"
    assert assets[0]["type"] == "credentials"


def test_public_opinion_adapter_complete_with_search() -> None:
    text = "公开讨论迅速发酵，评论区出现愤怒表达、未经证实的目击叙述和要求官方立即公布细节的呼声。"
    result = _base_result("public_opinion")
    result["scenario_extension"]["propagation_intervention_search"] = run_oasis_counterfactual_intervention_search(
        scenario_type="public_opinion",
        seed_text=text,
        risk_graph_bundle=result["risk_graph_bundle"],
        quick_mode=True,
    )
    payload = build_benchmark_payload(result=result, scenario_text=text, scenario_type="public_opinion")
    prediction = payload["prediction"]

    assert all(field in prediction for field in PUBLIC_OPINION_FIELDS)
    assert prediction["best_intervention_window"]["open_stage"]
    assert prediction["expected_intervention_action"]
    assert payload["cogsec_analysis"]["provenance"]["branch_count"] >= 3


def test_event_propagation_adapter_complete_with_search() -> None:
    text = "首发帖被多个新闻账号和个人账号转发，随后有人补充未经证实的嫌疑人身份，权威账号发布更正。"
    result = _base_result("event_propagation")
    result["scenario_extension"]["propagation_intervention_search"] = run_oasis_counterfactual_intervention_search(
        scenario_type="event_propagation",
        seed_text=text,
        risk_graph_bundle=result["risk_graph_bundle"],
        quick_mode=True,
    )
    payload = build_benchmark_payload(result=result, scenario_text=text, scenario_type="event_propagation")
    prediction = payload["prediction"]

    assert all(field in prediction for field in EVENT_PROPAGATION_FIELDS)
    assert prediction["containment_window"]["open_step"] >= 1
    assert prediction["expected_containment_action"]
    assert payload["cogsec_analysis"]["propagation_analysis"]["counterfactual_branches"]


def test_llm_only_provenance_is_not_runtime_grounded() -> None:
    analysis = build_llm_only_cogsec_analysis(
        prediction={"evidence_spans": ["迅速发酵"], "best_intervention_window": {}},
        scenario_type="public_opinion",
    )
    provenance = analysis["provenance"]
    assert provenance["source"] == "llm_only"
    assert provenance["has_runtime_simulation"] is False
    assert provenance["has_oasis_counterfactual_branches"] is False

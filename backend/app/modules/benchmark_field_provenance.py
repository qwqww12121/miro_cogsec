"""Field-level benchmark provenance and score lineage.

This is intentionally a reporting aid, not a scoring implementation.  The
mapping names the prediction fields consumed by the existing benchmark rubric
so a low score can be traced to a concrete state field and source.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping


SCORE_LINEAGE: Dict[str, Dict[str, Any]] = {
    "fraud_im": {
        "IWA": ["intervention_window"],
        "ASA": ["expected_safe_action"],
        "WSA": ["expected_warning"],
        "ATA": ["asset_targets"],
        "FPA": ["fork_points"],
        "RCA": ["risk_level"],
        "EAR": ["evidence_spans"],
    },
    "public_opinion": {
        "NSS": ["narrative_threads"],
        "UGS": ["uncertainty_points"],
        "IWA": ["best_intervention_window"],
        "IAS": ["expected_intervention_action"],
        "SPS": ["expected_safe_public_action"],
        "RCA": ["propagation_risk_level"],
        "EAS": ["emotion_signal"],
        "OGS": ["official_response_gap"],
        "EAR": ["evidence_spans"],
    },
    "event_propagation": {
        "OVS": ["origin_node"],
        "ANS": ["amplifier_nodes"],
        "PCS": ["propagation_path"],
        "DCS": ["distortion_points"],
        "CWS": ["containment_window"],
        "CAS": ["expected_containment_action"],
        "RCA": ["coverage_risk"],
        "EAR": ["evidence_spans"],
    },
}


def build_benchmark_field_provenance(
    *,
    scenario: str,
    prediction: Mapping[str, Any],
    report_state: Mapping[str, Any] | None = None,
    adapter_diagnostics: Mapping[str, Any] | None = None,
) -> Dict[str, Any]:
    """Return field provenance plus the score-oriented low-score lineage."""
    state = report_state if isinstance(report_state, Mapping) else {}
    state_fields = state.get("field_provenance") if isinstance(state.get("field_provenance"), Mapping) else {}
    branch = {"fraud_im": "fraud", "public_opinion": "public_opinion", "event_propagation": "event_propagation"}.get(scenario, "")
    diagnostics = adapter_diagnostics if isinstance(adapter_diagnostics, Mapping) else {}
    fallback_note = "adapter fallback or field unavailable"
    fields: Dict[str, Any] = {}
    for field in _prediction_fields(scenario, prediction):
        state_key = f"{branch}.{_state_field(field, scenario)}" if branch else field
        existing = state_fields.get(state_key) if isinstance(state_fields, Mapping) else None
        if isinstance(existing, Mapping):
            item = dict(existing)
            item.setdefault("value", prediction.get(field))
            item.setdefault("source_state_field", state_key)
        else:
            value = prediction.get(field)
            item = {
                "value": value,
                "source_agent": None,
                "source_state_field": state_key,
                "evidence_refs": _evidence_refs(value, state),
                "transform_chain": ["canonical_runtime", "report_state", "benchmark_export"],
                "confidence": prediction.get("confidence"),
                "fallback_used": field not in prediction or not value,
                "reason": fallback_note if field not in prediction or not value else "adapter field emitted without Report State provenance",
            }
        item["benchmark_field"] = field
        fields[field] = item

    lineage: Dict[str, Any] = {}
    for metric, required_fields in SCORE_LINEAGE.get(scenario, {}).items():
        lineage[metric] = {
            "score_metric": metric,
            "prediction_fields": list(required_fields),
            "fields": {field: fields.get(field) for field in required_fields},
            "missing_fields": [field for field in required_fields if field not in prediction],
            "fallback_used": any(bool((fields.get(field) or {}).get("fallback_used")) for field in required_fields),
            "reason": "score metric consumes these prediction fields; inspect field values and sources before interpreting a low score",
        }

    return {
        "schema_version": "benchmark_field_provenance.v1",
        "scenario": scenario,
        "fields": fields,
        "score_lineage": lineage,
        "adapter_fallbacks": diagnostics.get("adapter_warnings", []),
        "source_contract": "canonical runtime -> Report State -> benchmark export -> offline score",
    }


def _prediction_fields(scenario: str, prediction: Mapping[str, Any]) -> Iterable[str]:
    listed = set()
    for fields in SCORE_LINEAGE.get(scenario, {}).values():
        listed.update(fields)
    listed.update(prediction.keys())
    return sorted(field for field in listed if not str(field).startswith("_"))


def _state_field(field: str, scenario: str) -> str:
    aliases = {
        "fraud_type": "risk_type",
        "attack_stage": "current_stage",
        "fork_points": "critical_transitions",
        "asset_targets": "requested_assets",
        "intervention_window": "recommended_timing",
        "expected_warning": "recommended_actions",
        "expected_safe_action": "recommended_actions",
        "best_intervention_window": "intervention_timing",
        "expected_intervention_action": "candidate_interventions",
        "expected_safe_public_action": "candidate_interventions",
        "propagation_risk_level": "misinformation_signal",
        "emotion_signal": "polarization_signal",
        "official_response_gap": "source_status",
        "origin_node": "source_nodes",
        "propagation_path": "cross_platform_path",
        "distortion_points": "lost_context",
        "containment_window": "containment_timing",
        "expected_containment_action": "containment_action",
    }
    return aliases.get(field, field)


def _evidence_refs(value: Any, state: Mapping[str, Any]) -> list[str]:
    evidence = state.get("evidence") if isinstance(state.get("evidence"), list) else []
    if isinstance(value, (list, dict)):
        return [f"ev:{item}" for item in evidence[:8] if item]
    text = str(value or "")
    return [f"ev:{item}" for item in evidence[:8] if item and str(item) in text]

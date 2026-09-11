"""Pure benchmark export adapter for canonical CogSec runtime state.

This module intentionally performs no inference from raw scenario text.  Its
only job is to map the already-built :mod:`report_state` contract to the field
names expected by the offline benchmark.  Keeping this adapter pure prevents
benchmark phrases, keyword rules, or a second LLM call from changing online
behaviour.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional

from .benchmark_field_provenance import build_benchmark_field_provenance
from .report_state import build_report_state


FRAUD_FIELDS = [
    "is_fraud", "fraud_type", "risk_level", "attack_stage", "asset_targets",
    "fork_points", "intervention_window", "expected_warning",
    "expected_safe_action", "counterfactual_paths", "evidence_spans",
    "confidence",
]

PUBLIC_OPINION_FIELDS = [
    "event_summary", "narrative_threads", "emotion_signal",
    "uncertainty_points", "official_response_gap", "propagation_risk_level",
    "best_intervention_window", "expected_intervention_action",
    "expected_safe_public_action", "evidence_spans", "confidence",
]

EVENT_PROPAGATION_FIELDS = [
    "event_summary", "origin_node", "amplifier_nodes", "propagation_path",
    "distortion_points", "coverage_risk", "containment_window",
    "expected_containment_action", "evidence_spans", "confidence",
]

REQUIRED_BY_SCENARIO = {
    "fraud_im": FRAUD_FIELDS,
    "public_opinion": PUBLIC_OPINION_FIELDS,
    "event_propagation": EVENT_PROPAGATION_FIELDS,
}


def build_benchmark_payload(
    *,
    result: Dict[str, Any],
    scenario_text: str,
    scenario_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Export one runtime result without performing benchmark-side inference.

    ``scenario_text`` remains in the signature because callers naturally have
    it, but it is deliberately not read by this export adapter.
    """
    del scenario_text
    scenario = _resolve_scenario(result, scenario_type)
    state = _dict(result.get("report_state")) or build_report_state(result)

    if scenario == "public_opinion":
        prediction = _public_prediction(state)
    elif scenario == "event_propagation":
        prediction = _event_prediction(state)
    else:
        scenario = "fraud_im"
        prediction = _fraud_prediction(state)

    evidence = _strings(state.get("evidence"))
    prediction["evidence_pack"] = _evidence_pack(evidence)
    diagnostics = _diagnostics(scenario, prediction, state)
    cogsec_analysis = _cogsec_analysis(result, state, scenario)
    field_provenance = build_benchmark_field_provenance(
        scenario=scenario,
        prediction=prediction,
        report_state=state,
        adapter_diagnostics=diagnostics,
    )
    diagnostics["benchmark_field_provenance"] = field_provenance

    return {
        "scenario": scenario,
        "prediction": prediction,
        "cogsec_analysis": cogsec_analysis,
        "report_state": state,
        "benchmark_field_provenance": field_provenance,
        "adapter_diagnostics": diagnostics,
        "provenance": {
            "source": "canonical_report_state",
            "raw_input_used": False,
            "second_inference_pass": False,
        },
    }


def _fraud_prediction(state: Mapping[str, Any]) -> Dict[str, Any]:
    fraud = _dict(state.get("fraud"))
    summary = _dict(state.get("summary"))
    actions = _strings(fraud.get("recommended_actions"))
    risk_type = str(fraud.get("risk_type") or "unknown")
    selected = _selected(state)
    return {
        "is_fraud": risk_type not in {"", "unknown", "no_fraud_signal"},
        "fraud_type": risk_type,
        "risk_level": summary.get("risk_level") or "unknown",
        "attack_stage": fraud.get("current_stage") or fraud.get("attack_stage") or "unknown",
        "asset_targets": _list(fraud.get("requested_assets") or fraud.get("target")),
        "fork_points": _list(fraud.get("critical_transitions") or fraud.get("critical_actions")),
        "intervention_window": _dict(fraud.get("recommended_timing")),
        "expected_warning": actions[0] if actions else "",
        "expected_safe_action": actions[1] if len(actions) > 1 else (actions[0] if actions else ""),
        "counterfactual_paths": {
            "selected_action": selected,
            "expected_effect": _dict(state.get("counterfactual_effect")),
        },
        "evidence_spans": _strings(fraud.get("evidence_spans") or state.get("evidence")),
        "confidence": fraud.get("confidence"),
    }


def _public_prediction(state: Mapping[str, Any]) -> Dict[str, Any]:
    public = _dict(state.get("public_opinion"))
    summary = _dict(state.get("summary"))
    selected = _selected(state)
    action = _action_text(selected)
    candidates = _list(public.get("candidate_interventions") or state.get("candidate_actions"))
    if not action and candidates:
        action = _action_text(_dict(candidates[0]))
    return {
        "event_summary": summary.get("text") or "",
        "narrative_threads": _list(public.get("narrative_threads") or public.get("core_claims")),
        "emotion_signal": _dict(public.get("polarization_signal")),
        "uncertainty_points": _list(public.get("uncertainty_points") or public.get("uncertainty")),
        "official_response_gap": _dict(public.get("source_status")),
        "propagation_risk_level": summary.get("risk_level") or public.get("misinformation_signal") or "unknown",
        "best_intervention_window": _dict(public.get("intervention_timing") or selected.get("best_intervention_window") or selected.get("timing")),
        "expected_intervention_action": str(public.get("recommended_intervention_action") or action),
        "expected_safe_public_action": str(public.get("recommended_public_action") or action),
        "evidence_spans": _strings(state.get("evidence")),
        "confidence": public.get("confidence"),
    }


def _event_prediction(state: Mapping[str, Any]) -> Dict[str, Any]:
    event = _dict(state.get("event_propagation"))
    summary = _dict(state.get("summary"))
    source_nodes = _list(event.get("source_nodes"))
    selected = _selected(state)
    action = str(event.get("containment_action") or _action_text(selected))
    return {
        "event_summary": event.get("original_claim") or summary.get("text") or "",
        "origin_node": _node(source_nodes[0]) if source_nodes else {},
        "amplifier_nodes": _list(event.get("amplifier_nodes")),
        "propagation_path": _list(event.get("cross_platform_path") or event.get("mutation_steps")),
        "distortion_points": _list(event.get("lost_context")),
        "coverage_risk": summary.get("risk_level") or event.get("certainty_change") or "unknown",
        "containment_window": _dict(event.get("containment_timing") or selected.get("best_intervention_window") or selected.get("timing")),
        "expected_containment_action": action,
        "evidence_spans": _strings(state.get("evidence")),
        "confidence": event.get("confidence"),
    }


def _cogsec_analysis(
    result: Mapping[str, Any], state: Mapping[str, Any], scenario: str
) -> Dict[str, Any]:
    extension = _dict(result.get("scenario_extension"))
    search = _dict(extension.get("propagation_intervention_search"))
    return {
        "scenario": scenario,
        "risk_graph": _dict(result.get("risk_graph_bundle")),
        "social_state": _dict(result.get("world_state_snapshot")),
        "evidence_trace": [
            {"id": f"ev:runtime:{index}", "text": span, "source": "canonical_runtime"}
            for index, span in enumerate(_strings(state.get("evidence")))
        ],
        "propagation_analysis": {
            "runtime": _dict(extension.get("propagation_normalized")),
            "intervention_search": search,
            "effective_selected_intervention": _selected(state),
        },
        "counterfactual_effect": _dict(state.get("counterfactual_effect")),
        "provenance": {
            **_dict(state.get("provenance")),
            "adapter_source": "canonical_report_state",
            "raw_input_used": False,
        },
    }


def _diagnostics(
    scenario: str, prediction: Mapping[str, Any], state: Mapping[str, Any]
) -> Dict[str, Any]:
    required = REQUIRED_BY_SCENARIO[scenario]
    missing = [field for field in required if field not in prediction]
    empty = [field for field in required if field in prediction and not _present(prediction[field])]
    warnings: List[str] = []
    if missing:
        warnings.append("missing_runtime_fields:" + ",".join(missing))
    if empty:
        warnings.append("empty_runtime_fields:" + ",".join(empty))
    return {
        "adapter_version": "runtime_export.v2",
        "source": "canonical_report_state",
        "required_fields": required,
        "missing_fields": missing,
        "empty_fields": empty,
        "field_coverage": round((len(required) - len(missing) - len(empty)) / max(1, len(required)), 3),
        "adapter_warnings": warnings,
        "report_state_schema": state.get("schema_version"),
        "inference_pass": {"used": False, "reason": "pure_runtime_export"},
        "raw_input_used": False,
    }


def _resolve_scenario(result: Mapping[str, Any], scenario_type: Optional[str]) -> str:
    candidates = [
        scenario_type,
        _dict(result.get("report_state")).get("scenario"),
        _dict(result.get("scenario_metadata")).get("canonical"),
        _dict(result.get("profile")).get("scenario_type"),
    ]
    aliases = {
        "fraud": "fraud_im", "fraud_im": "fraud_im",
        "public": "public_opinion", "public_opinion": "public_opinion",
        "event": "event_propagation", "event_propagation": "event_propagation",
    }
    for value in candidates:
        normalized = aliases.get(str(value or "").strip().lower())
        if normalized:
            return normalized
    return "fraud_im"


def _selected(state: Mapping[str, Any]) -> Dict[str, Any]:
    values = _list(state.get("selected_actions"))
    return _dict(values[0]) if values else {}


def _action_text(action: Mapping[str, Any]) -> str:
    return str(
        action.get("action")
        or action.get("message")
        or action.get("best_intervention_action")
        or action.get("action_description")
        or ""
    )


def _evidence_pack(evidence: Iterable[str]) -> List[Dict[str, Any]]:
    return [
        {"id": f"ev:runtime:{index}", "span": span, "supports": ["runtime_analysis"]}
        for index, span in enumerate(evidence)
    ]


def _node(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    text = str(value or "").strip()
    return {"id": text, "label": text} if text else {}


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip()) and value.strip().lower() not in {"unknown", "unavailable", "not_available"}
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def _dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [] if value is None else [value]


def _strings(value: Any) -> List[str]:
    output: List[str] = []
    for item in _list(value):
        if isinstance(item, Mapping):
            item = item.get("text") or item.get("span") or item.get("label") or item.get("id")
        text = str(item or "").strip()
        if text and text not in output:
            output.append(text)
    return output

"""Canonical, scenario-aware state consumed by the final Reporter.

``ReportState`` is an online-runtime boundary.  It is built only from the
canonical runtime analysis and counterfactual-search state.  Benchmark
predictions and score-oriented post-processors must never feed it, otherwise
benchmark-specific wording can leak back into the user-facing answer.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping


MECHANISM_LABELS = {
    "private_contact_lure": "转入私人渠道后，核验、举报和追责能力下降",
    "unlicensed_financial_service": "以未核验的信用卡代还、刷卡或低点位服务诱导交付资产",
    "transfer_money": "诱导付款、充值或转账",
    "phishing_link_entry": "诱导点击链接并提交账号凭证",
    "screen_share": "诱导开启屏幕共享或远程控制",
    "verification_code": "诱导提供验证码或动态口令",
}


def build_report_state(result: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize canonical runtime outputs into one bounded Report State.

    Missing values remain explicit.  In particular, this function deliberately
    ignores ``benchmark_prediction``, ``cogsec_analysis`` and ``agent_states``:
    those are evaluation/export artefacts, not online sources of truth.
    """
    scenario = _scenario(result)
    core = _dict(result.get("core_analysis"))
    prediction = dict(core)

    search = _dict(_dict(result.get("scenario_extension")).get("propagation_intervention_search"))
    selected = _selected(search)
    evidence = _evidence(prediction)
    candidates = _candidate_actions(search)
    runtime_provenance = _dict(search.get("provenance"))
    provenance = {
        **_dict(core.get("provenance")),
        **runtime_provenance,
        "metric_source": runtime_provenance.get("metric_source") or "runtime",
        "has_oasis_counterfactual_branches": bool(runtime_provenance.get("has_oasis_counterfactual_branches", False)),
        "state_builder": "build_report_state",
        "source_contract": "canonical_runtime -> report_state -> reporter",
    }

    state: Dict[str, Any] = {
        "schema_version": "report_state.v2",
        "scenario": scenario,
        "summary": {
            "text": prediction.get("event_summary") or prediction.get("summary") or prediction.get("assessment") or "",
            "risk_level": prediction.get("risk_level") or prediction.get("propagation_risk_level") or prediction.get("coverage_risk") or "unknown",
        },
        "actors": _as_list(prediction.get("actors")),
        "claims": _as_list(prediction.get("claims") or prediction.get("narrative_threads")),
        "evidence": evidence,
        "mechanisms": _mechanisms(prediction, selected),
        "stage": prediction.get("attack_stage") or prediction.get("containment_window") or prediction.get("best_intervention_window") or "",
        "candidate_actions": candidates,
        "selected_actions": [selected] if selected else [],
        "counterfactual_effect": _dict(selected.get("final_metrics")) if selected else _dict(search.get("selection_metrics")),
        "provenance": provenance,
        "is_direct_llm_baseline": bool(result.get("is_direct_llm_baseline") or core.get("is_direct_llm_baseline")),
        "direct_llm": {
            "summary": core.get("summary") or core.get("assessment"),
            "evidence": _as_list(core.get("evidence")),
            "recommended_action": core.get("recommended_action"),
            "assistant_message": core.get("assistant_message"),
        } if result.get("is_direct_llm_baseline") or core.get("is_direct_llm_baseline") else {},
    }

    if scenario == "fraud_im":
        fraud = {
            "risk_type": prediction.get("fraud_type") or "unknown",
            "threat_level": prediction.get("threat_level") or prediction.get("risk_level") or "unknown",
            "personalized_outcome_risk_level": prediction.get("personalized_outcome_risk_level") or "unknown",
            "actor": _first_actor(prediction),
            "target": _as_list(prediction.get("asset_targets")),
            "current_stage": prediction.get("attack_stage") or "unknown",
            "critical_transitions": _as_list(prediction.get("fork_points")),
            "requested_assets": _as_list(prediction.get("asset_targets")),
            "evidence_spans": evidence,
            "mechanisms": _mechanisms(prediction, selected),
            "recommended_actions": _unique([prediction.get("expected_warning"), prediction.get("expected_safe_action")]),
            "recommended_timing": prediction.get("intervention_window") or {},
            "action_actor": prediction.get("action_actor") or "用户/平台",
            "action_target": prediction.get("action_target") or _as_list(prediction.get("asset_targets")),
            "confidence": prediction.get("confidence"),
            "provenance": _runtime_provenance("fraud"),
        }
        # Compatibility aliases used by older UI/report code.
        fraud["attack_stage"] = fraud["current_stage"]
        fraud["critical_actions"] = fraud["critical_transitions"]
        fraud["mechanism"] = fraud["mechanisms"]
        state["fraud"] = fraud
    elif scenario == "public_opinion":
        public = {
            "core_claims": _as_list(prediction.get("core_claims") or prediction.get("narrative_threads") or prediction.get("claims")),
            "narrative_threads": _as_list(prediction.get("narrative_threads")),
            "uncertainty_points": _as_list(prediction.get("uncertainty_points")),
            "source_status": _dict(prediction.get("source_status") or prediction.get("official_response_gap")),
            "affected_communities": _as_list(prediction.get("affected_communities")),
            "bridge_nodes": _as_list(prediction.get("bridge_nodes")),
            "key_nodes": _as_list(prediction.get("key_nodes") or prediction.get("important_nodes")),
            "misinformation_signal": prediction.get("misinformation_signal") or prediction.get("propagation_risk_level"),
            "polarization_signal": prediction.get("polarization_signal") or _dict(prediction.get("emotion_signal")),
            "fragmentation_signal": prediction.get("fragmentation_signal") or _dict(_dict(prediction.get("narrative_analysis")).get("fragmentation")),
            "candidate_interventions": candidates,
            "selected_interventions": [selected] if selected else [],
            "intervention_actor": _action_value(selected, "actor") or prediction.get("intervention_actor") or "平台/核验主体",
            "intervention_target": _action_value(selected, "target_nodes") or prediction.get("intervention_target") or [],
            "intervention_type": _action_value(selected, "intervention_type") or prediction.get("intervention_type") or "",
            "intervention_timing": _action_value(selected, "best_intervention_window") or prediction.get("best_intervention_window") or {},
            "intervention_strength": _action_value(selected, "strength") or prediction.get("intervention_strength"),
            "expected_effect": _dict(selected.get("final_metrics")) if selected else {},
            "recommended_intervention_action": prediction.get("expected_intervention_action") or "",
            "recommended_public_action": prediction.get("expected_safe_public_action") or "",
            "confidence": prediction.get("confidence"),
            "provenance": _runtime_provenance("public"),
        }
        public["uncertainty"] = public["uncertainty_points"]
        public["source_status_legacy"] = public["source_status"]
        state["public_opinion"] = public
    elif scenario == "event_propagation":
        event = {
            "original_claim": prediction.get("original_claim") or prediction.get("event_summary") or "",
            "mutation_steps": _as_list(prediction.get("mutation_steps") or prediction.get("propagation_path")),
            "lost_context": _as_list(prediction.get("lost_context") or prediction.get("distortion_points")),
            "certainty_change": prediction.get("certainty_change") or prediction.get("coverage_risk"),
            "source_nodes": _as_list(prediction.get("source_nodes") or prediction.get("origin_node")),
            "amplifier_nodes": _as_list(prediction.get("amplifier_nodes")),
            "bridge_nodes": _as_list(prediction.get("bridge_nodes")),
            "cross_platform_path": _as_list(prediction.get("cross_platform_path") or prediction.get("propagation_path")),
            "correction_status": prediction.get("correction_status") or _dict(prediction.get("official_response_gap")),
            "correction_binding": prediction.get("correction_binding") or "unknown",
            "containment_actor": _action_value(selected, "actor") or prediction.get("containment_actor") or "平台/来源方",
            "containment_target": _action_value(selected, "target_nodes") or prediction.get("containment_target") or [],
            "containment_action": _action_value(selected, "best_intervention_action") or _action_value(selected, "message") or prediction.get("expected_containment_action") or "",
            "containment_timing": _action_value(selected, "best_intervention_window") or prediction.get("containment_window") or {},
            "expected_effect": _dict(selected.get("final_metrics")) if selected else {},
            "confidence": prediction.get("confidence"),
            "provenance": _runtime_provenance("event"),
        }
        event["intervention"] = selected or {"action": event["containment_action"]}
        state["event_propagation"] = event

    state["field_provenance"] = _field_provenance(
        state=state,
        prediction=prediction,
        evidence=evidence,
        selected=selected,
    )
    return state


def _field_provenance(
    *, state: Dict[str, Any], prediction: Dict[str, Any], evidence: List[str], selected: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """Return provenance for normalized fields, not merely a global source."""
    scenario = state.get("scenario", "unknown")
    branch = {"fraud_im": "fraud", "public_opinion": "public_opinion", "event_propagation": "event_propagation"}.get(scenario)
    if not branch:
        return {}
    values = state.get(branch, {}) if isinstance(state.get(branch), dict) else {}
    output: Dict[str, Dict[str, Any]] = {}
    for field, value in values.items():
        if field.endswith("_legacy") or field in {"provenance"}:
            continue
        source_field = _source_field(field, prediction)
        output[f"{branch}.{field}"] = {
            "value": value,
            "source_agent": None,
            "source_state_field": source_field,
            "evidence_refs": _evidence_refs(value, evidence),
            "transform_chain": ["canonical_runtime", "report_state_normalization"],
            "confidence": values.get("confidence") if field != "confidence" else value,
            "fallback_used": source_field not in prediction,
            "reason": "runtime field normalized" if source_field in prediction else "field unavailable",
        }
    return output


def _source_field(field: str, prediction: Dict[str, Any]) -> str:
    aliases = {
        "risk_type": "fraud_type", "current_stage": "attack_stage", "mechanisms": "fork_points",
        "threat_level": "threat_level", "personalized_outcome_risk_level": "personalized_outcome_risk_level",
        "core_claims": "narrative_threads", "source_status": "official_response_gap",
        "misinformation_signal": "propagation_risk_level", "polarization_signal": "emotion_signal",
        "fragmentation_signal": "narrative_analysis", "original_claim": "event_summary",
        "mutation_steps": "propagation_path", "lost_context": "distortion_points",
        "certainty_change": "coverage_risk", "cross_platform_path": "propagation_path",
        "containment_action": "expected_containment_action", "containment_timing": "containment_window",
        "recommended_timing": "intervention_window", "recommended_actions": "expected_safe_action",
    }
    return aliases.get(field, field)


def _evidence_refs(value: Any, evidence: List[str]) -> List[str]:
    text = str(value or "")
    return [f"ev:{span}" for span in evidence if span and (span in text or isinstance(value, (list, dict)))][:8]


def _runtime_provenance(label: str) -> Dict[str, Any]:
    return {"state_branch": label, "source": "canonical_runtime"}


def _scenario(result: Dict[str, Any]) -> str:
    meta = _dict(result.get("scenario_metadata"))
    profile = _dict(result.get("profile"))
    return str(meta.get("canonical") or profile.get("scenario_type") or "unknown")


def _selected(search: Dict[str, Any]) -> Dict[str, Any]:
    for value in (
        search.get("effective_selected_intervention"),
        search.get("selected_best_branch"),
    ):
        if isinstance(value, dict) and value:
            return dict(value)
    return {}


def _evidence(prediction: Dict[str, Any]) -> List[str]:
    observed: List[str] = []
    runtime_supported: List[str] = []
    for item in _as_list(prediction.get("evidence_spans")) + _as_list(prediction.get("evidence_trace")):
        source = str(item.get("source") or "") if isinstance(item, dict) else ""
        value = item.get("text") or item.get("span") if isinstance(item, dict) else item
        if isinstance(value, (str, int, float)) and str(value).strip():
            text = str(value).strip()
            if source in {"canonical_case", "input_text", "user_input", "chat", "text"}:
                observed.append(text)
            elif source != "risk_graph":
                runtime_supported.append(text)
    # RiskGraph/RAG phrases may be synthetic strategy evidence.  They remain in
    # the machine payload but are never quoted to the user as if they appeared
    # in the original input.
    return _minimal_unique(observed or runtime_supported)


def _mechanisms(prediction: Dict[str, Any], selected: Dict[str, Any]) -> List[str]:
    values: List[str] = []
    for item in _as_list(prediction.get("fork_points")):
        if isinstance(item, dict):
            reason = item.get("reason") or item.get("description")
            values.append(str(reason or MECHANISM_LABELS.get(str(item.get("type") or ""), item.get("type") or "")))
    for key in ("expected_mechanism", "expected_intervention_action", "expected_containment_action"):
        if prediction.get(key):
            values.append(str(prediction[key]))
    if selected.get("message"):
        values.append(str(selected["message"]))
    return _minimal_unique(values)


def _candidate_actions(search: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = search.get("intervention_candidates") or _dict(search.get("branch_comparison")).get("ranked_branches") or []
    output = []
    for item in candidates:
        if not isinstance(item, dict):
            continue
        output.append({
            "candidate_id": item.get("candidate_id"),
            "candidate_type": item.get("intervention_type") or item.get("action_type"),
            "action": item.get("message") or item.get("best_intervention_action") or item.get("action_description") or item.get("action"),
            "actor": item.get("actor") or item.get("intervention_actor"),
            "target_nodes": _as_list(item.get("target_nodes")),
            "target_communities": _as_list(item.get("target_communities")),
            "target_content": _as_list(item.get("target_content")),
            "timing": item.get("best_intervention_window") or item.get("timing") or {},
            "strength": item.get("strength"),
            "expected_effect": _dict(item.get("final_metrics") or item.get("expected_effect")),
            "metric_source": item.get("metric_source") or _dict(search.get("provenance")).get("metric_source", "proxy"),
            "provenance": item.get("provenance") or {},
        })
    return output[:6]


def _action_value(action: Dict[str, Any], key: str) -> Any:
    return action.get(key) if isinstance(action, dict) else None


def _first_actor(prediction: Dict[str, Any]) -> Any:
    actors = _as_list(prediction.get("actors"))
    return actors[0] if actors else "对方/信息发布者"


def _minimal_unique(values: Iterable[Any]) -> List[str]:
    cleaned = [str(item).strip() for item in values if str(item).strip()]
    output: List[str] = []
    for item in cleaned:
        if item in output or any(item in existing for existing in output):
            continue
        output = [existing for existing in output if existing not in item]
        output.append(item)
    return output


def _unique(values: Iterable[Any]) -> List[str]:
    output: List[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in output:
            output.append(text)
    return output


def _dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    return [] if value is None else [value]

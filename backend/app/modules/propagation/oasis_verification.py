"""Supported-candidate OASIS verification for proxy-selected interventions.

Round 2 Completion: wires proxy → Top-K selection → OASIS verification into
the official call path.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from .intervention_search import _candidate_identity
from .schema import PropagationAgent, PropagationEvent


EFFECT_EPSILON = 1e-6


def _metric_semantics() -> Dict[str, Any]:
    return {
        "primary_metric": "organic_propagation_coverage",
        "direction": "lower_is_better",
        "system_intervention_action_excluded": True,
        "content_semantics_classified": False,
        "interpretation": "propagation_activity_proxy",
    }


def _proxy_selected(proxy_result: Dict[str, Any], ranked: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return the proxy winner while retaining candidate contract fields."""
    selected = proxy_result.get("selected_best_branch")
    selected = selected if isinstance(selected, dict) else {}
    selected_id = selected.get("candidate_id")
    ranked_match = next(
        (item for item in ranked if item.get("candidate_id") == selected_id),
        ranked[0] if ranked else {},
    )
    proxy = {**ranked_match, **selected}
    if proxy:
        proxy.setdefault("metric_source", "proxy")
        proxy.setdefault("proxy_score", proxy.get("total_score", 0.0))
    return proxy


def _effectiveness_status(signed_utility: Optional[float]) -> str:
    if signed_utility is None:
        return "unknown"
    if signed_utility > EFFECT_EPSILON:
        return "effective"
    if signed_utility < -EFFECT_EPSILON:
        return "harmful"
    return "neutral"


def _is_oasis_verifiable(candidate: Dict[str, Any]) -> bool:
    """Return whether the current adapter can execute this candidate honestly."""
    return (
        candidate.get("intervention_type") == "official_response"
        and not (candidate.get("target_nodes") or [])
    )


def run_topk_oasis_verification(
    *,
    scenario_type: str,
    seed_text: str,
    agents: List[PropagationAgent],
    proxy_result: Dict[str, Any],
    quick_mode: bool = True,
    k: int = 1,
    seed: int = 42,
    snapshot: Any = None,
    simulation_state_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Run supported-candidate OASIS verification for proxy-ranked candidates.

    Parameters
    ----------
    proxy_result:
        Output from ``run_proxy_intervention_search``.
    quick_mode:
        If True, K=1; otherwise K=2.
    snapshot:
        Optional SocialStateSnapshot for OASIS initialization.

    Returns
    -------
    dict with:
        - proxy_ranked_candidates
        - top_k_selected
        - oasis_verified_branches
        - final_ranking
        - provenance
    """
    # Determine effective K: quick_mode → 1, normal → max(requested_k, 2)
    quick_multi_candidate = os.environ.get(
        "MIRO_OASIS_QUICK_MULTI_CANDIDATE", "false"
    ).lower() == "true"
    if quick_mode:
        effective_k = max(1, k) if quick_multi_candidate else 1
    else:
        effective_k = max(k, 2)  # normal mode defaults to Top-2

    shared_state_provenance = {
        "simulation_state_id": simulation_state_id,
        "initial_state_source": "canonical_social_state" if simulation_state_id else "legacy_agent_input",
        "shared_initial_world": simulation_state_id is not None,
    }

    # Preserve proxy order while making the two ranking spaces explicit.
    raw_ranked = proxy_result.get("branch_comparison", {}).get("ranked_branches", [])
    if not raw_ranked:
        return {
            "status": "no_candidates",
            "proxy_ranked_candidates": [],
            "top_k_selected": [],
            "top_k_oasis_attempted": 0,
            "top_k_oasis_completed": 0,
            "selected": {},
            "requested_k": k,
            "effective_k": effective_k,
            "verifiable_candidate_count": 0,
            "oasis_verification": {
                "attempted": False, "completed": False,
                "status": "not_run",
                "reason": "no proxy candidates to verify",
            },
            "provenance": "proxy_only",
            **shared_state_provenance,
            "selection_source": "proxy",
            "metric_source": "proxy",
        }

    ranked = []
    for proxy_rank, candidate in enumerate(raw_ranked, start=1):
        item = dict(candidate) if isinstance(candidate, dict) else {}
        item["proxy_rank"] = proxy_rank
        item.setdefault("proxy_score", item.get("total_score", 0.0))
        ranked.append(item)
    verifiable_candidates = [item for item in ranked if _is_oasis_verifiable(item)]
    top_k = verifiable_candidates[:effective_k]
    proxy_selected = _proxy_selected(proxy_result, ranked)

    # Check availability and project-specific credentials before classifying
    # candidates.  If OASIS cannot run, the honest status is ``not_run`` even
    # when a proxy candidate is not executable by the OASIS adapter.
    try:
        from .oasis_adapter import (
            OasisPropagationAdapter,
            UnsupportedOasisIntervention,
            _OASIS_AVAILABLE,
        )  # noqa: F811
    except ImportError:
        _OASIS_AVAILABLE = False

    if not _OASIS_AVAILABLE:
        return {
            "proxy_ranked_candidates": ranked,
            "top_k_selected": top_k,
            "top_k_oasis_attempted": 0,
            "top_k_oasis_completed": 0,
            "selected": proxy_selected,
            "oasis_verified": False,
            "oasis_effective": False,
            "requested_k": k,
            "effective_k": effective_k,
            "verifiable_candidate_count": len(verifiable_candidates),
            "oasis_verification": {
                "attempted": False, "completed": False,
                "status": "not_run",
                "reason": "camel-oasis not installed",
            },
            "final_ranking": ranked,
            "provenance": "proxy_only",
            **shared_state_provenance,
            "selection_source": "proxy",
            "metric_source": "proxy",
        }

    # Project-specific OASIS credentials are intentionally separate from the
    # main analysis API key.  Missing config means no verified branch ran.
    llm_api_key = os.environ.get("MIRO_COGSEC_OASIS_API_KEY")
    llm_base_url = os.environ.get("MIRO_COGSEC_OASIS_BASE_URL")
    llm_model_name = os.environ.get("MIRO_COGSEC_OASIS_MODEL")
    if not all((llm_api_key, llm_base_url, llm_model_name)):
        return {
            "proxy_ranked_candidates": ranked,
            "top_k_selected": top_k,
            "top_k_oasis_attempted": 0,
            "top_k_oasis_completed": 0,
            "oasis_verification": {
                "attempted": False, "completed": False,
                "status": "not_run",
                "verification_status": "not_run",
                "reason": "project_specific_oasis_key_not_configured",
            },
            "final_ranking": ranked,
            "selected": proxy_selected,
            "provenance": "proxy_only",
            **shared_state_provenance,
            "selection_source": "proxy",
            "metric_source": "proxy",
            "oasis_verified": False,
            "oasis_effective": False,
            "requested_k": k,
            "effective_k": effective_k,
            "verifiable_candidate_count": len(verifiable_candidates),
        }

    if not verifiable_candidates:
        unsupported_branches = []
        for candidate in ranked:
            unsupported_branches.append({
                **candidate,
                "oasis_verification": {
                    "attempted": False, "completed": False,
                    "status": "unsupported",
                    "reason": "no_oasis_verifiable_candidate",
                },
                "verification_status": "unsupported",
                "metric_source": "proxy",
                "utility": 0.0,
            })
        return {
            "proxy_ranked_candidates": ranked,
            "top_k_selected": [],
            "oasis_verified_branches": unsupported_branches,
            "final_ranking": unsupported_branches,
            "selected": proxy_selected,
            "oasis_verification": {
                "attempted": True, "completed": False,
                "status": "unsupported",
                "verification_status": "unsupported",
                "reason": "no_oasis_verifiable_candidate",
            },
            "provenance": "proxy_only",
            **shared_state_provenance,
            "selection_source": "proxy",
            "metric_source": "proxy",
            "oasis_verified": False,
            "oasis_effective": False,
            "requested_k": k,
            "effective_k": effective_k,
            "verifiable_candidate_count": 0,
            "intra_run_ab_comparisons": 0,
            "top_k_oasis_attempted": 0,
            "top_k_oasis_completed": 0,
        }

    # Build event
    event = PropagationEvent.create(
        scenario_type=scenario_type,
        seed_text=seed_text,
        risk_dimensions=_risk_dims(scenario_type),
    )

    # Each candidate run contains Branch A and Branch B, both initialized from
    # the supplied canonical S0 snapshot and actor mapping.
    n_agents = (
        max(2, int(os.environ.get("MIRO_OASIS_QUICK_N_AGENTS", "12")))
        if quick_mode else 50
    )
    ticks = (
        max(1, int(os.environ.get("MIRO_OASIS_QUICK_TICKS", "5")))
        if quick_mode else 20
    )

    oasis = OasisPropagationAdapter()

    # Keep unsupported proxy candidates for provenance, but spend OASIS budget
    # only inside the verifiable subset.
    verified_branches = []
    unsupported_branches = []
    for candidate in ranked:
        if not _is_oasis_verifiable(candidate):
            unsupported_branches.append({
                **candidate,
                "oasis_verification": {
                    "attempted": False, "completed": False,
                    "status": "unsupported",
                    "reason": "oasis_action_not_supported",
                },
                "verification_status": "unsupported",
                "metric_source": "proxy",
                "utility": 0.0,
            })

    for verification_rank, candidate in enumerate(top_k, start=1):
        candidate_id = candidate.get("candidate_id", "unknown")
        intervention_type = candidate.get("intervention_type", "official_response")
        candidate_message = candidate.get("message", "")
        target_nodes = candidate.get("target_nodes", [])
        intervention_tick_candidate = candidate.get("intervention_tick", max(1, ticks // 3))
        evidence_basis = candidate.get("evidence_basis", [])

        # Build candidate-specific intervention payload
        candidate_intervention = {
            "candidate_id": candidate_id,
            "intervention_type": intervention_type,
            "message": candidate_message,
            "target_nodes": target_nodes,
            "intervention_tick": intervention_tick_candidate,
            "evidence_basis": evidence_basis,
        }

        # Defensive guard: the subset filter above should make this branch
        # unreachable, but unsupported actions must never reach the adapter.
        if not _is_oasis_verifiable(candidate):
            verified_branches.append({
                **candidate,
                "candidate_id": candidate_id,
                "intervention_type": intervention_type,
                "intervention_tick": intervention_tick_candidate,
                "target_nodes": target_nodes,
                "message": candidate_message,
                "oasis_verification_rank": verification_rank,
                "oasis_verification": {
                    "attempted": False, "completed": False,
                    "status": "unsupported",
                    "reason": "oasis_action_not_supported",
                },
                "verification_status": "unsupported",
                "metric_source": "proxy",
                "proxy_score": candidate.get("total_score", 0.0),
                "utility": 0.0,
            })
            continue

        try:
            candidate_result = oasis.run(
                event=event, agents=agents, scenario_type=scenario_type,
                n_ticks=ticks, intervention_tick=intervention_tick_candidate,
                llm_api_key=llm_api_key,
                llm_base_url=llm_base_url,
                llm_model_name=llm_model_name,
                snapshot=snapshot, seed=seed,
                intervention=candidate_intervention,
            )
            baseline_metrics = candidate_result.branch_a.final_metrics
            intervention_metrics = candidate_result.branch_b.final_metrics

            # Compare Branch A and Branch B from this same candidate run.
            base_cov = baseline_metrics.get(
                "organic_propagation_coverage",
                baseline_metrics.get("cumulative_coverage"),
            )
            cand_cov = intervention_metrics.get(
                "organic_propagation_coverage",
                intervention_metrics.get("cumulative_coverage"),
            )
            metric_values_available = base_cov is not None and cand_cov is not None
            signed_utility = (
                round(float(base_cov) - float(cand_cov), 6)
                if metric_values_available else None
            )
            effectiveness_status = _effectiveness_status(signed_utility)
            delta = {
                "coverage_reduction": signed_utility,
                "action_delta": (
                    baseline_metrics.get("total_actions", 0)
                    - intervention_metrics.get("total_actions", 0)
                ),
            }

            verified_branches.append({
                **candidate,
                "candidate_id": candidate_id,
                "intervention_type": intervention_type,
                "intervention_tick": intervention_tick_candidate,
                "target_nodes": target_nodes,
                "message": candidate_message,
                "oasis_verification_rank": verification_rank,
                "best_intervention_window": {
                    "open_step": intervention_tick_candidate,
                    "close_step": intervention_tick_candidate + 1,
                    "open_stage": candidate.get("target_stage", "early"),
                    "label": f"{candidate.get('target_stage', 'early')} stage {intervention_type}",
                },
                "best_intervention_action": candidate_message,
                "selection_reason": "OASIS intra-run Branch A/B utility verification",
                "oasis_verification": {
                    "attempted": True, "completed": True, "status": "completed",
                },
                "verification_status": "executed",
                "baseline_metrics": baseline_metrics,
                "intervention_metrics": intervention_metrics,
                "delta": delta,
                "baseline_coverage": base_cov,
                "candidate_coverage": cand_cov,
                "coverage_reduction": signed_utility,
                "signed_utility": signed_utility,
                "utility": signed_utility,
                "effectiveness_status": effectiveness_status,
                "metric_semantics": _metric_semantics(),
                "proxy_score": candidate.get("total_score", 0.0),
                "metric_source": "oasis",
                "oasis_verified_metrics": intervention_metrics,
            })
        except UnsupportedOasisIntervention as exc:
            verified_branches.append({
                **candidate,
                "candidate_id": candidate_id,
                "intervention_type": intervention_type,
                "intervention_tick": intervention_tick_candidate,
                "target_nodes": target_nodes,
                "message": candidate_message,
                "oasis_verification_rank": verification_rank,
                "oasis_verification": {
                    "attempted": True, "completed": False,
                    "status": "unsupported", "reason": str(exc),
                },
                "verification_status": "unsupported",
                "proxy_score": candidate.get("total_score", 0.0),
                "metric_source": "proxy",
                "utility": 0.0,
            })
        except Exception as exc:
            verified_branches.append({
                **candidate,
                "candidate_id": candidate_id,
                "intervention_type": intervention_type,
                "intervention_tick": intervention_tick_candidate,
                "target_nodes": target_nodes,
                "message": candidate_message,
                "oasis_verification_rank": verification_rank,
                "oasis_verification": {
                    "attempted": True, "completed": False,
                    "status": "failed", "reason": str(exc),
                },
                "verification_status": "failed",
                "proxy_score": candidate.get("total_score", 0.0),
                "metric_source": "proxy",
                "utility": 0.0,
            })

    verified_branches.extend(unsupported_branches)

    successful_oasis_results = [
        result for result in verified_branches
        if result.get("verification_status") == "executed"
        and result.get("metric_source") == "oasis"
        and result.get("effectiveness_status") == "effective"
    ]
    executed_oasis_results = [
        result for result in verified_branches
        if result.get("verification_status") == "executed"
        and result.get("metric_source") == "oasis"
    ]
    effective_ids = {
        _candidate_identity(result)
        for result in successful_oasis_results
    }
    negative_vetoed_ids = {
        _candidate_identity(result)
        for result in executed_oasis_results
        if result.get("effectiveness_status") == "harmful"
    }
    successful_oasis_results = [
        result for result in successful_oasis_results
        if _candidate_identity(result) not in negative_vetoed_ids
    ]
    proxy_results = [
        result for result in ranked
        if _candidate_identity(result) not in effective_ids
        and _candidate_identity(result) not in negative_vetoed_ids
    ]
    oasis_audit_branches = [
        result for result in executed_oasis_results
        if result.get("effectiveness_status") != "effective"
    ]
    # Ranking policy is source-first; proxy scores are never compared directly
    # with OASIS utility values.
    final_ranking = (
        sorted(successful_oasis_results, key=lambda result: result.get("utility", 0.0), reverse=True)
        + sorted(proxy_results, key=lambda result: result.get("proxy_score", 0.0), reverse=True)
    )
    selected = successful_oasis_results[0] if successful_oasis_results else next(
        (
            candidate for candidate in ranked
            if _candidate_identity(candidate) not in negative_vetoed_ids
        ),
        {},
    )
    selected_metric_source = (selected or {}).get("metric_source", "proxy")
    completed_count = sum(
        1 for branch in verified_branches
        if branch["oasis_verification"]["completed"]
    )
    if completed_count:
        verification_status = {
            "attempted": True,
            "completed": True,
            "status": "complete",
        }
    else:
        verification_status = {
            "attempted": bool(top_k),
            "completed": False,
            "status": "degraded" if top_k else "unsupported",
            "verification_status": "failed" if top_k else "unsupported",
            "reason": (
                "all_oasis_candidates_failed"
                if top_k else "no_oasis_verifiable_candidate"
            ),
        }
    return {
        "proxy_ranked_candidates": ranked,
        "top_k_selected": top_k,
        "oasis_verified_branches": verified_branches,
        "final_ranking": final_ranking,
        "selected": selected,
        "oasis_verification": verification_status,
        "provenance": "proxy_and_oasis_verified" if executed_oasis_results else "proxy_only",
        **shared_state_provenance,
        "selection_source": "oasis" if successful_oasis_results else "proxy",
        "metric_source": selected_metric_source,
        "oasis_verified": bool(executed_oasis_results),
        "oasis_effective": bool(successful_oasis_results),
        "negative_veto_applied": bool(negative_vetoed_ids),
        "negative_vetoed_candidate_ids": sorted(
            identity[1]
            for identity in negative_vetoed_ids
            if identity and identity[0] == "candidate_id"
        ),
        "selection_reason": (
            "OASIS positive promotion"
            if successful_oasis_results
            else "proxy fallback after OASIS harmful candidate veto"
            if negative_vetoed_ids and selected
            else "no non-vetoed proxy candidate remains"
            if negative_vetoed_ids and not selected
            else "proxy ranking"
        ),
        "oasis_audit_branches": oasis_audit_branches,
        "requested_k": k,
        "effective_k": effective_k,
        "verifiable_candidate_count": len(verifiable_candidates),
        "intra_run_ab_comparisons": len(executed_oasis_results),
        "top_k_oasis_attempted": len(top_k),
        "top_k_oasis_completed": sum(1 for b in verified_branches if b["oasis_verification"]["completed"]),
    }


def _risk_dims(scenario_type: str) -> List[str]:
    if scenario_type == "public_opinion":
        return ["narrative_intensity", "propagation_velocity", "polarization_index", "information_health"]
    if scenario_type == "event_propagation":
        return ["propagation_speed", "distortion_index", "engagement_depth", "containment_feasibility"]
    return ["risk"]

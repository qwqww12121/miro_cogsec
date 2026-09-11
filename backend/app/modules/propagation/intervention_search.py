"""Counterfactual intervention search for propagation scenarios.

The search layer is deliberately above the OASIS / lightweight propagation
runtime. It generates several intervention candidates, runs comparable
counterfactual branches with the available local propagation simulator, then
selects the branch with the best risk-reduction / cost tradeoff.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .agent_factory import build_agents
from .narrative_model import (
    NarrativeRelation,
    NarrativeState,
    build_narrative_relations,
    extract_public_opinion_narratives,
)
from ..social_state.behavior import update_institutional_trust
from .schema import PropagationAgent, PropagationEvent, PropagationTrace
from .simulator import run_propagation_simulation
from .topology import build_topology
from .intervention_ranker import normalize_ranker_mode, rank_branches
from .causal_targeting import select_causal_targets

try:  # supports both ``app.modules`` runtime imports and legacy test imports
    from ...config import Config
except ImportError:  # pragma: no cover - exercised by the legacy ``modules`` path
    from app.config import Config


_OFFICIAL_ROLES = {"school_official", "official_responder", "police_or_bank", "fact_checker"}
_AMPLIFIER_ROLES = {
    "anonymous_amplifier",
    "controversy_amplifier",
    "repost_kol",
    "media_observer",
    "student_kol",
}
_VULNERABLE_ROLES = {"ordinary_student", "ordinary_viewer", "victim"}
_ACTOR_BROADCAST_INTERVENTIONS = {"official_response", "clarification", "friction_prompt", "warning"}
_INTERVENTION_ACTION_TYPES = {
    "official_response", "community_note", "downranking", "friction_prompt",
    "source_verification", "content_labeling", "node_targeting", "debunking",
    "bind_correction", "preserve_context", "label_uncertainty",
    "target_amplifier",
}


def validate_intervention_candidate(candidate: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    """Validate an executable propagation action at the simulation boundary."""
    del scenario  # The current propagation runtimes share the same action schema.
    errors: List[str] = []
    action_type = str(candidate.get("intervention_type") or candidate.get("action_type") or "")
    if action_type not in _INTERVENTION_ACTION_TYPES:
        errors.append("unsupported_action_type")
    if not isinstance(candidate.get("target_nodes", []), list):
        errors.append("target_nodes_must_be_list")
    tick = candidate.get("intervention_tick")
    if tick is not None and (not isinstance(tick, int) or tick < 0):
        errors.append("invalid_intervention_tick")
    strength = candidate.get("strength")
    if strength is not None and (
        not isinstance(strength, (int, float)) or not 0 <= float(strength) <= 1
    ):
        errors.append("strength_out_of_range")
    if action_type in {"downranking", "node_targeting", "target_amplifier"} and not candidate.get("target_nodes"):
        errors.append("target_nodes_required_for_scoped_action")
    return {
        "valid": not errors,
        "errors": errors,
        "constraint": "actor/action/target/timing/strength",
    }


def actor_is_direct_intervention_target(
    *,
    intervention_type: str,
    target_nodes: Iterable[str],
    actor_id: str,
    fallback_target_nodes: Optional[Iterable[str]] = None,
) -> bool:
    """Apply actor-level scope without changing downstream propagation.

    Explicit targets are always strict.  Empty targets retain only the
    existing broadcast semantics (official/clarification and global
    friction/warning); node interventions may use their existing key-node
    fallback supplied by the caller.
    """
    explicit_targets = {str(item) for item in (target_nodes or [])}
    if explicit_targets:
        return str(actor_id) in explicit_targets
    fallback_targets = {str(item) for item in (fallback_target_nodes or [])}
    if fallback_targets:
        return str(actor_id) in fallback_targets
    return str(intervention_type) in _ACTOR_BROADCAST_INTERVENTIONS


@dataclass
class InterventionCandidate:
    candidate_id: str
    intervention_type: str
    target_nodes: List[str]
    target_stage: str
    intervention_tick: int
    message: str
    expected_mechanism: str
    evidence_basis: List[str]
    cost: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "intervention_type": self.intervention_type,
            "target_nodes": self.target_nodes,
            "target_stage": self.target_stage,
            "intervention_tick": self.intervention_tick,
            "message": self.message,
            "expected_mechanism": self.expected_mechanism,
            "evidence_basis": self.evidence_basis,
            "intervention_cost": self.cost,
        }


def resolve_effective_intervention(search_result: Dict[str, Any]) -> Dict[str, Any]:
    """Resolve the final intervention without mixing proxy/OASIS score scales."""
    proxy_selected = search_result.get("proxy_selected_intervention")
    if not isinstance(proxy_selected, dict) or not proxy_selected:
        proxy_selected = search_result.get("selected_best_branch")
    proxy_selected = proxy_selected if isinstance(proxy_selected, dict) else {}

    oasis_verification = search_result.get("oasis_verification")
    oasis_verification = oasis_verification if isinstance(oasis_verification, dict) else {}
    negative_vetoed_ids = _negative_vetoed_candidate_ids(oasis_verification)
    explicit_effective = search_result.get("effective_selected_intervention")
    if (
        isinstance(explicit_effective, dict)
        and explicit_effective
        and _candidate_identity(explicit_effective) not in negative_vetoed_ids
    ):
        return dict(explicit_effective)
    oasis_selected = oasis_verification.get("selected")
    if (
        isinstance(oasis_selected, dict)
        and _candidate_identity(oasis_selected) not in negative_vetoed_ids
        and oasis_selected.get("verification_status") == "executed"
        and oasis_selected.get("effectiveness_status") == "effective"
        and oasis_selected.get("metric_source") == "oasis"
    ):
        return dict(oasis_selected)
    proxy_pool = search_result.get("proxy_ranked_candidates")
    if not isinstance(proxy_pool, list):
        proxy_pool = search_result.get("branch_comparison", {}).get("ranked_branches", [])
    candidates = [proxy_selected] + [item for item in proxy_pool if isinstance(item, dict)]
    seen = set()
    for candidate in candidates:
        identity = _candidate_identity(candidate)
        if identity in seen:
            continue
        seen.add(identity)
        if identity not in negative_vetoed_ids:
            return dict(candidate)
    return {}


def _candidate_identity(candidate: Dict[str, Any]) -> tuple:
    """Return a stable candidate-level identity for proxy/OASIS matching."""
    candidate_id = str(candidate.get("candidate_id") or "").strip()
    if candidate_id:
        return ("candidate_id", candidate_id)
    return (
        "candidate_fields",
        str(candidate.get("intervention_type") or ""),
        tuple(sorted(str(item) for item in (candidate.get("target_nodes") or []))),
        str(candidate.get("intervention_tick") or ""),
        str(candidate.get("message") or ""),
    )


def _negative_vetoed_candidate_ids(oasis_verification: Dict[str, Any]) -> set[tuple]:
    """Collect only candidates with executed, harmful OASIS evidence."""
    branches = oasis_verification.get("oasis_verified_branches", [])
    if not isinstance(branches, list):
        return set()
    return {
        _candidate_identity(branch)
        for branch in branches
        if isinstance(branch, dict)
        and branch.get("verification_status") == "executed"
        and branch.get("effectiveness_status") == "harmful"
    }


class CandidateInterventionFork:
    """Apply one generated intervention at a fixed tick."""

    def __init__(self, candidate: InterventionCandidate, scenario_type: str = ""):
        self.candidate = candidate
        self.scenario_type = scenario_type
        self.name = candidate.intervention_type

    def should_apply(self, tick: int) -> bool:
        return tick == self.candidate.intervention_tick

    def apply(
        self,
        agents: List[PropagationAgent],
        adjacency: Dict[str, List[str]],
        key_nodes: List[Dict[str, Any]],
    ) -> tuple[List[PropagationAgent], Dict[str, List[str]], Dict[str, Any]]:
        new_agents = deepcopy(agents)
        new_adj = deepcopy(adjacency)
        target_ids = set(self.candidate.target_nodes)
        touched: List[str] = []
        intervention_type = self.candidate.intervention_type
        fallback_target_ids: set[str] = set()
        if not target_ids and intervention_type in {"downranking", "node_targeting"} and key_nodes:
            fallback_target_ids = {str(key_nodes[0].get("agent_id"))}
            target_ids = set(fallback_target_ids)

        def is_direct_target(agent_id: str) -> bool:
            return actor_is_direct_intervention_target(
                intervention_type=intervention_type,
                target_nodes=self.candidate.target_nodes,
                actor_id=agent_id,
                fallback_target_nodes=fallback_target_ids,
            )

        if intervention_type in {
            "official_response",
            "clarification",
            "debunking",
            "community_note",
            "source_verification",
        }:
            for agent in new_agents:
                if not is_direct_target(agent.agent_id):
                    continue
                update_institutional_trust(
                    agent,
                    tick=self.candidate.intervention_tick,
                    verified=True,
                    source_role="official_responder",
                    information_signal=0.25,
                )
                touched.append(agent.agent_id)
                if agent.role in _OFFICIAL_ROLES:
                    agent.activity = min(1.0, agent.activity + 0.25)
                    agent.influence = min(1.0, agent.influence + 0.15)
                elif agent.role in _AMPLIFIER_ROLES:
                    agent.influence = max(0.01, agent.influence - 0.18)
                    agent.activity = max(0.01, agent.activity - 0.10)

        elif intervention_type in {"downranking", "node_targeting"}:
            if self.scenario_type == "public_opinion" and intervention_type == "downranking":
                # The narrative layer maps this to source outbound reach; the
                # legacy activity/influence adjustment below remains as a
                # lightweight compatibility proxy for existing metrics.
                # It does not rewrite trust or remove the canonical S0 graph.
                touched.extend(sorted(target_ids))
            else:
                for target_id in target_ids:
                    if target_id in new_adj:
                        new_adj[target_id] = new_adj[target_id][: max(0, len(new_adj[target_id]) // 3)]
                    for aid, neighbours in list(new_adj.items()):
                        if target_id in neighbours:
                            new_adj[aid] = [n for n in neighbours if n != target_id]
                    touched.append(target_id)
            for agent in new_agents:
                if is_direct_target(agent.agent_id):
                    # Preserve the legacy proxy adjustment while narrative
                    # downranking uses source-side outbound reach semantics.
                    agent.influence = max(0.01, agent.influence - 0.28)
                    agent.activity = max(0.01, agent.activity - 0.20)

        elif intervention_type in {"warning", "friction_prompt", "content_labeling"}:
            if intervention_type == "friction_prompt" and self.scenario_type == "event_propagation":
                # Event friction is an action/share-cost intervention only.
                # It deliberately does not rewrite any claim-state dimension.
                for agent in new_agents:
                    if is_direct_target(agent.agent_id):
                        agent.metadata["claim_friction_share_multiplier"] = 0.72
                        touched.append(agent.agent_id)
                return new_agents, new_adj, {"candidate_id": self.candidate.candidate_id, "touched_agents": sorted(set(touched))}
            for agent in new_agents:
                if not is_direct_target(agent.agent_id):
                    continue
                if agent.role in _VULNERABLE_ROLES or agent.susceptibility >= 0.55:
                    agent.susceptibility = max(0.01, agent.susceptibility - 0.22)
                    agent.activity = max(0.01, agent.activity - 0.08)
                    touched.append(agent.agent_id)
                elif agent.role in _AMPLIFIER_ROLES:
                    agent.susceptibility = max(0.01, agent.susceptibility - 0.12)

        else:
            for agent in new_agents:
                agent.susceptibility = max(0.01, agent.susceptibility - 0.08)
                touched.append(agent.agent_id)

        return new_agents, new_adj, {"candidate_id": self.candidate.candidate_id, "touched_agents": sorted(set(touched))}


def run_proxy_intervention_search(
    *,
    scenario_type: str,
    seed_text: str,
    risk_graph_bundle: Optional[Dict[str, Any]] = None,
    propagation_result: Optional[Dict[str, Any]] = None,
    quick_mode: bool = True,
    seed: int = 42,
    social_state: Any = None,
    simulation_state: Any = None,
    canonical_case: Any = None,
) -> Dict[str, Any]:
    """Run baseline + multi-branch counterfactual intervention search.

    The current implementation uses the local propagation simulator as a
    deterministic proxy branch runner. It records this explicitly in provenance
    so later full OASIS branch runners can replace it without changing the
    output contract.
    """
    if social_state is None:
        social_state = simulation_state

    n_agents = _agent_count(scenario_type, quick_mode)
    ticks = 5 if quick_mode else 20
    from ..social_state.builder import demo_topology_type
    topology_type = demo_topology_type(scenario_type, seed_text)
    if social_state is not None:
        # All proxy branches are copied from the service-owned canonical S0.
        # This path deliberately does not rebuild agents or topology.
        from ..social_state.mapping import actor_to_propagation_agent

        agents = [actor_to_propagation_agent(actor) for actor in social_state.actors]
        adjacency = social_state.to_adjacency()
        initial_state_provenance = {
            "simulation_state_id": social_state.simulation_state_id,
            "initial_state_source": "canonical_social_state",
            "shared_initial_world": True,
            "canonical_case_id": getattr(canonical_case, "case_id", None),
        }
    else:
        agents = build_agents(scenario_type, n_agents=n_agents, seed=seed)
        adjacency = build_topology(agents, topology_type=topology_type, seed=seed)
        initial_state_provenance = {
            "simulation_state_id": None,
            "initial_state_source": "legacy_agent_factory",
            "shared_initial_world": False,
            "canonical_case_id": getattr(canonical_case, "case_id", None),
        }
    event = PropagationEvent.create(
        scenario_type=scenario_type,
        seed_text=seed_text,
        risk_dimensions=_risk_dimensions(scenario_type),
        initial_emotion=_infer_initial_emotion(seed_text),
    )

    narrative_states: list[NarrativeState] = []
    narrative_relations: list[NarrativeRelation] = []
    if scenario_type == "public_opinion":
        narrative_states = extract_public_opinion_narratives(
            canonical_case or {"summary": seed_text},
            max_narratives=4,
        )
        narrative_relations = build_narrative_relations(narrative_states)
    canonical_claims = (
        canonical_case.get("claims", [])
        if isinstance(canonical_case, dict)
        else getattr(canonical_case, "claims", [])
    )
    claim_inputs = (
        list(canonical_claims or [])
        if scenario_type == "event_propagation"
        else None
    )

    baseline_trace = run_propagation_simulation(
        event=event,
        agents=deepcopy(agents),
        adjacency=deepcopy(adjacency),
        ticks=ticks,
        seed=seed,
        narratives=narrative_states,
        narrative_relations=narrative_relations,
        claims=deepcopy(claim_inputs),
    )
    evidence_basis = _evidence_basis(seed_text, risk_graph_bundle or {})
    targeting_mode = str(getattr(Config, "CAUSAL_TARGETING_MODE", "causal_targeting") or "causal_targeting")
    candidate_generation_mode = str(getattr(Config, "INTERVENTION_CANDIDATE_MODE", "fixed_candidate_template") or "fixed_candidate_template")
    target_selection = select_causal_targets(baseline_trace, mode=targeting_mode)
    candidates = generate_intervention_candidates(
        scenario_type=scenario_type,
        baseline_trace=baseline_trace,
        evidence_basis=evidence_basis,
        ticks=ticks,
        causal_targets=target_selection.get("selected_node_ids", []),
        targeting_mode=targeting_mode,
        candidate_generation_mode=candidate_generation_mode,
    )

    branch_started = time.perf_counter()

    def run_candidate_branch(index: int, candidate: InterventionCandidate) -> Dict[str, Any]:
        branch_trace = run_propagation_simulation(
            event=event,
            agents=deepcopy(agents),
            adjacency=deepcopy(adjacency),
            ticks=ticks,
            seed=seed,
            fork_strategy=CandidateInterventionFork(candidate, scenario_type=scenario_type),
            narratives=deepcopy(narrative_states),
            narrative_relations=deepcopy(narrative_relations),
            claims=deepcopy(claim_inputs),
        )
        branch_metrics = _compare_branch(
            baseline_trace=baseline_trace,
            branch_trace=branch_trace,
            candidate=candidate,
        )
        return {
            "branch_id": f"branch_{index:03d}",
            "intervention_candidate": candidate.to_dict(),
            "coverage_curve": branch_trace.coverage_curve,
            "polarization_curve": _polarization_curve(branch_trace),
            "misinformation_curve": _misinformation_curve(branch_trace, seed_text),
            "key_node_activity": _key_node_activity_curve(branch_trace, baseline_trace.key_nodes),
            "narrative_analysis": branch_trace.narrative_analysis,
            "claim_analysis": branch_trace.claim_analysis,
            "final_metrics": branch_metrics,
        }

    if len(candidates) <= 1:
        branches = [run_candidate_branch(index, candidate) for index, candidate in enumerate(candidates, start=1)]
        branch_execution_mode = "single_proxy"
    else:
        max_workers = min(4, len(candidates))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [
                executor.submit(run_candidate_branch, index, candidate)
                for index, candidate in enumerate(candidates, start=1)
            ]
            branches = [future.result() for future in futures]
        branches = sorted(branches, key=lambda item: item.get("branch_id", ""))
        branch_execution_mode = "parallel_proxy"
    branch_execution_latency_ms = round((time.perf_counter() - branch_started) * 1000, 2)

    requested_ranker_mode = normalize_ranker_mode(Config.INTERVENTION_RANKER_MODE)
    ranked_for_selection = rank_branches(
        branches,
        scenario_type=scenario_type,
        mode=requested_ranker_mode,
        weights_path=getattr(Config, "INTERVENTION_RANKER_WEIGHTS_PATH", None),
        strict=False,
    )
    ranker_fallback_used = any(bool(branch.get("ranker_fallback_used")) for branch in ranked_for_selection)
    ranker_fallback_reason = next(
        (branch.get("ranker_fallback_reason") for branch in ranked_for_selection if branch.get("ranker_fallback_reason")),
        None,
    )
    ranker_mode = "fixed_weight" if ranker_fallback_used else requested_ranker_mode
    selected = _select_ranked_branch(ranked_for_selection, ranker_mode)
    policy_selection = _select_with_optional_ppo(
        ranked_for_selection,
        scenario_type=scenario_type,
        baseline_trace=baseline_trace,
    )
    if policy_selection.get("applied"):
        selected = _select_ranked_branch(policy_selection["ordered_branches"], "ppo_policy")
        selected["policy_action_type"] = policy_selection.get("action_type")
        selected["policy_path"] = policy_selection.get("policy_path")
    policy_selection.pop("ordered_branches", None)
    selected_branch = next(
        (
            branch for branch in branches
            if branch.get("branch_id") == selected.get("branch_id")
        ),
        None,
    )
    baseline_branch = {
        "branch_id": "baseline_no_intervention",
        "intervention": None,
        "coverage_curve": baseline_trace.coverage_curve,
        "polarization_curve": _polarization_curve(baseline_trace),
        "misinformation_curve": _misinformation_curve(baseline_trace, seed_text),
        "key_node_activity": _key_node_activity_curve(baseline_trace, baseline_trace.key_nodes),
        "key_nodes": baseline_trace.key_nodes,
        "narrative_analysis": baseline_trace.narrative_analysis,
        "claim_analysis": baseline_trace.claim_analysis,
        "final_metrics": {
            **baseline_trace.final_metrics,
            "polarization_peak": _curve_peak(_polarization_curve(baseline_trace), "polarization"),
            "misinformation_peak": _curve_peak(_misinformation_curve(baseline_trace, seed_text), "misinformation"),
            "key_node_activity_peak": _curve_peak(_key_node_activity_curve(baseline_trace, baseline_trace.key_nodes), "activity"),
        },
    }
    baseline_metric_snapshot = _metric_snapshot(baseline_branch)
    candidate_diagnostics = []
    for branch in branches:
        candidate = branch.get("intervention_candidate", {})
        action_validation = validate_intervention_candidate(candidate, scenario_type)
        metrics = branch.get("final_metrics", {})
        counterfactual_metrics = _metric_snapshot(branch)
        deltas = _metric_deltas(baseline_metric_snapshot, counterfactual_metrics)
        score_available = isinstance(metrics.get("total_score"), (int, float))
        candidate_diagnostics.append({
            "candidate_id": candidate.get("candidate_id"),
            "candidate_type": candidate.get("intervention_type"),
            "baseline_metric": baseline_metric_snapshot,
            "counterfactual_metric": counterfactual_metrics,
            "delta": deltas,
            "metric_source": metrics.get("metric_source", "proxy"),
            "valid": score_available,
            "invalid_reason": None if score_available else "missing_final_score",
            "cost": candidate.get("intervention_cost"),
            "latency": metrics.get("latency_cost"),
            "final_score": metrics.get("total_score"),
            "ranking_score": branch.get("ranking_score", metrics.get("total_score")),
            "ranking_mode": ranker_mode,
            "requested_ranking_mode": requested_ranker_mode,
            "ranker_fallback_used": ranker_fallback_used,
            "ranker_fallback_reason": ranker_fallback_reason,
            "action_validation": action_validation,
            "suppression_safe_features": {
                key: metrics.get(key)
                for key in (
                    "overblocking_risk", "false_positive_risk", "legitimate_information_loss",
                    "verified_information_reach_loss", "correction_suppression_risk", "proportionality",
                    "specificity", "reversibility", "misinformation_coverage", "legitimate_coverage",
                    "verified_correction_coverage",
                )
            },
            "suppression_feature_validity": metrics.get("suppression_feature_validity", {}),
            "suppression_feature_provenance": metrics.get("suppression_feature_provenance", {}),
        })
    comparison = {
        "branch_count": len(branches),
        "ranked_branches": [
            {
                "branch_id": branch["branch_id"],
                "candidate_id": branch["intervention_candidate"].get("candidate_id"),
                "intervention_type": branch["intervention_candidate"].get("intervention_type"),
                "target_nodes": branch["intervention_candidate"].get("target_nodes", []),
                "target_stage": branch["intervention_candidate"].get("target_stage"),
                "intervention_tick": branch["intervention_candidate"].get("intervention_tick"),
                "message": branch["intervention_candidate"].get("message", ""),
                "evidence_basis": branch["intervention_candidate"].get("evidence_basis", []),
                "total_score": branch["final_metrics"].get("total_score", 0.0),
                "coverage_reduction": branch["final_metrics"].get("coverage_reduction", 0.0),
                "polarization_reduction": branch["final_metrics"].get("polarization_reduction", 0.0),
                "misinformation_reduction": branch["final_metrics"].get("misinformation_reduction", 0.0),
                "claim_fidelity_gain": branch["final_metrics"].get("claim_fidelity_gain", 0.0),
                "distortion_reduction": branch["final_metrics"].get("distortion_reduction", 0.0),
                "source_loss_reduction": branch["final_metrics"].get("source_loss_reduction", 0.0),
                "certainty_inflation_reduction": branch["final_metrics"].get("certainty_inflation_reduction", 0.0),
                "unsupported_claim_reduction": branch["final_metrics"].get("unsupported_claim_reduction", 0.0),
                "verified_claim_reach_gain": branch["final_metrics"].get("verified_claim_reach_gain", 0.0),
                "correction_reach_gain": branch["final_metrics"].get("correction_reach_gain", 0.0),
                "key_node_activity_reduction": branch["final_metrics"].get("key_node_activity_reduction", 0.0),
                "narrative_polarization_reduction": branch["final_metrics"].get("narrative_polarization_reduction", 0.0),
                "community_fragmentation_reduction": branch["final_metrics"].get("community_fragmentation_reduction", 0.0),
                "corrective_narrative_reach": branch["final_metrics"].get("corrective_narrative_reach", 0.0),
                "claim_metric_source": branch["final_metrics"].get("claim_metric_source"),
                "ranking_score": branch.get("ranking_score", branch["final_metrics"].get("total_score", 0.0)),
                "ranking_mode": ranker_mode,
                "requested_ranking_mode": requested_ranker_mode,
                "ranker_fallback_used": ranker_fallback_used,
            }
            for branch in ranked_for_selection
        ],
    }
    metric_source = "proxy"
    runtime_engine = "lightweight_counterfactual_proxy"
    oasis_grounded = _propagation_oasis_grounded(propagation_result or {})

    return {
        "baseline_branch": baseline_branch,
        "intervention_candidates": [candidate.to_dict() for candidate in candidates],
        "counterfactual_branches": branches,
        "branch_comparison": comparison,
        "selected_best_branch": selected,
        "claim_analysis": {
            "baseline": baseline_trace.claim_analysis,
            "selected": (selected_branch or {}).get("claim_analysis", {}),
            "metric_semantics": "simulation_proxy" if scenario_type == "event_propagation" else "not_applicable",
            "claim_metric_source": "lightweight_claim_model" if scenario_type == "event_propagation" else "not_applicable",
        },
        "selection_metrics": selected.get("score_breakdown", {}),
        "ranking_mode": ranker_mode,
        "requested_ranking_mode": requested_ranker_mode,
        "ranker_fallback_used": ranker_fallback_used,
        "ranker_fallback_reason": ranker_fallback_reason,
        "intervention_policy": policy_selection,
        "candidate_diagnostics": candidate_diagnostics,
        "causal_targeting": target_selection,
        "candidate_generation_mode": candidate_generation_mode,
        "provenance": {
            "source": "mirofish_pipeline",
            "runtime_engine": runtime_engine,
            "metric_source": metric_source,
            "has_oasis_counterfactual_branches": False,
            "has_oasis_baseline_propagation": oasis_grounded,
            "branch_count": len(branches),
            "candidate_diagnostics": candidate_diagnostics,
            "ranking_mode": ranker_mode,
            "requested_ranking_mode": requested_ranker_mode,
            "ranker_fallback_used": ranker_fallback_used,
            "ranker_fallback_reason": ranker_fallback_reason,
            "intervention_policy": policy_selection,
            "candidate_generation_source": "risk_graph|evidence_chain|key_nodes|heuristic",
            "candidate_generation_mode": candidate_generation_mode,
            "causal_targeting": target_selection.get("provenance", {}),
            "branch_execution_mode": branch_execution_mode,
            **initial_state_provenance,
        },
        "diagnostics": {
            "quick_mode": quick_mode,
            "agent_count": n_agents,
            "ticks": ticks,
            "topology_type": topology_type,
            "metric_source": metric_source,
            "branch_execution_mode": branch_execution_mode,
            "branch_execution_latency_ms": branch_execution_latency_ms,
            "branch_count": len(branches),
            "ranking_mode": ranker_mode,
            "requested_ranking_mode": requested_ranker_mode,
            "ranker_fallback_used": ranker_fallback_used,
            "ranker_fallback_reason": ranker_fallback_reason,
            "intervention_policy": policy_selection,
            "causal_targeting_mode": targeting_mode,
            **initial_state_provenance,
            "notes": [
                "Counterfactual branches currently use local propagation proxy metrics.",
                "Full OASIS per-candidate execution can replace this module without changing the output schema.",
            ],
        },
    }


def generate_intervention_candidates(
    *,
    scenario_type: str,
    baseline_trace: PropagationTrace,
    evidence_basis: List[str],
    ticks: int,
    causal_targets: Optional[List[str]] = None,
    targeting_mode: str = "causal_targeting",
    candidate_generation_mode: str = "fixed_candidate_template",
) -> List[InterventionCandidate]:
    templates = _generate_template_candidates(
        scenario_type=scenario_type,
        baseline_trace=baseline_trace,
        evidence_basis=evidence_basis,
        ticks=ticks,
        causal_targets=causal_targets,
        targeting_mode=targeting_mode,
        candidate_generation_mode=candidate_generation_mode,
    )
    if candidate_generation_mode != "evidence_bound_candidate":
        return templates
    target_nodes = [str(item) for item in (causal_targets or []) if item]
    action_type = "source_verification" if scenario_type == "event_propagation" else "community_note"
    evidence = evidence_basis[:2] or ["当前输入中的传播/核验线索"]
    generated = InterventionCandidate(
        candidate_id="cand_evidence_bound",
        intervention_type=action_type,
        target_nodes=target_nodes[:2],
        target_stage="early",
        intervention_tick=max(1, min(ticks, ticks // 4 or 1)),
        message=f"围绕“{evidence[0]}”绑定来源、核验状态和原始上下文。",
        expected_mechanism="由证据线索生成具体核验动作，先修正来源不确定性再决定是否扩大处置。",
        evidence_basis=evidence,
        cost=0.18,
    )
    return [generated, *templates]


def _generate_template_candidates(
    *,
    scenario_type: str,
    baseline_trace: PropagationTrace,
    evidence_basis: List[str],
    ticks: int,
    causal_targets: Optional[List[str]] = None,
    targeting_mode: str = "causal_targeting",
    candidate_generation_mode: str = "fixed_candidate_template",
) -> List[InterventionCandidate]:
    if causal_targets is not None:
        key_nodes = [str(item) for item in causal_targets if item]
    elif targeting_mode == "centrality_only":
        key_nodes = [str(item.get("agent_id")) for item in baseline_trace.key_nodes[:3] if item.get("agent_id")]
    else:
        key_nodes = select_causal_targets(baseline_trace, mode=targeting_mode).get("selected_node_ids", [])
    early_tick = max(1, min(ticks, ticks // 4 or 1))
    accel_tick = max(1, min(ticks, ticks // 3 or 1))
    peak_tick = _peak_tick(baseline_trace)
    cue = _candidate_cue(evidence_basis)

    if scenario_type == "public_opinion":
        return [
            InterventionCandidate(
                candidate_id="cand_official_response_early",
                intervention_type="official_response",
                # OASIS implements this as an official-agent broadcast.
                target_nodes=[],
                target_stage="early",
                intervention_tick=early_tick,
                message=f"围绕“{cue}”发布权威时间线，并逐项标明已确认与仍在核实的信息。",
                expected_mechanism="用权威事实供给填补回应缺口，降低情绪化单一叙事扩散。",
                evidence_basis=evidence_basis,
                cost=0.28,
            ),
            InterventionCandidate(
                candidate_id="cand_community_note_acceleration",
                intervention_type="community_note",
                target_nodes=key_nodes[:2],
                target_stage="acceleration",
                intervention_tick=accel_tick,
                message=f"在传播“{cue}”的高活跃节点旁绑定原始来源和当前核验状态。",
                expected_mechanism="给转发链增加上下文，降低未经证实叙事的再扩散概率。",
                evidence_basis=evidence_basis,
                cost=0.18,
            ),
            InterventionCandidate(
                candidate_id="cand_downranking_amplifiers",
                intervention_type="downranking",
                target_nodes=key_nodes,
                target_stage="acceleration",
                intervention_tick=accel_tick,
                message=f"降低持续放大“{cue}”且未补充来源的关键节点推荐权重。",
                expected_mechanism="压低结构性放大节点的外溢覆盖率，保留正常讨论空间。",
                evidence_basis=evidence_basis,
                cost=0.34,
            ),
            InterventionCandidate(
                candidate_id="cand_friction_prompt_peak",
                intervention_type="friction_prompt",
                target_nodes=key_nodes[:2],
                target_stage="peak",
                intervention_tick=peak_tick,
                message=f"用户转发“{cue}”前提示核验来源，并说明哪些信息仍未确认。",
                expected_mechanism="降低易感用户的即时转发率，延缓峰值传播。",
                evidence_basis=evidence_basis,
                cost=0.12,
            ),
        ]

    return [
        InterventionCandidate(
            candidate_id="cand_official_response_early",
            intervention_type="official_response",
            target_nodes=[],
            target_stage="early",
            intervention_tick=early_tick,
            message=f"针对“{cue}”公开发布事实核查、来源说明和更正内容。",
            expected_mechanism="由官方账号公开澄清，降低传播链中的事实不确定性。",
            evidence_basis=evidence_basis,
            cost=0.28,
        ),
        InterventionCandidate(
            candidate_id="cand_source_verification_early",
            intervention_type="source_verification",
            target_nodes=key_nodes[:1],
            target_stage="early",
            intervention_tick=early_tick,
            message=f"对“{cue}”的首发或早期来源标注核验状态，并要求补充原始时间、地点和证据。",
            expected_mechanism="在传播链早期修正来源不确定性，减少后续失真复制。",
            evidence_basis=evidence_basis,
            cost=0.20,
        ),
        InterventionCandidate(
            candidate_id="cand_content_labeling_acceleration",
            intervention_type="content_labeling",
            target_nodes=key_nodes[:2],
            target_stage="acceleration",
            intervention_tick=accel_tick,
            message=f"对“{cue}”中尚未确认的身份、地点或时间加显著标签并绑定更正链接。",
            expected_mechanism="让二次传播携带上下文，降低误传和语境丢失。",
            evidence_basis=evidence_basis,
            cost=0.16,
        ),
        InterventionCandidate(
            candidate_id="cand_node_targeting_amplifiers",
            intervention_type="node_targeting",
            target_nodes=key_nodes,
            target_stage="acceleration",
            intervention_tick=accel_tick,
            message=f"优先要求正在放大“{cue}”的新闻、汇总或高影响力账号更新更正。",
            expected_mechanism="切断放大节点继续传播旧版本信息的路径。",
            evidence_basis=evidence_basis,
            cost=0.36,
        ),
        InterventionCandidate(
            candidate_id="cand_debunking_peak",
            intervention_type="debunking",
            target_nodes=key_nodes[:2],
            target_stage="peak",
            intervention_tick=peak_tick,
            message=f"在传播峰值前发布“{cue}”的澄清摘要，明确哪些细节不准确。",
            expected_mechanism="用集中纠偏降低峰值阶段的误传强度。",
            evidence_basis=evidence_basis,
            cost=0.24,
        ),
    ]


def _compare_branch(
    *,
    baseline_trace: PropagationTrace,
    branch_trace: PropagationTrace,
    candidate: InterventionCandidate,
) -> Dict[str, Any]:
    base_cov_final = _coverage_final(baseline_trace)
    branch_cov_final = _coverage_final(branch_trace)
    base_cov_peak = _coverage_peak(baseline_trace)
    branch_cov_peak = _coverage_peak(branch_trace)
    base_pol_peak = _curve_peak(_polarization_curve(baseline_trace), "polarization")
    branch_pol_peak = _curve_peak(_polarization_curve(branch_trace), "polarization")
    base_mis_peak = _curve_peak(_misinformation_curve(baseline_trace, baseline_trace.scenario_type), "misinformation")
    branch_mis_peak = _curve_peak(_misinformation_curve(branch_trace, branch_trace.scenario_type), "misinformation")
    base_key_peak = _curve_peak(_key_node_activity_curve(baseline_trace, baseline_trace.key_nodes), "activity")
    branch_key_peak = _curve_peak(_key_node_activity_curve(branch_trace, baseline_trace.key_nodes), "activity")

    coverage_reduction = round(max(0.0, base_cov_final - branch_cov_final), 3)
    peak_coverage_reduction = round(max(0.0, base_cov_peak - branch_cov_peak), 3)
    polarization_reduction = round(max(0.0, base_pol_peak - branch_pol_peak), 3)
    misinformation_reduction = round(max(0.0, base_mis_peak - branch_mis_peak), 3)
    key_node_activity_reduction = round(max(0.0, base_key_peak - branch_key_peak), 3)
    time_to_peak_delay = max(0, _peak_tick(branch_trace) - _peak_tick(baseline_trace))
    cost_penalty = round(candidate.cost + candidate.intervention_tick * 0.01, 3)

    narrative_metrics: Dict[str, Any] = {}
    if baseline_trace.scenario_type == "public_opinion":
        base_narrative = baseline_trace.narrative_analysis or {}
        branch_narrative = branch_trace.narrative_analysis or {}
        base_polarization = float(base_narrative.get("narrative_polarization", 0.0) or 0.0)
        branch_polarization = float(branch_narrative.get("narrative_polarization", 0.0) or 0.0)
        base_fragmentation = float(base_narrative.get("community_fragmentation", 0.0) or 0.0)
        branch_fragmentation = float(branch_narrative.get("community_fragmentation", 0.0) or 0.0)
        narrative_polarization_reduction = round(max(0.0, base_polarization - branch_polarization), 3)
        community_fragmentation_reduction = round(max(0.0, base_fragmentation - branch_fragmentation), 3)
        corrective_narrative_reach = _corrective_narrative_reach(branch_narrative)
        narrative_metrics = {
            "narrative_polarization_reduction": narrative_polarization_reduction,
            "community_fragmentation_reduction": community_fragmentation_reduction,
            "corrective_narrative_reach": corrective_narrative_reach,
        }

    claim_metrics: Dict[str, Any] = {}
    if baseline_trace.scenario_type == "event_propagation":
        base_claim = baseline_trace.claim_analysis or {}
        branch_claim = branch_trace.claim_analysis or {}

        def _claim_metric(key: str) -> tuple[float, float, float]:
            base_value = float(base_claim.get(key, 0.0) or 0.0)
            branch_value = float(branch_claim.get(key, 0.0) or 0.0)
            return base_value, branch_value, branch_value - base_value

        _, _, fidelity_delta = _claim_metric("claim_fidelity")
        base_distortion, branch_distortion, _ = _claim_metric("distortion_index")
        base_source_loss, branch_source_loss, _ = _claim_metric("source_loss_rate")
        base_inflation, branch_inflation, _ = _claim_metric("certainty_inflation")
        base_unsupported, branch_unsupported, _ = _claim_metric("unsupported_claim_share")
        _, _, verified_delta = _claim_metric("verified_claim_reach")
        _, _, correction_delta = _claim_metric("correction_reach")
        claim_metrics = {
            "claim_fidelity_gain": round(max(0.0, fidelity_delta), 6),
            "distortion_reduction": round(max(0.0, base_distortion - branch_distortion), 6),
            "source_loss_reduction": round(max(0.0, base_source_loss - branch_source_loss), 6),
            "certainty_inflation_reduction": round(max(0.0, base_inflation - branch_inflation), 6),
            "unsupported_claim_reduction": round(max(0.0, base_unsupported - branch_unsupported), 6),
            "verified_claim_reach_gain": round(max(0.0, verified_delta), 6),
            "correction_reach_gain": round(max(0.0, correction_delta), 6),
            "uncertainty_gap_reduction": round(max(0.0, base_inflation - branch_inflation), 6),
            "claim_metric_source": branch_claim.get("claim_metric_source", "lightweight_claim_model"),
            "claim_metric_semantics": branch_claim.get("metric_semantics", "simulation_proxy"),
        }
    score_breakdown = {
        "coverage_score": round(coverage_reduction * 0.35 + peak_coverage_reduction * 0.15, 3),
        "polarization_score": round(polarization_reduction * 0.18, 3),
        "misinformation_score": round(misinformation_reduction * 0.20, 3),
        "key_node_score": round(key_node_activity_reduction * 0.12, 3),
        "latency_bonus": round(min(0.08, time_to_peak_delay * 0.02), 3),
        "cost_penalty": cost_penalty,
    }
    if claim_metrics:
        score_breakdown["claim_fidelity_score"] = round(claim_metrics.get("claim_fidelity_gain", 0.0) * 0.30, 3)
    total = (
        sum(
            value for key, value in score_breakdown.items()
            if key != "cost_penalty"
            and not str(key).startswith("claim_")
            and isinstance(value, (int, float))
        )
        - cost_penalty * 0.10
    )
    suppression_safe = _suppression_safe_features(
        baseline_trace=baseline_trace,
        branch_trace=branch_trace,
        candidate=candidate,
        misinformation_reduction=misinformation_reduction,
        correction_reach_gain=claim_metrics.get("correction_reach_gain", narrative_metrics.get("corrective_narrative_reach")),
    )

    return {
        **branch_trace.final_metrics,
        "final_coverage": branch_cov_final,
        "peak_coverage": branch_cov_peak,
        "coverage_reduction": coverage_reduction,
        "peak_coverage_reduction": peak_coverage_reduction,
        "time_to_peak_delay": time_to_peak_delay,
        "polarization_reduction": polarization_reduction,
        "negative_emotion_reduction": polarization_reduction,
        "misinformation_reduction": misinformation_reduction,
        "distortion_reduction": claim_metrics.get("distortion_reduction", misinformation_reduction),
        "uncertainty_gap_reduction": claim_metrics.get("uncertainty_gap_reduction", misinformation_reduction),
        "key_node_activity_reduction": key_node_activity_reduction,
        "amplifier_suppression": key_node_activity_reduction,
        "bridge_node_suppression": key_node_activity_reduction,
        "latency_cost": round(candidate.intervention_tick / max(1, branch_trace.ticks), 3),
        "intervention_cost": candidate.cost,
        **suppression_safe["features"],
        "suppression_feature_validity": suppression_safe["validity"],
        "suppression_feature_provenance": suppression_safe["provenance"],
        "score_breakdown": score_breakdown,
        "total_score": round(total, 3),
        "metric_source": "proxy",
        **narrative_metrics,
        **claim_metrics,
        **({"narrative_metric_semantics": "simulation_proxy"} if baseline_trace.scenario_type == "public_opinion" else {}),
    }


def _suppression_safe_features(
    *,
    baseline_trace: PropagationTrace,
    branch_trace: PropagationTrace,
    candidate: InterventionCandidate,
    misinformation_reduction: float,
    correction_reach_gain: Any,
) -> Dict[str, Any]:
    """Build non-suppression features and mark unavailable telemetry honestly."""
    total_agents = len(getattr(baseline_trace, "agents", []) or [])
    target_count = len(set(str(item) for item in (candidate.target_nodes or []) if item))
    scope_ratio = (target_count / total_agents) if total_agents else None
    final_claim = branch_trace.claim_analysis if isinstance(branch_trace.claim_analysis, dict) else {}
    base_claim = baseline_trace.claim_analysis if isinstance(baseline_trace.claim_analysis, dict) else {}

    def numeric(container: Dict[str, Any], key: str) -> float | None:
        value = container.get(key)
        return float(value) if isinstance(value, (int, float)) else None

    base_verified = numeric(base_claim, "verified_claim_reach")
    branch_verified = numeric(final_claim, "verified_claim_reach")
    verified_loss = None if base_verified is None or branch_verified is None else max(0.0, base_verified - branch_verified)
    if scope_ratio is not None:
        proportionality = round(max(0.0, 1.0 - scope_ratio), 6)
        specificity = round(min(1.0, target_count / max(1.0, min(3.0, total_agents))), 6)
    else:
        proportionality = specificity = None
    reversibility_by_type = {
        "friction_prompt": 1.0, "content_labeling": 0.95, "community_note": 0.9,
        "source_verification": 0.9, "official_response": 0.85, "clarification": 0.85,
        "debunking": 0.8, "downranking": 0.55, "node_targeting": 0.45,
    }
    safe = {
        "overblocking_risk": round(scope_ratio * (1.0 - reversibility_by_type.get(candidate.intervention_type, 0.7)), 6) if scope_ratio is not None else None,
        "false_positive_risk": None,
        "legitimate_information_loss": None,
        "verified_information_reach_loss": round(verified_loss, 6) if verified_loss is not None else None,
        "correction_suppression_risk": round(verified_loss, 6) if verified_loss is not None and candidate.intervention_type in {"downranking", "node_targeting"} else None,
        "proportionality": proportionality,
        "specificity": specificity,
        "reversibility": reversibility_by_type.get(candidate.intervention_type, 0.7),
        "misinformation_coverage": round(max(0.0, misinformation_reduction), 6),
        "legitimate_coverage": None,
        "verified_correction_coverage": round(float(correction_reach_gain), 6) if isinstance(correction_reach_gain, (int, float)) else None,
    }
    validity = {key: value is not None for key, value in safe.items()}
    provenance = {
        key: ("counterfactual_trace" if validity[key] and key in {"verified_information_reach_loss", "correction_suppression_risk", "verified_correction_coverage"} else "candidate_scope_policy" if validity[key] else "unavailable_telemetry")
        for key in safe
    }
    return {"features": safe, "validity": validity, "provenance": provenance}


def _select_best_branch(branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not branches:
        return {}
    best = max(
        branches,
        key=lambda item: item.get("ranking_score", item["final_metrics"].get("total_score", 0.0)),
    )
    candidate = best.get("intervention_candidate", {})
    score_breakdown = best.get("final_metrics", {}).get("score_breakdown", {})
    claim_ranked = "claim_fidelity_gain" in best.get("final_metrics", {})
    if claim_ranked:
        selection_reason = (
            f"{candidate.get('intervention_type')} gives the best simulated claim-fidelity gain "
            "and distortion reduction after the event claim-metric cost penalty."
        )
    else:
        selection_reason = (
            f"{candidate.get('intervention_type')} gives the best simulated reduction "
            "across coverage, polarization, misinformation, and key-node activity after cost penalty."
        )
    return {
        "branch_id": best.get("branch_id"),
        "candidate_id": candidate.get("candidate_id"),
        "best_intervention_window": {
            "open_step": max(1, int(candidate.get("intervention_tick", 1))),
            "close_step": max(1, int(candidate.get("intervention_tick", 1))) + 1,
            "open_stage": candidate.get("target_stage", "early"),
            "close_stage": "before_peak" if candidate.get("target_stage") != "peak" else "at_peak",
            "label": f"{candidate.get('target_stage', 'early')} stage {candidate.get('intervention_type', 'intervention')}",
        },
        "best_intervention_action": candidate.get("message", ""),
        "target_nodes": candidate.get("target_nodes", []),
        "selection_reason": selection_reason,
        "score_breakdown": {
            **score_breakdown,
            "total_score": best.get("final_metrics", {}).get("total_score", 0.0),
            "ranking_score": best.get("ranking_score", best.get("final_metrics", {}).get("total_score", 0.0)),
        },
    }


def _select_ranked_branch(branches: List[Dict[str, Any]], ranking_mode: str) -> Dict[str, Any]:
    """Build the existing selected-branch contract from any ranker output."""
    selected = _select_best_branch(branches)
    selected["ranking_mode"] = ranking_mode
    if branches:
        best = branches[0]
        selected.setdefault("score_breakdown", {})["ranking_score"] = best.get("ranking_score", 0.0)
    return selected


def _select_with_optional_ppo(
    branches: List[Dict[str, Any]],
    *,
    scenario_type: str,
    baseline_trace: PropagationTrace,
) -> Dict[str, Any]:
    """Apply a saved PPO policy only when explicitly configured."""
    mode = str(getattr(Config, "MIRO_INTERVENTION_POLICY_MODE", "ranker") or "ranker").lower()
    path = getattr(Config, "MIRO_PPO_POLICY_PATH", None)
    base = {
        "requested_mode": mode,
        "applied": False,
        "fallback_used": False,
        "fallback_reason": None,
        "policy_path": path,
    }
    if mode != "ppo":
        return base
    if not path:
        return {**base, "fallback_used": True, "fallback_reason": "ppo_policy_path_missing"}
    try:
        from training.ppo import DiscretePPOBackend, InterventionState

        metrics = baseline_trace.final_metrics if isinstance(baseline_trace.final_metrics, dict) else {}
        state = InterventionState(
            scenario=scenario_type,
            propagation_metrics={
                "misinformation_coverage": float(metrics.get("misinformation_coverage", metrics.get("cumulative_coverage", 0.0)) or 0.0),
                "correction_reach": float(metrics.get("correction_reach", 0.0) or 0.0),
                "polarization": float(metrics.get("polarization", metrics.get("polarization_peak", 0.0)) or 0.0),
                "fragmentation": float(metrics.get("fragmentation", 0.0) or 0.0),
                "key_node_activity": float(metrics.get("key_node_activity", 0.0) or 0.0),
                "legitimate_information_reach": float(metrics.get("legitimate_information_reach", 0.0) or 0.0),
            },
            key_nodes=[
                str(item.get("agent_id")) for item in baseline_trace.key_nodes
                if isinstance(item, dict) and item.get("agent_id")
            ],
            provenance={"environment": "runtime_selector", "metric_source": "proxy"},
        )
        policy = DiscretePPOBackend()
        policy.load(path)
        action = policy.predict(state)
        matched = [
            branch for branch in branches
            if branch.get("intervention_candidate", {}).get("intervention_type") == action.action_type
        ]
        if not matched:
            return {
                **base,
                "fallback_used": True,
                "fallback_reason": "ppo_action_not_in_candidate_set",
                "action_type": action.action_type,
            }
        ordered = [*matched, *[branch for branch in branches if branch not in matched]]
        return {
            **base,
            "applied": True,
            "action_type": action.action_type,
            "actor": action.actor,
            "ordered_branches": ordered,
        }
    except Exception as exc:
        return {
            **base,
            "fallback_used": True,
            "fallback_reason": f"ppo_policy_load_or_inference_failed:{type(exc).__name__}",
        }


def _metric_snapshot(branch: Dict[str, Any]) -> Dict[str, Any]:
    """Return raw comparable metrics, separate from derived score deltas."""
    final_metrics = branch.get("final_metrics", {}) if isinstance(branch, dict) else {}
    final_metrics = final_metrics if isinstance(final_metrics, dict) else {}
    coverage_curve = branch.get("coverage_curve", []) if isinstance(branch, dict) else []
    misinformation_curve = branch.get("misinformation_curve", []) if isinstance(branch, dict) else []
    polarization_curve = branch.get("polarization_curve", []) if isinstance(branch, dict) else []
    key_activity_curve = branch.get("key_node_activity", []) if isinstance(branch, dict) else []

    def _last_or_max(curve: Any, key: str, *, maximum: bool = False) -> float:
        values = [item.get(key) for item in curve if isinstance(item, dict) and isinstance(item.get(key), (int, float))]
        if not values:
            return 0.0
        return float(max(values) if maximum else values[-1])

    narrative = branch.get("narrative_analysis", {}) if isinstance(branch, dict) else {}
    narrative = narrative if isinstance(narrative, dict) else {}
    claim = branch.get("claim_analysis", {}) if isinstance(branch, dict) else {}
    claim = claim if isinstance(claim, dict) else {}
    correction_reach = final_metrics.get("corrective_narrative_reach")
    if not isinstance(correction_reach, (int, float)):
        correction_reach = final_metrics.get("correction_reach")
    if not isinstance(correction_reach, (int, float)):
        correction_reach = claim.get("correction_reach", 0.0)
    fragmentation = narrative.get("community_fragmentation", 0.0)
    if not isinstance(fragmentation, (int, float)):
        fragmentation = 0.0
    snapshot: Dict[str, Any] = {
        "coverage": float(final_metrics.get("final_coverage", _last_or_max(coverage_curve, "coverage")) or 0.0),
        "misinformation": _last_or_max(misinformation_curve, "misinformation", maximum=True),
        "polarization": _last_or_max(polarization_curve, "polarization", maximum=True),
        "fragmentation": float(fragmentation),
        "key_node_activity": _last_or_max(key_activity_curve, "activity", maximum=True),
        "correction_reach": float(correction_reach or 0.0),
        "latency": float(final_metrics.get("latency_cost", 0.0) or 0.0),
        "cost": float(final_metrics.get("intervention_cost", 0.0) or 0.0),
    }
    for key in (
        "misinformation_coverage", "legitimate_coverage", "verified_correction_coverage",
        "overblocking_risk", "false_positive_risk", "legitimate_information_loss",
        "verified_information_reach_loss", "correction_suppression_risk", "proportionality",
        "specificity", "reversibility",
    ):
        snapshot[key] = final_metrics.get(key)
    snapshot["validity"] = final_metrics.get("suppression_feature_validity", {})
    snapshot["provenance"] = final_metrics.get("suppression_feature_provenance", {})
    return snapshot


def _metric_deltas(baseline: Dict[str, float], counterfactual: Dict[str, float]) -> Dict[str, float]:
    """Use positive values for risk reduction and correction reach gain."""
    return {
        "coverage_delta": round(baseline.get("coverage", 0.0) - counterfactual.get("coverage", 0.0), 6),
        "misinformation_delta": round(baseline.get("misinformation", 0.0) - counterfactual.get("misinformation", 0.0), 6),
        "polarization_delta": round(baseline.get("polarization", 0.0) - counterfactual.get("polarization", 0.0), 6),
        "fragmentation_delta": round(baseline.get("fragmentation", 0.0) - counterfactual.get("fragmentation", 0.0), 6),
        "key_node_delta": round(baseline.get("key_node_activity", 0.0) - counterfactual.get("key_node_activity", 0.0), 6),
        "correction_reach_delta": round(counterfactual.get("correction_reach", 0.0) - baseline.get("correction_reach", 0.0), 6),
        "latency": round(counterfactual.get("latency", 0.0) - baseline.get("latency", 0.0), 6),
        "cost": round(counterfactual.get("cost", 0.0) - baseline.get("cost", 0.0), 6),
    }


def _agent_count(scenario_type: str, quick_mode: bool) -> int:
    from ..social_state.builder import demo_agent_count
    return demo_agent_count(scenario_type)


def _risk_dimensions(scenario_type: str) -> List[str]:
    if scenario_type == "public_opinion":
        return ["narrative_intensity", "propagation_velocity", "polarization_index", "information_health"]
    if scenario_type == "event_propagation":
        return ["propagation_speed", "distortion_index", "engagement_depth", "containment_feasibility"]
    return ["risk"]


def _infer_initial_emotion(seed_text: str) -> str:
    text = seed_text.lower()
    if any(term in text for term in ["愤怒", "不公平", "处罚", "歧视", "指责"]):
        return "anger"
    if any(term in text for term in ["焦虑", "危险", "泄露", "威胁", "恐慌"]):
        return "panic"
    if any(term in text for term in ["辟谣", "更正", "澄清", "说明"]):
        return "trust"
    return "confusion"


def _evidence_basis(seed_text: str, risk_graph_bundle: Dict[str, Any]) -> List[str]:
    basis: List[str] = []
    first_clause = next(
        (part.strip() for part in re.split(r"[。！？!?\n]", seed_text) if part.strip()),
        "",
    )
    if first_clause:
        basis.append(first_clause[:72])
    for item in risk_graph_bundle.get("evidence_items", []) if isinstance(risk_graph_bundle.get("evidence_items"), list) else []:
        if isinstance(item, dict):
            basis.extend(str(v) for v in item.get("matched_terms", []) if v)
            if item.get("label"):
                basis.append(str(item["label"]))
    for term in [
        "未经证实",
        "要求官方",
        "愤怒",
        "焦虑",
        "更正",
        "首发帖",
        "转发",
        "遗漏",
        "不准确",
        "现场图片",
    ]:
        if term in seed_text:
            basis.append(term)
    return _unique([item for item in basis if item])


def _candidate_cue(evidence_basis: List[str]) -> str:
    cue = str(evidence_basis[0]).strip() if evidence_basis else "当前传播内容"
    cue = re.sub(r"\s+", " ", cue)
    return cue[:42] + ("…" if len(cue) > 42 else "")


def _coverage_final(trace: PropagationTrace) -> float:
    if not trace.coverage_curve:
        return 0.0
    return round(float(trace.coverage_curve[-1].get("coverage", 0.0)), 3)


def _coverage_peak(trace: PropagationTrace) -> float:
    return round(max((float(item.get("coverage", 0.0)) for item in trace.coverage_curve), default=0.0), 3)


def _peak_tick(trace: PropagationTrace) -> int:
    if not trace.coverage_curve:
        return 1
    item = max(trace.coverage_curve, key=lambda row: float(row.get("coverage", 0.0)))
    return int(item.get("tick", 1))


def _polarization_curve(trace: PropagationTrace) -> List[Dict[str, Any]]:
    curve: List[Dict[str, Any]] = []
    for item in trace.emotion_curve:
        anger = float(item.get("anger", 0.0))
        panic = float(item.get("panic", 0.0))
        confusion = float(item.get("confusion", 0.0))
        trust = float(item.get("trust", 0.0))
        polarization = max(0.0, anger * 0.55 + panic * 0.30 + confusion * 0.15 - trust * 0.20)
        curve.append({"tick": item.get("tick", 0), "polarization": round(min(1.0, polarization), 3)})
    return curve


def _misinformation_curve(trace: PropagationTrace, seed_text: str) -> List[Dict[str, Any]]:
    cue_boost = 0.0
    if any(term in seed_text for term in ["未经证实", "不准确", "遗漏", "简写", "传言", "网传"]):
        cue_boost += 0.18
    if any(term in seed_text for term in ["截图", "现场图片", "身份", "亲友经验"]):
        cue_boost += 0.10
    curve: List[Dict[str, Any]] = []
    risk_by_tick = {item.get("tick"): float(item.get("risk", 0.0)) for item in trace.emotion_curve}
    for item in trace.coverage_curve:
        tick = item.get("tick", 0)
        coverage = float(item.get("coverage", 0.0))
        misinformation = min(1.0, coverage * 0.65 + risk_by_tick.get(tick, 0.0) * 0.25 + cue_boost)
        curve.append({"tick": tick, "misinformation": round(misinformation, 3)})
    return curve


def _key_node_activity_curve(trace: PropagationTrace, key_nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ids = {str(item.get("agent_id")) for item in key_nodes if item.get("agent_id")}
    if not ids:
        ids = {str(item.get("source_agent_id")) for item in trace.actions[:3]}
    by_tick: Dict[int, int] = {}
    for action in trace.actions:
        if action.source_agent_id in ids or action.target_agent_id in ids:
            by_tick[action.tick] = by_tick.get(action.tick, 0) + 1
    max_count = max(by_tick.values(), default=1)
    return [
        {"tick": tick, "activity": round(by_tick.get(tick, 0) / max_count, 3)}
        for tick in range(trace.ticks + 1)
    ]


def _curve_peak(curve: Iterable[Dict[str, Any]], key: str) -> float:
    return round(max((float(item.get(key, 0.0)) for item in curve), default=0.0), 3)


def _propagation_oasis_grounded(propagation_result: Dict[str, Any]) -> bool:
    for branch_key in ("branch_a", "branch_b"):
        branch = propagation_result.get(branch_key)
        if isinstance(branch, dict):
            metrics = branch.get("final_metrics") if isinstance(branch.get("final_metrics"), dict) else {}
            if metrics.get("oasis_driven"):
                return True
    return False


def _corrective_narrative_reach(analysis: Dict[str, Any]) -> float:
    if not isinstance(analysis, dict):
        return 0.0
    share = analysis.get("narrative_share", {})
    narratives = analysis.get("narratives", [])
    if not isinstance(share, dict) or not isinstance(narratives, list):
        return 0.0
    corrective_ids = {
        str(item.get("narrative_id"))
        for item in narratives
        if isinstance(item, dict) and item.get("stance_direction") == "official_correction"
    }
    return round(sum(float(value or 0.0) for key, value in share.items() if str(key) in corrective_ids), 6)


def _unique(items: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out

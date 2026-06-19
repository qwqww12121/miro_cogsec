"""Counterfactual intervention search for propagation scenarios.

The search layer is deliberately above the OASIS / lightweight propagation
runtime. It generates several intervention candidates, runs comparable
counterfactual branches with the available local propagation simulator, then
selects the branch with the best risk-reduction / cost tradeoff.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from .agent_factory import build_agents
from .schema import PropagationAgent, PropagationEvent, PropagationTrace
from .simulator import run_propagation_simulation
from .topology import build_topology


_OFFICIAL_ROLES = {"school_official", "official_responder", "police_or_bank", "fact_checker"}
_AMPLIFIER_ROLES = {
    "anonymous_amplifier",
    "controversy_amplifier",
    "repost_kol",
    "media_observer",
    "student_kol",
}
_VULNERABLE_ROLES = {"ordinary_student", "ordinary_viewer", "victim"}


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


class CandidateInterventionFork:
    """Apply one generated intervention at a fixed tick."""

    def __init__(self, candidate: InterventionCandidate):
        self.candidate = candidate
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

        if self.candidate.intervention_type in {
            "official_response",
            "clarification",
            "debunking",
            "community_note",
            "source_verification",
        }:
            for agent in new_agents:
                if agent.role in _OFFICIAL_ROLES:
                    agent.activity = min(1.0, agent.activity + 0.25)
                    agent.influence = min(1.0, agent.influence + 0.15)
                    agent.trust_in_official = min(1.0, agent.trust_in_official + 0.15)
                    touched.append(agent.agent_id)
                elif agent.role in _AMPLIFIER_ROLES:
                    agent.influence = max(0.01, agent.influence - 0.18)
                    agent.activity = max(0.01, agent.activity - 0.10)
                    touched.append(agent.agent_id)

        elif self.candidate.intervention_type in {"downranking", "node_targeting"}:
            if not target_ids and key_nodes:
                target_ids = {str(key_nodes[0].get("agent_id"))}
            for target_id in target_ids:
                if target_id in new_adj:
                    new_adj[target_id] = new_adj[target_id][: max(0, len(new_adj[target_id]) // 3)]
                for aid, neighbours in list(new_adj.items()):
                    if target_id in neighbours:
                        new_adj[aid] = [n for n in neighbours if n != target_id]
                touched.append(target_id)
            for agent in new_agents:
                if agent.agent_id in target_ids or agent.role in _AMPLIFIER_ROLES:
                    agent.influence = max(0.01, agent.influence - 0.28)
                    agent.activity = max(0.01, agent.activity - 0.20)

        elif self.candidate.intervention_type in {"warning", "friction_prompt", "content_labeling"}:
            for agent in new_agents:
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


def run_oasis_counterfactual_intervention_search(
    *,
    scenario_type: str,
    seed_text: str,
    risk_graph_bundle: Optional[Dict[str, Any]] = None,
    propagation_result: Optional[Dict[str, Any]] = None,
    quick_mode: bool = True,
    seed: int = 42,
) -> Dict[str, Any]:
    """Run baseline + multi-branch counterfactual intervention search.

    The current implementation uses the local propagation simulator as a
    deterministic proxy branch runner. It records this explicitly in provenance
    so later full OASIS branch runners can replace it without changing the
    output contract.
    """
    n_agents = _agent_count(scenario_type, quick_mode)
    ticks = 5 if quick_mode else 20
    agents = build_agents(scenario_type, n_agents=n_agents, seed=seed)
    topology_type = "campus_local" if scenario_type == "public_opinion" else "scale_free_like"
    adjacency = build_topology(agents, topology_type=topology_type, seed=seed)
    event = PropagationEvent.create(
        scenario_type=scenario_type,
        seed_text=seed_text,
        risk_dimensions=_risk_dimensions(scenario_type),
        initial_emotion=_infer_initial_emotion(seed_text),
    )

    baseline_trace = run_propagation_simulation(
        event=event,
        agents=deepcopy(agents),
        adjacency=deepcopy(adjacency),
        ticks=ticks,
        seed=seed,
    )
    evidence_basis = _evidence_basis(seed_text, risk_graph_bundle or {})
    candidates = generate_intervention_candidates(
        scenario_type=scenario_type,
        baseline_trace=baseline_trace,
        evidence_basis=evidence_basis,
        ticks=ticks,
    )

    branch_started = time.perf_counter()

    def run_candidate_branch(index: int, candidate: InterventionCandidate) -> Dict[str, Any]:
        branch_trace = run_propagation_simulation(
            event=event,
            agents=deepcopy(agents),
            adjacency=deepcopy(adjacency),
            ticks=ticks,
            seed=seed,
            fork_strategy=CandidateInterventionFork(candidate),
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

    selected = _select_best_branch(branches)
    baseline_branch = {
        "branch_id": "baseline_no_intervention",
        "intervention": None,
        "coverage_curve": baseline_trace.coverage_curve,
        "polarization_curve": _polarization_curve(baseline_trace),
        "misinformation_curve": _misinformation_curve(baseline_trace, seed_text),
        "key_node_activity": _key_node_activity_curve(baseline_trace, baseline_trace.key_nodes),
        "key_nodes": baseline_trace.key_nodes,
        "final_metrics": {
            **baseline_trace.final_metrics,
            "polarization_peak": _curve_peak(_polarization_curve(baseline_trace), "polarization"),
            "misinformation_peak": _curve_peak(_misinformation_curve(baseline_trace, seed_text), "misinformation"),
            "key_node_activity_peak": _curve_peak(_key_node_activity_curve(baseline_trace, baseline_trace.key_nodes), "activity"),
        },
    }
    comparison = {
        "branch_count": len(branches),
        "ranked_branches": [
            {
                "branch_id": branch["branch_id"],
                "candidate_id": branch["intervention_candidate"].get("candidate_id"),
                "intervention_type": branch["intervention_candidate"].get("intervention_type"),
                "total_score": branch["final_metrics"].get("total_score", 0.0),
                "coverage_reduction": branch["final_metrics"].get("coverage_reduction", 0.0),
                "polarization_reduction": branch["final_metrics"].get("polarization_reduction", 0.0),
                "misinformation_reduction": branch["final_metrics"].get("misinformation_reduction", 0.0),
                "key_node_activity_reduction": branch["final_metrics"].get("key_node_activity_reduction", 0.0),
            }
            for branch in sorted(branches, key=lambda item: item["final_metrics"].get("total_score", 0.0), reverse=True)
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
        "selection_metrics": selected.get("score_breakdown", {}),
        "provenance": {
            "source": "mirofish_pipeline",
            "runtime_engine": runtime_engine,
            "metric_source": metric_source,
            "has_oasis_counterfactual_branches": False,
            "has_oasis_baseline_propagation": oasis_grounded,
            "branch_count": len(branches),
            "candidate_generation_source": "risk_graph|evidence_chain|key_nodes|heuristic",
            "branch_execution_mode": branch_execution_mode,
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
) -> List[InterventionCandidate]:
    key_nodes = [str(item.get("agent_id")) for item in baseline_trace.key_nodes[:3] if item.get("agent_id")]
    early_tick = max(1, min(ticks, ticks // 4 or 1))
    accel_tick = max(1, min(ticks, ticks // 3 or 1))
    peak_tick = _peak_tick(baseline_trace)

    if scenario_type == "public_opinion":
        return [
            InterventionCandidate(
                candidate_id="cand_official_response_early",
                intervention_type="official_response",
                target_nodes=key_nodes[:1],
                target_stage="early",
                intervention_tick=early_tick,
                message="发布权威时间线和证据状态，区分已确认与仍在核实的信息。",
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
                message="在高传播节点内容旁绑定来源提示和核验状态。",
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
                message="降低重复放大未经证实说法的关键节点推荐权重。",
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
                message="转发前提示用户核验来源、等待权威更新，不扩散未经证实截图。",
                expected_mechanism="降低易感用户的即时转发率，延缓峰值传播。",
                evidence_basis=evidence_basis,
                cost=0.12,
            ),
        ]

    return [
        InterventionCandidate(
            candidate_id="cand_source_verification_early",
            intervention_type="source_verification",
            target_nodes=key_nodes[:1],
            target_stage="early",
            intervention_tick=early_tick,
            message="对首发或早期来源标注核验状态，要求补充原始时间、地点和证据。",
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
            message="对身份、地点、时间等未确认信息加显著标签并绑定更正链接。",
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
            message="优先要求新闻账号、汇总账号或高影响力转发节点更新更正。",
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
            message="在传播峰值前发布澄清摘要，说明哪些身份、地点或时间信息不准确。",
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

    score_breakdown = {
        "coverage_score": round(coverage_reduction * 0.35 + peak_coverage_reduction * 0.15, 3),
        "polarization_score": round(polarization_reduction * 0.18, 3),
        "misinformation_score": round(misinformation_reduction * 0.20, 3),
        "key_node_score": round(key_node_activity_reduction * 0.12, 3),
        "latency_bonus": round(min(0.08, time_to_peak_delay * 0.02), 3),
        "cost_penalty": cost_penalty,
    }
    total = (
        score_breakdown["coverage_score"]
        + score_breakdown["polarization_score"]
        + score_breakdown["misinformation_score"]
        + score_breakdown["key_node_score"]
        + score_breakdown["latency_bonus"]
        - cost_penalty * 0.10
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
        "distortion_reduction": misinformation_reduction,
        "uncertainty_gap_reduction": misinformation_reduction,
        "key_node_activity_reduction": key_node_activity_reduction,
        "amplifier_suppression": key_node_activity_reduction,
        "bridge_node_suppression": key_node_activity_reduction,
        "latency_cost": round(candidate.intervention_tick / max(1, branch_trace.ticks), 3),
        "intervention_cost": candidate.cost,
        "overblocking_risk": round(candidate.cost * 0.6, 3),
        "false_positive_risk": round(candidate.cost * 0.35, 3),
        "score_breakdown": score_breakdown,
        "total_score": round(total, 3),
        "metric_source": "proxy",
    }


def _select_best_branch(branches: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not branches:
        return {}
    best = max(branches, key=lambda item: item["final_metrics"].get("total_score", 0.0))
    candidate = best.get("intervention_candidate", {})
    score_breakdown = best.get("final_metrics", {}).get("score_breakdown", {})
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
        "selection_reason": (
            f"{candidate.get('intervention_type')} gives the best simulated reduction "
            "across coverage, polarization, misinformation, and key-node activity after cost penalty."
        ),
        "score_breakdown": {
            **score_breakdown,
            "total_score": best.get("final_metrics", {}).get("total_score", 0.0),
        },
    }


def _agent_count(scenario_type: str, quick_mode: bool) -> int:
    if quick_mode:
        return 12
    return 50 if scenario_type == "public_opinion" else 60


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

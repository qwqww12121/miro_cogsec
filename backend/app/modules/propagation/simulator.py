"""Lightweight propagation simulator — tick-based, no external dependencies."""

from __future__ import annotations

import random as _random
import uuid
from typing import Any, Dict, List, Optional

from .fork_strategies import (
    NoInterventionFork,
    OfficialClarificationFork,
    PropagationForkStrategy,
    RemoveKeyNodeFork,
)
from .metrics import compute_key_nodes, summarize_trace
from .schema import (
    ForkedPropagationResult,
    PropagationAction,
    PropagationAgent,
    PropagationEvent,
    PropagationTrace,
)

_RISK_FACTORS: Dict[str, float] = {
    "fraud_im": 0.75,
    "public_opinion": 0.65,
    "event_propagation": 0.70,
}
_DEFAULT_RISK = 0.60


def run_propagation_simulation(
    event: PropagationEvent,
    agents: list[PropagationAgent],
    adjacency: dict[str, list[str]],
    ticks: int = 30,
    seed: int = 42,
    fork_strategy: PropagationForkStrategy | None = None,
) -> PropagationTrace:
    """Run a single tick-based propagation simulation."""
    rng = _random.Random(seed)
    scenario = event.scenario_type
    risk_factor = _RISK_FACTORS.get(scenario, _DEFAULT_RISK)

    id_to_agent = {a.agent_id: a for a in agents}

    # initial seeds: top 1-3 influence agents
    sorted_by_inf = sorted(agents, key=lambda a: a.influence, reverse=True)
    seed_count = min(3, max(1, len(agents) // 20))
    covered: set[str] = {a.agent_id for a in sorted_by_inf[:seed_count]}
    active: set[str] = set(covered)

    actions: list[PropagationAction] = []
    coverage_curve: list[dict] = []
    emotion_curve: list[dict] = []

    for tick in range(ticks + 1):
        # apply fork strategy
        if fork_strategy is not None and fork_strategy.should_apply(tick):
            agents, adjacency, _ = fork_strategy.apply(agents, adjacency, compute_key_nodes(agents, adjacency, actions))
            id_to_agent = {a.agent_id: a for a in agents}

        next_active: set[str] = set()
        tick_actions: list[PropagationAction] = []

        if tick > 0:
            for source_id in active:
                source = id_to_agent.get(source_id)
                if source is None:
                    continue
                neighbours = adjacency.get(source_id, [])
                for target_id in neighbours:
                    if target_id in covered:
                        continue
                    target = id_to_agent.get(target_id)
                    if target is None:
                        continue
                    spread_chance = (
                        source.influence * 0.5
                        + target.susceptibility * 0.35
                        + risk_factor * 0.15
                    )
                    if rng.random() < spread_chance * source.activity:
                        covered.add(target_id)
                        next_active.add(target_id)
                        action_type = "spread" if target.susceptibility > 0.5 else "exposed"
                        influence_delta = round(source.influence * 0.05, 3)
                        risk_delta = round(risk_factor * target.susceptibility * 0.1, 3)
                        tick_actions.append(
                            PropagationAction(
                                tick=tick,
                                source_agent_id=source_id,
                                target_agent_id=target_id,
                                action_type=action_type,
                                content_summary=f"{source.role} -> {target.role}",
                                influence_delta=influence_delta,
                                risk_delta=risk_delta,
                            )
                        )

            # keep previously active (still spreading)
            still_active = {aid for aid in active if id_to_agent.get(aid) and rng.random() < id_to_agent[aid].activity}
            next_active.update(still_active)

        actions.extend(tick_actions)
        active = next_active if next_active else set(covered) - set(covered)  # empty if no new

        coverage_curve.append({
            "tick": tick,
            "covered_count": len(covered),
            "coverage": round(len(covered) / max(1, len(agents)), 3),
        })
        emotion_curve.append(_compute_emotion(tick, scenario, coverage_curve[-1]["coverage"], actions, agents))

    key_nodes = compute_key_nodes(agents, adjacency, actions, top_k=5)

    trace = PropagationTrace(
        trace_id=str(uuid.uuid4()),
        scenario_type=scenario,
        ticks=ticks,
        agents=agents,
        actions=actions,
        coverage_curve=coverage_curve,
        emotion_curve=emotion_curve,
        key_nodes=key_nodes,
        final_metrics=summarize_trace(
            PropagationTrace(
                trace_id="", scenario_type=scenario, ticks=ticks,
                agents=agents, actions=actions,
                coverage_curve=coverage_curve, emotion_curve=emotion_curve,
                key_nodes=key_nodes, final_metrics={},
            )
        ),
    )
    # patch final_metrics with self-reference resolved
    trace.final_metrics = summarize_trace(trace)
    return trace


def run_forked_propagation(
    event: PropagationEvent,
    agents: list[PropagationAgent],
    adjacency: dict[str, list[str]],
    ticks: int = 30,
    intervention_tick: int = 10,
    strategy_type: str = "remove_key_node",
    seed: int = 42,
) -> ForkedPropagationResult:
    """Run Branch A (no intervention) and Branch B (intervention) and compare."""
    # Branch A
    trace_a = run_propagation_simulation(
        event=event, agents=agents, adjacency=adjacency,
        ticks=ticks, seed=seed,
        fork_strategy=NoInterventionFork(),
    )

    # Branch B
    if strategy_type == "official_clarification":
        strategy_b: PropagationForkStrategy = OfficialClarificationFork(intervention_tick)
    else:
        strategy_b = RemoveKeyNodeFork(intervention_tick)

    trace_b = run_propagation_simulation(
        event=event, agents=agents, adjacency=adjacency,
        ticks=ticks, seed=seed,
        fork_strategy=strategy_b,
    )

    cov_a = trace_a.coverage_curve[-1]["coverage"] if trace_a.coverage_curve else 0.0
    cov_b = trace_b.coverage_curve[-1]["coverage"] if trace_b.coverage_curve else 0.0
    acts_a = len(trace_a.actions)
    acts_b = len(trace_b.actions)
    peak_a = trace_a.final_metrics.get("peak_risk", 0.0)
    peak_b = trace_b.final_metrics.get("peak_risk", 0.0)

    comparison = {
        "coverage_delta": round(cov_a - cov_b, 3),
        "action_delta": acts_a - acts_b,
        "peak_risk_delta": round(peak_a - peak_b, 3),
        "intervention_effective": (cov_a - cov_b) > 0.05 or (peak_a - peak_b) > 0.02,
        "strategy_type": strategy_type,
    }

    return ForkedPropagationResult(
        fork_point={
            "intervention_tick": intervention_tick,
            "strategy_type": strategy_type,
        },
        branch_a=trace_a,
        branch_b=trace_b,
        comparison=comparison,
    )


# ---------------------------------------------------------------------------
# emotion heuristic
# ---------------------------------------------------------------------------


def _compute_emotion(
    tick: int,
    scenario: str,
    coverage: float,
    actions: list[PropagationAction],
    agents: list[PropagationAgent],
) -> dict:
    amplifier_actions = sum(
        1 for a in actions
        if a.tick == tick and a.action_type == "spread"
    )

    panic = 0.0
    anger = 0.0
    confusion = 0.3
    trust = 0.2
    risk = 0.0

    if scenario == "public_opinion":
        anger = min(1.0, coverage * 0.6 + amplifier_actions * 0.04)
        trust = max(0.0, 0.4 - coverage * 0.3)
        risk = round(anger * 0.7 + panic * 0.2 + (1 - trust) * 0.1, 3)
    elif scenario == "event_propagation":
        confusion = min(1.0, coverage * 0.7)
        panic = min(1.0, coverage * 0.5 + amplifier_actions * 0.05)
        trust = max(0.0, 0.5 - coverage * 0.35)
        risk = round(panic * 0.5 + confusion * 0.3 + (1 - trust) * 0.2, 3)
    elif scenario == "fraud_im":
        panic = min(1.0, coverage * 0.8)
        trust = max(0.0, 0.3 - coverage * 0.25)
        risk = round(panic * 0.8 + (1 - trust) * 0.2, 3)
    else:
        risk = round(coverage * 0.5, 3)

    return {
        "tick": tick,
        "panic": round(panic, 3),
        "anger": round(anger, 3),
        "confusion": round(confusion, 3),
        "trust": round(trust, 3),
        "risk": round(risk, 3),
    }

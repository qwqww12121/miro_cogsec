# PROPAGATION RUNTIME — Round 4

## Why lightweight propagation now

The existing MiroFish backend has a full OASIS-powered SimulationRunner (`simulation_runner.py`)
that drives Twitter/Reddit simulations with real LLM agents.  However:

1. OASIS is a subprocess / IPC / SQLite-oriented system, not an in-process library.
2. CogSec scenarios (public_opinion, event_propagation) need quick, repeatable,
   deterministic propagation traces for counterfactual comparison.
3. Calling OASIS inside a CogSec API request would add minutes of latency and
   require the simulation environment to be alive.

The lightweight runtime gives us **tick-based propagation with <100ms latency**,
no external processes, no LLM calls, and deterministic output (seeded `random.Random`).

## Module structure

```
backend/app/modules/propagation/
  schema.py           PropagationAgent / Event / Action / Trace / ForkedPropagationResult
  agent_factory.py    build_agents() — deterministic role/attribute assignment
  topology.py         build_topology() — small_world / scale_free_like / campus_local
  metrics.py          compute_key_nodes() / summarize_trace()
  fork_strategies.py  NoInterventionFork / RemoveKeyNodeFork / OfficialClarificationFork
  simulator.py        run_propagation_simulation() / run_forked_propagation()
  oasis_adapter.py    OasisPropagationAdapter — reserved placeholder
```

## Data structures

**PropagationAgent**: role, stance, influence, susceptibility, activity, trust_in_official (all 0-1).

**PropagationEvent**: seed_text, seed_modalities, risk_dimensions, initial_emotion.

**PropagationAction**: tick, source/target agent, action_type (spread|exposed), influence_delta, risk_delta.

**PropagationTrace**: agents, actions, coverage_curve, emotion_curve, key_nodes, final_metrics.

**ForkedPropagationResult**: branch_a (no intervention), branch_b (intervention), comparison.

## Branch A/B semantics

| Branch | Strategy | Description |
|--------|----------|-------------|
| A | NoInterventionFork | Natural propagation — no countermeasures |
| B | RemoveKeyNodeFork | At `intervention_tick`, remove the top key node's edges |
| B | OfficialClarificationFork | At `intervention_tick`, boost official roles, dampen amplifiers |

## Scenario wiring

| Scenario | supports_propagation | topology | strategy | quick_mode agents/ticks |
|---|---|---|---|---|
| `fraud_im` | **False** | — | — | — |
| `public_opinion` | **True** | campus_local | official_clarification | 20/10 |
| `event_propagation` | **True** | scale_free_like | remove_key_node | 20/10 |

## Error handling

Propagation failures are caught in `CogSecService.analyze_text()` and stored in
`scenario_extension.propagation_error`.  The mainline analysis is never affected.

## Current limitations

- No LLM calls — agent actions are heuristic.
- Emotion curves are formula-based, not sentiment-model-based.
- Coverage propagation is a simple influence × susceptibility model without
  content-dependent dynamics.
- Key-node scoring is degree + action-count based, not eigenvector-centrality.

## Future: replacing with OASIS

When `SimulationRunner` exposes a stable in-process API:

1. Implement `OasisPropagationAdapter.run()` to call OASIS.
2. Switch `PublicOpinionScenarioSpec.run_propagation()` to use the adapter
   when `OasisPropagationAdapter().is_available()` is True.
3. Keep the lightweight runtime as a fallback for quick-mode analysis.

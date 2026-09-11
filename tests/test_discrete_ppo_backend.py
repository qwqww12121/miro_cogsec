from __future__ import annotations

from dataclasses import replace

from training.ppo import (
    CallbackInterventionEnvironmentBackend,
    DiscretePPOBackend,
    InterventionEnvironment,
    InterventionReward,
    InterventionState,
    PPOTrainer,
)


def _initial(case):
    return InterventionState(
        scenario=case["scenario"],
        risk_state={"risk": 0.8},
        key_nodes=["node-1"],
        propagation_metrics={
            "misinformation_coverage": 0.9,
            "correction_reach": 0.1,
            "polarization": 0.7,
            "fragmentation": 0.5,
            "key_node_activity": 0.8,
            "legitimate_information_reach": 0.8,
        },
        provenance={"environment": "test_oasis", "metric_source": "oasis"},
    )


def _transition(case, state, action):
    good = action.action_type == "official_response"
    metrics = dict(state.propagation_metrics)
    metrics["misinformation_coverage"] = max(0.0, metrics["misinformation_coverage"] - (0.25 if good else 0.02))
    metrics["correction_reach"] = min(1.0, metrics["correction_reach"] + (0.25 if good else 0.01))
    metrics["proportionality"] = 0.9 if good else 0.3
    metrics["goal_completion"] = 0.8 if good else 0.1
    return {
        "state": replace(
            state,
            propagation_metrics=metrics,
            current_timestep=state.current_timestep + 1,
            remaining_budget=max(0.0, state.remaining_budget - action.cost),
            previous_interventions=[*state.previous_interventions, action.to_runtime_candidate()],
        ),
        "done": state.current_timestep >= 2,
    }


def test_discrete_ppo_updates_and_roundtrips_policy(tmp_path) -> None:
    cases = [{"scenario": "public_opinion"}]
    environment = InterventionEnvironment(CallbackInterventionEnvironmentBackend(
        _transition, state_factory=_initial, required_metric_source="oasis"
    ))
    backend = DiscretePPOBackend(cases=cases, seed=3, rollout_size=8)
    result = PPOTrainer(backend).train(
        environment, InterventionReward(), enabled=True, steps=40
    )
    assert result["status"] == "trained"
    assert result["metric_sources"] == {"oasis": 40}
    assert result["synthetic_zero_reward"] is False
    path = tmp_path / "ppo.json"
    backend.save(str(path))
    loaded = DiscretePPOBackend(cases=cases)
    loaded.load(str(path))
    assert loaded.training_steps == 40
    assert loaded.predict(_initial(cases[0])).action_type


def test_formal_environment_rejects_proxy_metrics() -> None:
    def proxy_initial(case):
        return InterventionState(scenario=case["scenario"], provenance={"metric_source": "proxy"})

    backend = CallbackInterventionEnvironmentBackend(
        _transition, state_factory=proxy_initial, required_metric_source="oasis"
    )
    try:
        backend.reset({"scenario": "public_opinion"})
    except ValueError as exc:
        assert "metric_source" in str(exc)
    else:
        raise AssertionError("proxy metrics must not enter formal OASIS PPO training")

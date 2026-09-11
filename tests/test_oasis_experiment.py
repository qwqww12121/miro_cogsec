from __future__ import annotations

from app.modules.propagation.oasis_experiment import (
    OasisExperimentConfig,
    run_multiseed_oasis_experiment,
)


def test_multiseed_experiment_enforces_shared_world_and_aggregates() -> None:
    def runner(**kwargs):
        seed = kwargs["seed"]
        candidate = {
            "candidate_id": "official",
            "metric_source": "oasis",
            "signed_utility": 0.1 + (seed % 2) * 0.02,
            "verification_status": "executed",
        }
        return {
            "top_k_oasis_completed": 1,
            "shared_initial_world": True,
            "simulation_state_id": kwargs["simulation_state_id"],
            "selected": candidate,
            "oasis_verified_branches": [candidate],
        }

    result = run_multiseed_oasis_experiment(
        scenario_type="public_opinion",
        seed_text="x",
        agents=[],
        proxy_result={},
        simulation_state_id="s0-fixed",
        config=OasisExperimentConfig(seeds=(10, 11), top_k=2),
        verification_runner=runner,
    )
    assert result["accepted"] is True
    assert result["completed_seeds"] == 2
    assert result["candidate_utility"]["official"]["runs"] == 2
    assert result["metric_source"] == "oasis"


def test_multiseed_experiment_rejects_missing_shared_world() -> None:
    def runner(**kwargs):
        return {
            "top_k_oasis_completed": 1,
            "shared_initial_world": False,
            "simulation_state_id": None,
            "selected": {},
            "oasis_verified_branches": [],
        }

    result = run_multiseed_oasis_experiment(
        scenario_type="event_propagation",
        seed_text="x",
        agents=[],
        proxy_result={},
        simulation_state_id="expected-s0",
        config=OasisExperimentConfig(seeds=(1,), require_oasis_metrics=False),
        verification_runner=runner,
    )
    assert result["accepted"] is False
    assert result["acceptance_checks"]["shared_initial_world"] is False

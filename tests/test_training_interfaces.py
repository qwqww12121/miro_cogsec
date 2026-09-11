from __future__ import annotations

import pytest

from training.contracts import TrainingBackendNotConfigured
from training.dpo import DPOConfig, DPOPipeline
from training.ppo import (
    InterventionAction,
    InterventionEnvironment,
    InterventionReward,
    InterventionState,
    PPOTrainer,
)
from training.sft import SFTConfig, SFTPipeline


def test_reporter_sft_and_dpo_validate_without_starting_training() -> None:
    state = {"schema_version": "report_state.v2", "scenario": "fraud_im"}
    sft = SFTPipeline(SFTConfig(task="reporter", base_model="local/base", output_dir="out"))
    sft_status = sft.validate_records([
        {"raw_input": "对方要求转账", "report_state": state, "target_answer": "先暂停转账并核验。"}
    ])
    assert sft_status["status"] == "validated"
    assert sft_status["training_started"] is False

    dpo = DPOPipeline(DPOConfig(base_model="local/base", output_dir="out"))
    dpo_status = dpo.validate_records([
        {
            "raw_input": "对方要求转账",
            "report_state": state,
            "chosen": "先暂停转账，并从官方入口核验。",
            "rejected": "存在风险，请注意。",
        }
    ])
    assert dpo_status["status"] == "validated"
    assert dpo_status["training_started"] is False


def test_training_enable_requires_real_backend() -> None:
    pipeline = SFTPipeline(SFTConfig(task="agent", base_model="local/base", output_dir="out"))
    records = [{"task": "narrative", "input": {"text": "x"}, "target": {"claims": ["x"]}}]
    assert pipeline.train(records, enabled=False)["status"] == "disabled"
    with pytest.raises(TrainingBackendNotConfigured):
        pipeline.train(records, enabled=True)


def test_ppo_reward_uses_transition_deltas_instead_of_constant_zero() -> None:
    state = InterventionState(
        scenario="public_opinion",
        propagation_metrics={
            "misinformation_coverage": 0.8,
            "correction_reach": 0.2,
            "polarization": 0.7,
            "fragmentation": 0.5,
            "key_node_activity": 0.9,
            "legitimate_information_reach": 0.8,
        },
        provenance={"environment": "proxy", "metric_source": "proxy"},
    )
    next_state = InterventionState(
        scenario="public_opinion",
        propagation_metrics={
            "misinformation_coverage": 0.4,
            "correction_reach": 0.7,
            "polarization": 0.5,
            "fragmentation": 0.4,
            "key_node_activity": 0.5,
            "legitimate_information_reach": 0.75,
            "proportionality": 0.8,
            "goal_completion": 0.6,
            "false_positive_risk": 0.05,
            "overblocking_risk": 0.1,
            "latency_cost": 0.1,
        },
        provenance={"environment": "proxy", "metric_source": "proxy"},
    )
    action = InterventionAction(
        actor="平台核验员",
        action_type="bind_correction",
        target_nodes=["bridge-1"],
        strength=0.6,
        cost=0.1,
    )

    reward = InterventionReward().compute(state, action, next_state)

    assert reward["reward"] != 0.0
    assert reward["components"]["misinformation_reduction"] == pytest.approx(0.4)
    assert reward["provenance"]["synthetic_zero_reward"] is False


def test_ppo_has_no_fake_environment_or_noop_policy() -> None:
    env = InterventionEnvironment()
    trainer = PPOTrainer()
    state = InterventionState(scenario="event_propagation")

    with pytest.raises(TrainingBackendNotConfigured):
        env.reset({"case_id": "case-1"})
    with pytest.raises(TrainingBackendNotConfigured):
        trainer.runtime_policy(state)
    assert trainer.train(env, InterventionReward(), enabled=False)["status"] == "disabled"

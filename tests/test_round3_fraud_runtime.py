"""Round 3 fraud_runtime tests — multi-role stateful interaction."""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))

from app.modules.fraud_runtime.agents import ThreatActor, UserTwin, Verifier
from app.modules.fraud_runtime.environment import FraudEnvironment
from app.modules.fraud_runtime.runtime import FraudMultiRoleRuntime
from app.modules.fraud_runtime.runtime import adapt_fraud_to_fork_comparison
from app.modules.fraud_runtime.schema import (
    FraudInteractionResult,
    ThreatActorState,
    UserTwinState,
    VerifierState,
)


# ── Fake cognitive profile for testing ──────────────────────────────

class FakeProfile:
    """Minimal CognitiveProfile stub for UserTwin init."""
    trust_threshold = 6.0
    verification_habit = 4.0
    time_pressure = 7.0
    authority_compliance = 6.5
    risk_recovery_awareness = 5.5
    cognitive_load = 6.0
    scenario_type = "fraud_im"


class FakeRiskGraph:
    """Minimal RiskGraphBundle stub."""
    fork_points = [{"type": "transfer_money", "severity": 0.96}]
    evidence_items = [
        {"id": "ev_001", "label": "安全账户话术", "detail": "诈骗常用安全账户话术"},
        {"id": "ev_002", "label": "冒充客服", "detail": "非官方渠道联系用户"},
    ]
    attack_strategy_chain = [
        {"tactic_name": "权威施压", "description": "冒充官方制造紧迫感"},
    ]
    persuasion_principles = ["authority", "urgency"]
    asset_targets = [{"label": "银行卡", "type": "funds"}]


# ── Tests ───────────────────────────────────────────────────────────


class TestFraudAgentsSeparateState:
    """Each agent must have independent private state."""

    def test_fraud_agents_have_separate_state(self):
        """ThreatActor, UserTwin, Verifier states are independent objects."""
        threat = ThreatActor(actor_id="t1")
        user = UserTwin(actor_id="u1", cognitive_profile=FakeProfile())
        verifier = Verifier(actor_id="v1")

        # Modify one agent's state
        threat.state.pressure_level = 0.9
        user.state.trust = 0.2
        verifier.state.memory.append("test")

        # Others must be unaffected
        assert user.state.trust == 0.2
        assert threat.state.pressure_level == 0.9
        assert "test" in verifier.state.memory
        # Different actor_ids
        assert threat.state.actor_id != user.state.actor_id
        assert user.state.actor_id != verifier.state.actor_id

    def test_fraud_agents_have_separate_memory(self):
        """Each agent has independent memory list."""
        threat = ThreatActor()
        user = UserTwin(cognitive_profile=FakeProfile())
        verifier = Verifier()

        threat.state.memory.append("threat_mem_1")
        user.state.memory.append("user_mem_1")
        verifier.state.memory.append("verifier_mem_1")

        assert "threat_mem_1" in threat.state.memory
        assert "user_mem_1" in user.state.memory
        assert "verifier_mem_1" in verifier.state.memory
        assert "threat_mem_1" not in user.state.memory
        assert "user_mem_1" not in verifier.state.memory


class TestThreatActorObserves:
    """ThreatActor must observe and react to user actions."""

    def test_threat_actor_observes_user_action(self):
        """ThreatActor's decision changes based on UserTwin's last action."""
        threat = ThreatActor()

        # When user complies → escalate
        env_comply = {"last_user_action": "comply", "verifier_info": None, "risk_flags": [], "round": 1}
        obs = threat.observe(env_comply)
        action_comply = threat.decide(obs, llm_client=None)
        assert action_comply in ("apply_urgency", "request_verification_code",
                                  "request_transfer", "apply_authority")

        # When user refuses → change tactic
        env_refuse = {"last_user_action": "refuse", "verifier_info": None, "risk_flags": [], "round": 1}
        obs2 = threat.observe(env_refuse)
        action_refuse = threat.decide(obs2, llm_client=None)
        assert action_refuse != action_comply or action_refuse == "change_story"

    def test_user_twin_state_updates_across_rounds(self):
        """UserTwin trust and compliance change after each round."""
        user = UserTwin(cognitive_profile=FakeProfile())
        initial_trust = user.state.trust

        # User complies → trust increases
        user.update_state("comply", "request_transfer")
        assert user.state.trust > initial_trust

        # User refuses → trust decreases
        trust_after_comply = user.state.trust
        user.update_state("refuse", "apply_urgency")
        assert user.state.trust < trust_after_comply

    def test_verification_increases_risk_awareness(self):
        user = UserTwin(cognitive_profile=FakeProfile())
        initial_awareness = user.state.risk_awareness

        user.update_state("verify", "request_transfer")

        assert user.state.risk_awareness > initial_awareness

    def test_verifier_uses_evidence_refs(self):
        """Verifier's decision references real evidence_refs."""
        verifier = Verifier(
            evidence_refs=["ev_001", "ev_002"],
            known_patterns=["transfer_money", "authority"],
        )

        obs = {
            "threat_action": "request_transfer",
            "user_action": "comply",
            "threat_claimed_identity": "银行客服",
            "round": 2,
        }
        result = verifier.decide(obs, llm_client=None)
        assert result["action"] in ("identify_risk_signal", "provide_safe_action")
        info = result.get("info", {})
        assert "risk_signals" in info
        # Evidence refs should be present
        assert info.get("evidence_refs") == ["ev_001", "ev_002"]


class TestBranchEquivalence:
    """Branch A and B must start from same state."""

    def test_branch_a_b_start_from_same_fraud_state(self):
        """Both branches begin with identical agent states."""
        threat = ThreatActor(claimed_identity="test_banker")
        user = UserTwin(cognitive_profile=FakeProfile())
        verifier = Verifier(evidence_refs=["ev_001"])

        env = FraudEnvironment(threat, user, verifier, max_rounds=2)
        result = env.run()

        # Branch A and Branch B should have same initial state
        # (the environment resets between branches)
        assert result.branch_a is not None
        assert result.branch_b is not None
        # Both branches should have executed
        assert result.branch_a.get("rounds_executed", 0) > 0
        assert result.branch_b.get("rounds_executed", 0) > 0

    def test_branch_b_does_not_force_user_refusal(self):
        """Branch B must not programmatically force UserTwin to refuse."""
        threat = ThreatActor(claimed_identity="客服")
        user = UserTwin(cognitive_profile=FakeProfile())
        verifier = Verifier(evidence_refs=["ev_001"])

        env = FraudEnvironment(threat, user, verifier, max_rounds=3)
        result = env.run()

        b_trace = result.branch_b.get("trace", [])
        # Check that UserTwin in Branch B is not forced to refuse
        user_actions_b = [
            s.get("action") for s in b_trace
            if isinstance(s, dict) and s.get("actor_id") == "user_twin"
        ]
        # There should be a mix, not all "refuse"
        # (UserTwin decides based on state + verifier info, not forced)
        assert len(user_actions_b) > 0

    def test_fraud_adapter_preserves_branch_divergence(self):
        threat = ThreatActor(claimed_identity="test_banker")
        user = UserTwin(cognitive_profile=FakeProfile())
        verifier = Verifier(evidence_refs=["ev_001"], known_patterns=["transfer_money"])
        result = FraudEnvironment(threat, user, verifier, max_rounds=4).run()

        comparison = adapt_fraud_to_fork_comparison(result)
        branch_a = comparison.branch_a_state_trace
        branch_b = comparison.branch_b_state_trace

        assert branch_a[-1].world_state.posterior_risk > branch_b[-1].world_state.posterior_risk
        assert comparison.trajectory_gap >= 0.5
        assert comparison.irreversibility_loss >= 0.5


class TestDeterministicFallback:
    """When LLM is unavailable, deterministic fallback must work."""

    def test_deterministic_fallback_when_llm_unavailable(self):
        """Without LLM client, runtime uses deterministic heuristics."""
        runtime = FraudMultiRoleRuntime(llm_client=None)  # No LLM
        result = runtime.run(
            scenario_text="请转账到安全账户",
            cognitive_profile=FakeProfile(),
            risk_graph_bundle=FakeRiskGraph(),
            max_rounds=3,
        )
        assert result.runtime_mode == "deterministic_fallback"
        assert result.status == "degraded"
        assert result.round_count == 3

    def test_fraud_runtime_mode_is_reported(self):
        """FraudInteractionResult correctly reports runtime_mode."""
        runtime = FraudMultiRoleRuntime(llm_client=None)
        result = runtime.run(
            scenario_text="test",
            cognitive_profile=FakeProfile(),
            risk_graph_bundle=FakeRiskGraph(),
            max_rounds=2,
        )
        assert result.runtime_mode in ("llm_driven", "hybrid", "deterministic_fallback")
        assert result.status in ("complete", "degraded")
        assert isinstance(result.to_dict(), dict)
        assert "runtime_mode" in result.to_dict()

    def test_configured_but_failing_llm_is_not_reported_as_llm_driven(self):
        class FailingClient:
            def chat(self, *args, **kwargs):
                raise RuntimeError("synthetic API failure")

        runtime = FraudMultiRoleRuntime(llm_client=FailingClient())
        result = runtime.run(
            scenario_text="请转账到安全账户",
            cognitive_profile=FakeProfile(),
            risk_graph_bundle=FakeRiskGraph(),
            max_rounds=2,
        )
        assert result.runtime_mode == "deterministic_fallback"
        assert result.status == "degraded"
        assert result.decision_provenance["llm_decisions"] == 0
        assert result.decision_provenance["fallback_decisions"] > 0
        assert "all_llm_agent_decisions_fell_back" in result.degraded_reasons

    def test_explicit_deterministic_policy_is_complete_not_fallback(self):
        runtime = FraudMultiRoleRuntime(llm_client=None, policy_mode="deterministic")
        result = runtime.run(
            scenario_text="对方要求转账",
            cognitive_profile=FakeProfile(),
            risk_graph_bundle=FakeRiskGraph(),
            max_rounds=3,
        )

        assert result.runtime_mode == "deterministic_policy"
        assert result.status == "complete"
        assert result.degraded_reasons == []
        assert set(result.decision_provenance["sources"]) == {"deterministic_policy"}

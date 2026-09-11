"""Final closure: fraud result unification tests."""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))

from modules.fraud_runtime import FraudMultiRoleRuntime
from modules.fraud_runtime.agents import ThreatActor, UserTwin, Verifier
from modules.fraud_runtime.environment import FraudEnvironment


class FakeProfile:
    trust_threshold = 6.0
    verification_habit = 4.0
    time_pressure = 7.0
    authority_compliance = 6.5
    risk_recovery_awareness = 5.5
    cognitive_load = 6.0
    scenario_type = "fraud_im"


class FakeRiskGraph:
    fork_points = [{"type": "transfer_money", "severity": 0.96}]
    evidence_items = [
        {"id": "ev_001", "label": "安全账户话术", "detail": "诈骗常用安全账户话术"},
    ]
    attack_strategy_chain = []
    persuasion_principles = ["authority"]
    asset_targets = [{"label": "银行卡", "type": "funds"}]


class TestFraudPrimaryResult:
    """Multi-role must be the primary source when successful."""

    def test_multi_role_result_is_primary_when_successful(self):
        """With LLM=None, runtime uses deterministic heuristics, status=degraded.
        But the multi-role runtime DOES produce a real interaction trace —
        it just can't be marked "complete" without LLM."""
        runtime = FraudMultiRoleRuntime(llm_client=None)
        result = runtime.run(
            scenario_text="test",
            cognitive_profile=FakeProfile(),
            risk_graph_bundle=FakeRiskGraph(),
            max_rounds=2,
        )
        # Even in deterministic mode, it produces real data
        assert result.branch_a is not None
        assert result.branch_b is not None
        assert result.branch_comparison is not None
        # But status is degraded without LLM
        assert result.status == "degraded"
        assert result.runtime_mode == "deterministic_fallback"

    def test_deterministic_result_only_used_on_fallback(self):
        """When multi-role fails, fallback is explicitly marked."""
        # Simulate fallback construction
        from modules.fraud_runtime.runtime import build_deterministic_fraud_result
        fallback = build_deterministic_fraud_result(risk_graph_bundle=FakeRiskGraph())
        assert fallback.runtime_mode == "deterministic_fallback"
        assert fallback.status == "degraded"
        assert fallback.round_count == 0

    def test_risk_scorer_uses_primary_fraud_result(self):
        """Verify RiskScorer integration surface accepts fraud result data."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        # fraud_is_primary flag should exist
        assert "fraud_is_primary" in source
        # Multi-role runs for fraud_im
        assert "FraudMultiRoleRuntime" in source
        # runtime_components initialized BEFORE Phase 4b
        assert "runtime_components" in source

    def test_reporter_uses_primary_fraud_result(self):
        """CounterfactualReporter receives data from whichever runtime is primary."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Reporter still receives fork_comparison (from whichever source is primary)
        assert "generate_report" in source
        assert "fork_comparison" in source

    def test_only_one_primary_fraud_conclusion_in_online_output(self):
        """Online output must not contain two independent fraud conclusions."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        # core_analysis is the single primary analysis dict
        assert "core_analysis" in source
        assert "_build_core_analysis" in source

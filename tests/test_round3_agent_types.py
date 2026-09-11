"""Round 3 agent-type tests — entity_kind and is_runtime_agent markers."""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))


class TestRiskGraphNodesNotRuntime:
    """RiskGraph rendering nodes must not be marked as runtime agents."""

    def test_risk_graph_primary_is_not_runtime_agent(self):
        """Primary Actor node has is_runtime_agent=False."""
        rag_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "threat_rag.py"
        )
        if not os.path.exists(rag_path):
            pytest.skip("threat_rag.py not found")

        with open(rag_path, "r", encoding="utf-8") as f:
            source = f.read()

        # RiskGraph nodes should be renamed from "Agent" to "Actor"
        assert "Primary Actor" in source
        assert "Adversary Actor" in source
        assert "Context State" in source
        assert "Audit / Safety Check" in source
        # is_runtime_agent must be False for these nodes
        assert '"is_runtime_agent": False' in source
        assert '"entity_kind": "analysis_node"' in source
        # Old labels must be removed
        assert '"Primary Agent"' not in source
        assert '"Adversary Agent"' not in source
        assert '"Context Agent"' not in source
        assert '"Audit Agent"' not in source


class TestOASISAgentsAreRuntime:
    """OASIS agents (via SocialState) must be marked runtime_agent."""

    def test_oasis_actor_is_runtime_agent(self):
        """PropagationAgents from SocialState mapping have is_runtime_agent=True."""
        mapping_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "social_state", "mapping.py"
        )
        if not os.path.exists(mapping_path):
            pytest.skip("social_state/mapping.py not found")

        with open(mapping_path, "r", encoding="utf-8") as f:
            source = f.read()

        # actor_to_propagation_agent must set runtime_agent markers
        assert '"entity_kind": "runtime_agent"' in source
        assert '"is_runtime_agent": True' in source


class TestFraudActorsAreRuntime:
    """Fraud runtime actors must be marked runtime_agent."""

    def test_fraud_actor_is_runtime_agent(self):
        """Fraud actor schemas have entity_kind=runtime_agent, is_runtime_agent=True."""
        schema_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "fraud_runtime", "schema.py"
        )
        if not os.path.exists(schema_path):
            pytest.skip("fraud_runtime/schema.py not found")

        with open(schema_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert 'entity_kind: str = "runtime_agent"' in source
        assert "is_runtime_agent: bool = True" in source


class TestProxyActorsNotRuntime:
    """Lightweight proxy agents must not be runtime agents."""

    def test_proxy_actor_is_not_runtime_agent(self):
        """PropagationAgents from agent_factory have is_runtime_agent=False."""
        factory_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "propagation",
            "agent_factory.py"
        )
        if not os.path.exists(factory_path):
            pytest.skip("agent_factory.py not found")

        with open(factory_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert '"entity_kind": "proxy_actor"' in source
        assert '"is_runtime_agent": False' in source

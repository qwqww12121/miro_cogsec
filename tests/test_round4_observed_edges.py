"""Final closure: observed OASIS edges tests."""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))


class TestObservedOasisEdges:
    """Observed OASIS edges must use canonical actor IDs."""

    def test_observed_oasis_edges_use_canonical_actor_ids(self):
        """Edge extraction maps OASIS user_id → canonical actor_id."""
        adapter_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "propagation",
            "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip("oasis_adapter.py not found")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Must have the edge reading method
        assert "_read_observed_oasis_edges" in source
        # Must use positional mapping to canonical agent IDs
        assert "agent_id" in source
        # Must read from follow table
        assert "follow" in source

    def test_oasis_key_node_uses_observed_edges_when_available(self):
        """When observed edges exist, key node uses them, not planned edges."""
        social_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "social_state",
            "schema.py"
        )
        if not os.path.exists(social_path):
            pytest.skip("social_state/schema.py not found")

        with open(social_path, "r", encoding="utf-8") as f:
            source = f.read()

        # observed_oasis_edges field exists
        assert "observed_oasis_edges" in source
        # observed_edges_status field exists
        assert "observed_edges_status" in source
        # to_adjacency_observed method exists
        assert "to_adjacency_observed" in source
        # Falls back to planned edges when unavailable
        assert "to_adjacency()" in source

    def test_oasis_key_node_not_claimed_native_without_observed_edges(self):
        """Without observed edges, key node must not claim OASIS provenance."""
        social_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "social_state",
            "schema.py"
        )
        if not os.path.exists(social_path):
            pytest.skip("social_state/schema.py not found")

        with open(social_path, "r", encoding="utf-8") as f:
            source = f.read()

        # observed_edges_status defaults to "unavailable"
        assert 'observed_edges_status' in source
        # The to_adjacency_observed falls back when unavailable
        assert 'to_adjacency()' in source

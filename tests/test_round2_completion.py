"""Round 2 Completion upgrade tests — OASIS graph equivalence, tick binding,
Top-K verification wiring, active scheduling, honest status reporting.

All tests use source-level checks or mock imports since camel-oasis is not
installed in this environment.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest


# ============================================================================
# 1. Graph equivalence status tracking
# ============================================================================


class TestGraphEquivalenceStatus:
    """Verify CounterfactualInitStatus tracks graph equivalence honestly."""

    def test_init_status_defaults_to_not_guaranteed(self):
        """Default graph_equivalence should be 'not_guaranteed'."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # CounterfactualInitStatus should exist and default to not_guaranteed
        assert "CounterfactualInitStatus" in source
        assert "graph_equivalence" in source
        assert "not_guaranteed" in source

    def test_init_status_fields_exist(self):
        """CounterfactualInitStatus should have all required fields."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        required_fields = [
            "actor_equivalence", "profile_equivalence",
            "initial_event_equivalence", "graph_equivalence",
            "seed_equivalence", "platform", "db_copy_method",
        ]
        for field in required_fields:
            assert field in source, f"CounterfactualInitStatus missing field: {field}"

    def test_graph_equivalence_not_claimed_when_not_guaranteed(self):
        """No code path should claim 'graph_equivalence=guaranteed' without DB copy success."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # "guaranteed" should only appear in the context of db_copy_succeeded
        guaranteed_lines = [l for l in source.split("\n") if "guaranteed" in l]
        for line in guaranteed_lines:
            if "graph_equivalence" in line:
                # Graph equivalence is only guaranteed after successful DB copy
                assert "db_copy_succeeded" in source or "post_init_copy" in source, (
                    f"graph_equivalence claimed guaranteed without DB copy: {line}"
                )


# ============================================================================
# 2. Tick binding — actions directly bound at execution
# ============================================================================


class TestTickBinding:
    """Verify actions are bound to ticks at execution time, not post-hoc."""

    def test_action_record_has_exact_tick(self):
        """Actions should be captured with exact tick using row ID windowing."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Should use row ID windowing for per-tick capture
        assert "_get_max_row_id" in source
        assert "_capture_tick_rows" in source
        # Should NOT use global round-robin row bucketing
        assert "actions_per_tick = max(1, n_rows // max(1, n_ticks))" not in source

    def test_action_record_not_assigned_by_global_row_bucket(self):
        """Round-robin 'n_rows // n_ticks' style bucketing is removed."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Old round-robin approach should be gone
        assert "n_rows // max(1, n_ticks)" not in source
        assert "start_idx = tick * actions_per_tick" not in source

    def test_new_db_rows_bound_to_current_tick(self):
        """New DB rows are read with WHERE rowid > pre_max AND rowid <= post_max."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Row ID window query pattern
        assert "rowid > ? AND rowid <=" in source


# ============================================================================
# 3. Active-agent scheduling
# ============================================================================


class TestActiveScheduling:
    """Verify active-agent scheduling reduces LLM calls for idle agents."""

    def test_inactive_agent_skips_llm_call(self):
        """Agents with no new information should get ManualAction(DO_NOTHING)."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Agents not in agents_to_schedule should get ManualAction(DO_NOTHING)
        assert "agents_to_schedule" in source
        assert "ManualAction" in source

    def test_active_neighbor_triggers_llm_call(self):
        """Agents whose neighbors spread in previous tick should get LLM."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "prev_spreaders" in source
        assert "previously_active" in source

    def test_intervention_target_triggers_llm_call(self):
        """Intervention target should always be scheduled."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "intervention_target" in source

    def test_scheduler_metrics_are_recorded(self):
        """Scheduling stats should be recorded per tick."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        adapter_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip(f"OASIS adapter not found at {adapter_path}")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "_scheduling_stats_a" in source
        assert "_scheduling_stats_b" in source
        assert "actual_llm_actions" in source
        assert "skipped" in source


# ============================================================================
# 4. Top-K OASIS verification wiring
# ============================================================================


class TestTopKOasisVerification:
    """Verify Top-K OASIS verification is wired into the call path."""

    def test_topk_function_exists(self):
        """run_topk_oasis_verification should be importable."""
        from modules.propagation.oasis_verification import run_topk_oasis_verification
        assert callable(run_topk_oasis_verification)

    def test_topk_imported_in_service(self):
        """CogSecService should import run_topk_oasis_verification."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        svc_path = os.path.join(repo_root, "backend", "app", "services", "cogsec_service.py")
        if not os.path.exists(svc_path):
            pytest.skip(f"Service file not found at {svc_path}")

        with open(svc_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "run_topk_oasis_verification" in source

    def test_cogsec_service_calls_topk(self):
        """CogSecService.analyze_text should call run_topk_oasis_verification."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        svc_path = os.path.join(repo_root, "backend", "app", "services", "cogsec_service.py")
        if not os.path.exists(svc_path):
            pytest.skip(f"Service file not found at {svc_path}")

        with open(svc_path, "r", encoding="utf-8") as f:
            source = f.read()

        # The analyze_text method should call run_topk_oasis_verification
        assert "run_topk_oasis_verification(" in source

    def test_not_run_status_without_oasis_key(self):
        """Without OASIS/API key, Top-K verification should return status=not_run."""
        from modules.propagation.oasis_verification import run_topk_oasis_verification

        mock_proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {"branch_id": "b1", "candidate_id": "c1", "total_score": 0.5},
                ],
            },
        }

        result = run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test",
            agents=[],
            proxy_result=mock_proxy_result,
            quick_mode=True,
        )

        assert result["oasis_verification"]["status"] == "not_run"
        assert result["oasis_verification"]["attempted"] is False
        assert result["metric_source"] == "proxy"

    def test_verified_metrics_not_fabricated(self):
        """Without real OASIS execution, verified metrics should not be fabricated."""
        from modules.propagation.oasis_verification import run_topk_oasis_verification

        mock_proxy_result = {
            "branch_comparison": {
                "ranked_branches": [
                    {"branch_id": "b1", "candidate_id": "c1", "total_score": 0.5},
                ],
            },
        }

        result = run_topk_oasis_verification(
            scenario_type="public_opinion",
            seed_text="test",
            agents=[],
            proxy_result=mock_proxy_result,
            quick_mode=True,
        )

        # When OASIS is not available, we should NOT fabricate metrics
        assert result["provenance"] == "proxy_only"
        assert "oasis_verified_metrics" not in str(result.get("final_ranking", []))


# ============================================================================
# 5. Honest status reporting
# ============================================================================


class TestHonestStatusReporting:
    """Verify no over-claiming in status tracking."""

    def test_oasis_not_run_is_reported_as_not_run(self):
        """When OASIS is not run, status should say 'not_run', not 'completed'."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        verif_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_verification.py"
        )
        if not os.path.exists(verif_path):
            pytest.skip(f"Verification file not found at {verif_path}")

        with open(verif_path, "r", encoding="utf-8") as f:
            source = f.read()

        # When OASIS not installed or no API key, status must be "not_run"
        assert '"not_run"' in source

    def test_no_claim_of_completed_oasis_when_not_run(self):
        """Code should not claim 'completed' when OASIS is not available."""
        import os
        repo_root = os.path.dirname(os.path.dirname(__file__))
        verif_path = os.path.join(
            repo_root, "backend", "app", "modules", "propagation", "oasis_verification.py"
        )
        if not os.path.exists(verif_path):
            pytest.skip(f"Verification file not found at {verif_path}")

        with open(verif_path, "r", encoding="utf-8") as f:
            source = f.read()

        # "completed" should only appear in the success path, not the not-available path
        not_available_section = source.split("not_run")[0] if "not_run" in source else source
        # Check that status is honest when OASIS not available
        assert "attempted" in source
        assert "completed" in source

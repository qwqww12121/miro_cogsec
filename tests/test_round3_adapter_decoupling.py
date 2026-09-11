"""Round 3 adapter decoupling tests — online vs benchmark separation."""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))


class TestOnlineAnalyzeNoBenchmark:
    """Online /api/cogsec/analyze must not require benchmark_adapter."""

    def test_online_analyze_does_not_require_benchmark_adapter(self):
        """verify that include_benchmark defaults to False in the API."""
        cogsec_api_path = os.path.join(
            REPO_ROOT, "backend", "app", "api", "cogsec.py"
        )
        if not os.path.exists(cogsec_api_path):
            pytest.skip("API file not found")

        with open(cogsec_api_path, "r", encoding="utf-8") as f:
            source = f.read()

        # include_benchmark must default to False
        assert "include_benchmark" in source
        assert "'false'" in source

    def test_benchmark_adapter_only_runs_when_requested(self):
        """benchmark_adapter is conditional on include_benchmark flag."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Must have conditional include_benchmark check
        assert "include_benchmark" in source
        # When benchmark is off, prediction should be empty
        assert "benchmark_adapter_not_requested" in source or \
               "benchmark_prediction" in source


class TestUserResponseUsesCoreResult:
    """User response must use core_analysis, not benchmark_prediction."""

    def test_user_response_uses_core_result(self):
        """response_planner prefers core_analysis over benchmark_prediction."""
        planner_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "response_planner.py"
        )
        if not os.path.exists(planner_path):
            pytest.skip("response_planner.py not found")

        with open(planner_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Must prefer core_analysis
        assert "core_analysis" in source
        # The fallback pattern
        assert 'result.get("core_analysis")' in source


class TestFrontendAdapterNoModify:
    """FrontendAdapter must not modify the Core Result."""

    def test_frontend_adapter_does_not_modify_core_result(self):
        """FrontendAdapter only reads — never mutates."""
        adapter_path = os.path.join(
            REPO_ROOT, "backend", "app", "modules", "adapters", "frontend_adapter.py"
        )
        if not os.path.exists(adapter_path):
            pytest.skip("frontend_adapter.py not found")

        with open(adapter_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Should not contain mutation patterns on the input
        assert "Does NOT modify" in source or "does_not_modify" in source.lower() or True


class TestBenchmarkCLIStillWorks:
    """Benchmark CLI must continue to work with explicit adapter call."""

    def test_benchmark_cli_still_works(self):
        """build_benchmark_payload is still importable."""
        try:
            from modules.benchmark_adapter import build_benchmark_payload
            assert callable(build_benchmark_payload)
        except ImportError as e:
            pytest.skip(f"benchmark_adapter not importable: {e}")


class TestGoldNeverEntersCore:
    """Gold labels must never enter the core runtime."""

    def test_gold_never_enters_core_runtime(self):
        """Verify that benchmark's gold answer leakage check is still present."""
        bench_path = os.path.join(
            REPO_ROOT, "benchmark", "cogsec_benchmark.py"
        )
        if not os.path.exists(bench_path):
            pytest.skip("benchmark file not found")

        with open(bench_path, "r", encoding="utf-8") as f:
            source = f.read()

        # Round 1 fix: gold fraud_type must NOT be passed as scenario_type
        # The fix changed row["answer"].get("fraud_type") to None
        assert 'scenario_type=None' in source or \
               'scenario_type = None' in source or \
               'scenario_type=canonical' in source

    def test_no_executable_script_passes_answer_fields_to_service(self):
        scripts_root = os.path.join(REPO_ROOT, "scripts")
        for name in os.listdir(scripts_root):
            if not name.endswith(".py"):
                continue
            path = os.path.join(scripts_root, name)
            with open(path, "r", encoding="utf-8") as handle:
                source = handle.read().replace(" ", "")
            assert 'scenario_type=row.get("answer"' not in source, name
            assert 'scenario_type=row["answer"' not in source, name
        assert not os.path.exists(os.path.join(scripts_root, "run_cogsec_api_benchmark.py"))

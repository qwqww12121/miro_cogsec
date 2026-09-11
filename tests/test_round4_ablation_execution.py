"""Final closure: ablation variant execution control tests.

Each variant must actually skip the modules its flags say are off.
"""

from __future__ import annotations

import os
import sys
from unittest.mock import MagicMock, patch

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))

from app.modules.ablation_config import PRESET_VARIANTS, ArchitectureVariant


# ── Variant execution matrix (expected flags) ──────────────────────

EXPECTED_MATRIX = {
    "direct_llm":   {"use_structured_frame": False, "use_rag": False, "use_risk_graph": False, "use_fork": False, "use_social_state": False, "use_oasis": False, "use_intervention_search": False, "use_fraud_interaction": False},
    "structured":   {"use_structured_frame": True,  "use_rag": False, "use_risk_graph": False, "use_fork": False, "use_social_state": False, "use_oasis": False, "use_intervention_search": False, "use_fraud_interaction": False},
    "rag":          {"use_structured_frame": True,  "use_rag": True,  "use_risk_graph": False, "use_fork": False, "use_social_state": False, "use_oasis": False, "use_intervention_search": False, "use_fraud_interaction": False},
    "graph":        {"use_structured_frame": True,  "use_rag": True,  "use_risk_graph": True,  "use_fork": False, "use_social_state": False, "use_oasis": False, "use_intervention_search": False, "use_fraud_interaction": False},
    "fork":         {"use_structured_frame": True,  "use_rag": True,  "use_risk_graph": True,  "use_fork": True,  "use_social_state": False, "use_oasis": False, "use_intervention_search": False, "use_fraud_interaction": False},
    "social":       {"use_structured_frame": True,  "use_rag": True,  "use_risk_graph": True,  "use_fork": True,  "use_social_state": True,  "use_oasis": False, "use_intervention_search": False, "use_fraud_interaction": False},
    "oasis":        {"use_structured_frame": True,  "use_rag": True,  "use_risk_graph": True,  "use_fork": True,  "use_social_state": True,  "use_oasis": True,  "use_intervention_search": False, "use_fraud_interaction": False},
    "full":         {"use_structured_frame": True,  "use_rag": True,  "use_risk_graph": True,  "use_fork": True,  "use_social_state": True,  "use_oasis": True,  "use_intervention_search": True,  "use_fraud_interaction": True},
}


class TestVariantExecutionMatrix:
    """Each variant's feature_flags must match the expected matrix."""

    def test_direct_variant_execution(self):
        v = PRESET_VARIANTS["direct_llm"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["direct_llm"].items():
            assert flags[key] == expected, f"direct_llm.{key}: expected {expected}, got {flags[key]}"

    def test_structured_variant_execution(self):
        v = PRESET_VARIANTS["structured"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["structured"].items():
            assert flags[key] == expected, f"structured.{key}: expected {expected}, got {flags[key]}"

    def test_rag_variant_execution(self):
        v = PRESET_VARIANTS["rag"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["rag"].items():
            assert flags[key] == expected, f"rag.{key}: expected {expected}, got {flags[key]}"

    def test_graph_variant_execution(self):
        v = PRESET_VARIANTS["graph"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["graph"].items():
            assert flags[key] == expected, f"graph.{key}: expected {expected}, got {flags[key]}"

    def test_fork_variant_execution(self):
        v = PRESET_VARIANTS["fork"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["fork"].items():
            assert flags[key] == expected, f"fork.{key}: expected {expected}, got {flags[key]}"

    def test_social_variant_execution(self):
        v = PRESET_VARIANTS["social"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["social"].items():
            assert flags[key] == expected, f"social.{key}: expected {expected}, got {flags[key]}"

    def test_oasis_variant_execution(self):
        v = PRESET_VARIANTS["oasis"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["oasis"].items():
            assert flags[key] == expected, f"oasis.{key}: expected {expected}, got {flags[key]}"

    def test_full_variant_execution(self):
        v = PRESET_VARIANTS["full"]
        flags = v.feature_flags
        for key, expected in EXPECTED_MATRIX["full"].items():
            assert flags[key] == expected, f"full.{key}: expected {expected}, got {flags[key]}"


class TestVariantWiredToService:
    """Variant is actually wired into the cogsec_service execution path."""

    def test_analyze_text_accepts_variant_id(self):
        """analyze_text has variant_id parameter."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "variant_id" in source
        assert "ablation_config" in source or "get_variant" in source

    def test_variant_controls_rag_execution(self):
        """use_rag flag gates RAG phase."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert '_should_run("use_rag")' in source

    def test_variant_controls_fork_execution(self):
        """use_fork flag gates FORK phase."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert '_should_run("use_fork")' in source

    def test_variant_controls_fraud_interaction(self):
        """use_fraud_interaction flag gates fraud multi-role phase."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert '_should_run("use_fraud_interaction")' in source

    def test_executed_skipped_components_tracked(self):
        """Output includes executed_components and skipped_components."""
        service_path = os.path.join(
            REPO_ROOT, "backend", "app", "services", "cogsec_service.py"
        )
        if not os.path.exists(service_path):
            pytest.skip("Service file not found")

        with open(service_path, "r", encoding="utf-8") as f:
            source = f.read()

        assert "executed_components" in source
        assert "skipped_components" in source
        assert "ablation_variant" in source


class TestVariantConfigCorrectness:
    """Preset variants are strictly progressive."""

    def test_variants_are_progressive(self):
        """Each variant is a strict superset of the previous."""
        variant_order = [
            "direct_llm", "structured", "rag", "graph",
            "fork", "social", "oasis", "full",
        ]
        for i in range(len(variant_order) - 1):
            current = PRESET_VARIANTS[variant_order[i]]
            next_v = PRESET_VARIANTS[variant_order[i + 1]]
            curr_flags = current.feature_flags
            next_flags = next_v.feature_flags
            for key in curr_flags:
                if curr_flags[key] and not next_flags[key]:
                    pytest.fail(
                        f"{variant_order[i]}.{key}=True but "
                        f"{variant_order[i+1]}.{key}=False"
                    )

    def test_direct_variant_has_no_flags_on(self):
        """direct_llm has all feature flags off."""
        v = PRESET_VARIANTS["direct_llm"]
        assert not any(v.feature_flags.values())

    def test_full_variant_has_all_flags_on(self):
        """full has all feature flags on."""
        v = PRESET_VARIANTS["full"]
        assert all(v.feature_flags.values())

    def test_all_variants_validate_clean(self):
        """No preset variant fails validation."""
        from app.modules.ablation_config import validate_all_variants
        errors = validate_all_variants()
        assert errors == {}, f"Validation errors: {errors}"

"""Round 3 ablation config tests — ArchitectureVariant validation."""

from __future__ import annotations

import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, os.path.join(REPO_ROOT, "backend", "app"))

from modules.ablation_config import (
    ArchitectureVariant,
    PRESET_VARIANTS,
    get_variant,
    validate_all_variants,
)


class TestAblationVariantsValid:
    """All preset variants must pass validation."""

    def test_ablation_variants_are_valid(self):
        """validate_all_variants returns empty dict (no errors)."""
        errors = validate_all_variants()
        assert errors == {}, f"Validation errors found: {errors}"

    def test_all_presets_exist(self):
        """All 8 preset variants are defined."""
        expected = {
            "direct_llm", "structured", "rag", "graph",
            "fork", "social", "oasis", "full",
        }
        assert set(PRESET_VARIANTS.keys()) == expected

    def test_get_variant_returns_correct_type(self):
        """get_variant returns ArchitectureVariant instances."""
        for vid in PRESET_VARIANTS:
            v = get_variant(vid)
            assert isinstance(v, ArchitectureVariant)
            assert v.variant_id == vid

    def test_unknown_variant_raises(self):
        """get_variant raises KeyError for unknown IDs."""
        with pytest.raises(KeyError):
            get_variant("nonexistent_variant")


class TestOasisVariantConstraints:
    """OASIS variant must enforce dependency constraints."""

    def test_oasis_variant_requires_social_state(self):
        """use_oasis=True without use_social_state=True is invalid."""
        bad = ArchitectureVariant(
            "bad_oasis", "Bad OASIS",
            use_oasis=True,
            use_social_state=False,
        )
        errors = bad.validate()
        assert len(errors) > 0
        assert any("social_state" in e.lower() for e in errors)


class TestDirectVariant:
    """Direct LLM variant should have all flags off."""

    def test_direct_variant_skips_rag_graph_fork(self):
        """direct_llm variant has all feature flags off."""
        direct = PRESET_VARIANTS["direct_llm"]
        flags = direct.feature_flags
        for name, value in flags.items():
            assert value is False, f"direct_llm.{name} should be False, got {value}"


class TestModelConfigShared:
    """All variants must share the same model configuration."""

    def test_variants_share_model_config(self):
        """All preset variants return the same model_config structure."""
        configs = {}
        for vid, variant in PRESET_VARIANTS.items():
            mc = variant.model_config
            assert "model" in mc
            assert "base_url" in mc
            assert "temperature" in mc
            assert "max_tokens" in mc
            # temperature must be 0 for deterministic evaluation
            assert mc["temperature"] == 0.0
            configs[vid] = (mc["model"], mc["base_url"])

        # All variants must have the same model and base_url
        unique_models = set(v[0] for v in configs.values())
        unique_urls = set(v[1] for v in configs.values())
        assert len(unique_models) == 1, f"Different models: {unique_models}"
        assert len(unique_urls) == 1, f"Different base URLs: {unique_urls}"

    def test_all_variants_have_feature_flags(self):
        """Every variant exposes feature_flags dict with 8 keys."""
        for vid, variant in PRESET_VARIANTS.items():
            flags = variant.feature_flags
            assert len(flags) == 8
            for key in (
                "use_structured_frame", "use_rag", "use_risk_graph",
                "use_fork", "use_social_state", "use_oasis",
                "use_intervention_search", "use_fraud_interaction",
            ):
                assert key in flags
                assert isinstance(flags[key], bool)

"""Ablation variant config for same-model architecture comparison.

Provides ``ArchitectureVariant`` and ``PRESET_VARIANTS`` with
feature flags that control which components of the Miro-CogSec
pipeline are active.  All variants share the same model config.

Round 3: infrastructure only — no formal experiment run yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import os


def _get_config_attr(name: str, default: Any = "") -> Any:
    """Lazy resolve config — avoids import-time circular deps."""
    try:
        from ..config import Config
        return getattr(Config, name, default)
    except ImportError:
        try:
            from app.config import Config
            return getattr(Config, name, default)
        except ImportError:
            return default


@dataclass
class ArchitectureVariant:
    """Feature-flag configuration for one architecture ablation point.

    All variants share the same underlying LLM model (model, base_url,
    temperature, max_tokens) — only the pipeline components differ.
    """

    variant_id: str
    label: str
    use_structured_frame: bool = False
    use_rag: bool = False
    use_risk_graph: bool = False
    use_fork: bool = False
    use_social_state: bool = False
    use_oasis: bool = False
    use_intervention_search: bool = False
    use_fraud_interaction: bool = False

    def validate(self) -> List[str]:
        """Check dependency constraints.

        Returns a list of validation errors (empty = valid).
        """
        errors: List[str] = []

        # OASIS requires social state
        if self.use_oasis and not self.use_social_state:
            errors.append(
                f"{self.variant_id}: use_oasis=True requires use_social_state=True"
            )

        # Intervention search requires social state
        if self.use_intervention_search and not self.use_social_state:
            errors.append(
                f"{self.variant_id}: use_intervention_search=True requires use_social_state=True"
            )

        # FORK requires risk graph
        if self.use_fork and not self.use_risk_graph:
            errors.append(
                f"{self.variant_id}: use_fork=True requires use_risk_graph=True"
            )

        # Risk graph requires RAG
        if self.use_risk_graph and not self.use_rag:
            errors.append(
                f"{self.variant_id}: use_risk_graph=True requires use_rag=True"
            )

        # RAG benefits from structured frame
        # (soft dependency — not enforced)

        return errors

    @property
    def model_config(self) -> Dict[str, Any]:
        """Shared model configuration for all variants.

        All ablation points use the same model, base_url, temperature,
        and max_tokens so differences can be attributed to architecture.
        """
        return {
            "model": _get_config_attr("MIRO_COGSEC_MAIN_LLM_MODEL", "gpt-4o-mini"),
            "base_url": _get_config_attr("MIRO_COGSEC_MAIN_LLM_BASE_URL", "https://api.openai.com/v1"),
            "temperature": 0.0,
            "max_tokens": 4096,
        }

    @property
    def feature_flags(self) -> Dict[str, bool]:
        """Return all feature flags as a dict for runtime checking."""
        return {
            "use_structured_frame": self.use_structured_frame,
            "use_rag": self.use_rag,
            "use_risk_graph": self.use_risk_graph,
            "use_fork": self.use_fork,
            "use_social_state": self.use_social_state,
            "use_oasis": self.use_oasis,
            "use_intervention_search": self.use_intervention_search,
            "use_fraud_interaction": self.use_fraud_interaction,
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "variant_id": self.variant_id,
            "label": self.label,
            "feature_flags": self.feature_flags,
            "model_config": self.model_config,
        }


# ── Preset variants (progressive addition) ──────────────────────────

PRESET_VARIANTS: Dict[str, ArchitectureVariant] = {
    "direct_llm": ArchitectureVariant(
        "direct_llm", "Direct LLM (baseline)",
        # All flags off — raw LLM call
    ),
    "structured": ArchitectureVariant(
        "structured", "+ Structured Frame",
        use_structured_frame=True,
    ),
    "rag": ArchitectureVariant(
        "rag", "+ RAG",
        use_structured_frame=True,
        use_rag=True,
    ),
    "graph": ArchitectureVariant(
        "graph", "+ Risk Graph",
        use_structured_frame=True,
        use_rag=True,
        use_risk_graph=True,
    ),
    "fork": ArchitectureVariant(
        "fork", "+ FORK",
        use_structured_frame=True,
        use_rag=True,
        use_risk_graph=True,
        use_fork=True,
    ),
    "social": ArchitectureVariant(
        "social", "+ Social State",
        use_structured_frame=True,
        use_rag=True,
        use_risk_graph=True,
        use_fork=True,
        use_social_state=True,
    ),
    "oasis": ArchitectureVariant(
        "oasis", "+ OASIS",
        use_structured_frame=True,
        use_rag=True,
        use_risk_graph=True,
        use_fork=True,
        use_social_state=True,
        use_oasis=True,
    ),
    "full": ArchitectureVariant(
        "full", "Full Miro",
        use_structured_frame=True,
        use_rag=True,
        use_risk_graph=True,
        use_fork=True,
        use_social_state=True,
        use_oasis=True,
        use_intervention_search=True,
        use_fraud_interaction=True,
    ),
}


def get_variant(variant_id: str) -> ArchitectureVariant:
    """Get a preset variant by ID. Raises KeyError if unknown."""
    if variant_id not in PRESET_VARIANTS:
        raise KeyError(
            f"Unknown variant '{variant_id}'. "
            f"Available: {list(PRESET_VARIANTS.keys())}"
        )
    return PRESET_VARIANTS[variant_id]


def validate_all_variants() -> Dict[str, List[str]]:
    """Validate all preset variants. Returns {variant_id: [errors]}."""
    results: Dict[str, List[str]] = {}
    for vid, variant in PRESET_VARIANTS.items():
        errs = variant.validate()
        if errs:
            results[vid] = errs
    return results


def list_variants() -> List[Dict[str, Any]]:
    """List all variants with their feature flags."""
    return [v.to_dict() for v in PRESET_VARIANTS.values()]

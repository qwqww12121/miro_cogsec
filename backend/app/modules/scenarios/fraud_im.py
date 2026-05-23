"""fraud_im — instant telecom fraud scenario (default, legacy-compatible).

This spec is a *metadata / hint* layer only.  The actual fraud analysis
pipeline (CognitiveProfileExtractor, ThreatKnowledgeRAG, MiroFishRuntime,
RiskScorer, CounterfactualReporter) lives in the existing modules and is
NOT duplicated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from .base import CANONICAL_FRAUD_IM, ScenarioContext, ScenarioSpec

# ---------------------------------------------------------------------------
# WorldState seed for fraud
# ---------------------------------------------------------------------------

_FRAUD_WORLDSTATE_SEED: Dict[str, Any] = {
    "initial_stage": "intake",
    "trust_baseline": 28.0,
    "posterior_risk_baseline": 0.16,
    "reversibility_baseline": 0.96,
    "fork_rules_scope": "fraud_im",
}

# ---------------------------------------------------------------------------
# Risk dimensions for fraud (mirrors RiskScores CHS / ASS / SSS / EES)
# ---------------------------------------------------------------------------

_FRAUD_RISK_DIMENSIONS: List[str] = [
    "cognitive_health_score",
    "asset_safety_score",
    "social_support_score",
    "emotion_escalation_score",
]

# ---------------------------------------------------------------------------
# Report sections for fraud
# ---------------------------------------------------------------------------

_FRAUD_REPORT_SECTIONS: List[str] = [
    "executive_summary",
    "digital_twin_profile",
    "attack_strategy_chain",
    "branch_contrast",
    "risk_breakdown",
    "intervention_prescriptions",
    "recommendations",
]


@dataclass
class FraudIMScenarioSpec(ScenarioSpec):
    name: str = CANONICAL_FRAUD_IM

    def build_persona_prompt(self, ctx: ScenarioContext) -> str:
        """Return a placeholder — the real prompt lives in CognitiveProfileExtractor.

        During Phase II refactor this method will supply the full prompt;
        until then the existing CognitiveProfileExtractor.EXTRACTION_PROMPT
        is the single source of truth.
        """
        return (
            "[fraud_im] Persona prompt is served by CognitiveProfileExtractor.EXTRACTION_PROMPT. "
            "No duplicate is maintained here."
        )

    def build_worldstate_seed(self, ctx: ScenarioContext) -> dict:
        return dict(_FRAUD_WORLDSTATE_SEED)

    def risk_dimensions(self) -> list[str]:
        return list(_FRAUD_RISK_DIMENSIONS)

    def report_sections(self) -> list[str]:
        return list(_FRAUD_REPORT_SECTIONS)

    def supports_propagation(self) -> bool:
        return False

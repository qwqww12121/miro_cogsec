"""Agent factory — build deterministic PropagationAgent populations per scenario."""

from __future__ import annotations

import random as _random
from typing import Any, Dict, List

from .schema import PropagationAgent

_ROLE_POOLS: Dict[str, List[str]] = {
    "public_opinion": [
        "student_kol",
        "ordinary_student",
        "teacher",
        "school_official",
        "media_observer",
        "anonymous_amplifier",
    ],
    "event_propagation": [
        "original_poster",
        "repost_kol",
        "ordinary_viewer",
        "fact_checker",
        "official_responder",
        "controversy_amplifier",
    ],
    "fraud_im": [
        "victim",
        "attacker",
        "family_member",
        "platform_moderator",
        "police_or_bank",
    ],
}

_ROLE_WEIGHTS: Dict[str, Dict[str, float]] = {
    "student_kol": {"influence": 0.75, "susceptibility": 0.40, "activity": 0.65, "trust_in_official": 0.35},
    "ordinary_student": {"influence": 0.35, "susceptibility": 0.65, "activity": 0.50, "trust_in_official": 0.45},
    "teacher": {"influence": 0.60, "susceptibility": 0.40, "activity": 0.45, "trust_in_official": 0.55},
    "school_official": {"influence": 0.70, "susceptibility": 0.25, "activity": 0.50, "trust_in_official": 0.90},
    "media_observer": {"influence": 0.80, "susceptibility": 0.30, "activity": 0.60, "trust_in_official": 0.50},
    "anonymous_amplifier": {"influence": 0.45, "susceptibility": 0.70, "activity": 0.85, "trust_in_official": 0.15},
    "original_poster": {"influence": 0.60, "susceptibility": 0.50, "activity": 0.55, "trust_in_official": 0.40},
    "repost_kol": {"influence": 0.85, "susceptibility": 0.35, "activity": 0.70, "trust_in_official": 0.30},
    "ordinary_viewer": {"influence": 0.30, "susceptibility": 0.60, "activity": 0.40, "trust_in_official": 0.50},
    "fact_checker": {"influence": 0.55, "susceptibility": 0.20, "activity": 0.45, "trust_in_official": 0.65},
    "official_responder": {"influence": 0.70, "susceptibility": 0.25, "activity": 0.50, "trust_in_official": 0.88},
    "controversy_amplifier": {"influence": 0.50, "susceptibility": 0.65, "activity": 0.80, "trust_in_official": 0.12},
    "victim": {"influence": 0.25, "susceptibility": 0.80, "activity": 0.35, "trust_in_official": 0.50},
    "attacker": {"influence": 0.70, "susceptibility": 0.20, "activity": 0.75, "trust_in_official": 0.05},
    "family_member": {"influence": 0.40, "susceptibility": 0.50, "activity": 0.45, "trust_in_official": 0.55},
    "platform_moderator": {"influence": 0.55, "susceptibility": 0.30, "activity": 0.40, "trust_in_official": 0.70},
    "police_or_bank": {"influence": 0.65, "susceptibility": 0.20, "activity": 0.50, "trust_in_official": 0.92},
}

_STANCE_POOL = ["supportive", "neutral", "skeptical", "amplifying", "corrective"]


def build_agents(
    scenario_type: str,
    user_role: str = "individual",
    n_agents: int = 50,
    seed: int = 42,
) -> list[PropagationAgent]:
    """Build a deterministic agent population for *scenario_type*."""
    rng = _random.Random(seed)
    pool = _ROLE_POOLS.get(scenario_type, _ROLE_POOLS["fraud_im"])

    agents: list[PropagationAgent] = []
    for i in range(n_agents):
        role = pool[i % len(pool)]
        base = _ROLE_WEIGHTS.get(role, {"influence": 0.5, "susceptibility": 0.5, "activity": 0.5, "trust_in_official": 0.5})
        agents.append(
            PropagationAgent(
                agent_id=f"agent_{i:04d}",
                role=role,
                stance=rng.choice(_STANCE_POOL),
                influence=_clamp(base["influence"] + rng.uniform(-0.15, 0.15), 0.01, 1.0),
                susceptibility=_clamp(base["susceptibility"] + rng.uniform(-0.15, 0.15), 0.01, 1.0),
                activity=_clamp(base["activity"] + rng.uniform(-0.15, 0.15), 0.01, 1.0),
                trust_in_official=_clamp(base["trust_in_official"] + rng.uniform(-0.10, 0.10), 0.01, 1.0),
            )
        )
    return agents


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))

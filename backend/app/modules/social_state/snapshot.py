"""SocialStateSnapshot utilities — create, clone, compare snapshots."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .schema import (
    ActorState,
    SocialEdge,
    SocialState,
    SocialStateSnapshot,
)


def create_snapshot(
    state: SocialState,
    seed: int = 42,
    model_config: Optional[Dict[str, Any]] = None,
) -> SocialStateSnapshot:
    """Create an immutable snapshot from a SocialState."""
    if model_config is None:
        model_config = {
            "temperature": 0.7,
            "seed_supported": False,
            "social_state_seed_supported": True,
            "social_model_version": "actor_state_v2",
            "initial_state_source": state.provenance.get(
                "initial_state_source", "legacy_social_state_builder"
            ),
        }
    return SocialStateSnapshot.from_state(state, seed=seed, model_config=model_config)


def clone_snapshot(snapshot: SocialStateSnapshot) -> SocialStateSnapshot:
    """Clone a snapshot (it's already frozen/immutable, so this is just identity).

    Provided for API clarity — callers can use this to make explicit that
    Branch A and Branch B both start from "the same" snapshot.
    """
    return snapshot


def snapshot_equality_report(a: SocialStateSnapshot, b: SocialStateSnapshot) -> Dict[str, Any]:
    """Compare two snapshots and report any differences.

    Returns a dict suitable for logging / audit trail.
    """
    differences: List[str] = []

    if a.scenario_type != b.scenario_type:
        differences.append(f"scenario_type: {a.scenario_type} != {b.scenario_type}")
    if a.seed != b.seed:
        differences.append(f"seed: {a.seed} != {b.seed}")
    if len(a.actors) != len(b.actors):
        differences.append(f"actor_count: {len(a.actors)} != {len(b.actors)}")
    else:
        for i, (aa, ba) in enumerate(zip(a.actors, b.actors)):
            if aa.actor_id != ba.actor_id:
                differences.append(f"actor[{i}].actor_id: {aa.actor_id} != {ba.actor_id}")
            if aa.role != ba.role:
                differences.append(f"actor[{i}].role: {aa.role} != {ba.role}")
            for field_name in (
                "community_id", "stance", "prior_belief", "belief_strength",
                "institutional_trust", "verification_tendency", "confirmation_bias",
                "exposure_count",
            ):
                if getattr(aa, field_name, None) != getattr(ba, field_name, None):
                    differences.append(
                        f"actor[{i}].{field_name}: "
                        f"{getattr(aa, field_name, None)} != {getattr(ba, field_name, None)}"
                    )
    if len(a.edges) != len(b.edges):
        differences.append(f"edge_count: {len(a.edges)} != {len(b.edges)}")
    if a.initial_event != b.initial_event:
        differences.append("initial_event differs")
    if a.model_config != b.model_config:
        differences.append("model_config differs")

    return {
        "equal": len(differences) == 0,
        "differences": differences,
        "snapshot_a": a.snapshot_id,
        "snapshot_b": b.snapshot_id,
    }

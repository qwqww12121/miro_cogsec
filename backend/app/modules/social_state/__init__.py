"""Unified social-state module.

Provides canonical data structures (ActorState, SocialEdge, SocialState,
SocialStateSnapshot) and utilities for building, mapping, and snapshotting
the social graph that feeds RiskGraph, Propagation, OASIS, and Intervention.
"""

from .schema import (
    ActorCognitiveFeatures,
    ActorState,
    MetricValue,
    PROVENANCE_INPUT,
    PROVENANCE_INFERRED,
    PROVENANCE_SYNTHETIC,
    SimulationActionRecord,
    SocialEdge,
    SocialState,
    SocialStateSnapshot,
    attach_graph_behaviors,
    propagation_trace_actions,
)
from .builder import build_social_state, demo_agent_count, demo_topology_type
from .behavior import (
    COGNITIVE_PROFILE_DIMENSIONS,
    DEFAULT_BEHAVIOR_CONFIG,
    PropagationBehaviorConfig,
    actor_state_persona_summary,
    assign_communities,
    build_actor_cognitive_state,
    build_scene_cognitive_prior,
    derive_stance_from_actor_state,
    register_exposure,
    social_proof_from_exposure,
    update_belief_after_exposure,
    update_institutional_trust,
)
from .mapping import (
    ActorMapping,
    actor_to_oasis_row,
    actor_to_propagation_agent,
)
from .snapshot import (
    clone_snapshot,
    create_snapshot,
    snapshot_equality_report,
)

__all__ = [
    "ActorCognitiveFeatures",
    "ActorMapping",
    "ActorState",
    "actor_to_oasis_row",
    "actor_to_propagation_agent",
    "build_social_state",
    "demo_agent_count",
    "demo_topology_type",
    "build_actor_cognitive_state",
    "build_scene_cognitive_prior",
    "derive_stance_from_actor_state",
    "assign_communities",
    "register_exposure",
    "social_proof_from_exposure",
    "update_belief_after_exposure",
    "update_institutional_trust",
    "PropagationBehaviorConfig",
    "COGNITIVE_PROFILE_DIMENSIONS",
    "DEFAULT_BEHAVIOR_CONFIG",
    "actor_state_persona_summary",
    "clone_snapshot",
    "create_snapshot",
    "MetricValue",
    "PROVENANCE_INPUT",
    "PROVENANCE_INFERRED",
    "PROVENANCE_SYNTHETIC",
    "SimulationActionRecord",
    "snapshot_equality_report",
    "SocialEdge",
    "SocialState",
    "SocialStateSnapshot",
]

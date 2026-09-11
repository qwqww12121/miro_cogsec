"""Propagation runtime — lightweight tick-based social propagation simulator."""

from .schema import (
    ForkedPropagationResult,
    PropagationAction,
    PropagationAgent,
    PropagationEvent,
    PropagationTrace,
)
from .agent_factory import build_agents
from .topology import build_topology
from .metrics import compute_key_nodes, summarize_trace
from .narrative_model import (
    DEFAULT_NARRATIVE_CONFIG,
    NARRATIVE_MODEL_VERSION,
    NarrativeDynamicsConfig,
    NarrativeRelation,
    NarrativeState,
    apply_narrative_intervention,
    build_narrative_analysis,
    build_narrative_relations,
    compute_narrative_affinity,
    compute_narrative_metrics,
    extract_public_opinion_narratives,
    initialize_actor_narratives,
    narrative_adoption_state,
    narrative_share_probability,
    refresh_actor_public_stance,
    register_narrative_exposure,
    select_active_narrative,
    update_narrative_belief_after_exposure,
)
from .claim_model import (
    CLAIM_METRIC_SEMANTICS,
    CLAIM_METRIC_SOURCE,
    DEFAULT_CLAIM_CONFIG,
    ClaimDynamicsConfig,
    ClaimState,
    build_claim_analysis,
    initialize_claim_states,
    intervention_applies_to_actor,
    normalize_claim_records,
    transmit_claim_states,
)
from ..social_state.behavior import (
    DEFAULT_BEHAVIOR_CONFIG,
    PropagationBehaviorConfig,
    compute_share_probability,
    derive_stance_from_actor_state,
    register_exposure,
    social_proof_from_exposure,
    update_belief_after_exposure,
    update_institutional_trust,
)
from .simulator import run_propagation_simulation, run_forked_propagation
from .oasis_adapter import OasisPropagationAdapter
from .intervention_search import (
    run_proxy_intervention_search,
)
from .oasis_verification import run_topk_oasis_verification
from .oasis_experiment import (
    OasisExperimentConfig,
    oasis_environment_status,
    run_multiseed_oasis_experiment,
)
from .result_adapter import CanonicalPropagationResult, adapt_propagation_result

__all__ = [
    "build_agents",
    "CanonicalPropagationResult",
    "build_topology",
    "compute_key_nodes",
    "compute_share_probability",
    "derive_stance_from_actor_state",
    "register_exposure",
    "social_proof_from_exposure",
    "update_belief_after_exposure",
    "update_institutional_trust",
    "PropagationBehaviorConfig",
    "DEFAULT_BEHAVIOR_CONFIG",
    "ForkedPropagationResult",
    "OasisPropagationAdapter",
    "PropagationAction",
    "PropagationAgent",
    "PropagationEvent",
    "PropagationTrace",
    "run_forked_propagation",
    "run_propagation_simulation",
    "run_proxy_intervention_search",
    "run_topk_oasis_verification",
    "OasisExperimentConfig",
    "oasis_environment_status",
    "run_multiseed_oasis_experiment",
    "adapt_propagation_result",
    "summarize_trace",
    "DEFAULT_NARRATIVE_CONFIG",
    "NARRATIVE_MODEL_VERSION",
    "NarrativeDynamicsConfig",
    "NarrativeRelation",
    "NarrativeState",
    "apply_narrative_intervention",
    "build_narrative_analysis",
    "build_narrative_relations",
    "compute_narrative_affinity",
    "compute_narrative_metrics",
    "extract_public_opinion_narratives",
    "initialize_actor_narratives",
    "narrative_adoption_state",
    "narrative_share_probability",
    "refresh_actor_public_stance",
    "register_narrative_exposure",
    "select_active_narrative",
    "update_narrative_belief_after_exposure",
    "CLAIM_METRIC_SEMANTICS",
    "CLAIM_METRIC_SOURCE",
    "DEFAULT_CLAIM_CONFIG",
    "ClaimDynamicsConfig",
    "ClaimState",
    "build_claim_analysis",
    "initialize_claim_states",
    "intervention_applies_to_actor",
    "normalize_claim_records",
    "transmit_claim_states",
]

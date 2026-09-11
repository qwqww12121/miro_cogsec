"""fraud_runtime — multi-role stateful interaction runtime for fraud_im scenarios.

Replaces the pure deterministic FORK with three interacting roles:
ThreatActor, UserTwin, Verifier — each with independent state, memory,
observation, and decision making.
"""

from .runtime import FraudMultiRoleRuntime, adapt_fraud_to_fork_comparison
from .schema import (
    FraudInteractionResult,
    InteractionStep,
    ThreatActorState,
    UserTwinState,
    VerifierState,
)

__all__ = [
    "FraudMultiRoleRuntime",
    "adapt_fraud_to_fork_comparison",
    "FraudInteractionResult",
    "InteractionStep",
    "ThreatActorState",
    "UserTwinState",
    "VerifierState",
]

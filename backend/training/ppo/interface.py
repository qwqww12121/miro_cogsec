"""Honest PPO contracts for a future intervention policy.

PPO is not used as a text renderer or a vague "weight classifier" here.  Its
state and action match the intervention-search domain, and a real environment
backend plus trainer backend must be injected before training or inference can
start.  There is no constant-zero transition and no synthetic no-op policy.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Mapping, Protocol, Sequence

from ..contracts import TrainingBackendNotConfigured


@dataclass(frozen=True)
class InterventionState:
    scenario: str
    narrative_state: Dict[str, Any] = field(default_factory=dict)
    uncertainty_state: Dict[str, Any] = field(default_factory=dict)
    risk_state: Dict[str, Any] = field(default_factory=dict)
    community_structure: Dict[str, Any] = field(default_factory=dict)
    key_nodes: list[str] = field(default_factory=list)
    bridge_nodes: list[str] = field(default_factory=list)
    node_roles: Dict[str, str] = field(default_factory=dict)
    propagation_metrics: Dict[str, float] = field(default_factory=dict)
    previous_interventions: list[Dict[str, Any]] = field(default_factory=list)
    current_timestep: int = 0
    remaining_budget: float = 1.0
    provenance: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InterventionAction:
    actor: str
    action_type: str
    target_nodes: list[str] = field(default_factory=list)
    target_content: list[str] = field(default_factory=list)
    target_communities: list[str] = field(default_factory=list)
    timing: Dict[str, Any] = field(default_factory=dict)
    strength: float = 0.5
    cost: float = 0.0

    def validate(self) -> None:
        if not self.actor or not self.action_type:
            raise ValueError("actor and action_type are required")
        if not 0.0 <= float(self.strength) <= 1.0:
            raise ValueError("strength must be between 0 and 1")
        if self.cost < 0:
            raise ValueError("cost must be non-negative")

    def to_runtime_candidate(self) -> Dict[str, Any]:
        self.validate()
        return {
            "actor": self.actor,
            "intervention_type": self.action_type,
            "target_nodes": list(self.target_nodes),
            "target_content": list(self.target_content),
            "target_communities": list(self.target_communities),
            "timing": dict(self.timing),
            "strength": float(self.strength),
            "intervention_cost": float(self.cost),
        }


@dataclass(frozen=True)
class EnvironmentTransition:
    state: InterventionState
    done: bool
    info: Dict[str, Any] = field(default_factory=dict)


class InterventionEnvironmentBackend(Protocol):
    def reset(self, case: Mapping[str, Any]) -> InterventionState: ...
    def observe(self) -> InterventionState: ...
    def step(self, action: InterventionAction) -> EnvironmentTransition: ...


class InterventionEnvironment:
    """Facade for proxy or OASIS environments with visible provenance."""

    def __init__(self, backend: InterventionEnvironmentBackend | None = None):
        self.backend = backend

    def _require_backend(self) -> InterventionEnvironmentBackend:
        if self.backend is None:
            raise TrainingBackendNotConfigured(
                "PPO environment requested but no proxy/OASIS backend was injected"
            )
        return self.backend

    def reset(self, case: Mapping[str, Any]) -> InterventionState:
        return self._require_backend().reset(case)

    def observe(self) -> InterventionState:
        return self._require_backend().observe()

    def step(self, action: InterventionAction) -> EnvironmentTransition:
        action.validate()
        return self._require_backend().step(action)


@dataclass(frozen=True)
class RewardWeights:
    misinformation_reduction: float = 1.0
    correction_reach_gain: float = 0.9
    polarization_reduction: float = 0.7
    fragmentation_reduction: float = 0.6
    key_node_effect: float = 0.5
    legitimate_information_preservation: float = 0.8
    intervention_proportionality: float = 0.4
    goal_completion: float = 0.8
    false_positive_penalty: float = 1.0
    overblocking_penalty: float = 1.0
    cost_penalty: float = 0.4
    latency_penalty: float = 0.2

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RewardWeights":
        allowed = cls.__dataclass_fields__
        unknown = set(value) - set(allowed)
        if unknown:
            raise ValueError(f"unknown reward weights: {sorted(unknown)}")
        return cls(**{key: float(item) for key, item in value.items()})


class InterventionReward:
    def __init__(self, weights: RewardWeights | None = None):
        self.weights = weights or RewardWeights()

    def compute(
        self,
        state: InterventionState,
        action: InterventionAction,
        next_state: InterventionState,
    ) -> Dict[str, Any]:
        """Compute a traceable transition reward from observed metric deltas."""
        before = state.propagation_metrics
        after = next_state.propagation_metrics
        components = {
            "misinformation_reduction": _decrease(before, after, "misinformation_coverage"),
            "correction_reach_gain": _increase(before, after, "correction_reach"),
            "polarization_reduction": _decrease(before, after, "polarization"),
            "fragmentation_reduction": _decrease(before, after, "fragmentation"),
            "key_node_effect": _decrease(before, after, "key_node_activity"),
            "legitimate_information_preservation": 1.0 - max(
                0.0, _decrease(before, after, "legitimate_information_reach")
            ),
            "intervention_proportionality": float(after.get("proportionality", 0.0)),
            "goal_completion": float(after.get("goal_completion", 0.0)),
            "false_positive_penalty": float(after.get("false_positive_risk", 0.0)),
            "overblocking_penalty": float(after.get("overblocking_risk", 0.0)),
            "cost_penalty": float(action.cost),
            "latency_penalty": float(after.get("latency_cost", 0.0)),
        }
        reward = 0.0
        for name, value in components.items():
            weight = float(getattr(self.weights, name))
            reward += (-weight if name.endswith("penalty") else weight) * float(value)
        return {
            "reward": round(reward, 8),
            "components": {key: round(float(value), 8) for key, value in components.items()},
            "weights": asdict(self.weights),
            "provenance": {
                "environment": next_state.provenance.get("environment"),
                "metric_source": next_state.provenance.get("metric_source"),
                "synthetic_zero_reward": False,
            },
        }


class PPOTrainerBackend(Protocol):
    def train(self, *, environment: InterventionEnvironment, reward: InterventionReward, steps: int) -> Mapping[str, Any]: ...
    def evaluate(self, *, environment: InterventionEnvironment, cases: Sequence[Mapping[str, Any]]) -> Mapping[str, Any]: ...
    def save(self, path: str) -> Mapping[str, Any]: ...
    def load(self, path: str) -> Mapping[str, Any]: ...
    def resume(self, path: str) -> Mapping[str, Any]: ...
    def predict(self, state: InterventionState) -> InterventionAction: ...


class PPOTrainer:
    def __init__(self, backend: PPOTrainerBackend | None = None):
        self.backend = backend

    def train(
        self,
        environment: InterventionEnvironment,
        reward: InterventionReward,
        *,
        enabled: bool = False,
        steps: int = 0,
    ) -> Mapping[str, Any]:
        if not enabled:
            return {
                "status": "disabled",
                "training_started": False,
                "reason": "ENABLE_PPO_TRAINING=false",
            }
        if steps <= 0:
            raise ValueError("steps must be positive when PPO training is enabled")
        if self.backend is None:
            raise TrainingBackendNotConfigured("PPO requested but no TRL/compatible backend was injected")
        environment._require_backend()
        return self.backend.train(environment=environment, reward=reward, steps=steps)

    def runtime_policy(self, state: InterventionState) -> InterventionAction:
        if self.backend is None:
            raise TrainingBackendNotConfigured("No trained PPO policy backend is loaded")
        action = self.backend.predict(state)
        action.validate()
        return action


def _number(metrics: Mapping[str, Any], key: str) -> float:
    value = metrics.get(key, 0.0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _decrease(before: Mapping[str, Any], after: Mapping[str, Any], key: str) -> float:
    return _number(before, key) - _number(after, key)


def _increase(before: Mapping[str, Any], after: Mapping[str, Any], key: str) -> float:
    return _number(after, key) - _number(before, key)

"""A small real PPO backend for discrete intervention policies.

The implementation is pure Python so policy code remains testable on the API
machine.  Environment transitions are never fabricated: callers must inject a
callback backed by OASIS or another explicitly labelled environment.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import json
import math
from pathlib import Path
import random
from statistics import mean
from typing import Any, Callable, Mapping, Sequence

from .interface import (
    EnvironmentTransition,
    InterventionAction,
    InterventionEnvironment,
    InterventionReward,
    InterventionState,
)


STATE_FEATURES = (
    "bias",
    "misinformation_coverage",
    "correction_reach",
    "polarization",
    "fragmentation",
    "key_node_activity",
    "legitimate_information_reach",
    "false_positive_risk",
    "overblocking_risk",
    "risk_mean",
    "uncertainty_mean",
    "remaining_budget",
    "timestep",
    "previous_interventions",
)


DEFAULT_ACTION_CATALOG = (
    {"actor": "official_responder", "action_type": "official_response", "strength": 0.55, "cost": 0.20},
    {"actor": "fact_checker", "action_type": "community_note", "strength": 0.45, "cost": 0.12},
    {"actor": "platform", "action_type": "friction_prompt", "strength": 0.35, "cost": 0.08},
    {"actor": "fact_checker", "action_type": "source_verification", "strength": 0.50, "cost": 0.14},
    {"actor": "platform", "action_type": "content_labeling", "strength": 0.45, "cost": 0.10},
    {"actor": "platform", "action_type": "downranking", "strength": 0.60, "cost": 0.28},
)


def encode_state(state: InterventionState) -> list[float]:
    metrics = state.propagation_metrics
    numeric_risk = [float(value) for value in state.risk_state.values() if isinstance(value, (int, float))]
    numeric_uncertainty = [
        float(value) for value in state.uncertainty_state.values() if isinstance(value, (int, float))
    ]
    return [
        1.0,
        _number(metrics, "misinformation_coverage"),
        _number(metrics, "correction_reach"),
        _number(metrics, "polarization"),
        _number(metrics, "fragmentation"),
        _number(metrics, "key_node_activity"),
        _number(metrics, "legitimate_information_reach"),
        _number(metrics, "false_positive_risk"),
        _number(metrics, "overblocking_risk"),
        sum(numeric_risk) / max(1, len(numeric_risk)),
        sum(numeric_uncertainty) / max(1, len(numeric_uncertainty)),
        max(0.0, min(1.0, float(state.remaining_budget))),
        min(1.0, max(0.0, float(state.current_timestep) / 20.0)),
        min(1.0, len(state.previous_interventions) / 10.0),
    ]


class CallbackInterventionEnvironmentBackend:
    """Stateful adapter around a real transition callback.

    The callback receives ``case, state, action`` and must return either an
    ``EnvironmentTransition`` or a mapping containing ``state`` and ``done``.
    Set ``required_metric_source='oasis'`` for formal PPO runs.
    """

    def __init__(
        self,
        transition_callback: Callable[[Mapping[str, Any], InterventionState, InterventionAction], Any],
        *,
        state_factory: Callable[[Mapping[str, Any]], InterventionState],
        required_metric_source: str | None = None,
    ):
        self.transition_callback = transition_callback
        self.state_factory = state_factory
        self.required_metric_source = required_metric_source
        self._case: Mapping[str, Any] | None = None
        self._state: InterventionState | None = None

    def reset(self, case: Mapping[str, Any]) -> InterventionState:
        self._case = dict(case)
        self._state = self.state_factory(case)
        self._validate_source(self._state)
        return self._state

    def observe(self) -> InterventionState:
        if self._state is None:
            raise RuntimeError("environment must be reset before observe")
        return self._state

    def step(self, action: InterventionAction) -> EnvironmentTransition:
        if self._case is None or self._state is None:
            raise RuntimeError("environment must be reset before step")
        raw = self.transition_callback(self._case, self._state, action)
        if isinstance(raw, EnvironmentTransition):
            transition = raw
        elif isinstance(raw, Mapping):
            state = raw.get("state")
            if not isinstance(state, InterventionState):
                raise TypeError("transition callback mapping must contain InterventionState")
            transition = EnvironmentTransition(
                state=state, done=bool(raw.get("done")), info=dict(raw.get("info") or {})
            )
        else:
            raise TypeError("transition callback returned an unsupported value")
        self._validate_source(transition.state)
        self._state = transition.state
        return transition

    def _validate_source(self, state: InterventionState) -> None:
        if self.required_metric_source is None:
            return
        observed = str(state.provenance.get("metric_source") or "")
        accepted = {self.required_metric_source}
        if self.required_metric_source == "oasis":
            accepted.add("oasis_runtime")
        if observed not in accepted:
            raise ValueError(
                f"environment metric_source={observed!r}; required {self.required_metric_source!r}"
            )


class DiscretePPOBackend:
    """Linear softmax actor + value baseline trained with clipped PPO."""

    def __init__(
        self,
        *,
        cases: Sequence[Mapping[str, Any]] | None = None,
        action_catalog: Sequence[Mapping[str, Any]] | None = None,
        seed: int = 42,
        learning_rate: float = 0.03,
        value_learning_rate: float = 0.05,
        gamma: float = 0.97,
        clip_ratio: float = 0.2,
        update_epochs: int = 4,
        rollout_size: int = 32,
        max_episode_steps: int = 8,
    ):
        self.cases = [dict(item) for item in (cases or [])]
        catalog = action_catalog or DEFAULT_ACTION_CATALOG
        self.actions = [InterventionAction(
            actor=str(item["actor"]),
            action_type=str(item["action_type"]),
            target_nodes=list(item.get("target_nodes") or []),
            target_content=list(item.get("target_content") or []),
            target_communities=list(item.get("target_communities") or []),
            timing=dict(item.get("timing") or {}),
            strength=float(item.get("strength", 0.5)),
            cost=float(item.get("cost", 0.0)),
        ) for item in catalog]
        if not self.actions:
            raise ValueError("PPO action catalog cannot be empty")
        for action in self.actions:
            action.validate()
        self.seed = int(seed)
        self.learning_rate = float(learning_rate)
        self.value_learning_rate = float(value_learning_rate)
        self.gamma = float(gamma)
        self.clip_ratio = float(clip_ratio)
        self.update_epochs = int(update_epochs)
        self.rollout_size = int(rollout_size)
        self.max_episode_steps = int(max_episode_steps)
        randomizer = random.Random(self.seed)
        self.policy_weights = [
            [randomizer.uniform(-0.01, 0.01) for _ in STATE_FEATURES] for _ in self.actions
        ]
        self.value_weights = [0.0 for _ in STATE_FEATURES]
        self.training_steps = 0

    def predict(self, state: InterventionState) -> InterventionAction:
        probabilities = self._probabilities(encode_state(state))
        index = max(range(len(probabilities)), key=lambda item: probabilities[item])
        return self._materialize(self.actions[index], state)

    def train(
        self,
        *,
        environment: InterventionEnvironment,
        reward: InterventionReward,
        steps: int,
    ) -> Mapping[str, Any]:
        if not self.cases:
            raise ValueError("PPO backend requires at least one environment case")
        randomizer = random.Random(self.seed + self.training_steps)
        transitions: list[dict[str, Any]] = []
        rewards_seen: list[float] = []
        source_counts: Counter[str] = Counter()
        case_index = 0
        state = environment.reset(self.cases[case_index % len(self.cases)])
        episode_step = 0
        for _ in range(int(steps)):
            features = encode_state(state)
            probabilities = self._probabilities(features)
            action_index = _sample(probabilities, randomizer)
            action = self._materialize(self.actions[action_index], state)
            transition = environment.step(action)
            reward_result = reward.compute(state, action, transition.state)
            observed_reward = float(reward_result["reward"])
            done = bool(transition.done or episode_step + 1 >= self.max_episode_steps)
            transitions.append({
                "features": features,
                "action": action_index,
                "old_probability": max(1e-12, probabilities[action_index]),
                "reward": observed_reward,
                "done": done,
                "value": self._value(features),
            })
            rewards_seen.append(observed_reward)
            source_counts[str(transition.state.provenance.get("metric_source") or "unknown")] += 1
            state = transition.state
            episode_step += 1
            if len(transitions) >= self.rollout_size or done:
                self._update(transitions)
                transitions.clear()
            if done:
                case_index += 1
                state = environment.reset(self.cases[case_index % len(self.cases)])
                episode_step = 0
        if transitions:
            self._update(transitions)
        self.training_steps += int(steps)
        return {
            "status": "trained",
            "training_started": True,
            "environment_steps": int(steps),
            "total_training_steps": self.training_steps,
            "mean_reward": round(mean(rewards_seen), 8),
            "min_reward": round(min(rewards_seen), 8),
            "max_reward": round(max(rewards_seen), 8),
            "metric_sources": dict(source_counts),
            "policy_changed": any(abs(value) > 0.011 for row in self.policy_weights for value in row),
            "synthetic_zero_reward": False,
            "algorithm": "clipped_discrete_ppo",
        }

    def evaluate(
        self,
        *,
        environment: InterventionEnvironment,
        cases: Sequence[Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        totals = []
        sources: Counter[str] = Counter()
        reward = InterventionReward()
        for case in cases:
            state = environment.reset(case)
            total = 0.0
            for _ in range(self.max_episode_steps):
                action = self.predict(state)
                transition = environment.step(action)
                total += float(reward.compute(state, action, transition.state)["reward"])
                sources[str(transition.state.provenance.get("metric_source") or "unknown")] += 1
                state = transition.state
                if transition.done:
                    break
            totals.append(total)
        return {
            "cases": len(totals),
            "mean_episode_reward": round(mean(totals), 8) if totals else 0.0,
            "metric_sources": dict(sources),
        }

    def save(self, path: str) -> Mapping[str, Any]:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "discrete_ppo_policy.v1",
            "state_features": list(STATE_FEATURES),
            "actions": [asdict(action) for action in self.actions],
            "policy_weights": self.policy_weights,
            "value_weights": self.value_weights,
            "training_steps": self.training_steps,
            "hyperparameters": {
                "seed": self.seed,
                "learning_rate": self.learning_rate,
                "value_learning_rate": self.value_learning_rate,
                "gamma": self.gamma,
                "clip_ratio": self.clip_ratio,
                "update_epochs": self.update_epochs,
                "rollout_size": self.rollout_size,
                "max_episode_steps": self.max_episode_steps,
            },
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"status": "saved", "path": str(target.resolve()), "training_steps": self.training_steps}

    def load(self, path: str) -> Mapping[str, Any]:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if payload.get("schema_version") != "discrete_ppo_policy.v1":
            raise ValueError("PPO policy schema mismatch")
        if payload.get("state_features") != list(STATE_FEATURES):
            raise ValueError("PPO state feature contract mismatch")
        loaded = DiscretePPOBackend(
            cases=self.cases,
            action_catalog=payload["actions"],
            **payload.get("hyperparameters", {}),
        )
        loaded.policy_weights = [[float(value) for value in row] for row in payload["policy_weights"]]
        loaded.value_weights = [float(value) for value in payload["value_weights"]]
        loaded.training_steps = int(payload.get("training_steps", 0))
        self.__dict__.update(loaded.__dict__)
        return {"status": "loaded", "path": str(Path(path).resolve()), "training_steps": self.training_steps}

    def resume(self, path: str) -> Mapping[str, Any]:
        return self.load(path)

    def _probabilities(self, features: Sequence[float]) -> list[float]:
        logits = [sum(weight * value for weight, value in zip(row, features)) for row in self.policy_weights]
        maximum = max(logits)
        exponentials = [math.exp(max(-40.0, min(40.0, value - maximum))) for value in logits]
        total = sum(exponentials)
        return [value / total for value in exponentials]

    def _value(self, features: Sequence[float]) -> float:
        return sum(weight * value for weight, value in zip(self.value_weights, features))

    def _update(self, transitions: Sequence[Mapping[str, Any]]) -> None:
        returns = [0.0 for _ in transitions]
        running = 0.0
        for index in range(len(transitions) - 1, -1, -1):
            if transitions[index]["done"]:
                running = 0.0
            running = float(transitions[index]["reward"]) + self.gamma * running
            returns[index] = running
        advantages = [returns[index] - float(item["value"]) for index, item in enumerate(transitions)]
        advantage_mean = sum(advantages) / max(1, len(advantages))
        variance = sum((value - advantage_mean) ** 2 for value in advantages) / max(1, len(advantages))
        scale = math.sqrt(variance + 1e-8)
        advantages = [(value - advantage_mean) / scale for value in advantages]
        for _ in range(self.update_epochs):
            for item, target_return, advantage in zip(transitions, returns, advantages):
                features = item["features"]
                probabilities = self._probabilities(features)
                action_index = int(item["action"])
                ratio = probabilities[action_index] / float(item["old_probability"])
                clipped = max(1.0 - self.clip_ratio, min(1.0 + self.clip_ratio, ratio))
                active = not ((advantage >= 0 and ratio > clipped) or (advantage < 0 and ratio < clipped))
                if active:
                    coefficient = self.learning_rate * advantage * ratio
                    for action in range(len(self.actions)):
                        indicator = 1.0 if action == action_index else 0.0
                        for feature_index, value in enumerate(features):
                            self.policy_weights[action][feature_index] += (
                                coefficient * (indicator - probabilities[action]) * float(value)
                            )
                value_error = target_return - self._value(features)
                for feature_index, value in enumerate(features):
                    self.value_weights[feature_index] += self.value_learning_rate * value_error * float(value)

    @staticmethod
    def _materialize(action: InterventionAction, state: InterventionState) -> InterventionAction:
        targets = action.target_nodes or state.bridge_nodes[:1] or state.key_nodes[:1]
        return InterventionAction(
            actor=action.actor,
            action_type=action.action_type,
            target_nodes=list(targets),
            target_content=list(action.target_content),
            target_communities=list(action.target_communities),
            timing={"step": state.current_timestep, **action.timing},
            strength=min(float(action.strength), max(0.0, float(state.remaining_budget))),
            cost=min(float(action.cost), max(0.0, float(state.remaining_budget))),
        )


def _number(metrics: Mapping[str, Any], key: str) -> float:
    value = metrics.get(key, 0.0)
    return float(value) if isinstance(value, (int, float)) else 0.0


def _sample(probabilities: Sequence[float], randomizer: random.Random) -> int:
    threshold = randomizer.random()
    cumulative = 0.0
    for index, probability in enumerate(probabilities):
        cumulative += probability
        if threshold <= cumulative:
            return index
    return len(probabilities) - 1

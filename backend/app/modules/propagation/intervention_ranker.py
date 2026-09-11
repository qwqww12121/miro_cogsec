"""Small, inspectable rankers for single-stage intervention selection.

The proxy search keeps its historical fixed score as the default baseline.
This module adds opt-in global and scenario-contextual pairwise linear ranking
without introducing a training framework or pretending that proxy metrics are
OASIS observations.
"""

from __future__ import annotations

import math
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import warnings
import random
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Sequence


METRIC_FEATURES = (
    "coverage_reduction",
    "misinformation_reduction",
    "polarization_reduction",
    "community_fragmentation_reduction",
    "key_node_activity_reduction",
    "correction_reach_gain",
    "latency_cost",
    "intervention_cost",
    # Suppression-safe objective features.  These are kept separate from
    # misinformation reduction so a model cannot learn "suppress more" as a
    # universal shortcut.
    "overblocking_risk",
    "false_positive_risk",
    "legitimate_information_loss",
    "verified_information_reach_loss",
    "correction_suppression_risk",
    "proportionality",
    "specificity",
    "reversibility",
    "misinformation_coverage",
    "legitimate_coverage",
    "verified_correction_coverage",
)

INTERVENTION_TYPES = (
    "official_response",
    "community_note",
    "downranking",
    "friction_prompt",
    "source_verification",
    "content_labeling",
    "node_targeting",
    "debunking",
)

FEATURE_NAMES = METRIC_FEATURES + tuple(f"intervention_type:{item}" for item in INTERVENTION_TYPES)

# These are a transparent starting point for an opt-in learned mode. They are
# not used by the default fixed-weight baseline and can be replaced by fit().
DEFAULT_GLOBAL_WEIGHTS = {
    "coverage_reduction": 0.22,
    "misinformation_reduction": 0.24,
    "polarization_reduction": 0.16,
    "community_fragmentation_reduction": 0.12,
    "key_node_activity_reduction": 0.14,
    "correction_reach_gain": 0.18,
    "latency_cost": -0.08,
    "intervention_cost": -0.14,
    "overblocking_risk": -0.22,
    "false_positive_risk": -0.18,
    "legitimate_information_loss": -0.28,
    "verified_information_reach_loss": -0.30,
    "correction_suppression_risk": -0.26,
    "proportionality": 0.12,
    "specificity": 0.12,
    "reversibility": 0.08,
    "misinformation_coverage": 0.18,
    "legitimate_coverage": 0.12,
    "verified_correction_coverage": 0.16,
}

CONTEXT_ADJUSTMENTS = {
    "public_opinion": {
        "misinformation_reduction": 0.08,
        "polarization_reduction": 0.06,
        "community_fragmentation_reduction": 0.06,
        "correction_reach_gain": 0.08,
    },
    "event_propagation": {
        "correction_reach_gain": 0.10,
        "misinformation_reduction": 0.06,
        "latency_cost": -0.04,
    },
    "fraud_im": {
        "latency_cost": -0.02,
        "intervention_cost": -0.02,
    },
}


def feature_vector(candidate: Mapping[str, Any], metrics: Mapping[str, Any]) -> Dict[str, float]:
    """Build a stable, JSON-friendly feature vector for one candidate."""
    vector = {name: 0.0 for name in FEATURE_NAMES}
    for name in METRIC_FEATURES:
        value = metrics.get(name, 0.0)
        vector[name] = float(value) if isinstance(value, (int, float)) else 0.0
    intervention_type = str(candidate.get("intervention_type") or "")
    key = f"intervention_type:{intervention_type}"
    if key in vector:
        vector[key] = 1.0
    return vector


@dataclass
class PairwiseLinearRanker:
    """Bradley-Terry/RankNet-style linear pairwise ranker."""

    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_GLOBAL_WEIGHTS))

    def score(self, features: Mapping[str, Any]) -> float:
        return sum(
            float(self.weights.get(name, 0.0)) * float(value or 0.0)
            for name, value in features.items()
        )

    def fit(
        self,
        preferences: Iterable[Mapping[str, Any]],
        *,
        epochs: int = 80,
        learning_rate: float = 0.08,
        l2: float = 0.01,
    ) -> Dict[str, Any]:
        """Fit from pairwise records; ``preferred`` is ``a`` or ``b``."""
        records = list(preferences)
        history: List[float] = []
        for _ in range(max(1, int(epochs))):
            loss = 0.0
            for record in records:
                features_a = _record_features(record, "a")
                features_b = _record_features(record, "b")
                diff = {name: features_a.get(name, 0.0) - features_b.get(name, 0.0) for name in FEATURE_NAMES}
                preferred = str(record.get("preferred") or "a").lower()
                target = 1.0 if preferred == "a" else 0.0
                probability = _sigmoid(self.score(diff))
                error = target - probability
                for name, value in diff.items():
                    self.weights[name] = self.weights.get(name, 0.0) + learning_rate * (
                        error * value - l2 * self.weights.get(name, 0.0)
                    )
                loss += -(target * math.log(max(probability, 1e-8)) + (1 - target) * math.log(max(1 - probability, 1e-8)))
            history.append(round(loss / max(1, len(records)), 6))
        return {"records": len(records), "epochs": len(history), "loss_history": history, "weights": self.to_dict()}

    def validate(self, preferences: Iterable[Mapping[str, Any]]) -> Dict[str, Any]:
        records = list(preferences)
        correct = 0
        for record in records:
            a = self.score(_record_features(record, "a"))
            b = self.score(_record_features(record, "b"))
            preferred = str(record.get("preferred") or "a").lower()
            if (preferred == "a" and a >= b) or (preferred == "b" and b >= a):
                correct += 1
        return {
            "samples": len(records),
            "correct": correct,
            "accuracy": round(correct / max(1, len(records)), 6),
        }

    def fit_with_validation(
        self,
        train_preferences: Iterable[Mapping[str, Any]],
        validation_preferences: Iterable[Mapping[str, Any]],
        **fit_kwargs: Any,
    ) -> Dict[str, Any]:
        train_records = list(train_preferences)
        validation_records = list(validation_preferences)
        report = self.fit(train_records, **fit_kwargs)
        report["validation"] = self.validate(validation_records)
        return report

    def save_artifact(
        self,
        path: str | Path,
        *,
        training_samples: int,
        validation_accuracy: float,
        dataset_hash: str,
        config: Mapping[str, Any] | None = None,
    ) -> Dict[str, Any]:
        artifact = {
            "model_type": "pairwise_linear_ranker",
            "version": "1.0",
            "trained_at": datetime.now(timezone.utc).isoformat(),
            "feature_names": list(FEATURE_NAMES),
            "weights": self.to_dict(),
            "training_samples": int(training_samples),
            "validation_accuracy": float(validation_accuracy),
            "dataset_hash": str(dataset_hash),
            "config": dict(config or {}),
        }
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
        return artifact

    @classmethod
    def load_artifact(cls, path: str | Path) -> tuple["PairwiseLinearRanker", Dict[str, Any]]:
        target = Path(path)
        data = json.loads(target.read_text(encoding="utf-8"))
        if data.get("model_type") != "pairwise_linear_ranker":
            raise ValueError("ranker artifact model_type mismatch")
        if data.get("version") != "1.0":
            raise ValueError("ranker artifact version mismatch")
        if data.get("feature_names") != list(FEATURE_NAMES):
            raise ValueError("ranker artifact feature_names mismatch")
        if not isinstance(data.get("weights"), dict):
            raise ValueError("ranker artifact weights missing")
        return cls.from_dict(data["weights"]), data

    def to_dict(self) -> Dict[str, float]:
        return {name: round(float(self.weights.get(name, 0.0)), 8) for name in FEATURE_NAMES if self.weights.get(name, 0.0) != 0}

    @classmethod
    def from_dict(cls, weights: Mapping[str, Any]) -> "PairwiseLinearRanker":
        merged = dict(DEFAULT_GLOBAL_WEIGHTS)
        for name, value in weights.items():
            if name in FEATURE_NAMES and isinstance(value, (int, float)):
                merged[name] = float(value)
        return cls(weights=merged)


def rank_branches(
    branches: Sequence[Mapping[str, Any]],
    *,
    scenario_type: str,
    mode: str = "fixed_weight",
    weights_path: str | None = None,
    strict: bool = False,
) -> List[Dict[str, Any]]:
    """Return branches ordered by the selected ranking mode."""
    normalized_mode = normalize_ranker_mode(mode)
    ranker, fallback_used, fallback_reason = _ranker_for_mode(
        normalized_mode, scenario_type, weights_path=weights_path, strict=strict
    )
    ranked: List[Dict[str, Any]] = []
    for branch in branches:
        candidate = branch.get("intervention_candidate") if isinstance(branch, Mapping) else {}
        candidate = candidate if isinstance(candidate, Mapping) else {}
        metrics = branch.get("final_metrics") if isinstance(branch, Mapping) else {}
        metrics = metrics if isinstance(metrics, Mapping) else {}
        if normalized_mode == "fixed_weight":
            ranking_score = metrics.get("total_score", 0.0)
        else:
            ranking_score = ranker.score(feature_vector(candidate, metrics))
        item = dict(branch)
        item["ranking_score"] = round(float(ranking_score or 0.0), 6)
        item["ranking_mode"] = normalized_mode
        item["ranker_fallback_used"] = fallback_used
        item["ranker_fallback_reason"] = fallback_reason
        ranked.append(item)
    return sorted(ranked, key=lambda item: (item.get("ranking_score", 0.0), str(item.get("branch_id", ""))), reverse=True)


def make_preference_record(
    *,
    case_id: str,
    scenario: str,
    candidate_a: Mapping[str, Any],
    candidate_b: Mapping[str, Any],
    preferred: str,
    judge_reason: str = "",
    human_verified: bool = False,
) -> Dict[str, Any]:
    """Create the seed/hard-negative schema without claiming gold labels."""
    return {
        "case_id": case_id,
        "scenario": scenario,
        "state_features": {},
        "candidate_a": dict(candidate_a.get("intervention_candidate", candidate_a)),
        "candidate_b": dict(candidate_b.get("intervention_candidate", candidate_b)),
        "metrics_a": dict(candidate_a.get("final_metrics", {})),
        "metrics_b": dict(candidate_b.get("final_metrics", {})),
        "preferred": preferred,
        "judge_reason": judge_reason,
        "human_verified": bool(human_verified),
    }


def normalize_ranker_mode(mode: Any) -> str:
    value = str(mode or "fixed_weight").strip().lower()
    return value if value in {"fixed_weight", "learned_global_weight", "learned_contextual_weight"} else "fixed_weight"


def _ranker_for_mode(
    mode: str,
    scenario_type: str,
    *,
    weights_path: str | None = None,
    strict: bool = False,
) -> tuple[PairwiseLinearRanker, bool, str | None]:
    if mode == "fixed_weight":
        return PairwiseLinearRanker(), False, None
    if not weights_path:
        reason = "learned_ranker_weights_path_missing"
        if strict:
            raise FileNotFoundError(reason)
        warnings.warn(reason, RuntimeWarning, stacklevel=2)
        return PairwiseLinearRanker(), True, reason
    try:
        ranker, artifact = PairwiseLinearRanker.load_artifact(weights_path)
        if mode == "learned_contextual_weight":
            # Contextual learned mode is an artifact-defined interface.  A
            # context adjustment may be present in the artifact, but the
            # historical handcrafted defaults are never silently substituted.
            context_weights = artifact.get("config", {}).get("context_weights", {})
            for name, adjustment in context_weights.get(scenario_type, {}).items() if isinstance(context_weights, dict) else []:
                ranker.weights[name] = ranker.weights.get(name, 0.0) + float(adjustment)
        return ranker, False, None
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        reason = f"learned_ranker_artifact_invalid:{exc.__class__.__name__}"
        if strict:
            raise ValueError(reason) from exc
        warnings.warn(reason, RuntimeWarning, stacklevel=2)
        return PairwiseLinearRanker(), True, reason


def dataset_hash(records: Iterable[Mapping[str, Any]]) -> str:
    payload = json.dumps(list(records), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def split_preferences_by_case(
    preferences: Iterable[Mapping[str, Any]],
    *,
    validation_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Group-aware split that keeps every case entirely on one side."""
    if not 0.0 < float(validation_ratio) < 1.0:
        raise ValueError("validation_ratio must be between 0 and 1")
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for index, raw in enumerate(preferences):
        record = dict(raw)
        case_id = str(record.get("case_id") or f"row-{index + 1}")
        groups.setdefault(case_id, []).append(record)
    if len(groups) < 2:
        raise ValueError("at least two distinct case_id groups are required")
    case_ids = sorted(groups)
    random.Random(seed).shuffle(case_ids)
    validation_cases = max(1, min(len(case_ids) - 1, round(len(case_ids) * validation_ratio)))
    validation_ids = set(case_ids[:validation_cases])
    train = [record for case_id in case_ids if case_id not in validation_ids for record in groups[case_id]]
    validation = [record for case_id in case_ids if case_id in validation_ids for record in groups[case_id]]
    return train, validation


def train_ranker_with_holdout(
    preferences: Iterable[Mapping[str, Any]],
    *,
    artifact_path: str | Path | None = None,
    validation_ratio: float = 0.2,
    seed: int = 42,
    epochs: int = 80,
    learning_rate: float = 0.08,
    l2: float = 0.01,
    minimum_records: int = 20,
    minimum_validation_records: int = 4,
    minimum_accuracy_gain: float = 0.02,
) -> Dict[str, Any]:
    """Train, compare with fixed weights, and publish only when eligible."""
    records = [dict(item) for item in preferences]
    for record in records:
        preferred = str(record.get("preferred") or "").lower()
        if preferred not in {"a", "b"}:
            raise ValueError("each preference must set preferred to 'a' or 'b'")
        _record_features(record, "a")
        _record_features(record, "b")
    train, validation = split_preferences_by_case(
        records, validation_ratio=validation_ratio, seed=seed
    )
    fixed = PairwiseLinearRanker()
    baseline_metrics = fixed.validate(validation)
    learned = PairwiseLinearRanker()
    training = learned.fit(
        train, epochs=epochs, learning_rate=learning_rate, l2=l2
    )
    learned_metrics = learned.validate(validation)
    accuracy_gain = learned_metrics["accuracy"] - baseline_metrics["accuracy"]

    context_weights: Dict[str, Dict[str, float]] = {}
    for scenario in sorted({str(item.get("scenario") or "") for item in train} - {""}):
        subset = [item for item in train if str(item.get("scenario") or "") == scenario]
        if len(subset) < 2:
            continue
        contextual = PairwiseLinearRanker.from_dict(learned.to_dict())
        contextual.fit(
            subset,
            epochs=max(10, epochs // 3),
            learning_rate=learning_rate * 0.5,
            l2=l2,
        )
        context_weights[scenario] = {
            name: round(contextual.weights.get(name, 0.0) - learned.weights.get(name, 0.0), 8)
            for name in FEATURE_NAMES
            if abs(contextual.weights.get(name, 0.0) - learned.weights.get(name, 0.0)) > 1e-10
        }

    checks = {
        "minimum_records": len(records) >= minimum_records,
        "minimum_validation_records": len(validation) >= minimum_validation_records,
        "beats_fixed_weight": accuracy_gain >= minimum_accuracy_gain,
    }
    promoted = all(checks.values())
    artifact = None
    if promoted and artifact_path:
        artifact = learned.save_artifact(
            artifact_path,
            training_samples=len(train),
            validation_accuracy=learned_metrics["accuracy"],
            dataset_hash=dataset_hash(records),
            config={
                "seed": seed,
                "validation_ratio": validation_ratio,
                "epochs": epochs,
                "learning_rate": learning_rate,
                "l2": l2,
                "baseline_validation_accuracy": baseline_metrics["accuracy"],
                "accuracy_gain": round(accuracy_gain, 6),
                "context_weights": context_weights,
            },
        )
    return {
        "schema_version": "intervention_ranker_training.v1",
        "records": len(records),
        "train_records": len(train),
        "validation_records": len(validation),
        "dataset_hash": dataset_hash(records),
        "baseline": baseline_metrics,
        "learned": learned_metrics,
        "accuracy_gain": round(accuracy_gain, 6),
        "training": training,
        "context_scenarios": sorted(context_weights),
        "promotion_checks": checks,
        "promoted": promoted,
        "artifact_path": str(artifact_path) if artifact is not None else None,
        "artifact": artifact,
    }


def _record_features(record: Mapping[str, Any], side: str) -> Dict[str, float]:
    candidate = record.get(f"candidate_{side}")
    metrics = record.get(f"metrics_{side}")
    candidate = candidate if isinstance(candidate, Mapping) else {}
    metrics = metrics if isinstance(metrics, Mapping) else {}
    return feature_vector(candidate, metrics)


def _sigmoid(value: float) -> float:
    value = max(-40.0, min(40.0, float(value)))
    return 1.0 / (1.0 + math.exp(-value))

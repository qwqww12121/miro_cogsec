"""Canonical propagation result adapter.

Both the lightweight simulator and OASIS expose the same broad fork shape,
but their metrics live at different nested paths.  This module keeps the
service/core-analysis contract small and makes missing observations explicit.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class CanonicalPropagationResult:
    dominant_emotion: Optional[str] = None
    amplification_level: Optional[str] = None
    origin_node: Optional[Dict[str, Any]] = None
    amplifier_nodes: List[Dict[str, Any]] = field(default_factory=list)
    distortion_points: List[Dict[str, Any]] = field(default_factory=list)
    critical_nodes: List[Dict[str, Any]] = field(default_factory=list)
    propagation_path: List[Dict[str, Any]] = field(default_factory=list)
    narrative_threads: List[Dict[str, Any]] = field(default_factory=list)
    narrative_analysis: Dict[str, Any] = field(default_factory=dict)
    claim_analysis: Dict[str, Any] = field(default_factory=dict)
    branch_a_coverage: Optional[float] = None
    branch_b_coverage: Optional[float] = None
    coverage_delta: Optional[float] = None
    recommended_action: Optional[str] = None
    metric_source: str = "unknown"
    runtime_engine: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def adapt_propagation_result(raw_result: Any) -> CanonicalPropagationResult:
    """Normalize a local or OASIS fork result without inventing fields."""
    raw = _as_dict(raw_result)
    branch_a = _as_dict(raw.get("branch_a"))
    branch_b = _as_dict(raw.get("branch_b"))
    comparison = _as_dict(raw.get("comparison"))
    metrics_a = _as_dict(branch_a.get("final_metrics"))
    metrics_b = _as_dict(branch_b.get("final_metrics"))
    provenance = _as_dict(raw.get("provenance"))
    narrative_analysis = _as_dict(branch_a.get("narrative_analysis"))
    claim_analysis = _as_dict(branch_a.get("claim_analysis"))

    return CanonicalPropagationResult(
        dominant_emotion=_dominant_emotion(branch_a, branch_b),
        amplification_level=_first_value(
            metrics_a.get("amplification_level"),
            metrics_b.get("amplification_level"),
            comparison.get("amplification_level"),
        ),
        origin_node=_origin_node(raw, branch_a),
        amplifier_nodes=_first_list(
            comparison.get("amplifier_nodes"),
            branch_a.get("key_nodes"),
            metrics_a.get("key_nodes"),
        ),
        distortion_points=_first_list(
            comparison.get("distortion_points"),
            metrics_a.get("distortion_points"),
            metrics_b.get("distortion_points"),
        ) or _claim_distortion_points(claim_analysis),
        critical_nodes=_first_list(
            comparison.get("critical_nodes"),
            branch_a.get("key_nodes"),
        ),
        propagation_path=_first_list(branch_a.get("actions")),
        narrative_threads=_first_list(narrative_analysis.get("narratives")),
        narrative_analysis=narrative_analysis,
        claim_analysis=claim_analysis,
        branch_a_coverage=_coverage(branch_a, metrics_a),
        branch_b_coverage=_coverage(branch_b, metrics_b),
        coverage_delta=_number(comparison.get("coverage_delta")),
        recommended_action=_first_value(
            comparison.get("recommended_action"),
            raw.get("recommended_action"),
        ),
        metric_source=str(provenance.get("metric_source") or raw.get("metric_source") or "unknown"),
        runtime_engine=str(provenance.get("runtime_engine") or raw.get("runtime_engine") or "unknown"),
    )


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_dict"):
        converted = value.to_dict()
        return converted if isinstance(converted, dict) else {}
    return {}


def _first_value(*values: Any) -> Optional[str]:
    for value in values:
        if value is not None and str(value).strip():
            return str(value)
    return None


def _first_list(*values: Any) -> List[Dict[str, Any]]:
    for value in values:
        if isinstance(value, list):
            items = [item for item in value if isinstance(item, dict)]
            if items:
                return items
    return []


def _claim_distortion_points(claim_analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    labels = {
        "certainty_inflation": "确定性被夸大",
        "content_mutation": "内容发生变形",
        "context_loss": "限定条件或上下文丢失",
        "source_loss": "来源归属丢失",
    }
    output: List[Dict[str, Any]] = []
    by_claim = _as_dict(claim_analysis.get("distortion_by_claim"))
    for claim_id, raw in by_claim.items():
        item = _as_dict(raw)
        flags = [str(flag) for flag in item.get("distortion_flags", []) if str(flag)]
        if not flags:
            continue
        output.append({
            "claim_id": str(claim_id),
            "type": "claim_fidelity_loss",
            "description": "、".join(labels.get(flag, flag) for flag in flags),
            "flags": flags,
            "fidelity": item.get("fidelity"),
            "metric_source": "lightweight_claim_model",
        })
    return output[:5]


def _number(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _coverage(trace: Dict[str, Any], metrics: Dict[str, Any]) -> Optional[float]:
    curve = trace.get("coverage_curve")
    if isinstance(curve, list) and curve:
        last = curve[-1]
        if isinstance(last, dict) and last.get("coverage") is not None:
            return _number(last.get("coverage"))
    return _number(metrics.get("cumulative_coverage"))


def _dominant_emotion(branch_a: Dict[str, Any], branch_b: Dict[str, Any]) -> Optional[str]:
    curves = [
        item
        for branch in (branch_a, branch_b)
        for item in (branch.get("emotion_curve") or [])
        if isinstance(item, dict)
    ]
    if not curves:
        return None
    final = curves[-1]
    emotion_keys = [key for key in ("panic", "anger", "confusion", "trust") if key in final]
    if not emotion_keys:
        return None
    return max(emotion_keys, key=lambda key: float(final.get(key) or 0.0))


def _origin_node(raw: Dict[str, Any], branch_a: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    explicit = raw.get("origin_node")
    if isinstance(explicit, dict):
        return explicit
    actions = branch_a.get("actions") or []
    if actions and isinstance(actions[0], dict):
        first = actions[0]
        source = first.get("source_agent_id")
        if source:
            return {"id": source, "type": "source_agent"}
    return None

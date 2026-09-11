"""Dependency-free data contracts shared by optional training backends."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping


class TrainingBackendNotConfigured(RuntimeError):
    """Raised when training was explicitly requested without a real backend."""


def _non_empty_text(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} must not be empty")
    return text


@dataclass(frozen=True)
class StructuredAgentSFTRecord:
    task: str
    input: Dict[str, Any]
    target: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "StructuredAgentSFTRecord":
        task = _non_empty_text(value.get("task"), "task")
        input_payload = value.get("input")
        target = value.get("target")
        if not isinstance(input_payload, Mapping) or not input_payload:
            raise ValueError("input must be a non-empty object")
        if not isinstance(target, Mapping) or not target:
            raise ValueError("target must be a non-empty object")
        return cls(task, dict(input_payload), dict(target), dict(value.get("metadata") or {}))


@dataclass(frozen=True)
class ReporterSFTRecord:
    raw_input: str
    report_state: Dict[str, Any]
    target_answer: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ReporterSFTRecord":
        raw_input = _non_empty_text(value.get("raw_input"), "raw_input")
        report_state = value.get("report_state")
        if not isinstance(report_state, Mapping) or not report_state:
            raise ValueError("report_state must be a non-empty object")
        target = _non_empty_text(value.get("target_answer"), "target_answer")
        return cls(raw_input, dict(report_state), target, dict(value.get("metadata") or {}))


@dataclass(frozen=True)
class DPOPreferenceRecord:
    raw_input: str
    report_state: Dict[str, Any]
    chosen: str
    rejected: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DPOPreferenceRecord":
        raw_input = _non_empty_text(value.get("raw_input"), "raw_input")
        report_state = value.get("report_state")
        if not isinstance(report_state, Mapping) or not report_state:
            raise ValueError("report_state must be a non-empty object")
        chosen = _non_empty_text(value.get("chosen"), "chosen")
        rejected = _non_empty_text(value.get("rejected"), "rejected")
        if chosen == rejected:
            raise ValueError("chosen and rejected must differ")
        return cls(raw_input, dict(report_state), chosen, rejected, dict(value.get("metadata") or {}))

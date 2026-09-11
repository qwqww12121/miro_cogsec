"""Report rendering schema — payload and rendered output dataclasses."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List


@dataclass
class RoleReportPayload:
    scenario_type: str
    user_role: str
    source_result: Dict[str, Any]
    risk_scores: Dict[str, float]
    key_findings: List[Dict[str, Any]]
    fork_comparison: Dict[str, Any]
    propagation: Dict[str, Any] | None = None
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RenderedRoleReport:
    role: str
    title: str
    markdown: str
    sections: List[Dict[str, Any]]
    structured: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

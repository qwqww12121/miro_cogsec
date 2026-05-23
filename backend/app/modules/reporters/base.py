"""Base protocol for role-specific report renderers."""

from __future__ import annotations

from typing import Protocol

from .schema import RoleReportPayload, RenderedRoleReport


class ReportRenderer(Protocol):
    role: str

    def render(self, payload: RoleReportPayload) -> RenderedRoleReport:
        ...

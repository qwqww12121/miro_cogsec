"""Reporters module — role-specific report rendering layer."""

from .schema import RoleReportPayload, RenderedRoleReport
from .base import ReportRenderer
from .registry import (
    SUPPORTED_REPORT_ROLES,
    normalize_user_role,
    get_renderer,
    list_report_roles,
)
from .orchestrator import build_role_payload, render_role_report

__all__ = [
    "build_role_payload",
    "get_renderer",
    "list_report_roles",
    "normalize_user_role",
    "render_role_report",
    "RenderedRoleReport",
    "ReportRenderer",
    "RoleReportPayload",
    "SUPPORTED_REPORT_ROLES",
]

"""Reporter registry — role normalisation and renderer lookup."""

from __future__ import annotations

from .individual import IndividualReportRenderer
from .official import OfficialReportRenderer
from .media import MediaReportRenderer
from .target_group import TargetGroupReportRenderer

SUPPORTED_REPORT_ROLES = {
    "individual": IndividualReportRenderer(),
    "official": OfficialReportRenderer(),
    "media": MediaReportRenderer(),
    "target_group": TargetGroupReportRenderer(),
}


def normalize_user_role(user_role: str | None) -> str:
    if not user_role:
        return "individual"
    user_role = str(user_role).strip()
    if user_role in SUPPORTED_REPORT_ROLES:
        return user_role
    return "individual"


def get_renderer(user_role: str | None):
    return SUPPORTED_REPORT_ROLES[normalize_user_role(user_role)]


def list_report_roles() -> list[str]:
    return list(SUPPORTED_REPORT_ROLES.keys())

"""Tone settings for user-facing CogSec responses."""

from __future__ import annotations

from typing import Dict, List


SUPPORTED_TONES = {"friendly", "serious", "expert", "judge_friendly"}

TONE_SECTIONS: Dict[str, List[str]] = {
    "friendly": ["结论", "为什么", "建议你这样做"],
    "serious": ["风险判断", "关键依据", "处置建议"],
    "expert": ["系统判断", "机制链路", "干预分支比较", "建议"],
    "judge_friendly": ["结论", "关键依据", "建议动作", "为什么这样做"],
}

TONE_EVIDENCE_LIMIT = {
    "friendly": 3,
    "serious": 4,
    "expert": 4,
    "judge_friendly": 3,
}


def normalize_tone(tone: str | None) -> str:
    """Return a supported tone value, defaulting to friendly."""
    value = (tone or "friendly").strip().lower()
    return value if value in SUPPORTED_TONES else "friendly"


def section_titles(tone: str | None) -> List[str]:
    """Return section titles for the selected tone."""
    return TONE_SECTIONS[normalize_tone(tone)]


def evidence_limit(tone: str | None) -> int:
    """Return the preferred number of evidence points for a tone."""
    return TONE_EVIDENCE_LIMIT[normalize_tone(tone)]

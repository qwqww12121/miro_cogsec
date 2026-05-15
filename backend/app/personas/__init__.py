"""CogSec persona 模板导出。"""

from .security_personas import (
    SECURITY_PERSONA_TEMPLATES,
    build_adversary_persona,
    build_official_channel_persona,
    build_victim_persona,
)

__all__ = [
    "SECURITY_PERSONA_TEMPLATES",
    "build_adversary_persona",
    "build_official_channel_persona",
    "build_victim_persona",
]

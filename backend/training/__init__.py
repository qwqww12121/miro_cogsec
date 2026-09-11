"""Optional training contracts for Miro-CogSec.

Importing this package never starts training and does not require TRL/PEFT.
Concrete trainer backends are injected by the environment that owns the
models and accelerators.
"""

from .contracts import (
    DPOPreferenceRecord,
    ReporterSFTRecord,
    StructuredAgentSFTRecord,
    TrainingBackendNotConfigured,
)

__all__ = [
    "DPOPreferenceRecord",
    "ReporterSFTRecord",
    "StructuredAgentSFTRecord",
    "TrainingBackendNotConfigured",
]

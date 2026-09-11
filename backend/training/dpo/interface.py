"""Reporter DPO integration boundary with explicit no-training default."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence

from ..contracts import DPOPreferenceRecord, TrainingBackendNotConfigured


@dataclass(frozen=True)
class DPOConfig:
    base_model: str
    output_dir: str
    beta: float = 0.1
    max_length: int = 2048
    use_lora: bool = True
    use_qlora: bool = False
    epochs: int = 1
    learning_rate: float = 5e-6
    gradient_accumulation_steps: int = 4
    seed: int = 42
    device: str = "auto"

    def validate(self) -> None:
        if not self.base_model or not self.output_dir:
            raise ValueError("base_model and output_dir are required")
        if self.beta <= 0:
            raise ValueError("beta must be positive")
        if self.max_length < 128:
            raise ValueError("max_length must be >= 128")
        if self.use_qlora and not self.use_lora:
            raise ValueError("QLoRA requires use_lora=true")
        if self.epochs < 1 or self.gradient_accumulation_steps < 1:
            raise ValueError("epochs and gradient_accumulation_steps must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")


class DPOTrainerBackend(Protocol):
    def train(self, *, records: Sequence[DPOPreferenceRecord], config: DPOConfig) -> Mapping[str, Any]: ...
    def evaluate(self, *, records: Sequence[DPOPreferenceRecord], config: DPOConfig) -> Mapping[str, Any]: ...
    def save(self, path: str) -> Mapping[str, Any]: ...
    def load(self, path: str) -> Mapping[str, Any]: ...


class DPOPipeline:
    def __init__(self, config: DPOConfig, backend: DPOTrainerBackend | None = None):
        config.validate()
        self.config = config
        self.backend = backend

    def validate_records(self, records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        parsed = [DPOPreferenceRecord.from_mapping(item) for item in records]
        return {
            "status": "validated",
            "records": len(parsed),
            "config": asdict(self.config),
            "training_started": False,
        }

    def train(self, records: Iterable[Mapping[str, Any]], *, enabled: bool = False) -> Mapping[str, Any]:
        parsed = [DPOPreferenceRecord.from_mapping(item) for item in records]
        if not enabled:
            return {"status": "disabled", "records": len(parsed), "training_started": False}
        if self.backend is None:
            raise TrainingBackendNotConfigured("DPO requested but no concrete trainer backend was injected")
        return self.backend.train(records=parsed, config=self.config)

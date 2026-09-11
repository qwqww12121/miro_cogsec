"""SFT integration boundary; no model is trained by importing this module."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable, Mapping, Protocol, Sequence

from ..contracts import (
    ReporterSFTRecord,
    StructuredAgentSFTRecord,
    TrainingBackendNotConfigured,
)


@dataclass(frozen=True)
class SFTConfig:
    task: str
    base_model: str
    output_dir: str
    max_length: int = 2048
    use_lora: bool = True
    use_qlora: bool = False
    epochs: float = 1.0
    batch_size: int = 1
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    seed: int = 42
    device: str = "auto"

    def validate(self) -> None:
        if self.task not in {"agent", "reporter"}:
            raise ValueError("SFT task must be 'agent' or 'reporter'")
        if not self.base_model or not self.output_dir:
            raise ValueError("base_model and output_dir are required")
        if self.max_length < 128:
            raise ValueError("max_length must be >= 128")
        if self.use_qlora and not self.use_lora:
            raise ValueError("QLoRA requires use_lora=true")
        if self.epochs <= 0 or self.batch_size < 1 or self.gradient_accumulation_steps < 1:
            raise ValueError("epochs and batch sizes must be positive")
        if self.learning_rate <= 0:
            raise ValueError("learning_rate must be positive")


class SFTTrainerBackend(Protocol):
    def train(self, *, records: Sequence[Any], config: SFTConfig) -> Mapping[str, Any]: ...
    def evaluate(self, *, records: Sequence[Any], config: SFTConfig) -> Mapping[str, Any]: ...
    def save(self, path: str) -> Mapping[str, Any]: ...
    def load(self, path: str) -> Mapping[str, Any]: ...


class SFTPipeline:
    def __init__(self, config: SFTConfig, backend: SFTTrainerBackend | None = None):
        config.validate()
        self.config = config
        self.backend = backend

    def validate_records(self, records: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
        parsed = [self._parse(item) for item in records]
        return {
            "status": "validated",
            "task": self.config.task,
            "records": len(parsed),
            "config": asdict(self.config),
            "training_started": False,
        }

    def train(self, records: Iterable[Mapping[str, Any]], *, enabled: bool = False) -> Mapping[str, Any]:
        parsed = [self._parse(item) for item in records]
        if not enabled:
            return {"status": "disabled", "records": len(parsed), "training_started": False}
        if self.backend is None:
            raise TrainingBackendNotConfigured("SFT requested but no concrete trainer backend was injected")
        return self.backend.train(records=parsed, config=self.config)

    def _parse(self, item: Mapping[str, Any]) -> Any:
        if self.config.task == "reporter":
            return ReporterSFTRecord.from_mapping(item)
        return StructuredAgentSFTRecord.from_mapping(item)

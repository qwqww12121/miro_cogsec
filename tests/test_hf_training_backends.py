from __future__ import annotations

from training.hf_backends import HFCausalLMDPOBackend, HFCausalLMSFTBackend, training_stack_status


def test_concrete_training_backends_are_import_safe_without_heavy_stack() -> None:
    status = training_stack_status()
    assert set(status["modules"]) == {"torch", "transformers", "peft"}
    assert isinstance(HFCausalLMSFTBackend(), HFCausalLMSFTBackend)
    assert isinstance(HFCausalLMDPOBackend(), HFCausalLMDPOBackend)

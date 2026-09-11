"""Concrete, opt-in Hugging Face SFT and DPO trainer backends.

Imports of torch/transformers/peft are lazy: the normal API process does not
need a training stack.  Unlike the historical dry-run contracts, calling
``train`` here performs optimiser updates and writes a real model/adapter.
"""

from __future__ import annotations

from dataclasses import asdict
import json
import math
from pathlib import Path
import random
from typing import Any, Mapping, Sequence

from .contracts import DPOPreferenceRecord, ReporterSFTRecord, StructuredAgentSFTRecord
from .dpo.interface import DPOConfig
from .sft.interface import SFTConfig


def training_stack_status() -> dict[str, Any]:
    from importlib.util import find_spec

    modules = {name: bool(find_spec(name)) for name in ("torch", "transformers", "peft")}
    return {
        "modules": modules,
        "sft_ready": modules["torch"] and modules["transformers"],
        "lora_ready": all(modules.values()),
        "qlora_requires": ["bitsandbytes", "CUDA"],
    }


def _require_stack(*, lora: bool) -> tuple[Any, Any, Any, Any]:
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError("真实 Reporter 训练需要安装 torch 和 transformers") from exc
    get_peft_model = None
    lora_config = None
    if lora:
        try:
            from peft import LoraConfig, get_peft_model as _get_peft_model
        except ImportError as exc:
            raise RuntimeError("LoRA/QLoRA 训练需要安装 peft") from exc
        get_peft_model, lora_config = _get_peft_model, LoraConfig
    return torch, AutoModelForCausalLM, AutoTokenizer, (get_peft_model, lora_config)


def _reporter_prompt(raw_input: str, report_state: Mapping[str, Any]) -> str:
    safe_state = json.dumps(report_state, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return (
        "你是 Miro-CogSec 的最终回答器。只根据用户输入和 ReportState 作答；"
        "不得编造事实、内部标识或仿真数值。先给判断，再给证据与可执行建议。\n"
        f"用户输入：{raw_input}\nReportState：{safe_state}\n回答："
    )


def _sft_text(record: ReporterSFTRecord | StructuredAgentSFTRecord) -> tuple[str, str]:
    if isinstance(record, ReporterSFTRecord):
        return _reporter_prompt(record.raw_input, record.report_state), record.target_answer
    prompt = (
        f"任务：{record.task}\n输入："
        f"{json.dumps(record.input_payload, ensure_ascii=False, sort_keys=True)}\n输出："
    )
    return prompt, json.dumps(record.target, ensure_ascii=False, sort_keys=True)


def _load_model(config: SFTConfig | DPOConfig, *, reference: bool = False):
    torch, auto_model, auto_tokenizer, peft = _require_stack(lora=config.use_lora and not reference)
    tokenizer = auto_tokenizer.from_pretrained(config.base_model, use_fast=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    kwargs: dict[str, Any] = {}
    if config.use_qlora:
        try:
            from transformers import BitsAndBytesConfig
        except ImportError as exc:
            raise RuntimeError("QLoRA 需要支持 BitsAndBytesConfig 的 transformers") from exc
        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        )
        kwargs["device_map"] = "auto"
    model = auto_model.from_pretrained(config.base_model, **kwargs)
    if not config.use_qlora:
        requested = str(config.device or "auto").lower()
        device = "cuda" if torch.cuda.is_available() and requested != "cpu" else "cpu"
        model.to(device)
    if config.use_lora and not reference:
        get_peft_model, LoraConfig = peft
        model = get_peft_model(model, LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
        ))
    return torch, tokenizer, model


def _encode(tokenizer: Any, prompt: str, target: str, max_length: int) -> dict[str, list[int]]:
    eos = tokenizer.eos_token or ""
    prompt_ids = tokenizer(prompt, add_special_tokens=True, truncation=True, max_length=max_length)["input_ids"]
    full = tokenizer(
        prompt + target + eos,
        add_special_tokens=True,
        truncation=True,
        max_length=max_length,
    )
    input_ids = list(full["input_ids"])
    prompt_len = min(len(prompt_ids), len(input_ids))
    labels = [-100] * prompt_len + input_ids[prompt_len:]
    return {"input_ids": input_ids, "attention_mask": list(full["attention_mask"]), "labels": labels}


class _TokenDataset:
    def __init__(self, rows: Sequence[dict[str, list[int]]]):
        self.rows = list(rows)

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index: int):
        return self.rows[index]


class _CausalCollator:
    def __init__(self, tokenizer: Any, torch: Any):
        self.tokenizer, self.torch = tokenizer, torch

    def __call__(self, features: Sequence[Mapping[str, Any]]):
        max_len = max(len(item["input_ids"]) for item in features)
        pad = int(self.tokenizer.pad_token_id)
        ids, masks, labels = [], [], []
        for item in features:
            missing = max_len - len(item["input_ids"])
            ids.append(list(item["input_ids"]) + [pad] * missing)
            masks.append(list(item["attention_mask"]) + [0] * missing)
            labels.append(list(item["labels"]) + [-100] * missing)
        return {
            "input_ids": self.torch.tensor(ids, dtype=self.torch.long),
            "attention_mask": self.torch.tensor(masks, dtype=self.torch.long),
            "labels": self.torch.tensor(labels, dtype=self.torch.long),
        }


class HFCausalLMSFTBackend:
    def __init__(self):
        self.model = None
        self.tokenizer = None

    def train(self, *, records: Sequence[Any], config: SFTConfig) -> Mapping[str, Any]:
        if not records:
            raise ValueError("SFT requires at least one record")
        torch, tokenizer, model = _load_model(config)
        try:
            from transformers import Trainer, TrainingArguments
        except ImportError as exc:
            raise RuntimeError("SFT requires transformers.Trainer") from exc
        rows = [_encode(tokenizer, *_sft_text(record), config.max_length) for record in records]
        output = Path(config.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        arguments = TrainingArguments(
            output_dir=str(output),
            num_train_epochs=float(config.epochs),
            per_device_train_batch_size=int(config.batch_size),
            gradient_accumulation_steps=int(config.gradient_accumulation_steps),
            learning_rate=float(config.learning_rate),
            seed=int(config.seed),
            save_strategy="no",
            report_to=[],
            logging_steps=1,
            remove_unused_columns=False,
        )
        trainer = Trainer(
            model=model,
            args=arguments,
            train_dataset=_TokenDataset(rows),
            data_collator=_CausalCollator(tokenizer, torch),
        )
        result = trainer.train()
        model.save_pretrained(str(output))
        tokenizer.save_pretrained(str(output))
        self.model, self.tokenizer = model, tokenizer
        return {
            "status": "trained",
            "training_started": True,
            "optimizer_steps": int(result.global_step),
            "train_loss": float(result.training_loss),
            "records": len(records),
            "output_dir": str(output.resolve()),
            "adapter_only": bool(config.use_lora),
            "config": asdict(config),
        }

    def evaluate(self, *, records: Sequence[Any], config: SFTConfig) -> Mapping[str, Any]:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("train or load a model before evaluation")
        torch = __import__("torch")
        losses = []
        self.model.eval()
        for record in records:
            row = _encode(self.tokenizer, *_sft_text(record), config.max_length)
            batch = _CausalCollator(self.tokenizer, torch)([row])
            device = next(self.model.parameters()).device
            batch = {key: value.to(device) for key, value in batch.items()}
            with torch.inference_mode():
                losses.append(float(self.model(**batch).loss.item()))
        mean_loss = sum(losses) / max(1, len(losses))
        return {"records": len(records), "loss": mean_loss, "perplexity": math.exp(min(20.0, mean_loss))}

    def save(self, path: str) -> Mapping[str, Any]:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("no trained model to save")
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        return {"status": "saved", "path": str(Path(path).resolve())}

    def load(self, path: str) -> Mapping[str, Any]:
        raise NotImplementedError("Load through LocalGemmaClient with MIRO_REPORTER_ADAPTER_PATH")


def _sequence_log_probability(torch: Any, model: Any, tokenizer: Any, prompt: str, response: str, max_length: int):
    row = _encode(tokenizer, prompt, response, max_length)
    collated = _CausalCollator(tokenizer, torch)([row])
    device = next(model.parameters()).device
    input_ids = collated["input_ids"].to(device)
    attention = collated["attention_mask"].to(device)
    labels = collated["labels"].to(device)
    logits = model(input_ids=input_ids, attention_mask=attention).logits[:, :-1, :]
    targets = labels[:, 1:]
    mask = targets.ne(-100)
    safe_targets = targets.masked_fill(~mask, 0)
    token_logp = torch.log_softmax(logits, dim=-1).gather(-1, safe_targets.unsqueeze(-1)).squeeze(-1)
    return (token_logp * mask).sum() / mask.sum().clamp_min(1)


class HFCausalLMDPOBackend:
    """Minimal reference-policy DPO implementation with real gradient updates."""

    def __init__(self):
        self.model = None
        self.reference_model = None
        self.tokenizer = None

    def train(self, *, records: Sequence[DPOPreferenceRecord], config: DPOConfig) -> Mapping[str, Any]:
        if not records:
            raise ValueError("DPO requires at least one preference record")
        torch, tokenizer, model = _load_model(config)
        _, _, reference = _load_model(config, reference=True)
        reference.eval()
        for parameter in reference.parameters():
            parameter.requires_grad_(False)
        optimizer = torch.optim.AdamW(
            [parameter for parameter in model.parameters() if parameter.requires_grad],
            lr=float(config.learning_rate),
        )
        randomizer = random.Random(config.seed)
        losses = []
        optimizer_steps = 0
        model.train()
        ordered = list(records)
        for _ in range(config.epochs):
            randomizer.shuffle(ordered)
            optimizer.zero_grad()
            for index, record in enumerate(ordered, start=1):
                prompt = _reporter_prompt(record.raw_input, record.report_state)
                policy_chosen = _sequence_log_probability(torch, model, tokenizer, prompt, record.chosen, config.max_length)
                policy_rejected = _sequence_log_probability(torch, model, tokenizer, prompt, record.rejected, config.max_length)
                with torch.inference_mode():
                    ref_chosen = _sequence_log_probability(torch, reference, tokenizer, prompt, record.chosen, config.max_length)
                    ref_rejected = _sequence_log_probability(torch, reference, tokenizer, prompt, record.rejected, config.max_length)
                margin = (policy_chosen - policy_rejected) - (ref_chosen - ref_rejected)
                loss = -torch.nn.functional.logsigmoid(float(config.beta) * margin)
                (loss / config.gradient_accumulation_steps).backward()
                losses.append(float(loss.detach().item()))
                if index % config.gradient_accumulation_steps == 0 or index == len(ordered):
                    optimizer.step()
                    optimizer.zero_grad()
                    optimizer_steps += 1
        output = Path(config.output_dir)
        output.mkdir(parents=True, exist_ok=True)
        model.save_pretrained(str(output))
        tokenizer.save_pretrained(str(output))
        self.model, self.reference_model, self.tokenizer = model, reference, tokenizer
        return {
            "status": "trained",
            "training_started": True,
            "records": len(records),
            "optimizer_steps": optimizer_steps,
            "mean_dpo_loss": sum(losses) / max(1, len(losses)),
            "output_dir": str(output.resolve()),
            "adapter_only": bool(config.use_lora),
            "config": asdict(config),
        }

    def evaluate(self, *, records: Sequence[DPOPreferenceRecord], config: DPOConfig) -> Mapping[str, Any]:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("train a model before evaluation")
        torch = __import__("torch")
        correct = 0
        self.model.eval()
        with torch.inference_mode():
            for record in records:
                prompt = _reporter_prompt(record.raw_input, record.report_state)
                chosen = _sequence_log_probability(torch, self.model, self.tokenizer, prompt, record.chosen, config.max_length)
                rejected = _sequence_log_probability(torch, self.model, self.tokenizer, prompt, record.rejected, config.max_length)
                correct += int(float(chosen) > float(rejected))
        return {"records": len(records), "preference_accuracy": correct / max(1, len(records))}

    def save(self, path: str) -> Mapping[str, Any]:
        if self.model is None or self.tokenizer is None:
            raise RuntimeError("no trained model to save")
        self.model.save_pretrained(path)
        self.tokenizer.save_pretrained(path)
        return {"status": "saved", "path": str(Path(path).resolve())}

    def load(self, path: str) -> Mapping[str, Any]:
        raise NotImplementedError("Load through LocalGemmaClient with MIRO_REPORTER_ADAPTER_PATH")

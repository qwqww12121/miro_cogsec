"""本地 Gemma 客户端封装。"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import torch
from transformers import AutoModelForCausalLM, AutoModelForImageTextToText, AutoProcessor


logger = logging.getLogger(__name__)


class LocalGemmaClient:
    """使用本地 Hugging Face Gemma 模型的轻量客户端。"""

    mode_name = "local_gemma"

    def __init__(
        self,
        model_path: str,
        device: str = "auto",
        max_new_tokens: int = 768,
        torch_dtype: str = "auto",
        offload_folder: Optional[str] = None,
        attn_implementation: Optional[str] = None,
    ):
        self.model_path = str(Path(model_path).resolve())
        self.device_preference = device
        self.max_new_tokens = max_new_tokens
        self.torch_dtype_name = torch_dtype
        self.offload_folder = str(Path(offload_folder).resolve()) if offload_folder else None
        self.attn_implementation = attn_implementation

        self._processor: Any = None
        self._model: Any = None
        self._loader_name: Optional[str] = None
        self._load_lock = threading.Lock()

        self.loaded_device: Optional[str] = None
        self.last_error: Optional[str] = None

    def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """执行一次本地聊天推理。"""
        del response_format
        self._ensure_loaded()
        normalized_messages = self._normalize_messages(messages)
        inputs = self._build_inputs(normalized_messages)
        generation_kwargs = self._build_generation_kwargs(temperature, max_tokens)

        try:
            with torch.inference_mode():
                outputs = self._model.generate(**inputs, **generation_kwargs)
            prompt_length = int(inputs["input_ids"].shape[-1])
            generated = outputs[0][prompt_length:]
            text = self._decode(generated)
            self.last_error = None
            return self._clean_response(text)
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            raise

    def chat_json(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """执行推理并解析为 JSON。"""
        content = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return self._extract_json_payload(content)

    def _ensure_loaded(self) -> None:
        """延迟加载 processor 与 model。"""
        if self._model is not None and self._processor is not None:
            return

        with self._load_lock:
            if self._model is not None and self._processor is not None:
                return

            model_dir = Path(self.model_path)
            if not model_dir.exists():
                raise FileNotFoundError(f"本地 Gemma 模型目录不存在: {model_dir}")

            offload_dir = None
            if self.offload_folder:
                offload_dir = Path(self.offload_folder)
                offload_dir.mkdir(parents=True, exist_ok=True)

            self._processor = AutoProcessor.from_pretrained(
                self.model_path,
                local_files_only=True,
            )

            torch_dtype = self._resolve_torch_dtype()
            load_kwargs: Dict[str, Any] = {
                "pretrained_model_name_or_path": self.model_path,
                "local_files_only": True,
                "low_cpu_mem_usage": True,
                "torch_dtype": torch_dtype,
            }

            device_pref = self.device_preference.lower().strip()
            use_cuda = torch.cuda.is_available()
            if use_cuda and device_pref != "cpu":
                # 强制全部权重加载到 GPU 0，避免 accelerate 自动 offload 到 CPU
                load_kwargs["device_map"] = {"": 0}
            else:
                if device_pref == "cuda":
                    logger.warning("请求使用 CUDA，但当前 torch 未检测到 GPU，回退到 CPU。")
                load_kwargs["device_map"] = "cpu"

            attn_implementation = self._resolve_attn_implementation()
            if attn_implementation:
                load_kwargs["attn_implementation"] = attn_implementation

            last_exc: Optional[Exception] = None
            for loader_name, loader in (
                ("AutoModelForCausalLM", AutoModelForCausalLM),
                ("AutoModelForImageTextToText", AutoModelForImageTextToText),
            ):
                try:
                    self._model = loader.from_pretrained(**load_kwargs)
                    self._loader_name = loader_name
                    self.loaded_device = self._detect_loaded_device()
                    self.last_error = None
                    logger.info(
                        "本地 Gemma 已加载：loader=%s, requested_device=%s, loaded_device=%s, dtype=%s, attn=%s",
                        loader_name,
                        self.device_preference,
                        self.loaded_device,
                        self.torch_dtype_name,
                        attn_implementation or "default",
                    )
                    return
                except Exception as exc:
                    last_exc = exc

            self.last_error = f"{type(last_exc).__name__}: {last_exc}" if last_exc else "未知加载失败"
            raise RuntimeError(f"本地 Gemma 加载失败：{self.last_error}")

    def _build_inputs(self, messages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构造 Gemma 输入张量。"""
        prompt_inputs = self._processor.apply_chat_template(
            messages,
            add_generation_prompt=True,
            tokenize=True,
            return_dict=True,
            return_tensors="pt",
        )
        device = self._resolve_input_device()
        return {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in prompt_inputs.items()
        }

    def _build_generation_kwargs(self, temperature: float, max_tokens: int) -> Dict[str, Any]:
        """构造 generation 参数。"""
        target_tokens = max(64, min(int(max_tokens), self.max_new_tokens))
        kwargs: Dict[str, Any] = {
            "max_new_tokens": target_tokens,
            "pad_token_id": getattr(self._processor.tokenizer, "pad_token_id", 0),
            "eos_token_id": getattr(self._processor.tokenizer, "eos_token_id", None),
        }

        if temperature and temperature > 0.15:
            kwargs["do_sample"] = True
            kwargs["temperature"] = float(temperature)
            kwargs["top_p"] = 0.95
        else:
            kwargs["do_sample"] = False

        return kwargs

    def _normalize_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将 OpenAI 风格消息转换为 Gemma chat template 输入。"""
        normalized: List[Dict[str, Any]] = []
        for item in messages:
            role = str(item.get("role", "user"))
            content = item.get("content", "")
            if isinstance(content, str):
                normalized_content = [{"type": "text", "text": content}]
            elif isinstance(content, list):
                normalized_content = []
                for chunk in content:
                    if isinstance(chunk, str):
                        normalized_content.append({"type": "text", "text": chunk})
                    elif isinstance(chunk, dict):
                        if chunk.get("type") == "text" and "text" in chunk:
                            normalized_content.append({"type": "text", "text": str(chunk["text"])})
                        elif "text" in chunk:
                            normalized_content.append({"type": "text", "text": str(chunk["text"])})
                if not normalized_content:
                    normalized_content = [{"type": "text", "text": str(content)}]
            else:
                normalized_content = [{"type": "text", "text": str(content)}]

            normalized.append({"role": role, "content": normalized_content})
        return normalized

    def _resolve_torch_dtype(self) -> Any:
        """根据配置决定权重 dtype。"""
        if (
            self.torch_dtype_name.lower().strip() == "auto"
            and os.name == "nt"
            and self.device_preference.lower().strip() != "cpu"
            and torch.cuda.is_available()
        ):
            # Windows + CUDA + Gemma 4 在本地推理时更稳定地使用 fp16。
            return torch.float16

        mapping = {
            "auto": "auto",
            "float16": torch.float16,
            "fp16": torch.float16,
            "bfloat16": torch.bfloat16,
            "bf16": torch.bfloat16,
            "float32": torch.float32,
            "fp32": torch.float32,
        }
        return mapping.get(self.torch_dtype_name.lower().strip(), "auto")

    def _resolve_attn_implementation(self) -> Optional[str]:
        """决定 attention 实现。"""
        value = (self.attn_implementation or "").strip().lower()
        if not value or value in {"auto", "default"}:
            if os.name == "nt" and self.device_preference.lower().strip() != "cpu" and torch.cuda.is_available():
                # Windows 上 Gemma 4 的首轮 generate 在 eager 模式下更稳定。
                return "eager"
            return None
        return value

    def _resolve_input_device(self) -> torch.device:
        """找到输入张量应放置的设备。"""
        if hasattr(self._model, "hf_device_map"):
            for location in self._model.hf_device_map.values():
                if isinstance(location, int):
                    return torch.device(f"cuda:{location}")
                if isinstance(location, str) and location.startswith("cuda"):
                    return torch.device(location)
            return torch.device("cpu")

        parameter = next(self._model.parameters(), None)
        if parameter is None:
            return torch.device("cpu")
        return parameter.device

    def _detect_loaded_device(self) -> str:
        """读取模型加载后的主要设备。"""
        if hasattr(self._model, "hf_device_map"):
            locations = list(dict.fromkeys(str(item) for item in self._model.hf_device_map.values()))
            return ",".join(locations)
        parameter = next(self._model.parameters(), None)
        return str(parameter.device) if parameter is not None else "cpu"

    def _decode(self, token_ids: Any) -> str:
        """将输出 token 解码为文本。"""
        decode_fn = getattr(self._processor, "decode", None)
        if callable(decode_fn):
            return str(decode_fn(token_ids, skip_special_tokens=True))
        return str(self._processor.tokenizer.decode(token_ids, skip_special_tokens=True))

    def _clean_response(self, content: str) -> str:
        """清理模型响应中的包裹符号。"""
        cleaned = re.sub(r"<think>[\s\S]*?</think>", "", content, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
        return cleaned

    def _extract_json_payload(self, content: str) -> Dict[str, Any]:
        """从模型文本中提取 JSON 对象。"""
        cleaned = self._clean_response(content)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                raise ValueError(f"本地 Gemma 未返回有效 JSON：{cleaned}")
            return json.loads(match.group(0))

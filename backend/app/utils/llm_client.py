"""
LLM客户端封装
统一使用OpenAI格式调用，含超时与重试（Round 1 升级）。
"""

import json
import re
from typing import Optional, Dict, Any, List

import httpx
from openai import OpenAI, Timeout

from ..config import Config
from ..utils.logger import get_logger
from ..utils.retry import retry_with_backoff

logger = get_logger("mirofish.llm")


class LLMClient:
    """LLM客户端，含 connect/read 超时与有限重试。"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model: Optional[str] = None,
        connect_timeout: float = 15.0,
        read_timeout: float = 120.0,
        max_retries: int = 2,
        mode_name: str = "main_llm",
        enable_thinking: Optional[bool] = None,
        extra_body: Optional[Dict[str, Any]] = None,
    ):
        # Final: explicit key first, then project-specific main key, then
        # legacy LLM_API_KEY only when MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY is true
        _key = api_key or Config.MIRO_COGSEC_MAIN_LLM_API_KEY
        if not _key and Config.MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY:
            _key = Config.LLM_API_KEY
        self.api_key = _key
        self.base_url = base_url or Config.MIRO_COGSEC_MAIN_LLM_BASE_URL
        self.model = model or Config.MIRO_COGSEC_MAIN_LLM_MODEL
        self.mode_name = mode_name
        self.enable_thinking = enable_thinking
        # Optional provider-specific request-body extensions (merged into the
        # chat payload as top-level extra_body).  Used e.g. for DeepSeek V4's
        # ``thinking: {"type": "disabled"}`` switch, which the Qwen-style
        # ``enable_thinking`` flag cannot express.
        self.extra_body = extra_body
        self.last_response_metadata: Dict[str, Any] = {}

        if not self.api_key:
            raise ValueError("MIRO_COGSEC_MAIN_LLM_API_KEY 未配置")

        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._max_retries = max_retries

        timeout = Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=60.0,
            pool=10.0,
        )
        verify_ssl = getattr(Config, "MIRO_COGSEC_MAIN_LLM_VERIFY_SSL", True)
        trust_env = getattr(Config, "MIRO_COGSEC_MAIN_LLM_TRUST_ENV", True)
        self.client = OpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            timeout=timeout,
            max_retries=0,  # we handle retries ourselves for observability
            http_client=httpx.Client(
                verify=verify_ssl,
                timeout=timeout,
                trust_env=trust_env,
            ),
        )

    def _do_chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """Raw OpenAI chat call (no retry wrapper)."""
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            kwargs["response_format"] = response_format
        send_thinking_param = getattr(Config, "MIRO_COGSEC_MAIN_LLM_SEND_THINKING_PARAM", None)
        if send_thinking_param is None:
            # The USTC gateway currently rejects the OpenAI-compatible
            # ``enable_thinking`` extension for qwen models.  Omitting the
            # optional field is equivalent to the provider default and keeps
            # the normal OpenAI path unchanged.
            send_thinking_param = "ustc.edu.cn" not in str(self.base_url).lower()
        if self.enable_thinking is not None and send_thinking_param:
            kwargs["extra_body"] = {"enable_thinking": self.enable_thinking}
        if self.extra_body:
            merged = dict(kwargs.get("extra_body") or {})
            merged.update(self.extra_body)
            kwargs["extra_body"] = merged

        response = self.client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        content = choice.message.content or ""
        content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
        usage = getattr(response, "usage", None)
        self.last_response_metadata = {
            "finish_reason": getattr(choice, "finish_reason", None),
            "prompt_tokens": getattr(usage, "prompt_tokens", None),
            "completion_tokens": getattr(usage, "completion_tokens", None),
            "model": getattr(response, "model", None) or self.model,
        }
        return content

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        response_format: Optional[Dict] = None,
    ) -> str:
        """发送聊天请求（含超时 + 指数退避重试）。

        Retries on: connection errors, timeout, 429, 5xx.
        Does NOT retry on: 4xx (except 429).
        """
        do_call = retry_with_backoff(
            max_retries=self._max_retries,
            initial_delay=1.0,
            max_delay=15.0,
            backoff_factor=2.0,
            jitter=True,
            exceptions=(Exception,),
        )(self._do_chat)

        try:
            return do_call(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Exception as exc:
            logger.error(
                "LLM chat 调用在 %d 次重试后最终失败: %s",
                self._max_retries, exc,
            )
            raise

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """发送聊天请求并返回JSON。

        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大token数

        Returns:
            解析后的JSON对象
        """
        response = self.chat(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        # 清理markdown代码块标记
        cleaned_response = response.strip()
        cleaned_response = re.sub(r'^```(?:json)?\s*\n?', '', cleaned_response, flags=re.IGNORECASE)
        cleaned_response = re.sub(r'\n?```\s*$', '', cleaned_response)
        cleaned_response = cleaned_response.strip()

        try:
            return json.loads(cleaned_response)
        except json.JSONDecodeError:
            logger.error(
                "JSON 解析失败。finish_reason=%s completion_tokens=%s 原始返回(清洗前)=%r",
                self.last_response_metadata.get("finish_reason"),
                self.last_response_metadata.get("completion_tokens"),
                response,
            )
            raise ValueError(f"LLM返回的JSON格式无效: {cleaned_response}")

def clone_llm_client_with_thinking(client: "LLMClient", *, enable_thinking: bool) -> Any:
    """Return a copy of an ``LLMClient`` with an explicit thinking switch.

    Used when the final-answer reporter reuses the main analysis client: the
    reporter is a last-mile text renderer and ``MIRO_REPORTER_ENABLE_THINKING``
    defaults to false, but the shared main client may not carry that switch.
    Without it the provider default can burn the whole output budget on
    reasoning tokens and return empty content at ``finish_reason=length``
    (observed with deepseek-v4-flash on large event-propagation payloads).
    Cloning keeps the main client untouched for analysis calls.

    The switch is provider-specific: DeepSeek V4 expects
    ``thinking: {"type": "enabled"|"disabled"}`` in the request body and
    silently ignores the Qwen-style ``enable_thinking`` flag, so for DeepSeek
    endpoints the extra_body form is used; other providers get the
    ``enable_thinking`` kwarg as before.
    """
    base_url = str(client.base_url or "")
    extra_body = None
    thinking_flag: Optional[bool] = enable_thinking
    if "deepseek" in base_url.lower():
        extra_body = {"thinking": {"type": "enabled" if enable_thinking else "disabled"}}
        thinking_flag = None  # avoid sending the Qwen-style flag to DeepSeek
    return LLMClient(
        api_key=client.api_key,
        base_url=client.base_url,
        model=client.model,
        connect_timeout=client._connect_timeout,
        read_timeout=client._read_timeout,
        max_retries=client._max_retries,
        mode_name=client.mode_name,
        enable_thinking=thinking_flag,
        extra_body=extra_body,
    )

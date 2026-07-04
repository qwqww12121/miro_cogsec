"""场景字段提取器：根据分类场景从原始文本中提取表单所需的结构化字段。

单次 LLM 调用，只做信息提取，不做分析；提取不到的字段返回空字符串而非编造。
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..modules.scenarios import (
    CANONICAL_EVENT_PROPAGATION,
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
)
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.field_extractor")

_MAX_INPUT_CHARS = 2000

# 各场景需要提取的字段：key → 提示描述
_FIELD_SCHEMAS: Dict[str, Dict[str, str]] = {
    CANONICAL_FRAUD_IM: {
        "chat_platform": "对话平台（如微信、QQ、Telegram、陌陌等即时通讯软件名称）",
        "suspect_identity": "嫌疑人自称的身份（如投资顾问、网友、公检法人员、客服等）",
        "fraud_type": "疑似诈骗类别（如投资理财诈骗、冒充公检法、刷单诈骗、情感诈骗等）",
    },
    CANONICAL_PUBLIC_OPINION: {
        "platform": "舆情发生的平台（如微博、抖音、知乎、微信公众号等）",
        "topic": "话题或关键词（如话题名称、热搜词、事件关键词等）",
        "time_window": "时间窗口（如事件发生或讨论的起止时间段）",
    },
    CANONICAL_EVENT_PROPAGATION: {
        "event_name": "事件名称（如事件的标题或简称）",
        "origin": "起点账号或首发节点（如首发账号名、媒体名称等）",
        "channels": "发酵渠道（如微博、微信群、朋友圈、论坛等传播渠道）",
        "time_window": "时间窗口（如事件传播的起止时间段）",
    },
}


def _build_messages(text: str, scenario_type: str) -> List[Dict[str, str]]:
    fields = _FIELD_SCHEMAS[scenario_type]
    field_desc_lines = "\n".join(
        f'  "{k}": {desc}' for k, desc in fields.items()
    )
    empty_template = "{\n" + "\n".join(f'  "{k}": ""' for k in fields) + "\n}"

    system = (
        "你是一个信息提取助手。你会收到一段用户文本，"
        "你的任务是从中提取以下字段的值：\n\n"
        f"{field_desc_lines}\n\n"
        "提取规则：\n"
        "1. 只提取文本中明确出现或可直接推断的信息，绝不编造或猜测。\n"
        "2. 提取不到的字段必须返回空字符串 \"\"，不要填写任何推测内容。\n"
        "3. 只返回一个 JSON 对象，不要任何额外文字，不要 markdown 代码块。"
    )

    user = (
        f"请从下面的文本中提取信息，按如下 JSON 结构返回"
        f"（提取不到的字段填空字符串）：\n\n"
        f"{empty_template}\n\n"
        f"文本：\n\"\"\"\n{text}\n\"\"\"\n\n"
        "只返回 JSON，不要其他内容。"
    )

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


class LLMFieldExtractor:
    """从原始文本中提取各场景表单字段，单次 LLM 调用。"""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def extract(self, text: str, scenario_type: str) -> Dict[str, Any]:
        """提取指定场景的结构化字段。

        Args:
            text: 用户输入的原始文本。
            scenario_type: 场景类型（canonical）。

        Returns:
            各字段 key → 提取值的 dict；提取不到返回空字符串。
            若 scenario_type 未知则返回空 dict。
        """
        if scenario_type not in _FIELD_SCHEMAS:
            return {}

        truncated = (text or "").strip()[:_MAX_INPUT_CHARS]
        messages = _build_messages(truncated, scenario_type)

        try:
            payload = self.client.chat_json(messages=messages, temperature=0.1, max_tokens=300)
        except Exception as exc:
            logger.warning("字段提取 LLM 调用失败，返回空字段: %s", exc)
            return {k: "" for k in _FIELD_SCHEMAS[scenario_type]}

        result: Dict[str, Any] = {}
        for k in _FIELD_SCHEMAS[scenario_type]:
            raw = payload.get(k, "")
            result[k] = str(raw).strip() if raw else ""
        return result

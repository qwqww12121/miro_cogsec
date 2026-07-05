"""分析结果通俗化：将专业分析结果转换为面向普通用户的大白话解释。

单次 LLM 调用，不重新做分析，只做语言风格转换。
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.plainifier")

_MAX_INPUT_CHARS = 3000

_SYSTEM_PROMPT = """\
你是一个把专业分析报告翻译成大白话的助手。
用户会给你一段认知安全分析结果的关键字段，可能属于以下三种场景之一，
请先看 scenario_type 确定场景，再用对应场景的语言解释，不要混用其他场景的表述：

- fraud_im（诈骗即时通讯）：有人通过聊天软件实施诈骗，骗取钱财或个人信息
- public_opinion（舆情分析）：某话题在网络上引发情绪极化、信息误导或舆论操控
- event_propagation（事件传播分析）：某事件或信息在社交网络中快速扩散，存在传播风险

输出要求：
1. plain_summary：1~3 句话，用口语说清楚"这是什么情况、风险在哪里"，不用专业术语。
   场景对应说法举例：
   - fraud_im → 说清楚对方用什么手段骗人、想骗什么
   - public_opinion → 说清楚是什么舆情话题、情绪多激烈、主要风险是什么
   - event_propagation → 说清楚什么信息在传播、传播速度和风险有多高
2. action_advice：一句话，告诉用户最重要的一个行动建议，简洁直接。
3. 语气像跟朋友解释，不要说"根据分析结果""综上所述"这类官腔。
4. 不要重新做分析，只把给你的内容换一种更通俗的说法。
5. 只返回如下 JSON，不要任何额外文字，不要 markdown 代码块：
{
  "plain_summary": "...",
  "action_advice": "..."
}
6. 重要：plain_summary 和 action_advice 的文字内不得出现英文双引号（"），
   如需强调词汇请用「」或直接不加引号。\
"""

_USER_PROMPT_TEMPLATE = """\
以下是一次认知安全分析结果（专业版），请把它转成大白话：

{analysis_json}

只返回 JSON，不要其他内容。\
"""


def _extract_json(text: str) -> Dict[str, Any]:
    """从 LLM 输出中鲁棒地提取 JSON 对象。

    先尝试直接 json.loads；失败后用正则提取第一个 {...} 块再试一次。
    这能处理模型在 JSON 前后添加多余文字的情况。
    """
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 尝试提取第一个完整的 JSON 对象
    match = re.search(r'\{[\s\S]*\}', text)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"LLM返回的JSON格式无效: {text}")


class LLMPlainifier:
    """将专业分析结果通俗化，单次 LLM 调用。"""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def plainify(self, analysis_data: Dict[str, Any]) -> Dict[str, str]:
        """将分析结果转换为通俗语言。

        Args:
            analysis_data: 前端传入的分析结果字段（risk_type, confidence, 话术特征, 建议等）。

        Returns:
            { "plain_summary": "...", "action_advice": "..." }
        """
        analysis_json = json.dumps(analysis_data, ensure_ascii=False, indent=2)
        if len(analysis_json) > _MAX_INPUT_CHARS:
            analysis_json = analysis_json[:_MAX_INPUT_CHARS] + "\n... (已截断)"

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": _USER_PROMPT_TEMPLATE.format(analysis_json=analysis_json),
            },
        ]

        # 使用 chat() 而非 chat_json()，配合自定义的鲁棒解析，
        # 避免模型在 JSON 字符串值中使用未转义引号时 chat_json 直接抛错。
        raw = self.client.chat(messages=messages, temperature=0.5, max_tokens=800,
                               response_format={"type": "json_object"})
        # 清理 markdown 代码块标记
        raw = re.sub(r'^```(?:json)?\s*\n?', '', raw.strip(), flags=re.IGNORECASE)
        raw = re.sub(r'\n?```\s*$', '', raw)

        payload = _extract_json(raw)

        return {
            "plain_summary": str(payload.get("plain_summary", "")).strip() or "暂无摘要",
            "action_advice": str(payload.get("action_advice", "")).strip() or "暂无建议",
        }

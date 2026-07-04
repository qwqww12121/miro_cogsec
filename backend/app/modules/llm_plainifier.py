"""分析结果通俗化：将专业分析结果转换为面向普通用户的大白话解释。

单次 LLM 调用，不重新做分析，只做语言风格转换。
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.plainifier")

_MAX_INPUT_CHARS = 3000

_SYSTEM_PROMPT = """\
你是一个把专业分析报告翻译成大白话的助手。
用户会给你一段认知安全分析结果（含风险类型、置信度、话术特征、干预建议等专业字段），
你需要把它转成普通人能立刻看懂的语言。

输出要求：
1. plain_summary：1~3 句话，用口语说清楚"这是什么情况、风险在哪里"，不用专业术语。
2. action_advice：一句话，告诉用户最重要的一个行动建议，简洁直接。
3. 语气像跟朋友解释，不要说"根据分析结果""综上所述"这类官腔。
4. 不要重新做分析，只把给你的内容换一种更通俗的说法。
5. 只返回如下 JSON，不要任何额外文字，不要 markdown 代码块：
{
  "plain_summary": "...",
  "action_advice": "..."
}\
"""

_USER_PROMPT_TEMPLATE = """\
以下是一次认知安全分析结果（专业版），请把它转成大白话：

{analysis_json}

只返回 JSON，不要其他内容。\
"""


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
        # 序列化为 JSON 字符串，截断超长输入
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

        payload = self.client.chat_json(messages=messages, temperature=0.5, max_tokens=400)

        return {
            "plain_summary": str(payload.get("plain_summary", "")).strip() or "暂无摘要",
            "action_advice": str(payload.get("action_advice", "")).strip() or "暂无建议",
        }

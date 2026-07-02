"""LLM 驱动的场景智能分类器。

面向前端首页"智能识别"功能：用户粘贴一段非结构化、口语化、甚至模糊的文本
（可能是聊天记录、一段舆情描述、一个事件传播过程），判断它属于三大认知安全
场景中的哪一个，并提炼关键线索摘要。

与 ``scenario_detector.py``（关键词版本）的区别：
- 完全基于 LLM 语义理解，能处理口语化、多场景特征混合的输入（关键词版本会误判）；
- 信息不足时主动降低 confidence，不强行给出高置信度的错误分类；
- 单次 LLM 调用，轻量快速，不跑完整 cogsec 主链分析流程。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..modules.scenarios import (
    CANONICAL_EVENT_PROPAGATION,
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
)
from ..utils.llm_client import LLMClient
from ..utils.logger import get_logger

logger = get_logger("mirofish.classifier")

# 允许返回的合法场景集合
_VALID_SCENARIOS = frozenset({
    CANONICAL_FRAUD_IM,
    CANONICAL_PUBLIC_OPINION,
    CANONICAL_EVENT_PROPAGATION,
})

# 输入文本最大长度（超出截断，避免 token 爆炸、保证几秒内返回）
_MAX_INPUT_CHARS = 2000


@dataclass
class ClassificationResult:
    """场景分类结果。"""

    scenario_type: str
    confidence: float
    reason: str
    extracted_summary: str
    model: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_type": self.scenario_type,
            "confidence": self.confidence,
            "reason": self.reason,
            "extracted_summary": self.extracted_summary,
            "model": self.model,
        }


# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """你是一个认知安全（CogSec）场景智能分类专家。用户会粘贴一段非结构化、口语化、甚至模糊的文本（可能是聊天记录、一段舆情描述或一个事件传播过程），你需要判断它属于以下三个场景中的【哪一个】，并提炼出关键线索。

【三个场景及其核心判别维度】

1. fraud_im（诈骗即时通讯）
   核心：存在"施害者试图通过即时通讯 / 社交渠道实施诈骗"的行为模式。
   判别标志：文本描述了一个具体的诈骗 / 诱导行为——存在施害者与（潜在）受害者，
   含有诸如 诱导转账/汇款、投资理财高回报承诺、刷单返利、冒充公检法/客服/领导、
   索要验证码、安全账户、屏幕共享、解冻保证金 等行为要素。
   关键：关注"是否在骗人"。即便信息是通过社交渠道传播的，只要本质是诈骗，就判 fraud_im
   （传播只是手段，诈骗才是本质）。
   典型：原始股内部认购 + 承诺半年翻五倍 + 要求私聊转账 = 投资理财诈骗。

2. public_opinion（舆情分析）
   核心：公众群体对某件事 / 某话题的【反应、态度、讨论】形成舆论场。
   判别标志：焦点在于 社会情绪、民意、媒体关注、热搜话题、舆论发酵、群体讨论、
   造谣/辟谣/评论/转发 等舆论景观本身。
   关键：关注"公众怎么看、情绪如何、舆论走向"，而非信息怎么传播。

3. event_propagation（事件传播分析）
   核心：信息 / 事件在群体中的【传播动力学】。
   判别标志：焦点在于 传播路径、扩散速度与范围、首发源头、溯源、关键节点、
   跨群体/跨地域/跨平台扩散、链式/裂变/病毒式传播 等传播机制。
   关键：关注"信息怎么传的、传多快、从哪来、传到哪"。

【判别决策顺序（请严格遵循）】
步骤1（fraud_im 优先）：先判断文本是否描述了一个具体的诈骗 / 施害行为。
   - 只要存在"有人试图骗钱 / 骗取敏感信息"的施害意图与行为模式，即便它同时通过
     社交渠道传播，也应判为 fraud_im（传播只是手段，诈骗才是本质）。
   - 若判为 fraud_im，进入步骤4。
步骤2（区分两种"信息流"场景）：若不是诈骗，按焦点区分。
   - 焦点在"公众群体反应 / 舆论 / 情绪 / 媒体 / 话题" → public_opinion
   - 焦点在"传播路径 / 扩散速度 / 源头溯源 / 跨域传播 / 关键节点" → event_propagation
步骤3（边界处理）：若 public_opinion 与 event_propagation 的特征同时强烈出现，
   按文本的【主焦点】判定其一，但 confidence 必须降到 0.5~0.7 区间，并在 reason 中
   明确说明这是边界案例、为何倾向某一类、另一类的特征为何次之。
步骤4：输出结果。

【confidence 规则】
- 输入信息不足（太短、太模糊、无任何场景特征、无法判断本质）→ confidence < 0.5，
  并在 reason 中说明信息缺失点。此时仍需给出最可能的一类，但绝不可给高置信度。
- 边界 / 混合案例（两个场景特征都明显）→ confidence 0.5~0.75。
- 特征清晰、单一主场景 → confidence 0.85~0.95。
- 绝不要为了"显得确定"而给错误的分类强加高置信度。

【extracted_summary 规则】
从原始输入中提炼出关键线索（1~2 句话或 2~3 个要点），反映"你理解到的核心信息"，
而非复述原文。例如从模糊描述里提炼出"投资理财诈骗：原始股噱头 + 高回报承诺 + 引导转账"。

【输出格式】只返回一个 JSON 对象，不要任何额外文字、不要 markdown 代码块：
{
  "scenario_type": "fraud_im" 或 "public_opinion" 或 "event_propagation",
  "confidence": 0.0 到 1.0 之间的数字,
  "reason": "判定理由（中文，说明为何选这一类；边界或信息不足案例必须说明）",
  "extracted_summary": "提炼出的关键线索摘要（中文）"
}"""

_USER_PROMPT_TEMPLATE = """请对下面这段用户输入进行场景分类。

用户输入：
\"\"\"
{text}
\"\"\"

请严格按输出格式返回 JSON。"""


# ---------------------------------------------------------------------------
# Classifier
# ---------------------------------------------------------------------------


class LLMScenarioClassifier:
    """基于 LLM 的场景智能分类器。单次调用，轻量快速。"""

    def __init__(self, client: Optional[LLMClient] = None):
        self.client = client or LLMClient()

    def classify(self, text: str) -> ClassificationResult:
        """对一段文本进行场景分类。

        Args:
            text: 用户输入的非结构化文本。

        Returns:
            ClassificationResult: 含 scenario_type / confidence / reason / extracted_summary。
        """
        raw_text = (text or "").strip()
        if not raw_text:
            raise ValueError("输入文本为空")

        # 截断过长输入，保证响应速度
        truncated = raw_text[:_MAX_INPUT_CHARS]
        if len(raw_text) > _MAX_INPUT_CHARS:
            logger.info("输入文本过长(%d字符)，已截断至 %d 字符", len(raw_text), _MAX_INPUT_CHARS)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(text=truncated)},
        ]

        # 低温度 + 较小 max_tokens：分类任务需要稳定且响应快
        payload = self.client.chat_json(
            messages=messages,
            temperature=0.2,
            max_tokens=512,
        )

        return self._build_result(payload)

    # ------------------------------------------------------------------

    def _build_result(self, payload: Dict[str, Any]) -> ClassificationResult:
        """校验并归一化 LLM 返回的 JSON。"""
        scenario_type = str(payload.get("scenario_type", "")).strip()
        if scenario_type not in _VALID_SCENARIOS:
            # 模型偶发返回非法标签时，记录原始值并回退到 fraud_im（与关键词检测器一致）
            logger.warning("LLM 返回了非法 scenario_type=%r，回退到 fraud_im", scenario_type)
            scenario_type = CANONICAL_FRAUD_IM

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        reason = str(payload.get("reason", "")).strip() or "未提供理由"
        extracted_summary = str(payload.get("extracted_summary", "")).strip() or "未提炼出摘要"

        return ClassificationResult(
            scenario_type=scenario_type,
            confidence=round(confidence, 3),
            reason=reason,
            extracted_summary=extracted_summary,
            model=getattr(self.client, "model", ""),
        )

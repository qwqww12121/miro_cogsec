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

from dataclasses import dataclass, field
import re
from typing import Any, Dict, Optional, Tuple

from .scenarios import (
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

_GREETING_PATTERN = re.compile(
    r"^(你好|您好|嗨|哈喽|hello|hi|在吗|你是谁|介绍一下)([\s!！,.，。？?]*)$",
    re.IGNORECASE,
)

# 不依赖 LLM 的经典诈骗开场白。短输入一旦命中，就应识别为 fraud_im，
# 而不是被 prompt 里的“信息不足”规则压到低置信度。
_CLASSIC_FRAUD_HOOKS: Tuple[Tuple[re.Pattern[str], Dict[str, Any]], ...] = (
    (
        re.compile(r"我是秦始皇"),
        {
            "confidence": 0.84,
            "reason": "这是中国互联网常见的历史人物冒充诈骗开场白，虽短但场景特征明确。",
            "extracted_summary": "经典身份冒充话术开场：“我是秦始皇”。",
            "extracted_fields": {
                "chat_platform": "",
                "suspect_identity": "冒充秦始皇",
                "fraud_type": "身份冒充",
            },
        },
    ),
    (
        re.compile(r"我是(汉武帝|玉皇大帝|玉帝)"),
        {
            "confidence": 0.82,
            "reason": "以历史/神话人物自称，属于典型身份冒充诈骗话术钩子。",
            "extracted_summary": "神话或历史人物冒充开场白，疑为诈骗话术。",
            "extracted_fields": {
                "chat_platform": "",
                "suspect_identity": "冒充历史/神话人物",
                "fraud_type": "身份冒充",
            },
        },
    ),
    (
        re.compile(r"我是(纪委|公检法|公安|警察|检察院|法院|警官)"),
        {
            "confidence": 0.86,
            "reason": "自称公检法/纪委是冒充公检法诈骗的标准开场，即使尚未出现转账指令也已构成明确场景。",
            "extracted_summary": "冒充公检法或纪委的身份声明，属于高危诈骗开场白。",
            "extracted_fields": {
                "chat_platform": "",
                "suspect_identity": "冒充公检法",
                "fraud_type": "冒充公检法",
            },
        },
    ),
    (
        re.compile(r"我是(.{0,8})?(银行|客服|快递|物流).{0,6}(客服)?"),
        {
            "confidence": 0.8,
            "reason": "自称客服/银行/快递人员是冒充客服类诈骗的常见开场。",
            "extracted_summary": "冒充客服或机构工作人员的身份声明。",
            "extracted_fields": {
                "chat_platform": "",
                "suspect_identity": "冒充客服",
                "fraud_type": "冒充客服",
            },
        },
    ),
)

# 每个场景允许出现的结构化字段 key（用于过滤 LLM 返回中的多余/错位字段，
# 对应前端 FraudImPage / PublicOpinionPage / EventPropagationPage 里
# extractedFields.xxx 的读取逻辑）
_SCENARIO_FIELD_KEYS: Dict[str, tuple] = {
    CANONICAL_FRAUD_IM: ("chat_platform", "suspect_identity", "fraud_type"),
    CANONICAL_PUBLIC_OPINION: ("platform", "topic"),
    CANONICAL_EVENT_PROPAGATION: ("event_name", "origin", "channels"),
}


@dataclass
class ClassificationResult:
    """场景分类结果。"""

    scenario_type: str
    confidence: float
    reason: str
    extracted_summary: str
    model: str = ""
    extracted_fields: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_type": self.scenario_type,
            "confidence": self.confidence,
            "reason": self.reason,
            "extracted_summary": self.extracted_summary,
            "model": self.model,
            "extracted_fields": self.extracted_fields,
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
   短输入同样可以成立：一句可识别的诈骗话术开场白（如“我是秦始皇”“我是公安局的”）
   即使还没有转账、验证码等后续行为，也属于 fraud_im，不得因为“信息短”就放弃该类。

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
步骤0（先排除无关材料）：若文本明显是项目规划、技术文档、比赛案例集、产品说明、
   课程作业或系统 README，与即时通讯诈骗、公共舆情事件、信息传播动力学都无关，
   则 scenario_type 必须为 "unknown"，confidence < 0.3。
   禁止因为出现“案例”“模式”“转发”“争议”等词，就把规划案/案例集判成舆情或传播。
步骤1（fraud_im 优先）：先判断文本是否描述了一个具体的诈骗 / 施害行为。
   - 只要存在"有人试图骗钱 / 骗取敏感信息"的施害意图与行为模式，即便它同时通过
     社交渠道传播，也应判为 fraud_im（传播只是手段，诈骗才是本质）。
   - 若判为 fraud_im，进入步骤4。
步骤2（区分两种"信息流"场景）：若不是诈骗，按焦点区分。
   - 焦点在"公众群体反应 / 舆论 / 情绪 / 媒体 / 话题" → public_opinion
   - 焦点在"传播路径 / 扩散速度 / 源头溯源 / 跨域传播 / 关键节点" → event_propagation
步骤3（边界处理）：若 public_opinion 与 event_propagation 的特征同时强烈出现，
   按文本的【主焦点】判定其一，但 confidence 必须降到 0.3~0.7 区间，并在 reason 中
   简要说明这是边界案例、为何倾向某一类（1~2 句话即可，不要逐条展开分析两个场景的
   全部特征，保持精炼）。
步骤4：输出结果，并按下方【extracted_fields 规则】提取结构化字段。

【confidence 规则】
- 寒暄、无意义碎片、完全看不出安全场景 → confidence < 0.5，并在 reason 中说明信息缺失点。
- 经典诈骗话术开场白（身份冒充、历史人物冒充、冒充公检法/客服等）即使只有一句，
  也视为特征清晰：confidence 0.75~0.9。不要因为缺少转账细节就判“信息不足”。
- 输入信息不足（太短、太模糊、无任何场景特征、无法判断本质）→ confidence < 0.5，
  并在 reason 中说明信息缺失点。此时仍需给出最可能的一类，但绝不可给高置信度。
- 边界 / 混合案例（两个场景特征都明显）→ confidence 0.5~0.75。
- 特征清晰、单一主场景 → confidence 0.85~0.95。
- 绝不要为了"显得确定"而给错误的分类强加高置信度。

【extracted_summary 规则】
从原始输入中提炼出关键线索（1~2 句话或 2~3 个要点），反映"你理解到的核心信息"，
而非复述原文。例如从模糊描述里提炼出"投资理财诈骗：原始股噱头 + 高回报承诺 + 引导转账"。

【extracted_fields 规则】
根据判定出的 scenario_type，从原文中提取对应的结构化字段，用于自动填充分析表单。
只提取原文中【明确出现或可直接推断】的信息，找不到的字段一律留空字符串 ""，
绝不允许编造或猜测原文没有的具体内容（如凭空编一个平台名或人名）。

- scenario_type 为 fraud_im 时，提取：
  - chat_platform: 对话发生的平台（如"微信"、"QQ"、"短信"、"电话"），原文未提及则留空
  - suspect_identity: 嫌疑人自称或表现出的身份（如"客服"、"公检法"、"领导"），原文未提及则留空
  - fraud_type: 诈骗类别的简短描述（如"虚假征信"、"刷单返利"、"投资理财"），原文未提及则留空
- scenario_type 为 public_opinion 时，提取：
  - platform: 讨论发生的平台（如"微博"、"抖音"、"知乎"），原文未提及则留空
  - topic: 话题/关键词，10字以内的简短概括，原文未提及明确话题则留空
- scenario_type 为 event_propagation 时，提取：
  - event_name: 事件名称，15字以内的简短概括，原文未给出明确事件名则留空
  - origin: 信息起点（具体账号名，如原文只说"自媒体账号"而无具体名称，则填"自媒体账号"这类信源类型描述；完全无法判断则留空）
  - channels: 涉及的平台，多个用逗号分隔（如"微博,抖音"），原文未提及具体平台则留空

其余两个场景不适用的字段无需输出。

【输出格式】只返回一个 JSON 对象，不要任何额外文字、不要 markdown 代码块：
{
  "scenario_type": "fraud_im" 或 "public_opinion" 或 "event_propagation" 或 "unknown",
  "confidence": 0.0 到 1.0 之间的数字,
  "reason": "判定理由（中文，说明为何选这一类；边界或信息不足案例必须说明）",
  "extracted_summary": "提炼出的关键线索摘要（中文）",
  "extracted_fields": {
    "字段名": "字段值（原文未提及则为空字符串）"
  }
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
        # 分类任务只需要最终 JSON，不需要模型输出思考过程——之前没有显式关闭
        # enable_thinking 时，思考过程会占用 max_tokens 预算却被正则剥掉、完全
        # 用不上，还导致输出长度不稳定（边界案例 reason 较长时偶发被截断到
        # JSON 解析失败）。显式关闭后输出更短、更稳定。
        self._client = client
        self._owns_default_client = client is None

    @property
    def client(self) -> LLMClient:
        if self._client is None:
            self._client = LLMClient(enable_thinking=False)
        return self._client

    @classmethod
    def classify_without_llm(cls, text: str) -> Optional[ClassificationResult]:
        """Greeting / classic scam-hook path that never touches a remote model."""
        raw_text = (text or "").strip()
        if not raw_text:
            return None
        greeting = cls._match_greeting(raw_text)
        if greeting is not None:
            return greeting
        out_of_scope = cls._match_out_of_scope(raw_text)
        if out_of_scope is not None:
            return out_of_scope
        return cls._match_classic_fraud_hook(raw_text)

    def classify(self, text: str) -> ClassificationResult:
        """对一段文本进行场景分类。

        Args:
            text: 用户输入的非结构化文本。

        Returns:
            ClassificationResult: 含 scenario_type / confidence / reason /
                extracted_summary / extracted_fields。
        """
        raw_text = (text or "").strip()
        if not raw_text:
            raise ValueError("输入文本为空")

        local = self.classify_without_llm(raw_text)
        if local is not None:
            return local

        # 截断过长输入，保证响应速度
        truncated = raw_text[:_MAX_INPUT_CHARS]
        if len(raw_text) > _MAX_INPUT_CHARS:
            logger.info("输入文本过长(%d字符)，已截断至 %d 字符", len(raw_text), _MAX_INPUT_CHARS)

        messages = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _USER_PROMPT_TEMPLATE.format(text=truncated)},
        ]

        # 低温度 + 足够大的 max_tokens：deepseek-v4-flash 等推理模型会先输出
        # <think>...</think> 思考过程再给最终 JSON，思考过程本身也消耗
        # max_tokens 预算。extracted_fields 规则变长后模型思考量明显增加，
        # 768 曾把输出截断到空内容（"LLM返回的JSON格式无效: "），调大到 2048
        # 给思考+JSON 都留足空间。
        payload = self.client.chat_json(
            messages=messages,
            temperature=0.2,
            max_tokens=2048,
        )

        return self._build_result(payload)

    @staticmethod
    def _match_greeting(text: str) -> Optional[ClassificationResult]:
        if not _GREETING_PATTERN.fullmatch(text.strip()):
            return None
        return ClassificationResult(
            scenario_type="unknown",
            confidence=0.0,
            reason="这是日常寒暄，不含可分析的认知安全场景特征。",
            extracted_summary="用户正在打招呼，还没有提供对话、舆情或事件材料。",
            model="deterministic_guard",
            extracted_fields={},
        )

    @staticmethod
    def _match_out_of_scope(text: str) -> Optional[ClassificationResult]:
        raw = text or ""
        compact = re.sub(r"\s+", "", raw)
        if len(compact) < 40:
            return None
        needles = (
            "Hackathon", "Casebook", "Agent Workspace", "OpenHands", "Agent Zero",
            "规划案", "项目计划", "作品赛", "成熟模式", "案例集",
            "从300", "300+案例", "300＋案例",
        )
        hits = [item for item in needles if item.lower() in raw.lower() or item in compact]
        filename_hits = any(token in raw for token in ("_Agent_", "Casebook_20", "README"))
        if not hits and not filename_hits:
            return None
        return ClassificationResult(
            scenario_type="unknown",
            confidence=0.12,
            reason=(
                "原文更像项目规划、案例集或工程文档，而不是正在发生的诈骗对话、舆情事件或传播链。"
                f"命中标记：{'、'.join((hits or ['文档结构'])[:4])}。"
            ),
            extracted_summary="这是一份规划/案例材料，不能当成认知安全场景里的真实事件来分析。",
            model="deterministic_out_of_scope",
            extracted_fields={},
        )

    @staticmethod
    def _match_classic_fraud_hook(text: str) -> Optional[ClassificationResult]:
        compact = re.sub(r"\s+", "", text or "")
        if not compact or len(compact) > 80:
            return None
        for pattern, meta in _CLASSIC_FRAUD_HOOKS:
            if pattern.search(compact):
                return ClassificationResult(
                    scenario_type=CANONICAL_FRAUD_IM,
                    confidence=float(meta["confidence"]),
                    reason=str(meta["reason"]),
                    extracted_summary=str(meta["extracted_summary"]),
                    model="deterministic_pattern",
                    extracted_fields=dict(meta.get("extracted_fields") or {}),
                )
        return None

    # ------------------------------------------------------------------

    def _build_result(self, payload: Dict[str, Any]) -> ClassificationResult:
        """校验并归一化 LLM 返回的 JSON。"""
        scenario_type = str(payload.get("scenario_type", "")).strip()
        if scenario_type not in _VALID_SCENARIOS and scenario_type != "unknown":
            logger.warning("LLM 返回了非法 scenario_type=%r，回退到 unknown", scenario_type)
            scenario_type = "unknown"

        try:
            confidence = float(payload.get("confidence", 0.0))
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = max(0.0, min(1.0, confidence))

        reason = str(payload.get("reason", "")).strip() or "未提供理由"
        extracted_summary = str(payload.get("extracted_summary", "")).strip() or "未提炼出摘要"
        extracted_fields = self._normalize_extracted_fields(
            payload.get("extracted_fields"), scenario_type
        )

        return ClassificationResult(
            scenario_type=scenario_type,
            confidence=round(confidence, 3),
            reason=reason,
            extracted_summary=extracted_summary,
            model=getattr(self.client, "model", ""),
            extracted_fields=extracted_fields,
        )

    @staticmethod
    def _normalize_extracted_fields(raw: Any, scenario_type: str) -> Dict[str, str]:
        """只保留当前 scenario_type 允许的字段 key，值统一转成去空白字符串。

        防御性处理：LLM 偶发可能把其他场景的字段也一起返回，或返回非
        dict/非字符串的值，这里统一清洗，避免脏数据传到前端表单。
        """
        allowed_keys = _SCENARIO_FIELD_KEYS.get(scenario_type, ())
        normalized: Dict[str, str] = {key: "" for key in allowed_keys}

        if not isinstance(raw, dict):
            if raw:
                logger.warning("LLM 返回的 extracted_fields 不是 dict，已忽略: %r", raw)
            return normalized

        for key in allowed_keys:
            value = raw.get(key, "")
            if value is None:
                continue
            normalized[key] = str(value).strip()

        return normalized

"""认知画像提取模块。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import os
from pathlib import Path
import re
from typing import Any, Dict, Iterable, List, Optional

from .runtime_schema import PersonaStateVector


FEATURE_KEYS: List[str] = [
    "time_pressure",
    "financial_pressure",
    "info_asymmetry",
    "emotional_volatility",
    "cognitive_load",
    "authority_intensity",
    "authority_compliance",
    "social_proof_sensitivity",
    "scarcity_sensitivity",
    "loss_aversion_threshold",
    "gambler_fallacy",
    "trust_threshold",
    "decision_delay",
    "verification_habit",
    "help_seeking",
    "link_check_ability",
    "transaction_review",
    "prior_experience",
]

FEATURE_GROUPS: Dict[str, List[str]] = {
    "state": FEATURE_KEYS[:6],
    "vulnerability": FEATURE_KEYS[6:12],
    "protection": FEATURE_KEYS[12:18],
}

SCENARIO_KEYWORDS: Dict[str, List[str]] = {
    "虚假征信类": ["征信", "消除记录", "信用修复", "信用分", "征信中心"],
    "刷单返利类": ["刷单", "返利", "垫付", "任务单", "佣金", "做单"],
    "虚假网络投资理财类": ["投资", "理财", "带单", "内幕消息", "稳赚", "导师"],
    "冒充电商物流客服类": ["客服", "快递", "物流", "退款", "退货", "包裹异常"],
    "冒充公检法及政府机关类": ["公安", "检察院", "法院", "通缉", "洗钱", "安全账户"],
    "冒充领导熟人类": ["领导", "熟人", "老师", "朋友", "帮我转", "代付"],
    "网络游戏产品虚假交易类": ["游戏", "装备", "账号", "代练", "交易平台", "皮肤"],
    "网络婚恋交友类": ["交友", "恋爱", "网恋", "见面", "感情", "陪伴"],
    "机票退改签类": ["航班", "退改签", "机票", "改签", "航司", "客服专员"],
    "虚假贷款代办信用卡类": ["贷款", "额度", "流水", "保证金", "代办信用卡", "放款"],
}

HEURISTIC_FEATURE_RULES: Dict[str, Iterable[str]] = {
    "time_pressure": ["立即", "马上", "尽快", "限时", "最后机会", "今天内", "urgent"],
    "financial_pressure": ["收益", "返利", "贷款", "欠款", "赚钱", "垫付", "利息", "提现"],
    "info_asymmetry": ["内部", "私下", "专属", "只有我知道", "不要告诉别人", "单独联系"],
    "emotional_volatility": ["紧张", "害怕", "恐慌", "焦虑", "兴奋", "激动", "生气"],
    "cognitive_load": ["一边", "同时", "很多步骤", "验证码", "切换", "下载", "共享屏幕"],
    "authority_intensity": ["官方", "客服", "警方", "老师", "领导", "监管", "安全中心"],
    "authority_compliance": ["配合", "听从", "相信官方", "按要求做", "不敢拒绝"],
    "social_proof_sensitivity": ["大家都", "群里都在", "很多人", "朋友也做了", "都成功了"],
    "scarcity_sensitivity": ["名额", "最后", "限量", "错过", "冻结", "即将过期"],
    "loss_aversion_threshold": ["损失", "冻结", "扣费", "影响征信", "封号", "账户异常"],
    "gambler_fallacy": ["不会轮到我", "再试一次", "差一点", "回本", "这次肯定"],
    "trust_threshold": ["我就信了", "对方很专业", "头像正规", "语气官方", "没怀疑"],
    "decision_delay": ["先等等", "想一想", "缓一缓", "稍后决定", "不急着"],
    "verification_habit": ["官方渠道", "回拨", "核实", "二次确认", "客服电话", "官网"],
    "help_seeking": ["问家人", "问朋友", "请教", "找同学", "找同事"],
    "link_check_ability": ["网址", "域名", "链接", "二维码", "证书", "短信来源"],
    "transaction_review": ["转账前", "收款方", "银行卡", "核对账户", "付款备注"],
    "prior_experience": ["之前遇到过", "听过类似案例", "反诈", "被骗过", "宣传提醒"],
}

LIWC_DIMENSION_MAP: Dict[str, str] = {
    "anxiety": "emotional_volatility",
    "fear": "emotional_volatility",
    "urgency": "time_pressure",
    "money": "financial_pressure",
    "authority": "authority_intensity",
}


class LIWCAnalyzer:
    """轻量 LIWC 词典加载与频率统计。"""

    DEFAULT_LEXICON = {
        "anxiety": ["焦虑", "害怕", "恐慌", "紧张", "担心"],
        "fear": ["可怕", "吓人", "威胁", "恐惧", "慌"],
        "urgency": ["立即", "马上", "尽快", "现在", "立刻"],
        "money": ["转账", "汇款", "收益", "返利", "贷款", "赔付"],
        "authority": ["公安", "客服", "官方", "监管", "法院", "银行"],
    }

    def __init__(self, lexicon_path: Optional[str] = None):
        self.lexicon_path = lexicon_path
        self.lexicon = self._load_lexicon(lexicon_path)

    def analyze(self, text: str) -> Dict[str, float]:
        normalized = re.sub(r"\s+", "", text or "")
        total_chars = max(1, len(normalized))
        scores: Dict[str, float] = {}

        for category, keywords in self.lexicon.items():
            hits = 0
            for keyword in keywords:
                hits += normalized.count(keyword)
            scores[category] = hits / total_chars

        return scores

    def _load_lexicon(self, lexicon_path: Optional[str]) -> Dict[str, List[str]]:
        if not lexicon_path:
            return dict(self.DEFAULT_LEXICON)

        path = Path(lexicon_path)
        if not path.exists():
            return dict(self.DEFAULT_LEXICON)

        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return dict(self.DEFAULT_LEXICON)

        if isinstance(payload, dict) and "categories" in payload:
            payload = payload["categories"]

        if not isinstance(payload, dict):
            return dict(self.DEFAULT_LEXICON)

        parsed: Dict[str, List[str]] = {}
        for key, values in payload.items():
            if not isinstance(values, list):
                continue
            parsed[str(key)] = [str(item) for item in values if str(item).strip()]

        return parsed or dict(self.DEFAULT_LEXICON)


@dataclass
class CognitiveProfile:
    """18 维认知安全画像。"""

    time_pressure: float = 5.0
    financial_pressure: float = 5.0
    info_asymmetry: float = 5.0
    emotional_volatility: float = 5.0
    cognitive_load: float = 5.0
    authority_intensity: float = 5.0
    authority_compliance: float = 5.0
    social_proof_sensitivity: float = 5.0
    scarcity_sensitivity: float = 5.0
    loss_aversion_threshold: float = 5.0
    gambler_fallacy: float = 5.0
    trust_threshold: float = 5.0
    decision_delay: float = 5.0
    verification_habit: float = 5.0
    help_seeking: float = 5.0
    link_check_ability: float = 5.0
    transaction_review: float = 5.0
    prior_experience: float = 5.0
    scenario_type: str = "unknown"
    confidence_scores: Dict[str, float] = field(default_factory=dict)
    reasoning: Dict[str, str] = field(default_factory=dict)

    def overall_vulnerability_score(self) -> float:
        """计算总脆弱度分数，值越高表示越易受骗。"""
        vuln = (
            self.authority_compliance
            + self.social_proof_sensitivity
            + self.scarcity_sensitivity
            + self.loss_aversion_threshold
            + self.gambler_fallacy
            + self.trust_threshold
        ) / 6
        state = (
            self.time_pressure
            + self.financial_pressure
            + self.info_asymmetry
            + self.emotional_volatility
            + self.cognitive_load
            + self.authority_intensity
        ) / 6
        protection = (
            self.decision_delay
            + self.verification_habit
            + self.help_seeking
            + self.link_check_ability
            + self.transaction_review
            + self.prior_experience
        ) / 6
        protection = max(1.0, protection)
        score = (vuln * 0.45 + state * 0.35) / protection * 50
        return round(min(100.0, max(0.0, score)), 2)

    def protection_score(self) -> float:
        """返回保护习惯均值。"""
        total = sum(getattr(self, key) for key in FEATURE_GROUPS["protection"])
        return round(total / len(FEATURE_GROUPS["protection"]), 2)

    def to_dict(self) -> Dict[str, Any]:
        """转换为可序列化字典。"""
        payload = asdict(self)
        payload["overall_vulnerability_score"] = self.overall_vulnerability_score()
        payload["protection_score"] = self.protection_score()
        payload["dimension_details"] = {
            key: {
                "value": getattr(self, key),
                "confidence_level": self.confidence_scores.get(key, 0.0),
            }
            for key in FEATURE_KEYS
        }
        return payload

    def summary(self) -> str:
        """输出简短中文摘要。"""
        strongest_risks = sorted(
            FEATURE_GROUPS["vulnerability"] + FEATURE_GROUPS["state"],
            key=lambda item: getattr(self, item),
            reverse=True,
        )[:3]
        strongest_protections = sorted(
            FEATURE_GROUPS["protection"],
            key=lambda item: getattr(self, item),
            reverse=True,
        )[:2]
        risk_text = "、".join(f"{name}={getattr(self, name):.1f}" for name in strongest_risks)
        protection_text = "、".join(
            f"{name}={getattr(self, name):.1f}" for name in strongest_protections
        )
        return (
            f"场景类型：{self.scenario_type}；综合脆弱度 {self.overall_vulnerability_score():.1f}/100。"
            f" 主要风险维度为 {risk_text}；主要保护因子为 {protection_text}。"
        )

    def resolve_cognitive_mode(self) -> str:
        """依据 System 1 / System 2 切换条件解析当前模式。"""
        if self.time_pressure > 7 and self.emotional_volatility > 7:
            return "SYSTEM_1"
        return "SYSTEM_2"

    def to_persona_state_vector(self) -> PersonaStateVector:
        """将 18 维画像压缩为主链运行时向量。"""
        analytic_control = round(
            (
                self.decision_delay
                + self.link_check_ability
                + self.transaction_review
            ) / 3,
            2,
        )
        fomo_susceptibility = round(
            (self.scarcity_sensitivity + self.social_proof_sensitivity) / 2,
            2,
        )
        digital_trust_boundary = round(
            max(0.0, min(10.0, (10.0 - self.trust_threshold) * 0.6 + self.link_check_ability * 0.4)),
            2,
        )
        asset_sensitivity = round(
            (self.transaction_review + self.loss_aversion_threshold + self.financial_pressure) / 3,
            2,
        )
        risk_recovery_awareness = round(
            (self.prior_experience + self.help_seeking + self.verification_habit) / 3,
            2,
        )
        confidence_level = round(
            sum(self.confidence_scores.get(key, 0.45) for key in FEATURE_KEYS) / max(1, len(FEATURE_KEYS)),
            3,
        )
        system1_bias = round(
            (self.time_pressure + self.emotional_volatility + self.cognitive_load) / 3,
            2,
        )
        system2_control = round(
            (analytic_control + self.verification_habit + self.help_seeking) / 3,
            2,
        )

        return PersonaStateVector(
            authority_compliance=round(self.authority_compliance, 2),
            time_pressure_sensitivity=round(self.time_pressure, 2),
            financial_stress=round(self.financial_pressure, 2),
            loss_aversion=round(self.loss_aversion_threshold, 2),
            fomo_susceptibility=fomo_susceptibility,
            verification_habit=round(self.verification_habit, 2),
            help_seeking_tendency=round(self.help_seeking, 2),
            analytic_control=analytic_control,
            emotional_volatility=round(self.emotional_volatility, 2),
            digital_trust_boundary=digital_trust_boundary,
            asset_sensitivity=asset_sensitivity,
            risk_recovery_awareness=risk_recovery_awareness,
            confidence_level=confidence_level,
            system1_bias=system1_bias,
            system2_control=system2_control,
            cognitive_mode=self.resolve_cognitive_mode(),
            switch_policy={
                "force_system1_if": {
                    "time_pressure_gt": 7,
                    "emotional_volatility_gt": 7,
                },
                "allow_system2_reentry_if": {
                    "verification_habit_gte": 6,
                    "decision_delay_gte": 6,
                },
            },
            storage_policy={
                "default": "session_only",
                "persistent_opt_in_required": True,
                "minimal_necessary": True,
            },
            source_profile=self.to_dict(),
        )


class CognitiveProfileExtractor:
    """从场景描述中提取 18 维认知画像。"""

    EXTRACTION_PROMPT_FRAUD = """
你是一名认知安全分析师。请阅读场景，输出严格 JSON。

场景描述：
{scenario}

你必须输出：
{{
  "scenario_type": "最匹配的诈骗类别",
  "features": {{
    "time_pressure": 0-10,
    "financial_pressure": 0-10,
    "info_asymmetry": 0-10,
    "emotional_volatility": 0-10,
    "cognitive_load": 0-10,
    "authority_intensity": 0-10,
    "authority_compliance": 0-10,
    "social_proof_sensitivity": 0-10,
    "scarcity_sensitivity": 0-10,
    "loss_aversion_threshold": 0-10,
    "gambler_fallacy": 0-10,
    "trust_threshold": 0-10,
    "decision_delay": 0-10,
    "verification_habit": 0-10,
    "help_seeking": 0-10,
    "link_check_ability": 0-10,
    "transaction_review": 0-10,
    "prior_experience": 0-10
  }},
  "confidence": {{
    "time_pressure": 0-1,
    "financial_pressure": 0-1,
    "info_asymmetry": 0-1,
    "emotional_volatility": 0-1,
    "cognitive_load": 0-1,
    "authority_intensity": 0-1,
    "authority_compliance": 0-1,
    "social_proof_sensitivity": 0-1,
    "scarcity_sensitivity": 0-1,
    "loss_aversion_threshold": 0-1,
    "gambler_fallacy": 0-1,
    "trust_threshold": 0-1,
    "decision_delay": 0-1,
    "verification_habit": 0-1,
    "help_seeking": 0-1,
    "link_check_ability": 0-1,
    "transaction_review": 0-1,
    "prior_experience": 0-1
  }},
  "reasoning": {{
    "time_pressure": "简要依据",
    "financial_pressure": "简要依据"
  }}
}}

评分原则：
- 0-3: 低
- 4-6: 中
- 7-10: 高
- 保护维度分数越高表示防护越强。
- 关注诈骗类别、诱导方式、信任操纵、行动压力。
- 若场景含【受害人背景】（年龄、独居、缺少反诈教育、恐惧焦虑等），必须据此下调
  decision_delay / verification_habit / help_seeking / link_check_ability /
  transaction_review / prior_experience，不得把保护维度全部打成中性 5 分。
- 受害人背景是表单提供的已知事实，优先级高于对话里未出现的默认中性值。
""".strip()

    EXTRACTION_PROMPT_PUBLIC_OPINION = """
你是一名认知安全分析师。请阅读场景，输出严格 JSON。

当前场景为【舆情分析】，分析目标是评估公众在舆情事件中的认知脆弱性与信息处理模式。

场景描述：
{scenario}

你必须输出：
{{
  "scenario_type": "最匹配的舆情场景类型",
  "features": {{
    "time_pressure": 0-10,
    "financial_pressure": 0-10,
    "info_asymmetry": 0-10,
    "emotional_volatility": 0-10,
    "cognitive_load": 0-10,
    "authority_intensity": 0-10,
    "authority_compliance": 0-10,
    "social_proof_sensitivity": 0-10,
    "scarcity_sensitivity": 0-10,
    "loss_aversion_threshold": 0-10,
    "gambler_fallacy": 0-10,
    "trust_threshold": 0-10,
    "decision_delay": 0-10,
    "verification_habit": 0-10,
    "help_seeking": 0-10,
    "link_check_ability": 0-10,
    "transaction_review": 0-10,
    "prior_experience": 0-10
  }},
  "confidence": {{
    "time_pressure": 0-1,
    "financial_pressure": 0-1,
    "info_asymmetry": 0-1,
    "emotional_volatility": 0-1,
    "cognitive_load": 0-1,
    "authority_intensity": 0-1,
    "authority_compliance": 0-1,
    "social_proof_sensitivity": 0-1,
    "scarcity_sensitivity": 0-1,
    "loss_aversion_threshold": 0-1,
    "gambler_fallacy": 0-1,
    "trust_threshold": 0-1,
    "decision_delay": 0-1,
    "verification_habit": 0-1,
    "help_seeking": 0-1,
    "link_check_ability": 0-1,
    "transaction_review": 0-1,
    "prior_experience": 0-1
  }},
  "reasoning": {{
    "time_pressure": "简要依据",
    "financial_pressure": "简要依据"
  }}
}}

评分原则：
- 0-3: 低 / 4-6: 中 / 7-10: 高
- 保护维度分数越高表示防护越强。
- 关注叙事框架（narrative frame）、情绪（emotion）、立场（stance）、不确定性（uncertainty）、群体极化（group polarization）、权威感知（authority perception）、回应缺口（response gap）。
- 不要输出"诈骗类别"——这是舆情分析场景，不是诈骗识别。
""".strip()

    EXTRACTION_PROMPT_EVENT_PROPAGATION = """
你是一名认知安全分析师。请阅读场景，输出严格 JSON。

当前场景为【事件传播分析】，分析目标是评估信息在传播链中的认知失真风险与受众脆弱性。

场景描述：
{scenario}

你必须输出：
{{
  "scenario_type": "最匹配的传播事件类型",
  "features": {{
    "time_pressure": 0-10,
    "financial_pressure": 0-10,
    "info_asymmetry": 0-10,
    "emotional_volatility": 0-10,
    "cognitive_load": 0-10,
    "authority_intensity": 0-10,
    "authority_compliance": 0-10,
    "social_proof_sensitivity": 0-10,
    "scarcity_sensitivity": 0-10,
    "loss_aversion_threshold": 0-10,
    "gambler_fallacy": 0-10,
    "trust_threshold": 0-10,
    "decision_delay": 0-10,
    "verification_habit": 0-10,
    "help_seeking": 0-10,
    "link_check_ability": 0-10,
    "transaction_review": 0-10,
    "prior_experience": 0-10
  }},
  "confidence": {{
    "time_pressure": 0-1,
    "financial_pressure": 0-1,
    "info_asymmetry": 0-1,
    "emotional_volatility": 0-1,
    "cognitive_load": 0-1,
    "authority_intensity": 0-1,
    "authority_compliance": 0-1,
    "social_proof_sensitivity": 0-1,
    "scarcity_sensitivity": 0-1,
    "loss_aversion_threshold": 0-1,
    "gambler_fallacy": 0-1,
    "trust_threshold": 0-1,
    "decision_delay": 0-1,
    "verification_habit": 0-1,
    "help_seeking": 0-1,
    "link_check_ability": 0-1,
    "transaction_review": 0-1,
    "prior_experience": 0-1
  }},
  "reasoning": {{
    "time_pressure": "简要依据",
    "financial_pressure": "简要依据"
  }}
}}

评分原则：
- 0-3: 低 / 4-6: 中 / 7-10: 高
- 保护维度分数越高表示防护越强。
- 关注来源框架（origin framing）、失真风险（distortion risk）、传播动机（propagation motivation）、放大行为（amplification behavior）、不确定性（uncertainty）、来源可信度（source trust）。
- 不要输出"诈骗类别"——这是事件传播分析场景，不是诈骗识别。
""".strip()

    def __init__(
        self,
        llm_client: Any = None,
        scenario_defaults: Optional[Dict[str, Dict[str, float]]] = None,
        liwc_path: Optional[str] = None,
    ):
        self.llm = llm_client
        self.defaults = scenario_defaults or self._load_scenario_defaults()
        self.liwc = LIWCAnalyzer(liwc_path or os.environ.get("LIWC_DICT_PATH"))

    def extract(
        self,
        scenario: str,
        questionnaire: Optional[Dict[str, Any]] = None,
        scenario_type: Optional[str] = None,
        canonical_scenario: Optional[str] = None,
    ) -> CognitiveProfile:
        """执行认知画像提取，自动处理回退与问卷覆盖。

        Parameters
        ----------
        canonical_scenario:
            The canonical scenario (fraud_im, public_opinion, event_propagation).
            Controls which extraction prompt is used to avoid fraud-semantic
            pollution in non-fraud scenarios.
        """
        profile_text = self._compose_profile_text(scenario, questionnaire, scenario_type)
        cleaned_scenario = self._normalize_text(profile_text)
        inferred_scenario = self._resolve_fraud_subtype(
            scenario_type=scenario_type,
            questionnaire=questionnaire,
            cleaned_scenario=cleaned_scenario,
        )
        canonical = canonical_scenario or "fraud_im"

        try:
            raw_result = self._llm_extract(cleaned_scenario, canonical)
        except Exception:
            raw_result = self._heuristic_extract(cleaned_scenario, inferred_scenario)

        profile = self._build_profile(raw_result, inferred_scenario)
        self._apply_liwc_cross_validation(profile, cleaned_scenario)

        default_key = profile.scenario_type if profile.scenario_type in self.defaults else inferred_scenario
        if default_key in self.defaults:
            if profile.scenario_type not in self.defaults:
                profile.scenario_type = default_key
            for key in FEATURE_KEYS:
                confidence = profile.confidence_scores.get(key, 0.0)
                if confidence < 0.5:
                    setattr(
                        profile,
                        key,
                        self.defaults[default_key].get(key, getattr(profile, key)),
                    )
                    profile.reasoning.setdefault(key, "低置信度，已回退到场景默认值。")

        self._apply_victim_context(profile, cleaned_scenario, questionnaire)
        self._apply_dialogue_signals(profile, cleaned_scenario)

        if questionnaire:
            self._apply_questionnaire(profile, questionnaire)

        return profile

    def extract_persona_state_vector(
        self,
        scenario: str,
        questionnaire: Optional[Dict[str, Any]] = None,
        scenario_type: Optional[str] = None,
        canonical_scenario: Optional[str] = None,
    ) -> PersonaStateVector:
        """直接产出运行时画像向量。"""
        return self.extract(
            scenario=scenario,
            questionnaire=questionnaire,
            scenario_type=scenario_type,
            canonical_scenario=canonical_scenario,
        ).to_persona_state_vector()

    def detect_scenario_type(self, scenario: str) -> str:
        """根据关键词推断诈骗场景类别。"""
        text = self._normalize_text(scenario).lower()
        best_type = "unknown"
        best_score = 0
        for scenario_type, keywords in SCENARIO_KEYWORDS.items():
            score = sum(text.count(keyword.lower()) for keyword in keywords)
            if score > best_score:
                best_score = score
                best_type = scenario_type
        return best_type

    def _apply_liwc_cross_validation(self, profile: CognitiveProfile, scenario: str) -> None:
        liwc_scores = self.liwc.analyze(scenario)

        for liwc_category, feature_name in LIWC_DIMENSION_MAP.items():
            predicted = float(getattr(profile, feature_name, 5.0))
            evidence = float(liwc_scores.get(liwc_category, 0.0))
            confidence = profile.confidence_scores.get(feature_name, 0.5)

            if predicted >= 7.0 and evidence < 0.01:
                reduced = max(0.0, confidence - 0.25)
                profile.confidence_scores[feature_name] = reduced
                profile.reasoning[feature_name] = (
                    profile.reasoning.get(feature_name, "")
                    + " LIWC 交叉校验提示相关词频偏低，已下调置信度。"
                ).strip()

    def _llm_extract(self, scenario: str, canonical: str = "fraud_im") -> Dict[str, Any]:
        """调用外部 LLM 提取结构化结果。"""
        if self.llm is None:
            raise RuntimeError("未提供 LLM 客户端")

        # Select scenario-specific prompt to avoid fraud-semantic pollution
        if canonical == "public_opinion":
            prompt = self.EXTRACTION_PROMPT_PUBLIC_OPINION.format(scenario=scenario)
        elif canonical == "event_propagation":
            prompt = self.EXTRACTION_PROMPT_EVENT_PROPAGATION.format(scenario=scenario)
        else:
            prompt = self.EXTRACTION_PROMPT_FRAUD.format(scenario=scenario)
        is_local_gemma = getattr(self.llm, "mode_name", "") == "local_gemma"
        temperature = 0.0 if is_local_gemma else 0.1
        max_tokens = 192 if is_local_gemma else 4096

        if hasattr(self.llm, "chat_json"):
            return self.llm.chat_json(
                messages=[
                    {"role": "system", "content": "请返回严格 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )

        if hasattr(self.llm, "chat"):
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": "请返回严格 JSON。"},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
            )
            return self._extract_json_payload(response)

        if hasattr(self.llm, "complete"):
            response = self.llm.complete(prompt)
            text = getattr(response, "text", response)
            return self._extract_json_payload(text)

        raise RuntimeError("不支持的 LLM 客户端接口")

    def _build_profile(self, raw_result: Dict[str, Any], inferred_scenario: str) -> CognitiveProfile:
        """将原始结构化结果转换为 CognitiveProfile。"""
        features = raw_result.get("features", raw_result)
        confidence = raw_result.get("confidence", {})
        reasoning = raw_result.get("reasoning", {})
        scenario_type = raw_result.get("scenario_type") or inferred_scenario or "unknown"

        payload: Dict[str, Any] = {}
        confidence_payload: Dict[str, float] = {}
        reasoning_payload: Dict[str, str] = {}

        for key in FEATURE_KEYS:
            payload[key] = self._clip(features.get(key, 5.0), 0.0, 10.0)
            confidence_payload[key] = self._clip(confidence.get(key, 0.45), 0.0, 1.0)
            reasoning_payload[key] = str(reasoning.get(key, "未给出明确依据。"))

        return CognitiveProfile(
            **payload,
            scenario_type=scenario_type,
            confidence_scores=confidence_payload,
            reasoning=reasoning_payload,
        )

    def _heuristic_extract(self, scenario: str, inferred_scenario: str) -> Dict[str, Any]:
        """在 LLM 不可用时使用启发式规则回退。"""
        features: Dict[str, float] = {key: 5.0 for key in FEATURE_KEYS}
        confidence: Dict[str, float] = {key: 0.35 for key in FEATURE_KEYS}
        reasoning: Dict[str, str] = {}
        text = scenario.lower()

        if inferred_scenario in self.defaults:
            for key, value in self.defaults[inferred_scenario].items():
                features[key] = self._clip(value, 0.0, 10.0)
                confidence[key] = 0.45
                reasoning[key] = "匹配到诈骗类别默认画像。"

        for key, keywords in HEURISTIC_FEATURE_RULES.items():
            hits = [keyword for keyword in keywords if keyword.lower() in text]
            if not hits:
                continue
            delta = min(3.0, 0.8 * len(hits))
            if key in FEATURE_GROUPS["protection"]:
                if any(marker in text for marker in ["核实", "官方", "问家人", "等等", "回拨"]):
                    features[key] = self._clip(features[key] + delta, 0.0, 10.0)
                else:
                    features[key] = self._clip(features[key] - min(2.0, delta / 2), 0.0, 10.0)
            else:
                features[key] = self._clip(features[key] + delta, 0.0, 10.0)
            confidence[key] = min(0.78, 0.45 + 0.08 * len(hits))
            reasoning[key] = f"命中关键词：{', '.join(hits[:4])}"

        if any(word in text for word in ["转账", "付款", "汇款", "验证码"]):
            features["transaction_review"] = self._clip(
                features["transaction_review"] - 1.0,
                0.0,
                10.0,
            )
            features["cognitive_load"] = self._clip(features["cognitive_load"] + 1.2, 0.0, 10.0)
            confidence["transaction_review"] = 0.7
            confidence["cognitive_load"] = 0.7
            reasoning["transaction_review"] = "涉及支付或验证码环节，默认提高交易风险。"
            reasoning["cognitive_load"] = "涉及多步骤金融操作，认知负荷更高。"

        return {
            "scenario_type": inferred_scenario,
            "features": features,
            "confidence": confidence,
            "reasoning": reasoning,
        }

    def _compose_profile_text(
        self,
        scenario: str,
        questionnaire: Optional[Dict[str, Any]] = None,
        scenario_type: Optional[str] = None,
    ) -> str:
        """把表单侧背景拼进画像输入，但不要求调用方改主分析文本。

        前端为避免默认值污染主链 LLM，把平台/身份/受害人背景放进 questionnaire。
        画像提取必须读到这些字段，否则保护因子会停在中性 5 分。
        """
        parts = [self._normalize_text(scenario)]
        seen = set(parts)
        questionnaire = questionnaire or {}
        labeled = (
            ("[平台]", questionnaire.get("platform")),
            ("[嫌疑人身份]", questionnaire.get("attacker_role") or questionnaire.get("attackerRole")),
            ("[受害人背景]", self._questionnaire_victim_context(questionnaire)),
            ("[诈骗类别]", self._declared_fraud_subtype(questionnaire, scenario_type)),
        )
        for label, value in labeled:
            text = self._normalize_text(str(value or ""))
            if not text:
                continue
            chunk = text if text.startswith("[") else f"{label}{text}"
            if chunk in seen or text in (scenario or ""):
                continue
            parts.append(chunk)
            seen.add(chunk)
        return "\n".join(part for part in parts if part)

    def _questionnaire_victim_context(self, questionnaire: Optional[Dict[str, Any]]) -> str:
        questionnaire = questionnaire or {}
        for key in ("victim_context", "victimContext", "victim_background", "受害人背景"):
            value = questionnaire.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return ""

    def _declared_fraud_subtype(
        self,
        questionnaire: Optional[Dict[str, Any]],
        scenario_type: Optional[str],
    ) -> Optional[str]:
        questionnaire = questionnaire or {}
        candidates = [
            questionnaire.get("scenario_category"),
            questionnaire.get("fraud_type"),
            questionnaire.get("fraudType"),
            scenario_type,
        ]
        for item in candidates:
            text = str(item or "").strip()
            if text in self.defaults:
                return text
        return None

    def _resolve_fraud_subtype(
        self,
        scenario_type: Optional[str],
        questionnaire: Optional[Dict[str, Any]],
        cleaned_scenario: str,
    ) -> str:
        """优先使用用户声明的诈骗子类，避免 canonical `fraud_im` 丢掉默认画像。"""
        declared = self._declared_fraud_subtype(questionnaire, scenario_type)
        if declared:
            return declared
        detected = self.detect_scenario_type(cleaned_scenario)
        if detected != "unknown":
            return detected
        return scenario_type or "unknown"

    def _apply_victim_context(
        self,
        profile: CognitiveProfile,
        scenario: str,
        questionnaire: Optional[Dict[str, Any]] = None,
    ) -> None:
        """从受害人背景覆盖保护维度与部分易感维度。

        同时识别：
        - 原文里的 ``[受害人背景]`` 段落（原版拼装方式）
        - questionnaire.victim_context（当前前端为避免污染主链而拆出去的字段）
        """
        tagged = re.search(r"\[受害人背景\](.+?)(?:\[|$)", scenario or "", re.DOTALL)
        ctx = " ".join(
            part for part in (
                tagged.group(1).strip() if tagged else "",
                self._questionnaire_victim_context(questionnaire),
            ) if part
        ).strip()
        if not ctx:
            return

        def _set_protection(key: str, val: float, reason: str) -> None:
            current = getattr(profile, key, 5.0)
            if val < current:
                setattr(profile, key, self._clip(val, 0.0, 10.0))
                profile.confidence_scores[key] = 0.85
                profile.reasoning[key] = f"受害人背景推断: {reason}"

        def _set_risk(key: str, val: float, reason: str) -> None:
            current = getattr(profile, key, 5.0)
            if val > current:
                setattr(profile, key, self._clip(val, 0.0, 10.0))
                profile.confidence_scores[key] = 0.85
                profile.reasoning[key] = f"受害人背景推断: {reason}"

        # ── 保护因子：缺乏反诈教育 ──────────────────────────────────
        if any(kw in ctx for kw in ["缺少反诈", "缺乏反诈", "没有反诈", "反诈科普", "缺乏防范", "没有防范"]):
            _set_protection("verification_habit", 2.0, "缺乏反诈意识，不主动核验信息")
            _set_protection("prior_experience", 2.0, "无反诈科普背景，缺乏识骗经验")
            _set_protection("link_check_ability", 2.5, "反诈素养低，难以辨别链接/来源")
            _set_risk("authority_compliance", 7.5, "缺乏反诈知识使其对权威话术顺从")
            _set_risk("trust_threshold", 7.0, "缺乏防范意识导致信任阈值偏低")

        # ── 保护因子：独居 ────────────────────────────────────────────
        if any(kw in ctx for kw in ["独居", "独自生活", "一个人住", "空巢"]):
            _set_protection("help_seeking", 2.0, "独居缺乏可商量的家人/朋友")

        # ── 保护因子：年龄（数字+岁） ─────────────────────────────────
        age_m = re.search(r"(\d{2})\s*岁", ctx)
        if age_m:
            age = int(age_m.group(1))
            if age >= 60:
                _set_protection("link_check_ability", 2.0, f"{age}岁，数字技能偏弱")
                _set_protection("transaction_review", 2.5, f"{age}岁，转账前核对习惯差")
                _set_risk("authority_compliance", 8.0, f"{age}岁，对权威/客服高度顺从")
            elif age >= 50:
                _set_protection("link_check_ability", 3.0, f"{age}岁，数字技能一般")
                _set_protection("transaction_review", 3.0, f"{age}岁，转账复核意识弱")
                _set_risk("authority_compliance", 7.0, f"{age}岁，较易信任权威")

        # ── 易感维度：恐惧 / 焦虑背景 ────────────────────────────────
        if any(kw in ctx for kw in ["焦虑", "恐惧", "害怕", "担心", "不安"]):
            _set_risk("emotional_volatility", 7.5, "受害人背景描述含情绪脆弱信号")
            _set_risk("loss_aversion_threshold", 7.5, "高焦虑状态放大损失厌恶")

    def _apply_dialogue_signals(self, profile: CognitiveProfile, scenario: str) -> None:
        """让保护因子和认知模式跟随对话进展，而不是停在问卷先验。"""
        text = scenario or ""
        if not re.search(r"答应了|我答应|我同意|验证码发给|我转了|我去办|可以了", text):
            return

        def _set_protection(key: str, val: float, reason: str) -> None:
            current = getattr(profile, key, 5.0)
            if val < current:
                setattr(profile, key, self._clip(val, 0.0, 10.0))
                profile.confidence_scores[key] = 0.88
                profile.reasoning[key] = f"对话进展推断: {reason}"

        def _set_risk(key: str, val: float, reason: str) -> None:
            current = getattr(profile, key, 5.0)
            if val > current:
                setattr(profile, key, self._clip(val, 0.0, 10.0))
                profile.confidence_scores[key] = 0.88
                profile.reasoning[key] = f"对话进展推断: {reason}"

        _set_protection("decision_delay", 2.0, "受害人已口头答应，决策窗口被压缩")
        _set_protection("verification_habit", 2.2, "答应后仍未向官方渠道核验")
        _set_protection("transaction_review", 2.0, "准备按对方步骤提交验证码或账户")
        _set_risk("time_pressure", 8.2, "截止时间和名额稀缺下答应配合")
        _set_risk("emotional_volatility", 7.6, "被要求不要问同学/辅导员")
        _set_risk("authority_compliance", 8.4, "对教务或权威身份答应配合")
        _set_risk("cognitive_load", 7.5, "多步操作指令叠加")

    def _apply_questionnaire(self, profile: CognitiveProfile, questionnaire: Dict[str, Any]) -> None:
        """用问卷结果覆盖画像维度。"""
        for key, value in self._flatten_questionnaire(questionnaire).items():
            if key not in FEATURE_KEYS:
                continue
            numeric = self._coerce_numeric(value)
            if numeric is None:
                continue
            setattr(profile, key, self._clip(numeric, 0.0, 10.0))
            profile.confidence_scores[key] = 0.95
            profile.reasoning[key] = "由用户问卷直接覆盖。"

    def _flatten_questionnaire(self, payload: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
        """展开问卷字典。"""
        flattened: Dict[str, Any] = {}
        for key, value in payload.items():
            merged_key = f"{prefix}.{key}" if prefix else key
            if key in FEATURE_KEYS:
                if isinstance(value, dict) and "score" in value:
                    flattened[key] = value.get("score")
                else:
                    flattened[key] = value
                continue
            if isinstance(value, dict):
                flattened.update(self._flatten_questionnaire(value, merged_key))
        return flattened

    def _extract_json_payload(self, content: Any) -> Dict[str, Any]:
        """从文本中提取 JSON 对象。"""
        if isinstance(content, dict):
            return content

        text = getattr(content, "text", content)
        if not isinstance(text, str):
            raise ValueError("LLM 返回内容不是字符串")

        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:json)?", "", cleaned, flags=re.IGNORECASE).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", cleaned)
            if not match:
                raise
            return json.loads(match.group(0))

    def _normalize_text(self, text: Optional[str]) -> str:
        """清洗文本空白。"""
        return re.sub(r"\s+", " ", (text or "")).strip()

    def _coerce_numeric(self, value: Any) -> Optional[float]:
        """将输入转换为数字。"""
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"yes", "true", "高", "强"}:
                return 8.0
            if lowered in {"no", "false", "低", "弱"}:
                return 2.0
            try:
                return float(lowered)
            except ValueError:
                return None
        return None

    def _clip(self, value: Any, low: float, high: float) -> float:
        """裁剪到指定区间。"""
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = 5.0
        return round(min(high, max(low, numeric)), 2)

    def _load_scenario_defaults(self) -> Dict[str, Dict[str, float]]:
        """内置诈骗场景默认画像。"""
        return {
            "虚假征信类": {
                "authority_intensity": 8.5,
                "authority_compliance": 7.5,
                "time_pressure": 7.0,
                "loss_aversion_threshold": 8.0,
                "decision_delay": 3.5,
                "verification_habit": 3.5,
            },
            "刷单返利类": {
                "financial_pressure": 7.5,
                "scarcity_sensitivity": 7.5,
                "gambler_fallacy": 6.8,
                "verification_habit": 3.0,
                "transaction_review": 3.2,
            },
            "虚假网络投资理财类": {
                "financial_pressure": 8.5,
                "trust_threshold": 7.0,
                "gambler_fallacy": 7.8,
                "prior_experience": 2.5,
                "transaction_review": 3.8,
            },
            "冒充电商物流客服类": {
                "authority_intensity": 7.2,
                "time_pressure": 7.6,
                "loss_aversion_threshold": 7.3,
                "verification_habit": 3.6,
                "link_check_ability": 4.1,
            },
            "冒充公检法及政府机关类": {
                "authority_intensity": 9.2,
                "authority_compliance": 8.4,
                "emotional_volatility": 7.8,
                "decision_delay": 2.8,
                "help_seeking": 3.0,
            },
            "冒充领导熟人类": {
                "authority_compliance": 7.6,
                "trust_threshold": 7.4,
                "info_asymmetry": 7.0,
                "transaction_review": 3.8,
                "help_seeking": 3.6,
            },
            "网络游戏产品虚假交易类": {
                "scarcity_sensitivity": 7.2,
                "financial_pressure": 6.4,
                "gambler_fallacy": 6.8,
                "link_check_ability": 3.5,
                "prior_experience": 4.0,
            },
            "网络婚恋交友类": {
                "trust_threshold": 8.2,
                "emotional_volatility": 7.6,
                "help_seeking": 3.2,
                "verification_habit": 3.1,
                "decision_delay": 4.0,
            },
            "机票退改签类": {
                "time_pressure": 8.1,
                "authority_intensity": 7.0,
                "cognitive_load": 7.3,
                "verification_habit": 3.7,
                "transaction_review": 4.0,
            },
            "虚假贷款代办信用卡类": {
                "financial_pressure": 8.4,
                "loss_aversion_threshold": 7.1,
                "trust_threshold": 6.8,
                "verification_habit": 3.0,
                "transaction_review": 3.3,
            },
            "public_opinion": {
                # 舆情事件：群体情绪容易被叙事框架带动，从众效应是核心传播机制；
                # 稀缺感在舆情中相对较弱，信任门槛适中（公众对媒体/官方存疑）。
                "emotional_volatility": 6.5,
                "social_proof_sensitivity": 7.0,
                "authority_compliance": 5.0,
                "trust_threshold": 5.5,
                "scarcity_sensitivity": 3.5,
                "loss_aversion_threshold": 6.0,
            },
            "event_propagation": {
                # 信息传播场景：从众效应最显著（转发即认可），权威验证习惯偏弱；
                # 情绪化内容扩散速度更快，时间压力感适中。
                "emotional_volatility": 6.0,
                "social_proof_sensitivity": 7.5,
                "authority_compliance": 4.5,
                "trust_threshold": 5.0,
                "scarcity_sensitivity": 4.0,
                "loss_aversion_threshold": 5.5,
            },
        }

"""隐私信息脱敏模块。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any, Dict, List, Tuple

try:
    from presidio_analyzer import AnalyzerEngine
except Exception:  # pragma: no cover
    AnalyzerEngine = None


@dataclass
class SanitizedEntity:
    """脱敏实体记录。"""

    entity_type: str
    start: int
    end: int
    placeholder: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SanitizationResult:
    """脱敏输出。"""

    sanitized_text: str
    entities: List[SanitizedEntity]
    used_presidio: bool
    storage_policy: str = "session_only"
    minimal_necessary: bool = True
    retry_count: int = 0
    pii_leak_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["entities"] = [item.to_dict() for item in self.entities]
        return payload


class PrivacySanitizer:
    """优先 Presidio，回退到本地正则的脱敏器。"""

    FALLBACK_PATTERNS: Dict[str, str] = {
        "CH_ID": r"(?<!\d)\d{17}[\dXx](?!\d)",
        "CH_PHONE": r"(?<!\d)1[3-9]\d{9}(?!\d)",
        "BANK_CARD": r"(?<!\d)(?:\d[ -]?){16,19}(?!\d)",
        "AMOUNT": r"(?<!\d)\d{3,}(?:\.\d{1,2})?(?=\s*[元万块钱])",
        "PERSON_NAME": r"(?<![\w\u4e00-\u9fff])(?:[赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳唐罗薛伍余米贝姚孟顾尹江钟高夏蔡田樊胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘斜厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍郤璩桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公][\u4e00-\u9fff]{1,2})(?![\w\u4e00-\u9fff])",
    }

    PERSON_NAME_BLACKLIST: frozenset = frozenset([
        "程序", "程序员", "赵体", "赵国", "钱包", "孙子", "孙女", "孙氏",
        "李国", "李用", "周边", "周年", "吴语", "吴用", "郑重", "郑明",
        "王国", "王权", "王牌", "冯唐", "韩国", "杨树", "张贴", "张开",
        "陈述", "陈旧", "沈默", "刘海", "刘备", "蒋介", "马路", "马车",
        "唐朝", "柳树", "袁术", "朱砂", "秦朝", "许多", "徐速", "黄金",
        "蓝色", "白色", "黑色", "红色", "绿色",
        # Fraud vocabulary: the surname regex must not destroy an evidence span.
        "养卡",
    ])

    PLACEHOLDER_ZH = {
        "CH_PHONE": "某手机号",
        "BANK_CARD": "某银行卡",
        "CH_ID": "某身份证号",
        "AMOUNT": "某金额",
        "PERSON_NAME": "某姓名",
    }

    PRESIDIO_MAP: Dict[str, str] = {
        "PHONE_NUMBER": "CH_PHONE",
        "PERSON": "PERSON_NAME",
        "CREDIT_CARD": "BANK_CARD",
        "US_BANK_NUMBER": "BANK_CARD",
        "IBAN_CODE": "BANK_CARD",
        "ID_CARD": "CH_ID",
        "CN_ID": "CH_ID",
    }

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self.analyzer = AnalyzerEngine() if enabled and AnalyzerEngine is not None else None

    def sanitize(self, text: str, storage_policy: str = "session_only") -> SanitizationResult:
        source = text or ""
        if not source:
            return SanitizationResult(
                sanitized_text="",
                entities=[],
                used_presidio=False,
                storage_policy=storage_policy,
            )

        entities: List[SanitizedEntity]
        used_presidio = False

        if self.analyzer is not None:
            entities = self._detect_with_presidio(source)
            used_presidio = bool(entities)
            regex_entities = self._detect_with_regex(source)
            entities = self._merge_entities(entities + regex_entities)
        else:
            entities = self._detect_with_regex(source)

        sanitized = self._apply_replacements(source, entities)
        pii_leak_detected = self.contains_sensitive_data(sanitized)
        return SanitizationResult(
            sanitized_text=sanitized,
            entities=entities,
            used_presidio=used_presidio,
            storage_policy=storage_policy,
            minimal_necessary=True,
            retry_count=0,
            pii_leak_detected=pii_leak_detected,
        )

    def sanitize_with_retry(
        self,
        text: str,
        storage_policy: str = "session_only",
        max_retries: int = 1,
    ) -> SanitizationResult:
        """Retry once when PII still survives after sanitization."""
        result = self.sanitize(text, storage_policy=storage_policy)
        if not result.pii_leak_detected:
            return result

        attempts = 0
        while attempts < max_retries and result.pii_leak_detected:
            attempts += 1
            result = self.sanitize(result.sanitized_text, storage_policy=storage_policy)
            result.retry_count = attempts

        result.retry_count = attempts
        result.pii_leak_detected = self.contains_sensitive_data(result.sanitized_text)
        return result

    def contains_sensitive_data(self, text: str) -> bool:
        """Detect whether sensitive data still exists in text."""
        if not text:
            return False
        # The broad two-character Chinese PERSON_NAME regex is suitable for
        # replacement candidates but not for leak detection: ordinary words
        # such as “本地” or “信用” would otherwise make every analysis fail.
        for entity_type, pattern in self.FALLBACK_PATTERNS.items():
            if entity_type == "PERSON_NAME":
                continue
            if re.search(pattern, text):
                return True
        return False

    def _detect_with_presidio(self, text: str) -> List[SanitizedEntity]:
        try:
            results = self.analyzer.analyze(
                text=text,
                language="zh",
                entities=list(self.PRESIDIO_MAP.keys()),
            )
        except Exception:
            return []

        counters: Dict[str, int] = {}
        entities: List[SanitizedEntity] = []
        for item in results:
            entity_type = self.PRESIDIO_MAP.get(getattr(item, "entity_type", ""), "")
            if not entity_type:
                continue
            counters[entity_type] = counters.get(entity_type, 0) + 1
            entities.append(
                SanitizedEntity(
                    entity_type=entity_type,
                    start=int(getattr(item, "start", 0)),
                    end=int(getattr(item, "end", 0)),
                    placeholder=self._placeholder_for(entity_type, counters[entity_type]),
                )
            )
        return entities

    def _placeholder_for(self, entity_type: str, index: int) -> str:
        label = self.PLACEHOLDER_ZH.get(entity_type, entity_type)
        return label if index == 1 else f"{label}{index}"

    def _detect_with_regex(self, text: str) -> List[SanitizedEntity]:
        counters: Dict[str, int] = {}
        entities: List[SanitizedEntity] = []
        for entity_type, pattern in self.FALLBACK_PATTERNS.items():
            for match in re.finditer(pattern, text):
                start, end = match.start(), match.end()
                if end - start <= 1:
                    continue
                if entity_type == "PERSON_NAME" and text[start:end] in self.PERSON_NAME_BLACKLIST:
                    continue
                counters[entity_type] = counters.get(entity_type, 0) + 1
                entities.append(
                    SanitizedEntity(
                        entity_type=entity_type,
                        start=start,
                        end=end,
                        placeholder=self._placeholder_for(entity_type, counters[entity_type]),
                    )
                )
        return self._merge_entities(entities)

    def _merge_entities(self, entities: List[SanitizedEntity]) -> List[SanitizedEntity]:
        if not entities:
            return []
        ordered = sorted(entities, key=lambda item: (item.start, -(item.end - item.start)))
        merged: List[SanitizedEntity] = []
        current_end = -1
        for item in ordered:
            if item.start < current_end:
                continue
            merged.append(item)
            current_end = item.end
        return merged

    def _apply_replacements(self, text: str, entities: List[SanitizedEntity]) -> str:
        if not entities:
            return text

        chunks: List[str] = []
        cursor = 0
        for item in sorted(entities, key=lambda entity: entity.start):
            chunks.append(text[cursor:item.start])
            chunks.append(item.placeholder)
            cursor = item.end
        chunks.append(text[cursor:])
        return "".join(chunks)

"""Unified, provenance-first semantic quality scorer.

The scorer is intentionally independent from benchmark gold fields.  It can
score Miro-CogSec and LLM-only answers through the same code path.  Optional
embedding and NLI backends are injected (or loaded from local model paths);
when unavailable the result is explicitly labelled ``heuristic_fallback``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable, Mapping, Protocol, Sequence


SCORER_VERSION = "semantic_scorer.v2"


class EmbeddingBackend(Protocol):
    name: str

    def similarity(self, left: str, right: str) -> float: ...


class NLIBackend(Protocol):
    name: str

    def predict(self, premise: str, hypothesis: str) -> Mapping[str, float]: ...


@dataclass(frozen=True)
class SemanticScorerConfig:
    embedding_model: str | None = None
    nli_model: str | None = None
    allow_model_download: bool = False
    contradiction_cap: float = 0.25
    min_sentence_chars: int = 4


@dataclass(frozen=True)
class PairScore:
    score: float
    lexical_similarity: float
    embedding_similarity: float | None
    entailment: float
    contradiction: float
    negation_aligned: bool
    provenance: Mapping[str, Any]


_EQUIVALENCE = (
    ("辟谣", "澄清"), ("事实核查", "核验"), ("官方回应", "官方澄清"),
    ("转发", "传播"), ("扩散", "传播"), ("处置", "干预"),
    ("遏制", "干预"), ("安全建议", "安全行动"), ("风险提示", "风险提醒"),
    ("verification code", "验证码"), ("screen share", "屏幕共享"),
    ("transfer money", "转账"), ("misinformation", "失实信息"),
)

_NEGATIONS = ("不", "未", "无", "没有", "尚未", "无需", "并非", "不能", "不可")
_ACTION_TERMS = (
    "停止", "暂停", "核验", "联系", "保存", "截图", "举报", "报警", "澄清",
    "标注", "提醒", "复核", "观察", "限制", "冻结", "删除", "封禁", "不要",
)
_GROUNDING_EXEMPT = ("建议", "可以", "应当", "请", "不要", "先", "若", "如果")
_SEVERE_ACTIONS = ("封禁", "删除全部", "全面下架", "冻结账户", "立即报警", "强制限制", "永久限制")
_RISK_CUES = (
    "转账", "汇款", "验证码", "密码", "屏幕共享", "远程控制", "下载", "安全账户",
    "失实", "谣言", "误传", "伪造", "冒充", "威胁", "泄露", "诈骗", "攻击",
)
_CLAIM_CONCEPTS = {
    "money_transfer": ("转账", "汇款", "付款", "安全账户"),
    "credential": ("验证码", "密码", "银行卡号", "账户资料"),
    "remote_control": ("屏幕共享", "远程控制", "远程协助"),
    "confirmed_false": ("已证实为谣言", "确定是谣言", "已经证实失实", "确认造假"),
    "law_enforcement": ("公安", "警方", "检察院", "法院"),
}


def _normalise(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, sort_keys=True)
    text = re.sub(r"\s+", " ", text).strip().lower()
    for source, target in _EQUIVALENCE:
        text = text.replace(source.lower(), target.lower())
    return text


def _vector(text: str) -> Counter[str]:
    compact = re.sub(r"\s+", "", _normalise(text))
    result: Counter[str] = Counter()
    for token in re.findall(r"[a-z0-9_]+", compact):
        result[f"t:{token}"] += 2.0
    for size, weight in ((1, 0.35), (2, 1.4), (3, 1.0), (4, 0.65)):
        for index in range(max(0, len(compact) - size + 1)):
            gram = compact[index:index + size]
            if any("\u4e00" <= char <= "\u9fff" for char in gram):
                result[f"g{size}:{gram}"] += weight
    return result


def _cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left and not right:
        return 1.0
    if not left or not right:
        return 0.0
    numerator = sum(left[key] * right[key] for key in set(left) | set(right))
    denominator = math.sqrt(sum(value * value for value in left.values())) * math.sqrt(
        sum(value * value for value in right.values())
    )
    return float(numerator / denominator) if denominator else 0.0


def _negated(text: str) -> bool:
    normalised = _normalise(text)
    return any(token in normalised for token in _NEGATIONS)


def _heuristic_nli(premise: str, hypothesis: str) -> dict[str, float]:
    similarity = _cosine(_vector(premise), _vector(hypothesis))
    negation_mismatch = _negated(premise) != _negated(hypothesis) and similarity >= 0.35
    contradiction = min(1.0, 0.55 + similarity * 0.45) if negation_mismatch else 0.0
    entailment = max(0.0, similarity * (0.3 if negation_mismatch else 1.0))
    neutral = max(0.0, 1.0 - max(entailment, contradiction))
    total = max(1e-9, entailment + contradiction + neutral)
    return {
        "entailment": entailment / total,
        "contradiction": contradiction / total,
        "neutral": neutral / total,
    }


class SentenceTransformerEmbeddingBackend:
    """Lazy sentence-transformers backend; local-only unless explicitly allowed."""

    def __init__(self, model: str, *, allow_download: bool = False):
        from sentence_transformers import SentenceTransformer

        self.name = model
        self._model = SentenceTransformer(model, local_files_only=not allow_download)

    def similarity(self, left: str, right: str) -> float:
        vectors = self._model.encode([left, right], normalize_embeddings=True)
        return max(-1.0, min(1.0, float(vectors[0] @ vectors[1])))


class CrossEncoderNLIBackend:
    """Lazy Hugging Face sequence-classification NLI backend."""

    def __init__(self, model: str, *, allow_download: bool = False):
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        import torch

        self.name = model
        self._torch = torch
        self._tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=not allow_download)
        self._model = AutoModelForSequenceClassification.from_pretrained(
            model, local_files_only=not allow_download
        )
        self._model.eval()
        raw_map = getattr(self._model.config, "id2label", {}) or {}
        self._labels = {int(key): str(value).lower() for key, value in raw_map.items()}

    def predict(self, premise: str, hypothesis: str) -> Mapping[str, float]:
        inputs = self._tokenizer(premise, hypothesis, return_tensors="pt", truncation=True)
        with self._torch.inference_mode():
            logits = self._model(**inputs).logits[0]
        probabilities = self._torch.softmax(logits, dim=-1).tolist()
        result = {"entailment": 0.0, "contradiction": 0.0, "neutral": 0.0}
        for index, probability in enumerate(probabilities):
            label = self._labels.get(index, "")
            matched = next((name for name in result if name in label), None)
            if matched:
                result[matched] = float(probability)
        if not any(result.values()) and len(probabilities) == 3:
            result = {
                "contradiction": float(probabilities[0]),
                "neutral": float(probabilities[1]),
                "entailment": float(probabilities[2]),
            }
        return result


class SemanticScorerV2:
    def __init__(
        self,
        config: SemanticScorerConfig | None = None,
        *,
        embedder: EmbeddingBackend | None = None,
        nli: NLIBackend | None = None,
    ):
        self.config = config or SemanticScorerConfig()
        self.embedder = embedder
        self.nli = nli
        self.load_errors: list[str] = []
        if self.embedder is None and self.config.embedding_model:
            try:
                self.embedder = SentenceTransformerEmbeddingBackend(
                    self.config.embedding_model,
                    allow_download=self.config.allow_model_download,
                )
            except Exception as exc:  # optional backend must not block evaluation
                self.load_errors.append(f"embedding:{type(exc).__name__}")
        if self.nli is None and self.config.nli_model:
            try:
                self.nli = CrossEncoderNLIBackend(
                    self.config.nli_model,
                    allow_download=self.config.allow_model_download,
                )
            except Exception as exc:
                self.load_errors.append(f"nli:{type(exc).__name__}")

    def score_pair(self, reference: Any, candidate: Any) -> PairScore:
        left, right = _normalise(reference), _normalise(candidate)
        lexical = _cosine(_vector(left), _vector(right))
        embedding = self.embedder.similarity(left, right) if self.embedder else None
        nli_scores = dict(self.nli.predict(left, right)) if self.nli else _heuristic_nli(left, right)
        entailment = float(nli_scores.get("entailment", 0.0))
        contradiction = float(nli_scores.get("contradiction", 0.0))
        components = [(lexical, 0.35), (entailment, 0.30)]
        if embedding is not None:
            components.append(((embedding + 1.0) / 2.0, 0.35))
        else:
            components.append((lexical, 0.35))
        score = sum(value * weight for value, weight in components) / sum(weight for _, weight in components)
        negation_aligned = _negated(left) == _negated(right)
        if contradiction >= 0.5 or not negation_aligned:
            score = min(score, self.config.contradiction_cap)
        return PairScore(
            score=round(max(0.0, min(1.0, score)), 6),
            lexical_similarity=round(lexical, 6),
            embedding_similarity=None if embedding is None else round(float(embedding), 6),
            entailment=round(entailment, 6),
            contradiction=round(contradiction, 6),
            negation_aligned=negation_aligned,
            provenance=self.provenance(),
        )

    def score_response(self, *, source: str, answer: str, scenario_type: str = "") -> dict[str, Any]:
        source_text = _normalise(source)
        answer_text = _normalise(answer)
        sentences = [
            item.strip() for item in re.split(r"[。！？!?；;\n]+", answer_text)
            if len(item.strip()) >= self.config.min_sentence_chars
        ]
        factual_sentences = [item for item in sentences if not item.startswith(_GROUNDING_EXEMPT)]
        support_scores = [self.score_pair(source_text, sentence).score for sentence in factual_sentences]
        groundedness = sum(support_scores) / len(support_scores) if support_scores else 1.0

        action_hits = sorted({term for term in _ACTION_TERMS if term in answer_text})
        has_channel = any(term in answer_text for term in ("官方", "平台", "银行", "公安", "客服", "原始来源"))
        has_sequence = any(term in answer_text for term in ("先", "再", "随后", "第一", "第二", "立即"))
        actionability = min(1.0, len(action_hits) / 3.0 + 0.18 * has_channel + 0.15 * has_sequence)

        hallucinated_concepts = []
        for concept, terms in _CLAIM_CONCEPTS.items():
            if any(term in answer_text for term in terms) and not any(term in source_text for term in terms):
                hallucinated_concepts.append(concept)
        hallucination_penalty = min(1.0, len(hallucinated_concepts) / 3.0)

        risk_supported = any(term in source_text for term in _RISK_CUES)
        severe_hits = sorted({term for term in _SEVERE_ACTIONS if term in answer_text})
        over_intervention_penalty = min(1.0, len(severe_hits) * (0.25 if risk_supported else 0.65))
        if scenario_type == "fraud_im" and risk_supported:
            over_intervention_penalty *= 0.6

        contradiction = max(
            (self.score_pair(source_text, sentence).contradiction for sentence in factual_sentences),
            default=0.0,
        )
        quality = (
            0.42 * groundedness
            + 0.25 * actionability
            + 0.18 * (1.0 - hallucination_penalty)
            + 0.15 * (1.0 - over_intervention_penalty)
        )
        quality *= 1.0 - min(0.7, contradiction * 0.7)
        return {
            "schema_version": SCORER_VERSION,
            "quality_score": round(max(0.0, min(1.0, quality)), 6),
            "groundedness": round(groundedness, 6),
            "actionability": round(actionability, 6),
            "hallucination_penalty": round(hallucination_penalty, 6),
            "over_intervention_penalty": round(over_intervention_penalty, 6),
            "contradiction": round(contradiction, 6),
            "diagnostics": {
                "action_terms": action_hits,
                "hallucinated_concepts": hallucinated_concepts,
                "severe_actions": severe_hits,
                "factual_sentence_count": len(factual_sentences),
            },
            "provenance": self.provenance(),
        }

    def provenance(self) -> dict[str, Any]:
        return {
            "scorer_version": SCORER_VERSION,
            "embedding_backend": getattr(self.embedder, "name", None),
            "nli_backend": getattr(self.nli, "name", None),
            "mode": "model_augmented" if self.embedder or self.nli else "heuristic_fallback",
            "load_errors": list(self.load_errors),
            "config_hash": hashlib.sha256(
                json.dumps(asdict(self.config), sort_keys=True).encode("utf-8")
            ).hexdigest()[:16],
        }


def evaluate_records(
    records: Iterable[Mapping[str, Any]],
    *,
    scorer: SemanticScorerV2,
    system_name: str,
    source_field: str = "input",
    answer_field: str = "assistant_message",
    scenario_field: str = "scenario_type",
) -> dict[str, Any]:
    per_case = []
    for index, record in enumerate(records):
        source_value = record.get(source_field, "")
        if isinstance(source_value, Mapping):
            source_value = source_value.get("text") or source_value.get("scenario") or source_value
        answer_value = record.get(answer_field, "")
        if isinstance(answer_value, Mapping):
            answer_value = answer_value.get("assistant_message") or answer_value.get("text") or answer_value
        score = scorer.score_response(
            source=_normalise(source_value),
            answer=_normalise(answer_value),
            scenario_type=str(record.get(scenario_field) or record.get("scenario") or ""),
        )
        per_case.append({
            "case_id": record.get("case_id") or record.get("id") or f"row-{index + 1}",
            "system": system_name,
            **score,
        })
    metric_names = (
        "quality_score", "groundedness", "actionability", "hallucination_penalty",
        "over_intervention_penalty", "contradiction",
    )
    summary = {
        name: round(sum(float(item[name]) for item in per_case) / max(1, len(per_case)), 6)
        for name in metric_names
    }
    return {
        "schema_version": SCORER_VERSION,
        "system": system_name,
        "cases": len(per_case),
        "summary": summary,
        "provenance": scorer.provenance(),
        "per_case": per_case,
    }


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


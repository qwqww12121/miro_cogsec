"""Evidence-bound semantic frames for benchmark-facing CogSec analysis.

This module is deliberately narrow: it does not write the final answer and it
does not replace MIROFISH counterfactual or propagation logic.  Its job is to
turn the original text into a small semantic frame that downstream FORK,
counterfactual, and OASIS-facing adapters can consume.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional


RISK_LEVELS = {"none", "low", "medium", "high", "critical"}
TRUTHY = {"1", "true", "yes", "on", "enabled"}


def semantic_frame_enabled() -> bool:
    """Return True only when the caller explicitly enables LLM extraction."""
    return str(os.environ.get("MIRO_SEMANTIC_FRAME_ENABLED", "")).strip().lower() in TRUTHY


def extract_semantic_frame(
    *,
    text: str,
    scenario: str,
    runtime_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Extract and validate a semantic frame from source text.

    The function is opt-in because normal backend tests and offline runs should
    not perform network calls.  When disabled or unavailable, it returns a
    provenance-only frame and lets the existing runtime adapter path continue.
    """
    if not semantic_frame_enabled():
        return _disabled_frame("disabled")

    api_key = (
        os.environ.get("MIRO_SEMANTIC_FRAME_API_KEY")
        or os.environ.get("JUDGE_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        return _disabled_frame("missing_api_key")

    model = (
        os.environ.get("MIRO_SEMANTIC_FRAME_MODEL")
        or os.environ.get("JUDGE_MODEL_NAME")
        or os.environ.get("JUDGE_MODEL")
        or os.environ.get("LLM_MODEL_NAME")
        or "deepseek-v4-flash"
    )
    base_url = os.environ.get("MIRO_SEMANTIC_FRAME_BASE_URL") or os.environ.get("JUDGE_BASE_URL") or os.environ.get("LLM_BASE_URL")
    timeout = _int_env("MIRO_SEMANTIC_FRAME_TIMEOUT", 90)
    try:
        raw = _call_openai_compatible(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=_messages_for(text=text, scenario=scenario, runtime_context=runtime_context),
            timeout=timeout,
        )
        parsed = _parse_json(raw)
        frame = validate_semantic_frame(parsed, text=text, scenario=scenario)
        frame["provenance"] = {
            **_first_dict(frame.get("provenance")),
            "source": "llm_semantic_frame",
            "model": model,
            "evidence_policy": "exact_substring_only",
        }
        return frame
    except Exception as exc:  # pragma: no cover - network errors are environment-dependent.
        return {
            "available": False,
            "scenario": scenario,
            "risk_level": "low",
            "evidence_spans": [],
            "provenance": {
                "source": "llm_semantic_frame_error",
                "error_type": exc.__class__.__name__,
                "message": str(exc)[:240],
            },
        }


def validate_semantic_frame(frame: Dict[str, Any], *, text: str, scenario: str) -> Dict[str, Any]:
    """Normalize model output and drop unsupported evidence spans."""
    if not isinstance(frame, dict):
        frame = {}
    normalized = json.loads(json.dumps(frame, ensure_ascii=False))
    normalized["available"] = True
    normalized["scenario"] = scenario
    normalized["risk_level"] = _normalize_risk(normalized.get("risk_level"))
    normalized["is_harmful"] = bool(normalized.get("is_harmful", normalized["risk_level"] in {"medium", "high", "critical"}))

    _validate_nested_evidence(normalized, text)
    collected = _collect_nested_evidence(normalized)
    if not collected:
        collected = _fallback_evidence_clauses(text)
    normalized["evidence_spans"] = _unique([span for span in collected if span in text])[:8]
    return normalized


def has_semantic_content(frame: Optional[Dict[str, Any]]) -> bool:
    """True when an LLM semantic frame is available and evidence-bound."""
    if not isinstance(frame, dict) or not frame.get("available"):
        return False
    provenance = _first_dict(frame.get("provenance"))
    return provenance.get("source") == "llm_semantic_frame"


def _messages_for(*, text: str, scenario: str, runtime_context: Optional[Dict[str, Any]]) -> List[Dict[str, str]]:
    runtime_hint = _compact_runtime_hint(runtime_context or {})
    system = (
        "You extract evidence-bound semantic frames for MIROFISH cognitive-security analysis. "
        "You are not the final answer writer. Do not use hidden reference answers, benchmark labels, or external facts. "
        "Use only the original input text. Every evidence_spans item must be an exact substring copied from the input. "
        "All free-text string values must be written in Chinese. Keep only enum values in English. "
        "Return only strict JSON."
    )
    user = {
        "scenario": scenario,
        "original_text": text,
        "runtime_hint": runtime_hint,
        "task": (
            "Extract a compact semantic frame. Prefer abstract mechanism labels over surface keywords. "
            "The downstream system will use this for FORK generation, MIROFISH counterfactual paths, and OASIS-style propagation. "
            "For public_opinion and event_propagation, risk_level should reflect mechanism severity: raise it when unverified or contested claims are amplified, strong emotion/polarization is present, official information is absent, context is lost, or correction cannot bind to the original spread. Use low only when the source is reliable, context is preserved, and no meaningful distortion or mobilization appears."
        ),
        "schema": {
            "risk_level": "one of: none, low, medium, high, critical",
            "is_harmful": "boolean",
            "risk_type": "short mechanism-oriented subtype, or no_risk_signal",
            "summary": "one sentence grounded in the input",
            "actors": [{"role": "source|target|amplifier|authority|public|other", "description": "", "evidence_spans": []}],
            "claims": [{"claim": "", "certainty": "confirmed|unverified|contested|unknown", "risk": "", "evidence_spans": []}],
            "requested_actions": [{"action": "", "object": "", "risk_if_followed": "", "evidence_spans": []}],
            "assets": [{"type": "funds|identity|credentials|device|account|reputation|public_safety|trust|other", "description": "", "severity": 0.0, "evidence_spans": []}],
            "fork_candidates": [
                {
                    "type": "mechanism-oriented fork name",
                    "trigger": "what decision or propagation moment creates divergence",
                    "unsafe_branch": ["specific high-risk path steps"],
                    "safe_branch": ["specific safer path steps"],
                    "intervention_window": {
                        "start_turn": 0,
                        "end_turn": 1,
                        "open_stage": "",
                        "close_stage": "",
                        "label": "",
                        "rationale": "",
                    },
                    "evidence_spans": [],
                }
            ],
            "propagation": {
                "origin": {"description": "", "evidence_spans": []},
                "amplifiers": [{"description": "", "evidence_spans": []}],
                "path_steps": [{"step": 1, "action": "", "risk_state": "", "evidence_spans": []}],
                "distortions": [{"description": "", "severity": 0.0, "evidence_spans": []}],
                "corrections": [{"description": "", "evidence_spans": []}],
                "emotion": {"dominant_emotion": "neutral|anger|anxiety|fear|confusion|polarization", "amplification_level": "low|medium|high|critical", "rationale": "", "evidence_spans": []},
                "uncertainties": [{"description": "", "evidence_spans": []}],
                "official_gap": {"status": "none|present|unclear", "severity": 0.0, "description": "", "evidence_spans": []},
            },
            "intervention_action": "system/operator action for the earliest useful intervention",
            "warning": "one concise user-facing warning if applicable",
            "safe_action": "one concise action grounded in the semantic frame",
            "confidence": 0.0,
        },
    }
    return [{"role": "system", "content": system}, {"role": "user", "content": json.dumps(user, ensure_ascii=False)}]


def _call_openai_compatible(
    *,
    api_key: str,
    base_url: Optional[str],
    model: str,
    messages: List[Dict[str, str]],
    timeout: int,
) -> str:
    from openai import OpenAI

    kwargs: Dict[str, Any] = {"api_key": api_key, "timeout": timeout}
    if base_url:
        kwargs["base_url"] = base_url
    client = OpenAI(**kwargs)
    request: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
    }
    try:
        response = client.chat.completions.create(**request, response_format={"type": "json_object"})
    except Exception:
        response = client.chat.completions.create(**request)
    return response.choices[0].message.content or "{}"


def _parse_json(text: str) -> Dict[str, Any]:
    text = (text or "{}").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        parsed = json.loads(text[start : end + 1]) if start >= 0 and end > start else {}
    return parsed if isinstance(parsed, dict) else {}


def _validate_nested_evidence(value: Any, source_text: str) -> None:
    if isinstance(value, dict):
        for key, item in list(value.items()):
            if key == "evidence_spans":
                value[key] = _valid_spans(item, source_text)
            else:
                _validate_nested_evidence(item, source_text)
    elif isinstance(value, list):
        for item in value:
            _validate_nested_evidence(item, source_text)


def _collect_nested_evidence(value: Any) -> List[str]:
    spans: List[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if key == "evidence_spans":
                spans.extend(str(span) for span in item if span)
            else:
                spans.extend(_collect_nested_evidence(item))
    elif isinstance(value, list):
        for item in value:
            spans.extend(_collect_nested_evidence(item))
    return _unique(spans)


def _valid_spans(value: Any, source_text: str) -> List[str]:
    spans = value if isinstance(value, list) else []
    repaired: List[str] = []
    for raw in spans:
        span = str(raw or "").strip().strip("「」\"'")
        if not span:
            continue
        if span in source_text:
            repaired.append(span)
            continue
        clipped = span.strip("，。！？；:：、,.!?; ")
        if clipped and clipped in source_text:
            repaired.append(clipped)
            continue
        for part in _split_clauses(span):
            if len(part) >= 4 and part in source_text:
                repaired.append(part)
    return _unique(repaired)


def _fallback_evidence_clauses(text: str) -> List[str]:
    return _split_clauses(text)[:3]


def _split_clauses(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"[。！？；;，,]", text or "") if part.strip()]


def _normalize_risk(value: Any) -> str:
    raw = str(value or "").strip().lower()
    mapping = {
        "无": "none",
        "无风险": "none",
        "低": "low",
        "低风险": "low",
        "中": "medium",
        "中风险": "medium",
        "高": "high",
        "高风险": "high",
        "极高": "critical",
        "严重": "critical",
    }
    if raw in RISK_LEVELS:
        return raw
    return mapping.get(raw, "medium")


def _compact_runtime_hint(runtime_context: Dict[str, Any]) -> Dict[str, Any]:
    graph = _first_dict(runtime_context.get("risk_graph_bundle"), runtime_context.get("graph"))
    fork = _first_dict(runtime_context.get("fork_comparison"))
    scenario_ext = _first_dict(runtime_context.get("scenario_extension"))
    return {
        "runtime_fork_type": fork.get("fork_point_type"),
        "runtime_risk_level": _first_dict(_first_dict(runtime_context.get("metrics")).get("risk_breakdown")).get("risk_level"),
        "has_rag": bool(graph.get("attack_strategy_chain") or graph.get("evidence_items")),
        "has_propagation": bool(scenario_ext.get("propagation")),
        "has_intervention_search": bool(scenario_ext.get("propagation_intervention_search")),
    }


def _disabled_frame(reason: str) -> Dict[str, Any]:
    return {
        "available": False,
        "scenario": None,
        "risk_level": "low",
        "evidence_spans": [],
        "provenance": {"source": reason},
    }


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _first_dict(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _unique(items: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen: set[str] = set()
    for item in items:
        text = str(item).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        output.append(text)
    return output

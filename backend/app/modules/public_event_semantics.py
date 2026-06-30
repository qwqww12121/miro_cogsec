"""Specialized evidence-bound semantics for public/event propagation.

The generic semantic frame is good enough for fraud FORK generation, but public
opinion and event propagation need richer propagation-native structure before
MIROFISH/OASIS can reason well.  This module extracts that structure without
writing final judge reports.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, Iterable, List, Optional


SCENARIOS = {"public_opinion", "event_propagation"}
RISK_LEVELS = {"none", "low", "medium", "high", "critical"}
TRUTHY = {"1", "true", "yes", "on", "enabled"}


def public_event_frame_enabled() -> bool:
    return str(os.environ.get("MIRO_PUBLIC_EVENT_FRAME_ENABLED", "")).strip().lower() in TRUTHY


def extract_public_event_frame(
    *,
    text: str,
    scenario: str,
    runtime_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if scenario not in SCENARIOS:
        return _disabled_frame("unsupported_scenario", scenario)
    embedded = _embedded_public_event_frame(runtime_context or {}, scenario)
    if embedded:
        return validate_public_event_frame(embedded, text=text, scenario=scenario)
    if not public_event_frame_enabled():
        return _disabled_frame("disabled", scenario)

    api_key = (
        os.environ.get("MIRO_PUBLIC_EVENT_FRAME_API_KEY")
        or os.environ.get("MIRO_SEMANTIC_FRAME_API_KEY")
        or os.environ.get("JUDGE_API_KEY")
        or os.environ.get("LLM_API_KEY")
        or os.environ.get("OPENAI_API_KEY")
    )
    if not api_key:
        return _disabled_frame("missing_api_key", scenario)

    model = (
        os.environ.get("MIRO_PUBLIC_EVENT_FRAME_MODEL")
        or os.environ.get("MIRO_SEMANTIC_FRAME_MODEL")
        or os.environ.get("JUDGE_MODEL_NAME")
        or os.environ.get("JUDGE_MODEL")
        or os.environ.get("LLM_MODEL_NAME")
        or "deepseek-v4-flash"
    )
    base_url = os.environ.get("MIRO_PUBLIC_EVENT_FRAME_BASE_URL") or os.environ.get("JUDGE_BASE_URL") or os.environ.get("LLM_BASE_URL")
    timeout = _int_env("MIRO_PUBLIC_EVENT_FRAME_TIMEOUT", 90)
    try:
        raw = _call_openai_compatible(
            api_key=api_key,
            base_url=base_url,
            model=model,
            messages=_messages_for(text=text, scenario=scenario, runtime_context=runtime_context or {}),
            timeout=timeout,
        )
        parsed = _parse_json(raw)
        frame = validate_public_event_frame(parsed, text=text, scenario=scenario)
        frame["provenance"] = {
            **_first_dict(frame.get("provenance")),
            "source": "llm_public_event_frame",
            "model": model,
            "evidence_policy": "exact_substring_only",
        }
        return frame
    except Exception as exc:  # pragma: no cover - network behavior varies by environment.
        return {
            "available": False,
            "scenario": scenario,
            "risk_level": "low",
            "evidence_spans": [],
            "provenance": {
                "source": "llm_public_event_frame_error",
                "error_type": exc.__class__.__name__,
                "message": str(exc)[:240],
            },
        }


def validate_public_event_frame(frame: Dict[str, Any], *, text: str, scenario: str) -> Dict[str, Any]:
    if not isinstance(frame, dict):
        frame = {}
    normalized = json.loads(json.dumps(frame, ensure_ascii=False))
    normalized["available"] = True
    normalized["scenario"] = scenario
    normalized["risk_level"] = _normalize_risk(normalized.get("risk_level"))
    _validate_nested_evidence(normalized, text)
    evidence = _collect_nested_evidence(normalized)
    if not evidence:
        evidence = _split_clauses(text)[:3]
    normalized["evidence_spans"] = _unique([span for span in evidence if span in text])[:10]
    return normalized


def has_public_event_content(frame: Optional[Dict[str, Any]]) -> bool:
    if not isinstance(frame, dict) or not frame.get("available"):
        return False
    return _first_dict(frame.get("provenance")).get("source") == "llm_public_event_frame"


def _embedded_public_event_frame(runtime_context: Dict[str, Any], scenario: str) -> Dict[str, Any]:
    cogsec = _first_dict(runtime_context.get("cogsec_analysis"))
    frame = _first_dict(cogsec.get("public_event_frame"))
    if frame.get("scenario") == scenario and _first_dict(frame.get("provenance")).get("source") == "llm_public_event_frame":
        return frame
    frame = _first_dict(runtime_context.get("public_event_frame"))
    if frame.get("scenario") == scenario and _first_dict(frame.get("provenance")).get("source") == "llm_public_event_frame":
        return frame
    return {}


def _messages_for(*, text: str, scenario: str, runtime_context: Dict[str, Any]) -> List[Dict[str, str]]:
    system = (
        "You extract propagation-native semantic frames for MIROFISH/OASIS cognitive-security analysis. "
        "You are not the final answer writer. Use only the original input. "
        "Every evidence_spans item must be an exact substring copied from the input. "
        "All free-text values must be Chinese. Keep enum keys/values short and stable. Return strict JSON only."
    )
    if scenario == "public_opinion":
        schema = {
            "risk_level": "none|low|medium|high|critical",
            "summary": "一句话概述公共讨论",
            "narrative_claims": [
                {
                    "claim": "被传播或争议的具体说法",
                    "evidence_state": "confirmed|unverified|contested|unclear",
                    "why_risky": "为什么会造成误解、极化、恐慌或错误行动",
                    "evidence_spans": [],
                }
            ],
            "stance_dynamics": [
                {
                    "group": "支持者/反对者/旁观者/媒体/公众等",
                    "interpretation": "该群体如何理解该说法",
                    "reaction": "该群体如何放大、反驳或情绪化处理",
                    "evidence_spans": [],
                }
            ],
            "uncertainty_nodes": [
                {
                    "missing_fact": "缺失或未核验的关键事实",
                    "why_it_matters": "该缺口如何改变公众判断",
                    "evidence_spans": [],
                }
            ],
            "emotion_dynamics": {
                "dominant_emotion": "neutral|anger|anxiety|fear|confusion|polarization",
                "amplification_level": "low|medium|high|critical",
                "rationale": "",
                "evidence_spans": [],
            },
            "authority_gap": {
                "status": "none|present|unclear",
                "missing_response": "还缺什么权威信息；无缺口时说明无明显缺口",
                "severity": 0.0,
                "recommended_response": "权威方应发布或补充什么",
                "evidence_spans": [],
            },
            "intervention_plan": {
                "window_label": "",
                "open_stage": "",
                "close_stage": "",
                "actor_actions": [
                    {
                        "actor": "official|platform|media|community|public",
                        "target_surface": "原帖/热评/转发入口/媒体报道/搜索入口等",
                        "action": "",
                        "expected_effect": "",
                    }
                ],
                "public_actions": [],
                "evidence_spans": [],
            },
            "mechanism_summary": "用2-3句解释叙事如何从证据缺口/情绪/立场动态走向风险或稳定",
            "confidence": 0.0,
        }
    else:
        schema = {
            "risk_level": "none|low|medium|high|critical",
            "summary": "一句话概述事件传播",
            "origin": {"description": "", "evidence_spans": []},
            "amplifiers": [{"description": "", "role": "media|personal|community|influencer|cross_platform|official|other", "evidence_spans": []}],
            "propagation_steps": [
                {
                    "step": 1,
                    "actor": "",
                    "action": "",
                    "transformation": "新增、删除、裁剪、纠正或保持了什么信息",
                    "risk_state": "low|medium|high|critical",
                    "evidence_spans": [],
                }
            ],
            "distortion_points": [
                {
                    "type": "identity_error|time_loss|location_loss|context_loss|judgmental_framing|overgeneralization|none|other",
                    "description": "",
                    "severity": 0.0,
                    "evidence_spans": [],
                }
            ],
            "correction_status": {
                "has_correction": False,
                "binding_problem": "纠偏是否能绑定原始传播；没有纠偏时说明无纠偏",
                "evidence_spans": [],
            },
            "containment_plan": {
                "open_step": 1,
                "close_step": 2,
                "label": "",
                "actor_actions": [
                    {
                        "actor": "official|platform|media|community|source|public",
                        "target_surface": "原帖/截图/转发链/高影响节点/群组转发等",
                        "action": "",
                        "expected_effect": "",
                    }
                ],
                "evidence_spans": [],
            },
            "mechanism_summary": "用2-3句解释传播链中哪个转化造成风险，以及如何遏制",
            "confidence": 0.0,
        }
    user = {
        "scenario": scenario,
        "original_text": text,
        "runtime_hint": _compact_runtime_hint(runtime_context),
        "instruction": (
            "Extract a propagation-native frame for downstream MIROFISH/OASIS use. "
            "Do not make a generic safety report. Do not use reference answers. "
            "Be specific about who amplifies what, what changed, which uncertainty matters, and where intervention should attach."
        ),
        "schema": schema,
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
    request: Dict[str, Any] = {"model": model, "messages": messages, "temperature": 0.0}
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
    output: List[str] = []
    for raw in spans:
        span = str(raw or "").strip().strip("「」\"'")
        if not span:
            continue
        if span in source_text:
            output.append(span)
            continue
        clipped = span.strip("，。！？；:：、,.!?; ")
        if clipped and clipped in source_text:
            output.append(clipped)
            continue
        for clause in _split_clauses(span):
            if len(clause) >= 4 and clause in source_text:
                output.append(clause)
    return _unique(output)


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
    }
    if raw in RISK_LEVELS:
        return raw
    return mapping.get(raw, "medium")


def _compact_runtime_hint(runtime_context: Dict[str, Any]) -> Dict[str, Any]:
    scenario_ext = _first_dict(runtime_context.get("scenario_extension"))
    search = _first_dict(scenario_ext.get("propagation_intervention_search"))
    selected = _first_dict(search.get("selected_best_branch"))
    return {
        "has_propagation": bool(scenario_ext.get("propagation")),
        "has_intervention_search": bool(search),
        "runtime_selected_window": selected.get("best_intervention_window"),
        "runtime_selected_action": selected.get("best_intervention_action"),
    }


def _disabled_frame(reason: str, scenario: str) -> Dict[str, Any]:
    return {
        "available": False,
        "scenario": scenario,
        "risk_level": "low",
        "evidence_spans": [],
        "provenance": {"source": reason},
    }


def _split_clauses(text: str) -> List[str]:
    return [part.strip() for part in re.split(r"[。！？；;，,]", text or "") if part.strip()]


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

"""场景智能分类 API 路由。

供前端首页"智能识别"功能调用：用户粘贴一段非结构化、甚至模糊的文本，
接口返回它所属的认知安全场景、置信度、判定理由与关键线索摘要。

POST /api/classify
    入参: JSON { "text": "..." }，或 multipart/form-data（text + files/file + audio/voice）
    出参: { "success": true, "data": {
        "scenario_type": "fraud_im" | "public_opinion" | "event_propagation",
        "confidence": 0.0~1.0,
        "reason": "...",
        "extracted_summary": "...",
        "model": "...",
        "recognition_status": "recognized" | "unknown" | "unavailable"
    }}

文件解析和场景识别是两步：PDF/TXT/MD/JSON/CSV 先走本地解析；只有场景识别
API 可用时才会输出具体场景。API 不可用时仍返回成功响应，但 scenario_type=unknown，
并在 recognition_status/input_summary 中明确显示“已解析、未识别”。
"""

import traceback
from flask import jsonify, request

from . import classify_bp
from ..config import Config
from ..modules.input_adapters import (
    InputAdapterError,
    SpeechTranscriptionUnavailable,
    adapt_text_file,
    build_adapted_scenario,
    transcribe_audio,
)
from ..modules.llm_scenario_classifier import (
    ClassificationResult,
    LLMScenarioClassifier,
)
from ..modules.dialogue_attribution import (
    attribute_dialogue,
    build_preview_graph,
    build_thinking_steps,
)
from ..modules.chat_composer import compose_chat_reply
from ..modules.agent_trace import build_classify_trace, fork_status_for_classify
from ..utils.logger import get_logger

logger = get_logger("mirofish.api.classify")

# 懒加载单例：避免在模块导入阶段就要求 LLM_API_KEY 就绪，
# 缺 key 时 app 仍能正常启动，仅本接口返回 500 并给出清晰错误。
_classifier_instance = None


def _get_classifier() -> LLMScenarioClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = LLMScenarioClassifier()
    return _classifier_instance


@classify_bp.route('/classify', methods=['POST'])
def classify_scenario():
    """对一段非结构化文本进行场景智能分类。"""
    try:
        if request.files or request.mimetype == 'multipart/form-data':
            return _classify_multipart()

        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()

        if not text:
            return jsonify({
                "success": False,
                "error": "请提供 text（待分类的文本）",
            }), 400

        return jsonify({"success": True, "data": _classify_text(text)})

    except ValueError as e:
        # 主要是 "LLM_API_KEY 未配置" / "输入文本为空" 这类业务校验
        logger.error("场景分类参数/配置错误: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except SpeechTranscriptionUnavailable as e:
        logger.warning("首页语音输入不可用: %s", e)
        # Keep the homepage result contract consistent with document input:
        # an audio blob can be received even when no ASR provider is
        # configured, but it must be shown as unrecognised rather than as a
        # generic failed request.
        audio_adapters = [
            {
                "kind": "audio",
                "filename": item.filename or "recording.webm",
                "content_type": item.mimetype or "",
                "byte_size": 0,
                "text_chars": 0,
                "metadata": {"transcription": "unavailable"},
            }
            for item in request.files.getlist("audio") + request.files.getlist("voice")
            if item and item.filename
        ]
        if audio_adapters:
            result = _unavailable_result(
                (request.form.get("text") or "").strip(),
                audio_adapters,
            )
            result["reason"] = f"语音识别不可用：{e}；未完成场景识别。"
            result["recognition_mode"] = "speech_unavailable"
            return jsonify({"success": True, "data": result})
        return jsonify({
            "success": False,
            "error_code": "speech_unavailable",
            "error": str(e),
        }), 503
    except InputAdapterError as e:
        logger.warning("首页文件输入无效: %s", e)
        return jsonify({
            "success": False,
            "error_code": "invalid_input",
            "error": str(e),
        }), 400
    except Exception as e:
        logger.error("场景分类失败: %s\n%s", e, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": "识别服务暂时不可用，请稍后重试。",
        }), 500


def _classifier_api_available() -> bool:
    """Whether the homepage classifier has a configured remote LLM."""
    return bool(getattr(Config, "MIRO_COGSEC_MAIN_LLM_API_KEY", None))


def _unavailable_result(text: str, input_adapters: list[dict]) -> dict:
    """Return an explicit no-API result instead of pretending to classify."""
    file_count = sum(1 for item in input_adapters if item.get("kind") == "file")
    audio_count = sum(1 for item in input_adapters if item.get("kind") == "audio")
    parsed = any(int(item.get("text_chars") or 0) > 0 for item in input_adapters)
    if input_adapters and parsed:
        summary = (
            f"已完成 {file_count} 个文件、{audio_count} 段语音的本地输入解析，"
            "但当前场景识别 API 不可用，因此没有完成场景识别。"
        )
    elif input_adapters:
        summary = "已收到输入文件，但当前没有可用的解析/识别服务，因此没有完成场景识别。"
    else:
        summary = "当前未接入场景识别 API，因此没有完成场景识别。"
    result = ClassificationResult(
        scenario_type="unknown",
        confidence=0.0,
        reason="未接入场景识别 API；本地只能完成文本/文件解析，不能替代场景分类模型。",
        extracted_summary=summary,
        model="not_configured",
        extracted_fields={},
    ).to_dict()
    result.update({
        "recognition_status": "unavailable",
        "recognition_mode": "local_parse_only" if input_adapters else "not_configured",
        "input_adapters": input_adapters,
        "input_summary": {
            "text_chars": len(text),
            "extracted_text_chars": sum(int(item.get("text_chars") or 0) for item in input_adapters),
            "file_count": file_count,
            "audio_count": audio_count,
            "parsed": parsed,
        },
    })
    return _attach_chat_layers(result, text)


def _classify_text(text: str, input_adapters: list[dict] | None = None) -> dict:
    """Run API classification, or clearly report that only parsing happened."""
    adapters = list(input_adapters or [])
    local = LLMScenarioClassifier.classify_without_llm(text)
    if local is None and adapters:
        named = text + "\n" + " ".join(str(item.get("filename") or "") for item in adapters)
        local = LLMScenarioClassifier.classify_without_llm(named)
    if local is not None:
        return _decorate_classification(local, text, adapters)

    if not _classifier_api_available():
        return _unavailable_result(text, adapters)

    try:
        result = _get_classifier().classify(text)
    except Exception as exc:
        # A configured-but-unreachable provider is operationally equivalent to
        # no classifier.  Keep the parsed input visible and avoid a misleading
        # 500 page in the homepage UI.
        logger.warning("场景识别 API 不可用，保留本地解析结果: %s", exc)
        fallback = _unavailable_result(text, adapters)
        fallback["reason"] = "场景识别 API 调用失败；已保留本地解析结果，未完成场景识别。"
        fallback["recognition_mode"] = "api_unavailable"
        return fallback

    return _decorate_classification(result, text, adapters)


def _decorate_classification(result: ClassificationResult, text: str, adapters: list[dict]) -> dict:
    payload = result.to_dict()
    is_guarded = result.model == "deterministic_guard"
    is_pattern = result.model == "deterministic_pattern"
    payload.update({
        "recognition_status": (
            "out_of_scope" if result.model == "deterministic_out_of_scope"
            else "unknown" if is_guarded or result.scenario_type == "unknown"
            else "recognized"
        ),
        "recognition_mode": (
            "deterministic_guard" if is_guarded
            else "deterministic_out_of_scope" if result.model == "deterministic_out_of_scope"
            else "deterministic_pattern" if is_pattern
            else "llm_api"
        ),
        "input_adapters": adapters,
        "input_summary": {
            "text_chars": len(text),
            "extracted_text_chars": sum(int(item.get("text_chars") or 0) for item in adapters),
            "file_count": sum(1 for item in adapters if item.get("kind") == "file"),
            "audio_count": sum(1 for item in adapters if item.get("kind") == "audio"),
            "parsed": bool(adapters),
        },
    })
    return _attach_chat_layers(payload, text)


def _attach_chat_layers(payload: dict, text: str) -> dict:
    if payload.get("model") == "deterministic_guard":
        payload["attribution"] = {
            "utterances": [],
            "victim_present": False,
            "suspect_present": False,
            "split_method": "greeting",
            "summary": "这是日常寒暄，不按对话双方切分。",
            "caveats": [],
        }
        payload["thinking"] = []
        payload["graph_payload"] = {"nodes": [], "edges": []}
        payload["fork_status"] = fork_status_for_classify()
        payload["agent_trace"] = []
        payload["chat_reply"] = compose_chat_reply(text, payload, payload["attribution"])
        return payload
    attribution = attribute_dialogue(text)
    payload["attribution"] = attribution.to_dict()
    _attach_propagation_preview(payload, text)
    payload["thinking"] = build_thinking_steps(text, attribution, payload)
    if not payload.get("graph_payload"):
        payload["graph_payload"] = build_preview_graph(text, attribution, payload)
    payload["fork_status"] = fork_status_for_classify()
    payload["agent_trace"] = build_classify_trace(text, payload, payload["attribution"])
    payload["chat_reply"] = compose_chat_reply(text, payload, payload["attribution"])
    return payload


def _attach_propagation_preview(payload: dict, text: str) -> None:
    """Give public-opinion / event chats a real social-graph skeleton.

    Classify does not run FORK or OASIS.  It can still materialise the demo
    population so the next page is a relationship map, not a fake star chart.
    """
    scenario = payload.get("scenario_type")
    if scenario not in {"public_opinion", "event_propagation"}:
        return
    try:
        from ..modules.social_state import build_social_state
        from ..modules.social_state.builder import demo_agent_count, demo_topology_type

        agent_count = demo_agent_count(scenario)
        state = build_social_state(
            scenario_text=text,
            scenario_type=scenario,
            n_agents=agent_count,
            seed=42,
        )
        graph = state.to_display_graph(max_nodes=28)
        graph["preview"] = True
        graph["source"] = "lightweight_propagation"
        graph["engine"] = "social_state"
        payload["graph_payload"] = graph
        payload["propagation_graph"] = graph
        payload["scenario_extension"] = {
            "propagation_graph": graph,
            "social_state_summary": state.summary(),
        }
        payload["core_analysis"] = {
            "scenario": scenario,
            "risk_type": "虚假信息",
            "agent_count": len(state.actors),
            "topology_type": demo_topology_type(scenario, text),
        }
    except Exception as exc:
        logger.warning("classify propagation preview failed: %s", exc)


def _classify_multipart():
    """Parse homepage files/audio, then classify the resulting text."""
    text = (request.form.get("text") or request.form.get("scenario") or "").strip()
    documents = []
    audio = []
    uploaded_files = [item for item in request.files.getlist("files") if item and item.filename]
    uploaded_files.extend(item for item in request.files.getlist("file") if item and item.filename)
    uploaded_audio = [item for item in request.files.getlist("audio") if item and item.filename]
    uploaded_audio.extend(item for item in request.files.getlist("voice") if item and item.filename)

    for uploaded in uploaded_files:
        documents.append(adapt_text_file(
            uploaded.filename,
            uploaded.read(),
            uploaded.mimetype or "",
        ))
    for uploaded in uploaded_audio:
        audio.append(transcribe_audio(
            uploaded.filename,
            uploaded.read(),
            uploaded.mimetype or "",
            language=request.form.get("language") or None,
        ))

    scenario_text, _fragments, adapter_info = build_adapted_scenario(text, documents, audio)
    if not scenario_text:
        raise InputAdapterError("请提供文本、文件或语音输入")
    return jsonify({"success": True, "data": _classify_text(scenario_text, adapter_info)})

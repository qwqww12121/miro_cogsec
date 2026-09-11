"""CogSec API 路由。"""

import json
import traceback
import uuid
from flask import jsonify, request

from . import cogsec_bp
from ..services.cogsec_service import CogSecService
from ..services.session_manager import SessionManager
from ..modules.conversational_response import answer_followup_from_state
from ..modules.session import (
    build_incremental_analysis,
    build_session_text,
)
from ..modules.input_adapters import (
    InputAdapterError,
    SpeechTranscriptionUnavailable,
    adapt_text_file,
    build_adapted_scenario,
    transcribe_audio,
)
from ..utils.logger import get_logger

logger = get_logger("mirofish.api.cogsec")

# Followup state field whitelist — only UI-safe context fields may be
# accepted from the client.  Core analysis fields (risk scores, evidence,
# selected branch, OASIS results, benchmark_prediction, etc.) are
# server-authoritative and are IGNORED even if submitted.
_FOLLOWUP_STATE_WHITELIST: frozenset = frozenset({
    "tone",
    "has_cached_analysis",
    "conversation_id",
    "turn_id",
    "scenario",
    "scenario_type",
    "user_role",
})


def _api_error(message: str, error_code: str = "internal_error", status: int = 500,
               request_id: str = "") -> tuple:
    """Build a safe error response that never leaks tracebacks to clients."""
    payload = {
        "success": False,
        "error_code": error_code,
        "message": message,
    }
    if request_id:
        payload["request_id"] = request_id
    return jsonify(payload), status


def _request_id() -> str:
    """Generate a short request id for error correlation."""
    return str(uuid.uuid4())[:8]


# =========================================================================
# 运行环境（不返回密钥）
# =========================================================================


@cogsec_bp.route('/runtime-status', methods=['GET'])
def runtime_status():
    """Tell the UI whether this Flask process can actually run OASIS."""
    from ..modules.propagation.oasis_experiment import oasis_environment_status
    return jsonify({"success": True, "data": oasis_environment_status()})


# =========================================================================
# 单条文本分析 (legacy)
# =========================================================================


@cogsec_bp.route('/analyze', methods=['POST'])
def analyze_cogsec():
    """直接根据场景文本执行 CogSec 分析。"""
    req_id = _request_id()
    try:
        if request.files or request.mimetype == 'multipart/form-data':
            return _analyze_cogsec_multipart(req_id)

        data = request.get_json() or {}
        scenario = data.get('scenario') or data.get('text')
        questionnaire = data.get('questionnaire')
        scenario_type = data.get('scenario_type')
        user_role = data.get('user_role', 'individual')
        tone = data.get('tone', 'friendly')
        variant_id = data.get('variant_id', 'full')
        input_fragments = data.get('fragments') or data.get('inputs')
        if not isinstance(input_fragments, list):
            input_fragments = None
        # Round 3: benchmark adapter is off by default for online analysis
        include_benchmark = data.get('include_benchmark', request.args.get('include_benchmark', 'false'))
        include_benchmark = str(include_benchmark).lower() == 'true'

        if not scenario:
            return _api_error("请提供 scenario 或 text", "missing_parameter", 400, req_id)

        # Use shared runtime (Round 1 upgrade)
        from ..runtime import get_runtime
        svc = get_runtime().build_service()
        result = svc.analyze_text(
            scenario_text=scenario,
            questionnaire=questionnaire,
            scenario_type=scenario_type,
            user_role=user_role,
            tone=tone,
            include_benchmark=include_benchmark,
            variant_id=variant_id,
            input_fragments=input_fragments,
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except SpeechTranscriptionUnavailable as e:
        logger.warning("[%s] 语音识别不可用: %s", req_id, str(e))
        return _api_error(str(e), "speech_unavailable", 503, req_id)
    except InputAdapterError as e:
        logger.warning("[%s] 多模态输入无效: %s", req_id, str(e))
        return _api_error(str(e), "invalid_input", 400, req_id)
    except ValueError as e:
        logger.warning("[%s] CogSec 请求参数无效: %s", req_id, str(e))
        return _api_error(str(e), "invalid_request", 400, req_id)
    except Exception as e:
        logger.error("[%s] CogSec 分析失败: %s", req_id, str(e))
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error(
            f"分析请求处理失败 (request_id={req_id})",
            "analysis_failed", 500, req_id,
        )


def _parse_multipart_json(value, default):
    """Parse optional JSON form fields without making the JSON API change."""
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError) as exc:
        raise InputAdapterError("multipart 字段 questionnaire/fragments 必须是合法 JSON") from exc


def _analyze_cogsec_multipart(req_id: str):
    """Adapt document/audio uploads into the existing analyze_text mainline."""
    scenario = (request.form.get('scenario') or request.form.get('text') or '').strip()
    scenario_type = request.form.get('scenario_type') or None
    questionnaire = _parse_multipart_json(request.form.get('questionnaire'), None)
    user_role = request.form.get('user_role', 'individual')
    tone = request.form.get('tone', 'friendly')
    variant_id = request.form.get('variant_id', 'full')
    include_benchmark = str(request.form.get('include_benchmark', 'false')).lower() == 'true'
    language = request.form.get('language') or None

    uploaded_files = [item for item in request.files.getlist('files') if item and item.filename]
    uploaded_files.extend(item for item in request.files.getlist('file') if item and item.filename)
    uploaded_audio = [item for item in request.files.getlist('audio') if item and item.filename]
    uploaded_audio.extend(item for item in request.files.getlist('voice') if item and item.filename)

    documents = []
    audio = []
    for uploaded in uploaded_files:
        documents.append(adapt_text_file(
            uploaded.filename,
            uploaded.read(),
            uploaded.mimetype or '',
        ))
    for uploaded in uploaded_audio:
        audio.append(transcribe_audio(
            uploaded.filename,
            uploaded.read(),
            uploaded.mimetype or '',
            language=language,
        ))

    scenario_text, adapted_fragments, adapter_info = build_adapted_scenario(
        scenario,
        documents,
        audio,
    )
    if not scenario_text:
        raise InputAdapterError("请提供文本、文件或语音输入")

    extra_fragments = _parse_multipart_json(request.form.get('fragments'), None)
    input_fragments = adapted_fragments
    if isinstance(extra_fragments, list):
        input_fragments.extend(extra_fragments)

    from ..runtime import get_runtime
    svc = get_runtime().build_service()
    result = svc.analyze_text(
        scenario_text=scenario_text,
        questionnaire=questionnaire,
        scenario_type=scenario_type,
        user_role=user_role,
        tone=tone,
        include_benchmark=include_benchmark,
        variant_id=variant_id,
        input_fragments=input_fragments,
    )
    payload = result.to_dict()
    payload['input_adapters'] = adapter_info
    payload['input_summary'] = {
        'text_chars': len(scenario_text),
        'file_count': len(documents),
        'audio_count': len(audio),
        'speech_provider_status': [item.metadata for item in audio],
    }
    return jsonify({"success": True, "data": payload})


@cogsec_bp.route('/transcribe', methods=['POST'])
def transcribe_cogsec():
    """Transcribe one browser-recorded audio blob without running CogSec."""
    req_id = _request_id()
    try:
        uploaded = next(
            (item for field in ('audio', 'voice', 'file')
             for item in request.files.getlist(field)
             if item and item.filename),
            None,
        )
        if uploaded is None:
            return _api_error("请上传音频 (field name: audio)", "missing_audio", 400, req_id)
        item = transcribe_audio(
            uploaded.filename,
            uploaded.read(),
            uploaded.mimetype or '',
            language=request.form.get('language') or None,
        )
        return jsonify({
            "success": True,
            "data": {
                "text": item.text,
                "filename": item.filename,
                "metadata": item.to_dict(),
            },
        })
    except SpeechTranscriptionUnavailable as e:
        logger.warning("[%s] 独立语音转写不可用: %s", req_id, str(e))
        return _api_error(str(e), "speech_unavailable", 503, req_id)
    except InputAdapterError as e:
        return _api_error(str(e), "invalid_audio", 400, req_id)
    except Exception as e:
        logger.error("[%s] 语音转写失败: %s", req_id, str(e))
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error(
            f"语音转写失败 (request_id={req_id})",
            "transcription_failed", 500, req_id,
        )


@cogsec_bp.route('/followup', methods=['POST'])
def cogsec_followup():
    """从缓存的 conversation_state 直接回答追问，不重跑完整 pipeline。

    Request JSON:
        state:   conversation_state（来自上次分析结果）
        message: 用户追问文本
        tone:    可选，默认沿用 state 里的 tone

    Round 1 upgrade: client-provided state is filtered through a whitelist.
    Core analysis fields (risk_scores, evidence, selected_branch, OASIS
    results) are always server-authoritative.
    """
    req_id = _request_id()
    try:
        data = request.get_json() or {}
        raw_state = data.get('state')
        message = (data.get('message') or '').strip()
        tone = data.get('tone')

        if not raw_state or not message:
            return _api_error("请提供 state 和 message", "missing_parameter", 400, req_id)

        # Filter client state through whitelist (UI-safe fields only)
        safe_state = _filter_followup_state(raw_state)
        if tone:
            safe_state["tone"] = tone

        # If conversation_id matches a server session, overlay server-authoritative state
        conversation_id = safe_state.get("conversation_id")
        if conversation_id:
            try:
                server_session = _session_manager.get(conversation_id)
                if server_session and isinstance(server_session.state, dict):
                    server_analysis = server_session.state.get("last_analysis", {})
                    if server_analysis:
                        # Server state is authoritative — overlay on safe client state
                        safe_state = {**safe_state, **server_analysis}
            except KeyError:
                pass  # session not found; use client state as-is

        result = answer_followup_from_state(
            state=safe_state,
            user_message=message,
            tone=tone,
        )
        if result is None:
            return _api_error("无法从缓存状态回答，请重新分析", "state_unusable", 422, req_id)

        return jsonify({"success": True, "data": result})

    except Exception as e:
        logger.error("[%s] 追问失败: %s", req_id, str(e))
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error(
            f"追问处理失败 (request_id={req_id})",
            "followup_failed", 500, req_id,
        )


@cogsec_bp.route('/story-summary', methods=['POST'])
def cogsec_story_summary():
    """Summarize one simulation-map story from original input + compact sim snapshot."""
    req_id = _request_id()
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            return _api_error("请提供 JSON", "missing_parameter", 400, req_id)
        input_text = str(data.get("input_text") or "")
        snapshot = data.get("snapshot") if isinstance(data.get("snapshot"), dict) else {}
        if not input_text.strip() and not snapshot.get("nodes") and not snapshot.get("attack_summary"):
            return _api_error("缺少原文或仿真摘要", "missing_parameter", 400, req_id)
        from ..modules.story_summarizer import summarize_simulation_story
        story = summarize_simulation_story(data)
        return jsonify({"success": True, "data": story})
    except RuntimeError as exc:
        if str(exc) == "llm_unavailable":
            return _api_error("当前无法生成事件说明", "llm_unavailable", 503, req_id)
        logger.error("[%s] 事件说明失败: %s", req_id, exc)
        return _api_error("事件说明失败", "story_failed", 500, req_id)
    except Exception as exc:
        logger.error("[%s] 事件说明失败: %s", req_id, exc)
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error("事件说明失败", "story_failed", 500, req_id)


@cogsec_bp.route('/step-explain', methods=['POST'])
def cogsec_step_explain():
    """Explain each FORK step from original input + branch logs."""
    req_id = _request_id()
    try:
        data = request.get_json() or {}
        if not isinstance(data, dict):
            return _api_error("请提供 JSON", "missing_parameter", 400, req_id)
        input_text = str(data.get("input_text") or "")
        steps = data.get("steps") if isinstance(data.get("steps"), list) else []
        branch_a = data.get("branch_a_log") if isinstance(data.get("branch_a_log"), list) else []
        if not input_text.strip() and not steps and not branch_a:
            return _api_error("缺少原文或对照路径", "missing_parameter", 400, req_id)
        from ..modules.story_summarizer import explain_fork_steps
        explained = explain_fork_steps(data)
        return jsonify({"success": True, "data": explained})
    except RuntimeError as exc:
        if str(exc) == "llm_unavailable":
            return _api_error("当前无法生成步骤说明", "llm_unavailable", 503, req_id)
        logger.error("[%s] 步骤说明失败: %s", req_id, exc)
        return _api_error("步骤说明失败", "step_explain_failed", 500, req_id)
    except Exception as exc:
        logger.error("[%s] 步骤说明失败: %s", req_id, exc)
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error("步骤说明失败", "step_explain_failed", 500, req_id)


def _filter_followup_state(raw_state: dict) -> dict:
    """Whitelist-filter client-provided followup state."""
    if not isinstance(raw_state, dict):
        return {}
    safe = {}
    for key in _FOLLOWUP_STATE_WHITELIST:
        if key in raw_state:
            safe[key] = raw_state[key]
    return safe


@cogsec_bp.route('/report/<report_id>', methods=['GET'])
def analyze_cogsec_by_report(report_id: str):
    """根据现有报告生成 CogSec 分析数据。"""
    req_id = _request_id()
    try:
        from ..models.project import ProjectManager
        from ..services.report_agent import ReportManager
        from ..services.simulation_manager import SimulationManager

        report = ReportManager.get_report(report_id)
        if not report:
            return _api_error(f"报告不存在: {report_id}", "not_found", 404, req_id)

        simulation_manager = SimulationManager()
        simulation = simulation_manager.get_simulation(report.simulation_id)
        if not simulation:
            return _api_error(f"模拟不存在: {report.simulation_id}", "not_found", 404, req_id)

        project = ProjectManager.get_project(simulation.project_id)
        if not project:
            return _api_error(f"项目不存在: {simulation.project_id}", "not_found", 404, req_id)

        summary_text = report.outline.summary if report.outline else ""
        scenario_text = "\n".join(filter(None, [
            project.simulation_requirement,
            project.analysis_summary,
            summary_text,
            report.markdown_content[:3000],
        ]))

        from ..runtime import get_runtime
        svc = get_runtime().build_service()
        result = svc.analyze_text(
            scenario_text=scenario_text,
            scenario_type=request.args.get('scenario_type')
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error("[%s] 按报告生成 CogSec 分析失败: %s", req_id, str(e))
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error(
            f"报告分析失败 (request_id={req_id})",
            "report_analysis_failed", 500, req_id,
        )


# =========================================================================
# 多轮 Session 接口 (new — Round 3)
# =========================================================================

_session_manager = SessionManager()


@cogsec_bp.route('/session/create', methods=['POST'])
def session_create():
    """创建新的多轮输入 Session。

    Request JSON (all optional):
        scenario_type: str   — canonical or legacy label
        user_role: str       — "individual" | "official" | "media" | "target_group"

    Returns:
        { success, data: { session_id, scenario_type, user_role, ... } }
    """
    req_id = _request_id()
    try:
        data = request.get_json() or {}
        scenario_type = data.get('scenario_type')
        user_role = data.get('user_role', 'individual')

        session = _session_manager.create(
            scenario_type=scenario_type,
            user_role=user_role,
        )
        return jsonify({
            "success": True,
            "data": session.to_dict(),
        })
    except Exception as e:
        logger.error("[%s] 创建 session 失败: %s", req_id, str(e))
        return _api_error(f"创建 session 失败 (request_id={req_id})", "session_create_failed", 500, req_id)


@cogsec_bp.route('/session/<session_id>', methods=['GET'])
def session_get(session_id: str):
    """获取 Session 详情，含所有 fragment 摘要。

    Query params:
        include_content: bool — 设为 "true" 同时返回 merged_text
    """
    req_id = _request_id()
    try:
        include_content = request.args.get('include_content', '').lower() == 'true'
        session = _session_manager.get(session_id)
        return jsonify({
            "success": True,
            "data": session.to_dict(include_content=include_content),
        })
    except KeyError:
        return _api_error(f"Session 不存在: {session_id}", "not_found", 404, req_id)
    except Exception as e:
        logger.error("[%s] 获取 session 失败: %s", req_id, str(e))
        return _api_error(f"获取 session 失败 (request_id={req_id})", "session_get_failed", 500, req_id)


@cogsec_bp.route('/session/<session_id>/append', methods=['POST'])
def session_append_text(session_id: str):
    """向 Session 追加一条文本 fragment。

    Request JSON:
        content: str  — 文本内容 (必填)
    """
    req_id = _request_id()
    try:
        data = request.get_json() or {}
        content = (data.get('content') or '').strip()
        if not content:
            return _api_error("请提供 content", "missing_parameter", 400, req_id)

        fragment = _session_manager.append_text(session_id, content)
        return jsonify({
            "success": True,
            "data": fragment.to_dict(),
        })
    except KeyError:
        return _api_error(f"Session 不存在: {session_id}", "not_found", 404, req_id)
    except ValueError as e:
        return _api_error(str(e), "invalid_input", 400, req_id)
    except Exception as e:
        logger.error("[%s] 追加文本失败: %s", req_id, str(e))
        return _api_error(f"追加文本失败 (request_id={req_id})", "append_failed", 500, req_id)


@cogsec_bp.route('/session/<session_id>/upload', methods=['POST'])
def session_upload_file(session_id: str):
    """向 Session 上传一个文件 (PDF / MD / TXT)，提取文本后作为 fragment 追加。

    兼容接口。标准接口请使用 /session/<id>/turn (multipart)。

    Request: multipart/form-data
        file: 文件 (必填)
    """
    req_id = _request_id()
    try:
        if 'file' not in request.files:
            return _api_error("请上传文件 (field name: file)", "missing_file", 400, req_id)

        uploaded = request.files['file']
        if not uploaded or not uploaded.filename:
            return _api_error("未选择文件", "empty_file", 400, req_id)

        file_data = uploaded.read()
        fragment = _session_manager.append_file(
            session_id=session_id,
            file_data=file_data,
            original_filename=uploaded.filename,
        )
        return jsonify({
            "success": True,
            "data": fragment.to_dict(),
        })
    except KeyError:
        return _api_error(f"Session 不存在: {session_id}", "not_found", 404, req_id)
    except ValueError as e:
        return _api_error(str(e), "invalid_input", 400, req_id)
    except Exception as e:
        logger.error("[%s] 上传文件失败: %s", req_id, str(e))
        return _api_error(f"上传文件失败 (request_id={req_id})", "upload_failed", 500, req_id)


# =========================================================================
# 标准 /turn 接口 (unified text + file input)
# =========================================================================


@cogsec_bp.route('/session/<session_id>/turn', methods=['POST'])
def session_add_turn(session_id: str):
    """标准多轮输入接口 — 同时支持 JSON 文本和 multipart 文件。

    **JSON 文本**:
        { "role": "user", "content": "..." }

    **multipart 文件**:
        file: 文件 (必填)
        role: 可选，默认 file_excerpt

    支持的文件类型: .txt / .md / .markdown / .json / .csv (最大 5MB)

    Returns:
        { success, data: { turns_added, incremental_analysis, session } }
    """
    req_id = _request_id()
    try:
        if request.is_json:
            return _turn_from_json(session_id, req_id)

        if request.files:
            return _turn_from_file(session_id, req_id)

        return _api_error(
            "请提供 JSON body (role+content) 或上传文件 (multipart/form-data)",
            "missing_input", 400, req_id,
        )

    except KeyError:
        return _api_error(f"Session 不存在: {session_id}", "not_found", 404, req_id)
    except ValueError as e:
        msg = str(e)
        code = 413 if "too large" in msg.lower() or "turn limit" in msg.lower() else 400
        return _api_error(msg, "invalid_input", code, req_id)
    except Exception as e:
        logger.error("[%s] 添加 turn 失败: %s", req_id, str(e))
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error(f"添加 turn 失败 (request_id={req_id})", "turn_failed", 500, req_id)


def _turn_from_json(session_id: str, req_id: str):
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    if not content:
        return _api_error("请提供 content", "missing_parameter", 400, req_id)

    role = data.get('role', 'user')
    turn = _session_manager.add_turn(
        session_id=session_id,
        role=role,
        content=content,
        source=data.get('source', 'chat'),
        metadata=data.get('metadata'),
    )
    return _build_turn_response(session_id, [turn], tone=data.get('tone'))


def _turn_from_file(session_id: str, req_id: str):
    if 'file' not in request.files:
        return _api_error("请上传文件 (field name: file)", "missing_file", 400, req_id)

    uploaded = request.files['file']
    if not uploaded or not uploaded.filename:
        return _api_error("未选择文件", "empty_file", 400, req_id)

    file_data = uploaded.read()
    turns = _session_manager.add_turns_from_file(
        session_id=session_id,
        file_data=file_data,
        original_filename=uploaded.filename,
    )
    return _build_turn_response(session_id, turns, tone=request.form.get('tone'))


def _build_turn_response(session_id: str, latest_turns, tone=None):
    session = _session_manager.get(session_id)
    all_turns = _session_manager.get_turns(session_id)

    incremental = build_incremental_analysis(
        scenario_type=session.scenario_type or "fraud_im",
        user_role=session.user_role,
        turns=all_turns,
        latest_turns=latest_turns,
    )

    conversational = None
    if latest_turns:
        latest = latest_turns[-1]
        if getattr(latest, "role", "user") == "user":
            conversational = _session_manager.answer_followup(
                session_id=session_id,
                content=getattr(latest, "content", ""),
                tone=tone,
            )

    data = {
        "turns_added": [t.to_dict() for t in latest_turns],
        "incremental_analysis": incremental,
        "session": session.to_dict(),
    }
    if conversational is not None:
        data["conversational_response"] = conversational

    return jsonify({
        "success": True,
        "data": data,
    })


# =========================================================================
# 标准 /analyze 接口
# =========================================================================


@cogsec_bp.route('/session/<session_id>/analyze', methods=['POST'])
def session_analyze(session_id: str):
    """合并 Session 中所有 fragment 并运行完整 CogSec 主链分析。

    返回结构与 POST /api/cogsec/analyze 相同，额外附加顶层 ``session`` 字段。
    """
    req_id = _request_id()
    try:
        data = request.get_json(silent=True) or {}
        tone = data.get('tone') or request.args.get('tone') or 'friendly'
        result = _session_manager.analyze(session_id, tone=tone)
        return jsonify({
            "success": True,
            "data": result,
        })
    except KeyError:
        return _api_error(f"Session 不存在: {session_id}", "not_found", 404, req_id)
    except ValueError as e:
        return _api_error(str(e), "invalid_input", 400, req_id)
    except Exception as e:
        logger.error("[%s] Session 分析失败: %s", req_id, str(e))
        logger.debug("[%s] Traceback: %s", req_id, traceback.format_exc())
        return _api_error(f"Session 分析失败 (request_id={req_id})", "session_analyze_failed", 500, req_id)


@cogsec_bp.route('/session/<session_id>', methods=['DELETE'])
def session_delete(session_id: str):
    """删除一个 Session 及其所有 fragment。"""
    req_id = _request_id()
    try:
        deleted = _session_manager.delete(session_id)
        if not deleted:
            return _api_error(f"Session 不存在: {session_id}", "not_found", 404, req_id)
        return jsonify({
            "success": True,
            "message": f"Session 已删除: {session_id}",
        })
    except Exception as e:
        logger.error("[%s] 删除 session 失败: %s", req_id, str(e))
        return _api_error(f"删除 session 失败 (request_id={req_id})", "delete_failed", 500, req_id)


@cogsec_bp.route('/session/list', methods=['GET'])
def session_list():
    """列出所有当前活跃的 Session（仅 DEBUG 模式可用）。"""
    from ..config import Config
    if not Config.DEBUG:
        return _api_error("session list is only available in debug mode", "not_available", 403, _request_id())
    req_id = _request_id()
    try:
        sessions = _session_manager.list_sessions()
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in sessions],
            "count": len(sessions),
        })
    except Exception as e:
        logger.error("[%s] 列出 session 失败: %s", req_id, str(e))
        return _api_error(f"列出 session 失败 (request_id={req_id})", "list_failed", 500, req_id)

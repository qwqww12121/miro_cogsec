"""CogSec API 路由。"""

import traceback
from flask import jsonify, request

from . import cogsec_bp
from ..services.cogsec_service import CogSecService
from ..services.session_manager import SessionManager
from ..modules.conversational_response import answer_followup_from_state
from ..modules.session import (
    build_incremental_analysis,
    build_session_text,
)
from ..utils.logger import get_logger

logger = get_logger("mirofish.api.cogsec")


# =========================================================================
# 单条文本分析 (legacy)
# =========================================================================


@cogsec_bp.route('/analyze', methods=['POST'])
def analyze_cogsec():
    """直接根据场景文本执行 CogSec 分析。"""
    try:
        data = request.get_json() or {}
        scenario = data.get('scenario') or data.get('text')
        questionnaire = data.get('questionnaire')
        scenario_type = data.get('scenario_type')
        user_role = data.get('user_role', 'individual')
        tone = data.get('tone', 'friendly')

        if not scenario:
            return jsonify({
                "success": False,
                "error": "请提供 scenario 或 text"
            }), 400

        service = CogSecService()
        result = service.analyze_text(
            scenario_text=scenario,
            questionnaire=questionnaire,
            scenario_type=scenario_type,
            user_role=user_role,
            tone=tone,
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error(f"CogSec 分析失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


@cogsec_bp.route('/followup', methods=['POST'])
def cogsec_followup():
    """从缓存的 conversation_state 直接回答追问，不重跑完整 pipeline。

    Request JSON:
        state:   conversation_state（来自上次分析结果）
        message: 用户追问文本
        tone:    可选，默认沿用 state 里的 tone
    """
    try:
        data = request.get_json() or {}
        state = data.get('state')
        message = (data.get('message') or '').strip()
        tone = data.get('tone')

        if not state or not message:
            return jsonify({"success": False, "error": "请提供 state 和 message"}), 400

        result = answer_followup_from_state(
            state=state,
            user_message=message,
            tone=tone,
        )
        if result is None:
            return jsonify({"success": False, "error": "无法从缓存状态回答，请重新分析"}), 422

        return jsonify({"success": True, "data": result})

    except Exception as e:
        logger.error(f"追问失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@cogsec_bp.route('/report/<report_id>', methods=['GET'])
def analyze_cogsec_by_report(report_id: str):
    """根据现有报告生成 CogSec 分析数据。"""
    try:
        from ..models.project import ProjectManager
        from ..services.report_agent import ReportManager
        from ..services.simulation_manager import SimulationManager

        report = ReportManager.get_report(report_id)
        if not report:
            return jsonify({
                "success": False,
                "error": f"报告不存在: {report_id}"
            }), 404

        simulation_manager = SimulationManager()
        simulation = simulation_manager.get_simulation(report.simulation_id)
        if not simulation:
            return jsonify({
                "success": False,
                "error": f"模拟不存在: {report.simulation_id}"
            }), 404

        project = ProjectManager.get_project(simulation.project_id)
        if not project:
            return jsonify({
                "success": False,
                "error": f"项目不存在: {simulation.project_id}"
            }), 404

        summary_text = report.outline.summary if report.outline else ""
        scenario_text = "\n".join(filter(None, [
            project.simulation_requirement,
            project.analysis_summary,
            summary_text,
            report.markdown_content[:3000],
        ]))

        service = CogSecService()
        result = service.analyze_text(
            scenario_text=scenario_text,
            scenario_type=request.args.get('scenario_type')
        )

        return jsonify({
            "success": True,
            "data": result.to_dict()
        })

    except Exception as e:
        logger.error(f"按报告生成 CogSec 分析失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500


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
        logger.error(f"创建 session 失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cogsec_bp.route('/session/<session_id>', methods=['GET'])
def session_get(session_id: str):
    """获取 Session 详情，含所有 fragment 摘要。

    Query params:
        include_content: bool — 设为 "true" 同时返回 merged_text
    """
    try:
        include_content = request.args.get('include_content', '').lower() == 'true'
        session = _session_manager.get(session_id)
        return jsonify({
            "success": True,
            "data": session.to_dict(include_content=include_content),
        })
    except KeyError:
        return jsonify({
            "success": False,
            "error": f"Session 不存在: {session_id}",
        }), 404
    except Exception as e:
        logger.error(f"获取 session 失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cogsec_bp.route('/session/<session_id>/append', methods=['POST'])
def session_append_text(session_id: str):
    """向 Session 追加一条文本 fragment。

    Request JSON:
        content: str  — 文本内容 (必填)
    """
    try:
        data = request.get_json() or {}
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({
                "success": False,
                "error": "请提供 content",
            }), 400

        fragment = _session_manager.append_text(session_id, content)
        return jsonify({
            "success": True,
            "data": fragment.to_dict(),
        })
    except KeyError:
        return jsonify({
            "success": False,
            "error": f"Session 不存在: {session_id}",
        }), 404
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400
    except Exception as e:
        logger.error(f"追加文本失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cogsec_bp.route('/session/<session_id>/upload', methods=['POST'])
def session_upload_file(session_id: str):
    """向 Session 上传一个文件 (PDF / MD / TXT)，提取文本后作为 fragment 追加。

    兼容接口。标准接口请使用 /session/<id>/turn (multipart)。

    Request: multipart/form-data
        file: 文件 (必填)
    """
    try:
        if 'file' not in request.files:
            return jsonify({
                "success": False,
                "error": "请上传文件 (field name: file)",
            }), 400

        uploaded = request.files['file']
        if not uploaded or not uploaded.filename:
            return jsonify({
                "success": False,
                "error": "未选择文件",
            }), 400

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
        return jsonify({
            "success": False,
            "error": f"Session 不存在: {session_id}",
        }), 404
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400
    except Exception as e:
        logger.error(f"上传文件失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


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
    try:
        if request.is_json:
            return _turn_from_json(session_id)

        if request.files:
            return _turn_from_file(session_id)

        return jsonify({
            "success": False,
            "error": "请提供 JSON body (role+content) 或上传文件 (multipart/form-data)",
        }), 400

    except KeyError:
        return jsonify({
            "success": False,
            "error": f"Session 不存在: {session_id}",
        }), 404
    except ValueError as e:
        msg = str(e)
        if "too large" in msg.lower() or "turn limit" in msg.lower():
            return jsonify({"success": False, "error": msg}), 413
        return jsonify({"success": False, "error": msg}), 400
    except Exception as e:
        logger.error(f"添加 turn 失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


def _turn_from_json(session_id: str):
    data = request.get_json() or {}
    content = (data.get('content') or '').strip()
    if not content:
        return jsonify({"success": False, "error": "请提供 content"}), 400

    role = data.get('role', 'user')
    turn = _session_manager.add_turn(
        session_id=session_id,
        role=role,
        content=content,
        source=data.get('source', 'chat'),
        metadata=data.get('metadata'),
    )
    return _build_turn_response(session_id, [turn], tone=data.get('tone'))


def _turn_from_file(session_id: str):
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "请上传文件 (field name: file)"}), 400

    uploaded = request.files['file']
    if not uploaded or not uploaded.filename:
        return jsonify({"success": False, "error": "未选择文件"}), 400

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
    try:
        data = request.get_json(silent=True) or {}
        tone = data.get('tone') or request.args.get('tone') or 'friendly'
        result = _session_manager.analyze(session_id, tone=tone)
        return jsonify({
            "success": True,
            "data": result,
        })
    except KeyError:
        return jsonify({
            "success": False,
            "error": f"Session 不存在: {session_id}",
        }), 404
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e),
        }), 400
    except Exception as e:
        logger.error(f"Session 分析失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500


@cogsec_bp.route('/session/<session_id>', methods=['DELETE'])
def session_delete(session_id: str):
    """删除一个 Session 及其所有 fragment。"""
    try:
        deleted = _session_manager.delete(session_id)
        if not deleted:
            return jsonify({
                "success": False,
                "error": f"Session 不存在: {session_id}",
            }), 404
        return jsonify({
            "success": True,
            "message": f"Session 已删除: {session_id}",
        })
    except Exception as e:
        logger.error(f"删除 session 失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500


@cogsec_bp.route('/session/list', methods=['GET'])
def session_list():
    """列出所有当前活跃的 Session。"""
    try:
        sessions = _session_manager.list_sessions()
        return jsonify({
            "success": True,
            "data": [s.to_dict() for s in sessions],
            "count": len(sessions),
        })
    except Exception as e:
        logger.error(f"列出 session 失败: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500

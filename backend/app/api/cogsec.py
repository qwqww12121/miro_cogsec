"""CogSec API 路由。"""

import traceback
from flask import jsonify, request

from . import cogsec_bp
from ..services.cogsec_service import CogSecService
from ..utils.logger import get_logger

logger = get_logger("mirofish.api.cogsec")


@cogsec_bp.route('/analyze', methods=['POST'])
def analyze_cogsec():
    """直接根据场景文本执行 CogSec 分析。"""
    try:
        data = request.get_json() or {}
        scenario = data.get('scenario') or data.get('text')
        questionnaire = data.get('questionnaire')
        scenario_type = data.get('scenario_type')

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

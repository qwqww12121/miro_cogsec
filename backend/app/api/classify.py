"""场景智能分类 API 路由。

供前端首页"智能识别"功能调用：用户粘贴一段非结构化、甚至模糊的文本，
接口返回它所属的认知安全场景、置信度、判定理由与关键线索摘要。

POST /api/classify
    入参: { "text": "..." }
    出参: { "success": true, "data": {
        "scenario_type": "fraud_im" | "public_opinion" | "event_propagation",
        "confidence": 0.0~1.0,
        "reason": "...",
        "extracted_summary": "...",
        "model": "..."
    }}
"""

import traceback
from flask import jsonify, request

from . import classify_bp
from ..modules.llm_scenario_classifier import LLMScenarioClassifier
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
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()

        if not text:
            return jsonify({
                "success": False,
                "error": "请提供 text（待分类的文本）",
            }), 400

        result = _get_classifier().classify(text)

        return jsonify({
            "success": True,
            "data": result.to_dict(),
        })

    except ValueError as e:
        # 主要是 "LLM_API_KEY 未配置" / "输入文本为空" 这类业务校验
        logger.error("场景分类参数/配置错误: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except Exception as e:
        logger.error("场景分类失败: %s\n%s", e, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500

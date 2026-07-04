"""场景智能分类 + 字段提取 + 结果通俗化 API 路由。

POST /api/classify
    入参: { "text": "..." }
    出参: { "success": true, "data": {
        "scenario_type": "fraud_im" | "public_opinion" | "event_propagation",
        "confidence": 0.0~1.0,
        "reason": "...",
        "extracted_summary": "...",
        "model": "...",
        "extracted_fields": { ... }   ← 新增，各场景表单字段，提取不到为空字符串
    }}

POST /api/plainify
    入参: { 分析结果的任意字段，如 risk_type, confidence, rhetoric_features, suggestions ... }
    出参: { "success": true, "data": {
        "plain_summary": "大白话摘要",
        "action_advice": "一句话行动建议"
    }}
"""

import traceback
from flask import jsonify, request

from . import classify_bp
from ..modules.llm_scenario_classifier import LLMScenarioClassifier
from ..modules.llm_field_extractor import LLMFieldExtractor
from ..modules.llm_plainifier import LLMPlainifier
from ..utils.logger import get_logger

logger = get_logger("mirofish.api.classify")

# 懒加载单例
_classifier_instance = None
_extractor_instance = None
_plainifier_instance = None


def _get_classifier() -> LLMScenarioClassifier:
    global _classifier_instance
    if _classifier_instance is None:
        _classifier_instance = LLMScenarioClassifier()
    return _classifier_instance


def _get_extractor() -> LLMFieldExtractor:
    global _extractor_instance
    if _extractor_instance is None:
        _extractor_instance = LLMFieldExtractor()
    return _extractor_instance


def _get_plainifier() -> LLMPlainifier:
    global _plainifier_instance
    if _plainifier_instance is None:
        _plainifier_instance = LLMPlainifier()
    return _plainifier_instance


# ---------------------------------------------------------------------------
# POST /api/classify
# ---------------------------------------------------------------------------

@classify_bp.route('/classify', methods=['POST'])
def classify_scenario():
    """对一段非结构化文本进行场景智能分类，同时提取各场景表单字段。"""
    try:
        data = request.get_json(silent=True) or {}
        text = (data.get('text') or '').strip()

        if not text:
            return jsonify({
                "success": False,
                "error": "请提供 text（待分类的文本）",
            }), 400

        # 场景分类（原有逻辑不变）
        result = _get_classifier().classify(text)
        result_dict = result.to_dict()

        # 字段提取（新增，独立 LLM 调用）
        try:
            extracted_fields = _get_extractor().extract(text, result.scenario_type)
        except Exception as exc:
            logger.warning("字段提取失败，返回空字段: %s", exc)
            extracted_fields = {}

        result_dict["extracted_fields"] = extracted_fields

        return jsonify({
            "success": True,
            "data": result_dict,
        })

    except ValueError as e:
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


# ---------------------------------------------------------------------------
# POST /api/plainify
# ---------------------------------------------------------------------------

@classify_bp.route('/plainify', methods=['POST'])
def plainify_result():
    """将专业分析结果转换为面向普通用户的大白话解释。

    入参：/api/cogsec/analyze 返回的关键字段（前端自行挑选传入，无固定格式）。
    至少传入一个有意义的字段，否则返回 400。
    """
    try:
        analysis_data = request.get_json(silent=True) or {}

        if not analysis_data:
            return jsonify({
                "success": False,
                "error": "请提供分析结果字段（如 risk_type, confidence, suggestions 等）",
            }), 400

        result = _get_plainifier().plainify(analysis_data)

        return jsonify({
            "success": True,
            "data": result,
        })

    except ValueError as e:
        logger.error("通俗化参数/配置错误: %s", e)
        return jsonify({
            "success": False,
            "error": str(e),
        }), 500
    except Exception as e:
        logger.error("通俗化失败: %s\n%s", e, traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }), 500

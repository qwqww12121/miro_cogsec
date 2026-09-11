"""CogSec 最小 Demo 服务。

说明：
1. 只启动 CogSec 相关 API 与演示页面。
2. 不加载 Zep / OASIS / ReportAgent 主链路。
3. 适合本地最小跑通与可视化演示。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, request


BACKEND_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.cogsec_minimal_runtime import build_demo_llm_client, run_minimal_cogsec_analysis  # noqa: E402


DEFAULT_SCENARIO = (
    "我接到自称电商平台客服的电话，对方说我的快递丢失了，要马上操作退款。"
    "他让我不要告诉别人，直接加QQ，发来一个链接让我填写银行卡和验证码。"
    "我当时有点着急，因为他说今天不处理就会过期。"
)


def create_demo_app() -> Flask:
    """创建只用于 CogSec 演示的 Flask 应用。"""
    demo_llm_client = build_demo_llm_client()

    app = Flask(
        __name__,
        template_folder=str(BACKEND_ROOT / "templates"),
        static_folder=str(BACKEND_ROOT / "static"),
    )

    if hasattr(app, "json") and hasattr(app.json, "ensure_ascii"):
        app.json.ensure_ascii = False

    @app.get("/")
    def index():
        return render_template("cogsec_demo.html", default_scenario=DEFAULT_SCENARIO)

    @app.get("/demo/cogsec")
    def cogsec_demo():
        return render_template("cogsec_demo.html", default_scenario=DEFAULT_SCENARIO)

    @app.get("/health")
    def health():
        llm_mode = "heuristic"
        llm_loaded_device = None
        llm_error = None
        llm_model_path = None
        if demo_llm_client is not None:
            llm_mode = getattr(demo_llm_client, "mode_name", demo_llm_client.__class__.__name__)
            llm_loaded_device = getattr(demo_llm_client, "loaded_device", None)
            llm_error = getattr(demo_llm_client, "last_error", None)
            llm_model_path = getattr(demo_llm_client, "model_path", None)

        return {
            "status": "ok",
            "service": "CogSec Demo",
            "llm_mode": llm_mode,
            "llm_loaded_device": llm_loaded_device,
            "llm_last_error": llm_error,
            "llm_model_path": llm_model_path,
        }

    @app.get("/api/cogsec/sample")
    def sample():
        return {"success": True, "data": {"scenario": DEFAULT_SCENARIO}}

    @app.post("/api/cogsec/analyze")
    def analyze():
        try:
            payload = request.get_json(silent=True) or {}
            scenario = payload.get("scenario") or payload.get("text") or DEFAULT_SCENARIO
            questionnaire = payload.get("questionnaire")
            scenario_type = payload.get("scenario_type") or None

            result = run_minimal_cogsec_analysis(
                scenario_text=scenario,
                questionnaire=questionnaire,
                scenario_type=scenario_type,
                llm_client=demo_llm_client,
            )
            return jsonify({"success": True, "data": result})
        except Exception as exc:  # pragma: no cover
            return jsonify({"success": False, "error": str(exc)}), 500

    return app


def main() -> None:
    """本地启动入口。"""
    port = int(os.environ.get("COGSEC_DEMO_PORT", "5052"))
    host = os.environ.get("COGSEC_DEMO_HOST", "127.0.0.1")
    debug = os.environ.get("COGSEC_DEMO_DEBUG", "false").lower() == "true"

    app = create_demo_app()
    app.run(host=host, port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()

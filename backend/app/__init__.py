"""
MiroFish Backend - Flask应用工厂
"""

import os
import warnings

# 抑制 multiprocessing resource_tracker 的警告（来自第三方库如 transformers）
# 需要在所有其他导入之前设置
warnings.filterwarnings("ignore", message=".*resource_tracker.*")

from flask import Flask, request
from flask_cors import CORS

from .config import Config
from .utils.logger import setup_logger, get_logger


def create_app(config_class=Config):
    """Flask应用工厂函数"""
    config_class.validate()
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # 设置JSON编码：确保中文直接显示（而不是 \uXXXX 格式）
    # Flask >= 2.3 使用 app.json.ensure_ascii，旧版本使用 JSON_AS_ASCII 配置
    if hasattr(app, 'json') and hasattr(app.json, 'ensure_ascii'):
        app.json.ensure_ascii = False
    
    # 设置日志
    logger = setup_logger('mirofish')
    
    # 只在 reloader 子进程中打印启动信息（避免 debug 模式下打印两次）
    is_reloader_process = os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    debug_mode = app.config.get('DEBUG', False)
    should_log_startup = not debug_mode or is_reloader_process
    
    if should_log_startup:
        logger.info("=" * 50)
        logger.info("MiroFish Backend 启动中...")
        logger.info("=" * 50)
    
    # 启用CORS — use the project config instead of an unconditional wildcard.
    configured_origins = config_class.CORS_ORIGINS
    if isinstance(configured_origins, str) and "," in configured_origins:
        configured_origins = [item.strip() for item in configured_origins.split(",") if item.strip()]
    CORS(app, resources={r"/api/*": {"origins": configured_origins}})
    
    # 请求日志中间件
    # Round 1 upgrade: only log metadata, never the full request body.
    # The body may contain raw PII (phone numbers, ID cards, chat content).
    # Full-body logging requires the DEBUG_REQUEST_BODY env switch.
    _log_full_body = os.environ.get('DEBUG_REQUEST_BODY', '').lower() in ('1', 'true', 'yes')

    @app.before_request
    def log_request():
        req_logger = get_logger('mirofish.request')
        req_logger.info(
            "请求: %s %s route=%s content_type=%s",
            request.method, request.path,
            request.endpoint or '-',
            request.content_type or '-',
        )
        if _log_full_body and request.content_type and 'json' in request.content_type:
            req_logger.debug("请求体(DEBUG): %s", request.get_json(silent=True))
    
    @app.after_request
    def log_response(response):
        logger = get_logger('mirofish.request')
        logger.debug(f"响应: {response.status_code}")
        return response
    
    # Register the maintained CogSec surface first.  The original graph,
    # simulation and report stack is isolated behind an explicit compatibility
    # flag so missing Zep/OASIS dependencies cannot break the primary API.
    from .api import (
        classify_bp, cogsec_bp, graph_bp, load_core_routes,
        load_legacy_routes, report_bp, simulation_bp,
    )
    load_core_routes()
    app.register_blueprint(cogsec_bp, url_prefix='/api/cogsec')
    app.register_blueprint(classify_bp, url_prefix='/api')

    if app.config.get('ENABLE_LEGACY_MIROFISH_API', False):
        load_legacy_routes()
        app.register_blueprint(graph_bp, url_prefix='/api/graph')
        app.register_blueprint(simulation_bp, url_prefix='/api/simulation')
        app.register_blueprint(report_bp, url_prefix='/api/report')
        try:
            from .services.simulation_runner import SimulationRunner
            SimulationRunner.register_cleanup()
            if should_log_startup:
                logger.info("已启用原始 MiroFish API，并注册模拟进程清理函数")
        except Exception as exc:
            logger.warning("原始 MiroFish 模拟运行器初始化失败: %s", exc)
    
    # 健康检查
    @app.route('/health')
    def health():
        return {'status': 'ok', 'service': 'MiroFish Backend'}
    
    if should_log_startup:
        logger.info("MiroFish Backend 启动完成")
    
    return app

"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    # 如果根目录没有 .env，尝试加载环境变量（用于生产环境）
    load_dotenv(override=True)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY', 'mirofish-secret-key')
    DEBUG = os.environ.get('FLASK_DEBUG', 'True').lower() == 'true'
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')
    
    # Zep配置
    ZEP_API_KEY = os.environ.get('ZEP_API_KEY')

    # CogSec-MiroFish 配置
    CHROMA_PATH = os.environ.get('CHROMA_PATH', os.path.join(PROJECT_ROOT, 'data', 'chroma_db'))
    FRAUD_CASE_DB_PATH = os.environ.get(
        'FRAUD_CASE_DB_PATH',
        os.path.join(PROJECT_ROOT, 'data', 'fraud_cases.json')
    )
    LOCAL_SANITIZE_ENABLED = os.environ.get('LOCAL_SANITIZE_ENABLED', 'true').lower() == 'true'
    MAX_SIMULATION_STEPS = int(os.environ.get('MAX_SIMULATION_STEPS', '10'))
    RISK_THRESHOLD_CRITICAL = float(os.environ.get('RISK_THRESHOLD_CRITICAL', '20'))
    BRANCH_FORK_MODE = os.environ.get('BRANCH_FORK_MODE', 'parallel')
    PRESIDIO_ENABLED = os.environ.get('PRESIDIO_ENABLED', 'false').lower() == 'true'
    LIWC_DICT_PATH = os.environ.get('LIWC_DICT_PATH', os.path.join(PROJECT_ROOT, 'data', 'liwc_chinese.json'))
    CHROMADB_PATH = os.environ.get('CHROMADB_PATH', CHROMA_PATH)
    T0_PATTERNS_PATH = os.environ.get('T0_PATTERNS_PATH', os.path.join(PROJECT_ROOT, 'data', 't0_regex_patterns.json'))
    FALLBACK_MODEL = os.environ.get('FALLBACK_MODEL', 'qwen2-7b-instruct')
    RISK_SCORE_THRESHOLD_CRITICAL = float(os.environ.get('RISK_SCORE_THRESHOLD_CRITICAL', '0.85'))
    REVERSIBILITY_WARN_THRESHOLD = float(os.environ.get('REVERSIBILITY_WARN_THRESHOLD', '0.3'))
    COGSEC_RUNTIME_TIMEOUT_SEC = float(os.environ.get('COGSEC_RUNTIME_TIMEOUT_SEC', '15'))

    # 本地 Gemma 运行配置
    COGSEC_USE_LOCAL_GEMMA = os.environ.get('COGSEC_USE_LOCAL_GEMMA', 'true').lower() == 'true'
    COGSEC_LOCAL_MODEL_PATH = os.environ.get('COGSEC_LOCAL_MODEL_PATH', os.path.join(PROJECT_ROOT, 'models', 'google--gemma-4-E2B-it'))
    COGSEC_LOCAL_GEMMA_DEVICE = os.environ.get('COGSEC_LOCAL_GEMMA_DEVICE', 'auto')
    COGSEC_LOCAL_GEMMA_DTYPE = os.environ.get('COGSEC_LOCAL_GEMMA_DTYPE', 'auto')
    COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS = int(os.environ.get('COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS', '768'))
    COGSEC_LOCAL_GEMMA_OFFLOAD_DIR = os.environ.get('COGSEC_LOCAL_GEMMA_OFFLOAD_DIR', os.path.join(PROJECT_ROOT, 'backend', '.cache', 'gemma_offload'))

    # 兼容本地开发：默认不强制外部 key（可通过 MIROFISH_STRICT_CONFIG=true 切回严格模式）
    MIROFISH_STRICT_CONFIG = os.environ.get('MIROFISH_STRICT_CONFIG', 'false').lower() == 'true'
    
    # 文件上传配置
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB
    UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), '../uploads')
    ALLOWED_EXTENSIONS = {'pdf', 'md', 'txt', 'markdown'}
    
    # 文本处理配置
    DEFAULT_CHUNK_SIZE = 500  # 默认切块大小
    DEFAULT_CHUNK_OVERLAP = 50  # 默认重叠大小
    
    # OASIS模拟配置
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get('OASIS_DEFAULT_MAX_ROUNDS', '10'))
    OASIS_SIMULATION_DATA_DIR = os.path.join(os.path.dirname(__file__), '../uploads/simulations')
    
    # OASIS平台可用动作配置
    OASIS_TWITTER_ACTIONS = [
        'CREATE_POST', 'LIKE_POST', 'REPOST', 'FOLLOW', 'DO_NOTHING', 'QUOTE_POST'
    ]
    OASIS_REDDIT_ACTIONS = [
        'LIKE_POST', 'DISLIKE_POST', 'CREATE_POST', 'CREATE_COMMENT',
        'LIKE_COMMENT', 'DISLIKE_COMMENT', 'SEARCH_POSTS', 'SEARCH_USER',
        'TREND', 'REFRESH', 'DO_NOTHING', 'FOLLOW', 'MUTE'
    ]
    
    # Report Agent配置
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get('REPORT_AGENT_MAX_TOOL_CALLS', '5'))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get('REPORT_AGENT_MAX_REFLECTION_ROUNDS', '2'))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get('REPORT_AGENT_TEMPERATURE', '0.5'))
    
    @classmethod
    def validate(cls):
        """验证必要配置"""
        errors = []
        if not cls.LLM_API_KEY and not cls.COGSEC_USE_LOCAL_GEMMA:
            errors.append("LLM_API_KEY 未配置")
        if cls.MIROFISH_STRICT_CONFIG and not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors

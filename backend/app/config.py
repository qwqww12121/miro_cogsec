"""
配置管理
统一从项目根目录的 .env 文件加载配置
"""

import os
from dotenv import load_dotenv

# 加载项目根目录的 .env 文件（仅显式路径，不自动向上查找）
# 路径: MiroFish/.env (相对于 backend/app/config.py)
project_root_env = os.path.join(os.path.dirname(__file__), '../../.env')
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))

if os.environ.get('MIRO_DISABLE_DOTENV', 'false').lower() != 'true':
    if os.path.exists(project_root_env):
        # Explicit process/container variables take precedence over the local
        # developer file.  This also lets test runners blank credentials
        # without a checked-in .env unexpectedly enabling network calls.
        load_dotenv(project_root_env, override=False)
    else:
        # 如果根目录没有 .env，加载当前工作目录的 .env（仅当前目录，不向上查找）
        load_dotenv(dotenv_path=os.path.join(os.getcwd(), '.env'), override=False)


class Config:
    """Flask配置类"""
    
    # Flask配置
    SECRET_KEY = os.environ.get('SECRET_KEY')
    DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

    @classmethod
    def _ensure_secret_key(cls):
        """Validate SECRET_KEY is configured in production (non-DEBUG mode)."""
        if not cls.DEBUG and not cls.SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY must be configured via environment variable in production mode. "
                "Set FLASK_DEBUG=true for development with auto-generated key."
            )
        if not cls.SECRET_KEY:
            # Dev fallback: auto-generate a key for local development
            import os as _os
            cls.SECRET_KEY = 'dev-' + _os.urandom(24).hex()
    
    # JSON配置 - 禁用ASCII转义，让中文直接显示（而不是 \uXXXX 格式）
    JSON_AS_ASCII = False

    # CORS — restrict in production via CORS_ORIGINS env var
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '*' if DEBUG else '')
    
    # LLM配置（统一使用OpenAI格式）
    LLM_API_KEY = os.environ.get('LLM_API_KEY')
    LLM_BASE_URL = os.environ.get('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = os.environ.get('LLM_MODEL_NAME', 'gpt-4o-mini')

    # Round 3 → Final: 项目专用 API Key — 禁止自动借用其他项目的 Key
    # OASIS 专用 Key（永远不 fallback）
    MIRO_COGSEC_OASIS_API_KEY = os.environ.get('MIRO_COGSEC_OASIS_API_KEY')
    MIRO_COGSEC_OASIS_MODEL = os.environ.get('MIRO_COGSEC_OASIS_MODEL')
    MIRO_COGSEC_OASIS_BASE_URL = os.environ.get('MIRO_COGSEC_OASIS_BASE_URL')
    # 主分析专用 Key（不 fallback 到 LLM_API_KEY，除非显式开启兼容模式）
    MIRO_COGSEC_MAIN_LLM_API_KEY = os.environ.get('MIRO_COGSEC_MAIN_LLM_API_KEY')
    MIRO_COGSEC_MAIN_LLM_MODEL = os.environ.get('MIRO_COGSEC_MAIN_LLM_MODEL', LLM_MODEL_NAME)
    MIRO_COGSEC_MAIN_LLM_BASE_URL = os.environ.get('MIRO_COGSEC_MAIN_LLM_BASE_URL', LLM_BASE_URL)
    MIRO_COGSEC_MAIN_LLM_CONNECT_TIMEOUT_SEC = float(os.environ.get('MIRO_COGSEC_MAIN_LLM_CONNECT_TIMEOUT_SEC', '15'))
    MIRO_COGSEC_MAIN_LLM_READ_TIMEOUT_SEC = float(os.environ.get('MIRO_COGSEC_MAIN_LLM_READ_TIMEOUT_SEC', '45'))
    MIRO_COGSEC_MAIN_LLM_RETRIES = int(os.environ.get('MIRO_COGSEC_MAIN_LLM_RETRIES', '1'))
    # Some institutional OpenAI-compatible gateways expose a certificate
    # chain that is not trusted by the local Windows CA store.  Keep TLS
    # verification enabled by default; disabling it is an explicit,
    # process-local opt-in for a trusted internal test endpoint.
    MIRO_COGSEC_MAIN_LLM_VERIFY_SSL = os.environ.get(
        'MIRO_COGSEC_MAIN_LLM_VERIFY_SSL', 'true'
    ).lower() != 'false'
    MIRO_COGSEC_MAIN_LLM_TRUST_ENV = os.environ.get(
        'MIRO_COGSEC_MAIN_LLM_TRUST_ENV', 'true'
    ).lower() != 'false'
    _thinking_param = os.environ.get('MIRO_COGSEC_MAIN_LLM_SEND_THINKING_PARAM')
    # ``None`` lets the client infer provider compatibility from the endpoint.
    MIRO_COGSEC_MAIN_LLM_SEND_THINKING_PARAM = (
        None if _thinking_param is None else _thinking_param.lower() != 'false'
    )
    # 旧版兼容开关：默认关闭，必须用户显式开启才允许 LLM_API_KEY 作为主分析 fallback
    MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY = os.environ.get('MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY', 'false').lower() == 'true'
    
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
    # ``auto`` uses LLM profiling for person-specific fraud cases and the
    # deterministic/LIWC extractor for aggregate public/event inputs where a
    # personal 18-dimension profile is not identifiable from the text.
    MIRO_COGSEC_PROFILE_MODE = os.environ.get('MIRO_COGSEC_PROFILE_MODE', 'auto').lower()

    # Single-stage intervention ranking. Fixed weights remain the default
    # baseline; learned modes are opt-in and preserve metric provenance.
    INTERVENTION_RANKER_MODE = os.environ.get('MIRO_INTERVENTION_RANKER_MODE', 'fixed_weight')
    INTERVENTION_RANKER_WEIGHTS_PATH = os.environ.get('MIRO_INTERVENTION_RANKER_WEIGHTS_PATH')
    CAUSAL_TARGETING_MODE = os.environ.get('MIRO_CAUSAL_TARGETING_MODE', 'causal_targeting')
    INTERVENTION_CANDIDATE_MODE = os.environ.get('MIRO_INTERVENTION_CANDIDATE_MODE', 'fixed_candidate_template')

    # The original graph/simulation/report APIs are retained for research
    # compatibility, but are not imported into the CogSec service by default.
    ENABLE_LEGACY_MIROFISH_API = os.environ.get('ENABLE_LEGACY_MIROFISH_API', 'false').lower() == 'true'

    # 本地 Gemma 运行配置
    # Local inference must be explicitly selected.  A default-true value made
    # a missing local directory shadow an otherwise valid external API key.
    COGSEC_USE_LOCAL_GEMMA = os.environ.get('COGSEC_USE_LOCAL_GEMMA', 'false').lower() == 'true'
    COGSEC_LOCAL_MODEL_PATH = os.environ.get('COGSEC_LOCAL_MODEL_PATH', os.path.join(PROJECT_ROOT, 'models', 'google--gemma-4-E2B-it'))
    COGSEC_LOCAL_GEMMA_DEVICE = os.environ.get('COGSEC_LOCAL_GEMMA_DEVICE', 'auto')
    COGSEC_LOCAL_GEMMA_DTYPE = os.environ.get('COGSEC_LOCAL_GEMMA_DTYPE', 'auto')
    COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS = int(os.environ.get('COGSEC_LOCAL_GEMMA_MAX_NEW_TOKENS', '768'))
    COGSEC_LOCAL_GEMMA_OFFLOAD_DIR = os.environ.get('COGSEC_LOCAL_GEMMA_OFFLOAD_DIR', os.path.join(PROJECT_ROOT, 'backend', '.cache', 'gemma_offload'))

    # Final response policy.  This remains behind the existing CogSec API;
    # only the internal last-mile renderer changes.
    # auto: configured main/local client -> grounded LLM reporter -> deterministic fallback
    MIRO_REPORTER_POLICY_MODE = os.environ.get('MIRO_REPORTER_POLICY_MODE', 'auto').lower()
    # Optional dedicated OpenAI-compatible reporter.  This is the intended
    # hook for a small/fast output model: it only sees ReportState and never
    # participates in the upstream analysis or benchmark scoring chain.
    MIRO_REPORTER_API_KEY = os.environ.get('MIRO_REPORTER_API_KEY')
    MIRO_REPORTER_BASE_URL = os.environ.get('MIRO_REPORTER_BASE_URL')
    MIRO_REPORTER_MODEL = os.environ.get('MIRO_REPORTER_MODEL')
    MIRO_REPORTER_CONNECT_TIMEOUT_SEC = float(os.environ.get('MIRO_REPORTER_CONNECT_TIMEOUT_SEC', '15'))
    MIRO_REPORTER_READ_TIMEOUT_SEC = float(os.environ.get('MIRO_REPORTER_READ_TIMEOUT_SEC', '45'))
    MIRO_REPORTER_RETRIES = int(os.environ.get('MIRO_REPORTER_RETRIES', '1'))
    MIRO_REPORTER_ENABLE_THINKING = os.environ.get('MIRO_REPORTER_ENABLE_THINKING', 'false').lower() == 'true'
    # Dual-view reporter: one JSON answer with professional_message (~600 chars)
    # + plain_view translation (~400-900 chars) + most_important_action.
    # Reasoning-style providers may additionally burn ~1-2k invisible
    # reasoning tokens before the JSON, so 4000 leaves headroom for the
    # retry pass (+400) without hitting finish_reason=length (which returns
    # empty content).  The cap does not increase the cost of successful calls.
    MIRO_REPORTER_OUTPUT_MAX_TOKENS = int(os.environ.get('MIRO_REPORTER_OUTPUT_MAX_TOKENS', '4000'))
    MIRO_REPORTER_MODEL_PATH = os.environ.get('MIRO_REPORTER_MODEL_PATH')
    MIRO_REPORTER_ADAPTER_PATH = os.environ.get('MIRO_REPORTER_ADAPTER_PATH')
    MIRO_REPORTER_DEVICE = os.environ.get('MIRO_REPORTER_DEVICE', COGSEC_LOCAL_GEMMA_DEVICE)
    MIRO_REPORTER_DTYPE = os.environ.get('MIRO_REPORTER_DTYPE', COGSEC_LOCAL_GEMMA_DTYPE)
    MIRO_REPORTER_MAX_NEW_TOKENS = int(os.environ.get('MIRO_REPORTER_MAX_NEW_TOKENS', '900'))
    MIRO_REPORTER_OFFLOAD_DIR = os.environ.get(
        'MIRO_REPORTER_OFFLOAD_DIR',
        os.path.join(PROJECT_ROOT, 'backend', '.cache', 'reporter_offload'),
    )

    # Fraud actors are stateful agents even when their action selector is a
    # deterministic policy.  Keeping the selector explicit avoids 24 remote
    # calls per case merely to obtain one token.  Set to ``llm`` for research
    # runs that intentionally compare LLM-driven agent decisions.
    MIRO_FRAUD_AGENT_POLICY_MODE = os.environ.get(
        'MIRO_FRAUD_AGENT_POLICY_MODE', 'deterministic'
    ).lower()

    # Multimodal input adapters.  File parsing reuses the existing
    # FileParser/session ingestor; speech is optional and follows an
    # OpenAI-compatible transcription contract (or local faster-whisper).
    MIRO_SPEECH_PROVIDER = os.environ.get('MIRO_SPEECH_PROVIDER', 'auto').lower()
    MIRO_SPEECH_API_KEY = os.environ.get('MIRO_SPEECH_API_KEY')
    MIRO_SPEECH_BASE_URL = os.environ.get('MIRO_SPEECH_BASE_URL')
    MIRO_SPEECH_MODEL = os.environ.get('MIRO_SPEECH_MODEL', 'whisper-1')
    MIRO_SPEECH_LANGUAGE = os.environ.get('MIRO_SPEECH_LANGUAGE', 'zh')
    MIRO_SPEECH_CONNECT_TIMEOUT_SEC = float(os.environ.get('MIRO_SPEECH_CONNECT_TIMEOUT_SEC', '15'))
    MIRO_SPEECH_READ_TIMEOUT_SEC = float(os.environ.get('MIRO_SPEECH_READ_TIMEOUT_SEC', '120'))
    MIRO_SPEECH_LOCAL_MODEL = os.environ.get('MIRO_SPEECH_LOCAL_MODEL', 'small')
    MIRO_SPEECH_LOCAL_DEVICE = os.environ.get('MIRO_SPEECH_LOCAL_DEVICE', 'cpu')
    MIRO_SPEECH_LOCAL_COMPUTE_TYPE = os.environ.get('MIRO_SPEECH_LOCAL_COMPUTE_TYPE', 'int8')

    # Training is opt-in.  Runtime and benchmark commands never start PPO.
    ENABLE_PPO_TRAINING = os.environ.get('ENABLE_PPO_TRAINING', 'false').lower() == 'true'
    ENABLE_REPORTER_TRAINING = os.environ.get('ENABLE_REPORTER_TRAINING', 'false').lower() == 'true'
    MIRO_PPO_POLICY_PATH = os.environ.get('MIRO_PPO_POLICY_PATH')
    MIRO_INTERVENTION_POLICY_MODE = os.environ.get('MIRO_INTERVENTION_POLICY_MODE', 'ranker').lower()

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
    OASIS_TRACE_RETENTION = os.environ.get('OASIS_TRACE_RETENTION', 'metadata')  # none | metadata | sanitized_full
    # Candidate verification stays cheap by default.  Formal experiments can
    # opt into Top-K=2 and multiple seeds without changing application code.
    MIRO_OASIS_VERIFICATION_QUICK_MODE = os.environ.get(
        'MIRO_OASIS_VERIFICATION_QUICK_MODE', 'true'
    ).lower() == 'true'
    MIRO_OASIS_VERIFICATION_K = max(1, int(os.environ.get('MIRO_OASIS_VERIFICATION_K', '1')))
    MIRO_OASIS_VERIFICATION_SEED = int(os.environ.get('MIRO_OASIS_VERIFICATION_SEED', '42'))
    # random: no Hugging Face recsys download. twhin-openai uses embedding API.
    MIRO_OASIS_RECSYS = os.environ.get('MIRO_OASIS_RECSYS', 'random')
    MIRO_OASIS_TIMEOUT_SEC = float(os.environ.get('MIRO_OASIS_TIMEOUT_SEC', '10'))
    
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
        cls._ensure_secret_key()
        main_key_available = bool(cls.MIRO_COGSEC_MAIN_LLM_API_KEY)
        legacy_key_available = bool(cls.MIRO_COGSEC_ALLOW_LEGACY_LLM_KEY and cls.LLM_API_KEY)
        if not (main_key_available or legacy_key_available) and not cls.COGSEC_USE_LOCAL_GEMMA:
            errors.append("MIRO_COGSEC_MAIN_LLM_API_KEY 未配置")
        if cls.MIROFISH_STRICT_CONFIG and not cls.ZEP_API_KEY:
            errors.append("ZEP_API_KEY 未配置")
        return errors

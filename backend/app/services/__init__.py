"""业务服务模块。"""

# 说明：部分服务依赖可选三方库（如 zep_cloud）。
# 为支持 CogSec 本地最小运行，这里做软导入，缺失依赖时只影响对应子模块。

from .cogsec_service import CogSecAnalysisResult, CogSecService

try:
    from .ontology_generator import OntologyGenerator
except Exception:  # pragma: no cover
    OntologyGenerator = None

try:
    from .graph_builder import GraphBuilderService
except Exception:  # pragma: no cover
    GraphBuilderService = None

try:
    from .text_processor import TextProcessor
except Exception:  # pragma: no cover
    TextProcessor = None

try:
    from .zep_entity_reader import ZepEntityReader, EntityNode, FilteredEntities
except Exception:  # pragma: no cover
    ZepEntityReader = None
    EntityNode = None
    FilteredEntities = None

try:
    from .oasis_profile_generator import OasisProfileGenerator, OasisAgentProfile
except Exception:  # pragma: no cover
    OasisProfileGenerator = None
    OasisAgentProfile = None

try:
    from .simulation_manager import SimulationManager, SimulationState, SimulationStatus
except Exception:  # pragma: no cover
    SimulationManager = None
    SimulationState = None
    SimulationStatus = None

try:
    from .simulation_config_generator import (
        SimulationConfigGenerator,
        SimulationParameters,
        AgentActivityConfig,
        TimeSimulationConfig,
        EventConfig,
        PlatformConfig,
    )
except Exception:  # pragma: no cover
    SimulationConfigGenerator = None
    SimulationParameters = None
    AgentActivityConfig = None
    TimeSimulationConfig = None
    EventConfig = None
    PlatformConfig = None

try:
    from .simulation_runner import (
        SimulationRunner,
        SimulationRunState,
        RunnerStatus,
        AgentAction,
        RoundSummary,
    )
except Exception:  # pragma: no cover
    SimulationRunner = None
    SimulationRunState = None
    RunnerStatus = None
    AgentAction = None
    RoundSummary = None

try:
    from .zep_graph_memory_updater import (
        ZepGraphMemoryUpdater,
        ZepGraphMemoryManager,
        AgentActivity,
    )
except Exception:  # pragma: no cover
    ZepGraphMemoryUpdater = None
    ZepGraphMemoryManager = None
    AgentActivity = None

try:
    from .simulation_ipc import (
        SimulationIPCClient,
        SimulationIPCServer,
        IPCCommand,
        IPCResponse,
        CommandType,
        CommandStatus,
    )
except Exception:  # pragma: no cover
    SimulationIPCClient = None
    SimulationIPCServer = None
    IPCCommand = None
    IPCResponse = None
    CommandType = None
    CommandStatus = None


__all__ = [
    'OntologyGenerator',
    'GraphBuilderService',
    'TextProcessor',
    'ZepEntityReader',
    'EntityNode',
    'FilteredEntities',
    'OasisProfileGenerator',
    'OasisAgentProfile',
    'SimulationManager',
    'SimulationState',
    'SimulationStatus',
    'SimulationConfigGenerator',
    'SimulationParameters',
    'AgentActivityConfig',
    'TimeSimulationConfig',
    'EventConfig',
    'PlatformConfig',
    'SimulationRunner',
    'SimulationRunState',
    'RunnerStatus',
    'AgentAction',
    'RoundSummary',
    'ZepGraphMemoryUpdater',
    'ZepGraphMemoryManager',
    'AgentActivity',
    'SimulationIPCClient',
    'SimulationIPCServer',
    'IPCCommand',
    'IPCResponse',
    'CommandType',
    'CommandStatus',
    'CogSecAnalysisResult',
    'CogSecService',
]

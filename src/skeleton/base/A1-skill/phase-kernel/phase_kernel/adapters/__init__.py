"""phase-kernel 适配器层（设计稿 §二：差异全在 adapters/）

core/ 与 ports/ 零 tc / sl / 外部服务依赖；所有后端差异在此实现。
"""

from .sqlite_store import SqliteStore
from .tc_executor import TCExecutor
from .tc_planner import TCPlanner
from .mechanical_planner import MechanicalPlanner
from .strata_matcher import StrataMatcher
from .llm_gate import LLMGate
from .local_executor import LocalExecutor
from .artifact_store import InMemoryArtifactStore

__all__ = [
    "SqliteStore", "TCExecutor", "TCPlanner",
    "MechanicalPlanner", "StrataMatcher", "LLMGate", "LocalExecutor",
    "InMemoryArtifactStore",
]

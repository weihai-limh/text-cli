"""phase-kernel —— 协议无关、tc 无关的相位推理机制（设计稿 §二）

core/ 与 ports/ 零外部依赖；差异全在 adapters/。

双形态（Phase 6，块3）：
- 形态一：独立 serve（`python -m phase_kernel.serve.server` 或等价入口）。
- 形态二：组件集成——上层应用 `from phase_kernel import PhaseReasoningEngine` 等，
  用 adapter 装配自己的执行体/规划器后直接驱动（sl 只需改 import，不碰内核）。
"""

from .core.models import (
    PhaseStatus, PipelineStatus, PhaseGates, PhaseDef, PhasePlan, PhaseKind,
    PhaseArtifact, PhaseResult, PipelineSession, GateType, GateResult,
)
from .core.gates import PhaseGateExecutor, MechanicalGate
from .core.actions import PhaseAction
from .orchestrator import PhaseReasoningEngine
from .ports import Executor, Planner, Store, Gate, ToolCatalog, ArtifactStore
from .adapters import (
    MechanicalPlanner, TCPlanner, StrataMatcher, TCExecutor, LocalExecutor,
    SqliteStore, InMemoryArtifactStore,
)

__all__ = [
    "PhaseStatus", "PipelineStatus", "PhaseGates", "PhaseDef", "PhasePlan", "PhaseKind",
    "PhaseArtifact", "PhaseResult", "PipelineSession", "GateType", "GateResult",
    "PhaseGateExecutor", "MechanicalGate", "PhaseAction", "PhaseReasoningEngine",
    "Executor", "Planner", "Store", "Gate", "ToolCatalog", "ArtifactStore",
    "MechanicalPlanner", "TCPlanner", "StrataMatcher", "TCExecutor", "LocalExecutor",
    "SqliteStore", "InMemoryArtifactStore",
]

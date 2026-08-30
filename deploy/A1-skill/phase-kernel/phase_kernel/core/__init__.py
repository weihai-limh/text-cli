"""phase-kernel 通用核（设计稿 §二）

零外部依赖：core/ 不 import 任何 tc / sl / FastAPI / 第三方包。
只依赖标准库 + 自身模块。
"""

from .models import (
    PhaseStatus, PipelineStatus, PhaseGates, PhaseDef, PhasePlan,
    PhaseArtifact, PhaseResult, PipelineSession, GateType, GateResult,
)
from .gates import PhaseGateExecutor, MechanicalGate
from .actions import PhaseAction

__all__ = [
    "PhaseStatus", "PipelineStatus", "PhaseGates", "PhaseDef", "PhasePlan",
    "PhaseArtifact", "PhaseResult", "PipelineSession", "GateType", "GateResult",
    "PhaseGateExecutor", "MechanicalGate", "PhaseAction",
]

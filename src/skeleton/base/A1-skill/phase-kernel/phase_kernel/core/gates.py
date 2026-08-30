"""三闸状态操作 + 机械闸门（设计稿 §4；ported from synth-loop phase_executor.py）

纪律：core/gates.py 零 tc/sl import，只操作 core/models 的 PipelineSession。

两类东西：
1. PhaseGateExecutor —— 三闸的「状态操作」（start/confirm/evaluate/approve/reject），
   直接改写 PipelineSession 状态机。这是 synth-loop phase_executor 的通用部分。
2. MechanicalGate —— 质量闸的「判定者」（实现 ports.Gate 协议）：比对
   PhaseResult.status 闭集，不调用 LLM。这是 aaa.md「状态可知性」的落实（§4.1）。
   LLMGate / HumanGate 是注入实现，放在 adapters/（需 LLM/人 I/O）。
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from .models import (
    PipelineSession, PhaseDef, PhaseStatus, GateType, GateResult,
)


class PhaseGateExecutor:
    """三闸状态机操作（零业务耦合，ported from synth-loop PhaseExecutor）"""

    async def start_phase(self, session: PipelineSession, phase: PhaseDef) -> Optional[PhaseDef]:
        """开始执行下一个待处理相位

        闸2 allow_path_edit → 先 AWAITING_PATH_CONFIRM 等外部 confirm path；
        闸2 OFF → 直接进 RUNNING。
        """
        if phase is None:
            return None
        if phase.gates.allow_path_edit:
            phase.status = PhaseStatus.AWAITING_PATH_CONFIRM
            session.updated_at = datetime.now()
            return phase
        phase.status = PhaseStatus.RUNNING
        session.advance_phase(phase.index, PhaseStatus.RUNNING)
        session.updated_at = datetime.now()
        return phase

    async def confirm_path(self, session: PipelineSession, phase_index: int,
                           confirmed: bool = True) -> PhaseDef:
        """闸2：确认 path JSON → 进 RUNNING（confirmed=False → 相位 FAILED）"""
        if phase_index >= len(session.phases):
            raise IndexError(f"Phase {phase_index} out of range")
        phase = session.phases[phase_index]
        if phase.status != PhaseStatus.AWAITING_PATH_CONFIRM:
            raise ValueError(f"Phase {phase_index} not awaiting path confirm (status={phase.status})")
        if not confirmed:
            phase.status = PhaseStatus.FAILED
            session.updated_at = datetime.now()
            return phase
        phase.status = PhaseStatus.RUNNING
        session.advance_phase(phase_index, PhaseStatus.RUNNING)
        session.updated_at = datetime.now()
        return phase

    async def evaluate_quality_gate(self, session: PipelineSession, phase: PhaseDef,
                                    execution_passed: bool, detail: str = "") -> PhaseStatus:
        """评估执行结果质量闸（设计稿 §4）

        执行完成先评估 → passed? 检查闸3 / failed? 相位 FAILED。
        闭集读取，不依赖 LLM（§一.2）。gate_reliability g 由判定者侧记录（见 MechanicalGate）。

        分形感知（Phase 1）：直接操作传入的 `phase` 对象，而非 `session.phases[phase_index]` 反查——
        因为含 NODE/children 时，相位不在顶层 index 序列里。`phase.index` 仅作历史/检查点记录（相对索引）。
        """
        phase_index = phase.index
        gate_type = GateType.EXECUTION_RESULT.value
        result = GateResult.PASSED.value if execution_passed else GateResult.FAILED.value
        session.add_quality_gate(phase_index, gate_type, result, detail)

        if not execution_passed:
            phase.status = PhaseStatus.FAILED
            session.updated_at = datetime.now()
            return PhaseStatus.FAILED

        if phase.gates.require_human_approval:
            phase.status = PhaseStatus.AWAITING_APPROVAL
            session.updated_at = datetime.now()
            return PhaseStatus.AWAITING_APPROVAL

        phase.status = PhaseStatus.COMPLETED
        session.advance_phase(phase_index, PhaseStatus.COMPLETED, output=f"Phase {phase_index} completed")
        session.checkpoint(phase_index)  # 检查点推进（子命题1）
        session.updated_at = datetime.now()
        return PhaseStatus.COMPLETED

    async def approve_phase(self, session: PipelineSession, phase: PhaseDef) -> PhaseDef:
        """闸3：审批通过 → COMPLETED + 检查点推进（分形感知：操作 phase 对象而非 index 反查）"""
        phase_index = phase.index
        if phase.status != PhaseStatus.AWAITING_APPROVAL:
            raise ValueError(f"Phase {phase_index} not awaiting approval (status={phase.status})")
        phase.status = PhaseStatus.COMPLETED
        session.add_quality_gate(phase_index, GateType.HUMAN_REVIEW.value,
                                  GateResult.PASSED.value, "approved by human")
        session.advance_phase(phase_index, PhaseStatus.COMPLETED, output=f"Phase {phase_index} approved")
        session.checkpoint(phase_index)
        session.updated_at = datetime.now()
        return phase

    async def reject_phase(self, session: PipelineSession, phase: PhaseDef, feedback: str) -> PhaseDef:
        """闸3：驳回 → RUNNING（重试，反馈注入下一轮）；内部触发 rollback_to(checkpoint)
        （分形感知：操作 phase 对象而非 index 反查）。

        Phase 重构 P4：`retry_phase` 的兼容别名（人闸三态 retry 语义）。
        """
        return await self.retry_phase(session, phase, feedback)

    async def retry_phase(self, session: PipelineSession, phase: PhaseDef,
                          feedback: str) -> PhaseDef:
        """闸3：人闸 retry（Phase 重构 P4）——按 `phase_path` 定位的受控写入口。

        相位状态 AWAITING_APPROVAL → RUNNING（重试，反馈注入下一轮）；内部触发
        rollback_to(checkpoint)。`phase.path` 为树路径定位（替换现 phase.index 反查）。
        与 `abort_tree` 组成人闸三态 approve/retry/abort_tree（redirect 本期不做）。
        """
        phase_path = phase.path
        phase_index = phase.index
        if phase.status != PhaseStatus.AWAITING_APPROVAL:
            raise ValueError(f"Phase {phase_index} not awaiting approval (status={phase.status})")
        phase.status = PhaseStatus.RUNNING
        session.add_quality_gate(phase_index, GateType.HUMAN_REVIEW.value,
                                  GateResult.FAILED.value, f"retry: {feedback}")
        session.updated_at = datetime.now()
        return phase

    async def abort_tree(self, session: PipelineSession) -> PipelineSession:
        """闸3：人闸 abort_tree（Phase 重构 P4）——置整树 ABORTED。

        复用 `PipelineSession.abort()`（已置整树 ABORTED + updated_at），返回 session。
        """
        session.abort("aborted by human (abort_tree)")
        return session


class MechanicalGate:
    """默认质量闸判定者（设计稿 §4.1）

    比对 PhaseResult.status 闭集：success → True，failed → False。
    不调用 LLM。gate_reliability 默认按会话相位 g 记录（诚实标注：默认 1.0 偏乐观）。
    """

    def __init__(self, gate_reliability: float = 1.0):
        self.gate_reliability = gate_reliability

    async def decide(self, phase: PhaseDef, result) -> bool:
        # 闭集读取：状态可知不是因为系统聪明，而是因为闭集信封（aaa.md 状态可知性）
        return result.status == "success"

"""MechanicalPlanner（设计稿 §13.6.2 二级回退；纯机械极小规划，零 LLM）

P_ctrl 不依赖 LLM 仍可推进的底线：当 strata-match 与 LLM 都不可用时，
状态机退化为纯机械极小规划——按 endpoint_hint 直发 tc path（或单相位直接执行）。
本规划器不调用任何模型，只产出结构合法的相位树（机制守「相位树形状」）。

这是 synth-loop 现状缺失的一层（sl 只返回默认两相位、path 仍靠 LLM）；本机制补上「可控的可靠」底线。
"""

from __future__ import annotations

from typing import Any

from ..core.models import PhaseDef, PhasePlan, PhaseGates


class MechanicalPlanner:
    """纯机械规划器（实现 ports.Planner，零 LLM）

    策略：
    - 若 goal 显式含多步标记（如「先…再…最后」）→ 拆为对应相位；
    - 否则 → 单相位直接执行（最小面，P_ctrl 不依赖 LLM 仍推进）。
    """

    async def plan(self, goal_repr: Any, context: dict) -> PhasePlan:
        # 兼容 PhaseDef（分形下钻传真实相位，Phase 5）：取 name 作 goal 文本
        if isinstance(goal_repr, PhaseDef):
            goal_repr = goal_repr.name or goal_repr.description or ""
        goal = str(goal_repr or "")
        steps = [s.strip() for s in goal.replace("，", ",").split(",") if s.strip()]
        # 极简启发：若 goal 含「先/再/然后/最后/分三步」等，拆相位；否则单相位
        multi = any(k in goal for k in ("先", "再", "然后", "最后", "分", "步骤", "阶段"))
        if multi and len(steps) >= 2:
            phases = [
                PhaseDef(index=i, name=f"步骤{i+1}", description=s,
                         gates=PhaseGates(), endpoint_hint=context.get("endpoint_hint"))
                for i, s in enumerate(steps)
            ]
        else:
            phases = [PhaseDef(index=0, name="执行", description=goal[:80],
                               gates=PhaseGates(), endpoint_hint=context.get("endpoint_hint"))]
        return PhasePlan(phases=phases)

    async def regenerate(self, phase, feedback: str) -> PhasePlan:
        return await self.plan(feedback, {})

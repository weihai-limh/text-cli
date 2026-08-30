"""TCPlanner（设计稿 §七.4 / §3.2；适配器层）

封装「焊死的 _PLANNING_SYSTEM_PROMPT + LLM 调用」→ ports.Planner。
本 Phase 仅焊死 prompt 占位；Phase 4 接 strata-match 替换主路径（§13.6）。
无 LLM 注入时回落默认 3 相位规划（降级默认规划，§13.6.2 一级/二级回退的基座）。

纪律：core/ 零 LLM / sl import；只有本适配器（adapters/）碰 LLM 调用。
"""

from __future__ import annotations

import json
from typing import Any, Callable, Optional

from ..core.models import PhaseDef, PhasePlan, PhaseGates


_PLANNING_SYSTEM_PROMPT = """你是任务规划器。将用户意图拆分为多个相位（phase），每个相位是一个可执行的步骤。

输出格式（严格 JSON）：
{"phases": [{"index": 0, "name": "相位名", "description": "该相位要做什么（含目标）", "mode": "single_ai"}]}

要求：
1. 相位划分要合理，每个相位目标明确
2. 3-6 个相位为佳
3. 只输出 JSON，不要其他文字"""


def _default_three_phase_plan(goal: str) -> PhasePlan:
    """降级默认规划（对齐 synth-loop 写死的两/三相位；升为可配置在 Phase 4）"""
    return PhasePlan(phases=[
        PhaseDef(index=0, name="需求分析", description=f"分析需求：{goal[:50]}", gates=PhaseGates()),
        PhaseDef(index=1, name="执行", description="执行主要任务", gates=PhaseGates()),
        PhaseDef(index=2, name="总结", description="总结并输出结果", gates=PhaseGates()),
    ])


class TCPlanner:
    """tc 规划适配器（实现 ports.Planner）

    llm: 可选异步 callable(messages: list[dict]) -> str。传入则真规划；
         为 None（--no-strata / 无 LLM 环境）→ 默认规划，保证 P_ctrl 不依赖 LLM 仍可推进。
    """

    def __init__(self, llm: Optional[Callable[[list[dict]], Any]] = None):
        self._llm = llm

    async def plan(self, goal_repr: Any, context: dict) -> PhasePlan:
        if self._llm is None:
            return _default_three_phase_plan(str(goal_repr))
        messages = [
            {"role": "system", "content": _PLANNING_SYSTEM_PROMPT},
            {"role": "user", "content": f"用户意图：{goal_repr}"},
        ]
        try:
            content = await _maybe_await(self._llm(messages))
            data = json.loads(content)
            phases = data.get("phases", [])
            if not phases:
                raise ValueError("规划为空")
            return PhasePlan(phases=[
                PhaseDef(index=int(p["index"]), name=p["name"],
                         description=p.get("description", ""), mode=p.get("mode", "single_ai"),
                         gates=PhaseGates.from_dict(p.get("gates", {})))
                for p in phases
            ])
        except Exception:
            # 规划非法/LLM 失败 → 机械兜底（§13.4①；不依赖 LLM）
            return _default_three_phase_plan(str(goal_repr))

    async def regenerate(self, phase, feedback: str) -> PhasePlan:
        if phase is None:
            return _default_three_phase_plan(feedback)
        # 单相位重规划：保持其它相位，重生成当前相位描述
        return _default_three_phase_plan(feedback)


async def _maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value

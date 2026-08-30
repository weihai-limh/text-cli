"""LLMGate（设计稿 §4.1 / §13.4②；注入式质量判定者）

默认实现是 MechanicalGate（闭集比对，零 LLM）。LLMGate 把「质量判定」交给 LLM：
LLM 自由文本结论强制映射回闭集 bool（不污染 P_ctrl）；其 gate_reliability g<1.0
写入 phase_summaries 供审计（诚实标注，§4.2）。LLM 不可用时回落 MechanicalGate。

纪律：core/ 零 LLM import；只有本适配器（adapters/）碰 LLM。
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..core.models import PhaseDef
from ..core.gates import MechanicalGate


class LLMGate:
    """LLM 质量判定者（实现 ports.Gate）"""

    def __init__(self, llm: Optional[Any] = None, gate_reliability: float = 0.9):
        self._llm = llm
        self.gate_reliability = gate_reliability  # 诚实：默认 <1.0
        self._mech = MechanicalGate()

    async def decide(self, phase: PhaseDef, result) -> bool:
        if self._llm is None:
            # 无 LLM → 闭集机械判定（不污染 P_ctrl）
            return await self._mech.decide(phase, result)
        try:
            messages = [
                {"role": "system", "content": "判断下列相位执行结果是否通过质量闸。只回 JSON {\"passed\": true/false}。"},
                {"role": "user", "content": json.dumps(getattr(result, "data", ""), ensure_ascii=False)[:2000]},
            ]
            content = await _maybe_await(self._llm(messages))
            data = json.loads(content)
            return bool(data.get("passed", result.status == "success"))
        except Exception:
            return await self._mech.decide(phase, result)


async def _maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value

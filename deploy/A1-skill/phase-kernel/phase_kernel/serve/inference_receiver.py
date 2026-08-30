"""serve 默认推理缝填缝：llm 推理接收器（Phase 重构 P1.3；refactor §一 1.3）

实现 `ports.InferenceSeam`——serve 身兼 pk 宿主 + 推理缝接入方（充当 ck 角色）时，
把 `context_patch` 变成 `inference_result`，使独立 pk 的 serve 能靠推理缝跑通一个
完整相位闭环（核心瘦身后不再直接调 LLM）。

- 有 `llm` 回调（可注入）→ 拼装上下文（当前最小闭环只带 intent；父产物 fetch 属 P2）+
  调 LLM → 回填 `inference_result`（带同一 context_id）。
- 无 LLM / LLM 失败 → 机械兜底：按 patch 返回最小 result（不丢 P_ctrl，serve 零 LLM 也能闭环）。

纪律：本接收器在 serve/（填缝层）实现 `ports.InferenceSeam`，不碰 core/；
`context_id` 由 pk 发起方生成透传，本接收器只持有它配对 + 回填，不创造 id。
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from ..core.models import ContextPatch, InferenceResult
from ..ports import InferenceSeam


class LlmInferenceReceiver:
    """serve 默认推理缝填缝（实现 ports.InferenceSeam）。

    llm: 可选异步 callable(messages: list[dict]) -> str。传入则真推理（拼装上下文
     + 调 LLM）；为 None（--no-strata / 无 LLM）→ 机械兜底最小 result。
    v3.3 家族化更正（integration_sl_draft §11.2）：本接收器**不按 routing 标签做模型/
    prompt 路由**——原 "tier→model 路由表由调用方持有" 从注释落到实做：模型路由决策归
    pk 外挂服务（peer 外部服务，同 ck 外挂），不在 pk 内核。接收器只负责拼装 + 调用
    + 回填；`routing`（经 patch.ext）仅作透传键，本接收器不解释、不路由。
    """

    def __init__(self, llm: Optional[Callable[[list[dict]], Any]] = None):
        self._llm = llm

    async def infer(self, patch: ContextPatch) -> InferenceResult:
        if self._llm is None:
            # 机械兜底：无 LLM → 返回最小 result（P_ctrl 不依赖 LLM 仍可闭环）
            return InferenceResult(
                context_id=patch.context_id,
                content=_mechanical_content(patch),
            )
        messages = _build_messages(patch)
        try:
            content = await _maybe_await(self._llm(messages))
        except Exception:
            # LLM 失败 → 机械兜底（不崩、不挂起）
            content = _mechanical_content(patch)
        return InferenceResult(context_id=patch.context_id, content=content)


def _build_messages(patch: ContextPatch) -> list[dict]:
    """拼装推理请求消息（Phase 重构 P1 最小闭环：当前只带 intent + phase_path）。

    v3.3 家族化更正：本接收器**不按 routing 标签选 system prompt**——系统提示为
    通用的"相位推理器"，不区分 planning/normal/summary（那三类是 sl 分形家族的模型
    分形类型，模型路由决策归 pk 外挂，不在内核）。`patch.ext` 里的 `routing` 仅透传，
    本函数不读取、不解释。父产物 fetch / 上游摘要注入属 P2（数据面缝）。
    """
    system = "你是相位推理执行器。基于相位意图与上下文生成该相位的推理结果（文本/结构化）。"
    user = f"相位路径：{patch.phase_path}；相位意图：{patch.intent}"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _mechanical_content(patch: ContextPatch) -> str:
    """机械兜底内容：无 LLM 时返回可被下游解析的最小结果。

    v3.3：不再按 routing 分支——planning 解析形态与 normal/summary 回显统一退化为
    不区分 routing 的最小结果（pk 内核不解释 routing，模型路由归外挂）。仍保留对
    `routing == "planning"` 的兼容产出以支撑 pk 独立 serve 的规划闭环测试，但这是
    接收器侧的便利默认、非内核语义。
    """
    routing = (patch.ext or {}).get("routing")
    if routing == "planning":
        return '{"phases": [{"index": 0, "name": "需求分析", "description": "分析需求：%s"}]}' % (
            patch.intent[:50])
    return f"[mechanical:{routing}] {patch.intent}"


async def _maybe_await(value):
    if hasattr(value, "__await__"):
        return await value
    return value

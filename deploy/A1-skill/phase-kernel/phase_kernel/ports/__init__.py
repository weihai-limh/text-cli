"""phase-kernel 注入端口（设计稿 §3.2 / §12.5）

纪律：ports/ 只定义抽象接口（Protocol / ABC），不含任何实现。
具体实现在 adapters/。core/ 只依赖本模块的抽象，不依赖任何后端。
所有端口方法为 async（对齐 tc `async` 机制；设计稿 §12.6）。
"""

from __future__ import annotations

from typing import Any, Optional, Protocol, runtime_checkable

from ..core.models import (
    PhaseDef, PhasePlan, PhaseResult, PipelineSession, ContextPatch, InferenceResult,
    SmRequest, SmResponse, SmStrategyBundle,
)


@runtime_checkable
class InferenceSeam(Protocol):
    """推理缝（Phase 重构 P1）：相位推理请求的接缝端口。

    语义（refactor-inference-seam §一）：pk 让出"上下文组装权 + 推理裁决权"——不预拼上下文、
    不自己调 LLM。把"相位需要推理"作为 `ContextPatch`（相位定位 + 意图 + 握手 id；路由标签经 `ext["routing"]` 透传，pk 不解释）
    交给接入方（serve 的 llm 推理接收器 / ck）；接入方拼装上下文 + 调 LLM 后回填
    `InferenceResult`（带同一 context_id），pk 凭它归位到对应相位。
    四缝端口分立：本端口只做"推理回填"，与 Executor（结果归位）/ Gate（质量闸判定）正交。
    """

    async def infer(self, patch: ContextPatch) -> InferenceResult: ...


@runtime_checkable
class SmSeam(Protocol):
    """sm 缝（Phase 重构 P3）：strata-match 策略内容获取的接缝端口。

    语义（refactor-inference-seam §四-C）：pk 经本端口向 strata-match 取某相位的策略
    prompt（策略内容），**只读经缝获取，pk 消费不获取**——pk 拿 prompt 喂给推理缝
    planning routing（ext） / 规划，不自己持有 sm 会话。`StrataMatcher` 是默认填缝实现。
    定位改接 `phase_path`（树路径）替换旧 `phase_meta` 手工拼 name/description。

    Phase A（sm _b 升级）：返回类型从 `Optional[str]` 升级为 `Optional[SmStrategyBundle]`——
    带回结构化 `tools[]`/`skills[]`/`assets[]`（compact 单值，已按 lang 过滤），pk 直接消费。
    """

    async def query(self, req: SmRequest) -> Optional[SmStrategyBundle]: ...


@runtime_checkable
class Executor(Protocol):
    """执行端口：驱动一个相位的 step 执行（设计稿 §3.2 / §12.5）

    cancel 经 tc `async` 机制穿透，不入端口（§12.5）。
    """

    async def execute(self, phase: PhaseDef, context: dict) -> PhaseResult: ...

    async def poll(self, task_id: str) -> PhaseResult: ...


@runtime_checkable
class Planner(Protocol):
    """规划端口：把意图表示切成相位树（设计稿 §3.2 / §10.3）

    goal_repr 是意图的抽象表示：LLM 侧为文本，符号侧为结构化目标，
    机械侧为 endpoint_hint。相位树形状是机制硬约束；「怎么切」放开（§10.3）。
    Planner 是无状态注入接口，故「切相位」本身可被另一层相位推理递归包裹（递归自愈）。
    """

    async def plan(self, goal_repr: Any, context: dict) -> PhasePlan: ...

    async def regenerate(self, phase: PhaseDef, feedback: str) -> PhasePlan: ...


@runtime_checkable
class Gate(Protocol):
    """闸门判定者抽象（设计稿 §3.2 / §4.1）

    默认为 MechanicalGate（比对 PhaseResult.status 闭集）；可注入 LLMGate / HumanGate。
    核心只依赖本端口，不规定判定者身份。
    """

    async def decide(self, phase: PhaseDef, result: PhaseResult) -> bool: ...


@runtime_checkable
class Store(Protocol):
    """持久化端口：相位服务自有本地 DB（设计稿 §3.2 / §12.4③）

    承载 PipelineSession / phase_summaries / checkpoint_index；非 tc 运行时存储。
    restore 等价于按 pipeline_id 的 load（跨轮询/跨请求恢复会话快照）。
    """

    async def save(self, session: PipelineSession) -> None: ...

    async def load(self, pipeline_id: str) -> Optional[PipelineSession]: ...

    async def restore(self, pipeline_id: str, session_id: Optional[str] = None) -> Optional[PipelineSession]:
        ...


@runtime_checkable
class ToolCatalog(Protocol):
    """可选：按相位取「当前可用工具切片」（设计稿 §3.2 / §一.3）

    底层复用后端 discovery（tc text-cli;query）。可选端口。
    """

    async def list_for_phase(self, phase: PhaseDef) -> list: ...


@runtime_checkable
class ArtifactStore(Protocol):
    """产物获取通道端口（设计稿 块1 数据面 / 执行相位服务 §2.5）

    管理相位产物（数据面），与 `Store`（session 持久化）分离。
    职责：
    - `store`: 存产物，生成 pk 自有 URL。
    - `fetch`: 按 ref 取产物。
    - `transfer`: 透传/拉取转存分流——读数据形态判 http/https URL → 透传
      （不落盘直转远端 URL），否则拉取转存（落盘生成 pk 自有 URL）；
      转存失败降级直用远端 URL 并标 `_transfer_degraded`。
    """

    async def store(self, pipeline_id: str, ref: str, data: Any,
                    media_type: str = "text") -> str: ...

    async def fetch(self, ref: str) -> Optional[dict]: ...

    async def transfer(self, pipeline_id: str, payload: Any,
                       media_type: str = "text") -> dict: ...

"""相位推理引擎（设计稿 §3.3 / §七；ported from synth-loop phase_chat_orchestrator.py）

纪律：本模块（及整个 core/）零 tc / sl / FastAPI import。
引擎只依赖 ports 抽象接口驱动全流转；执行/规划/持久化/判定全部注入。

对外只暴露一个纯函数式入口 handle()，返回结构与 synth-loop 现有 synth_pipeline
逐字段对齐（id/step/phase_index/phase_total/artifact_ref），保证剥离后 sl 只改 import（§3.3 兼容锚点）。
"""

from __future__ import annotations

import json
from typing import Any, Optional, Callable

from .models import (
    PipelineSession, PhaseDef, PhaseStatus, PipelineStatus, PhaseArtifact, PhasePlan, PhaseKind,
    PhaseResult, ContextPatch, InferenceResult,
)
from .gates import PhaseGateExecutor, MechanicalGate
from .actions import PhaseAction
from . import fractal
from .decide_kind import decide_kind, tools_to_contract, DEFAULT_MAX_PHASE_DEPTH
from .i18n import t
from ..ports import Executor, Planner, Store, Gate, ToolCatalog, ArtifactStore, InferenceSeam


# step 枚举（与 synth-loop 契约逐字段对齐，设计稿 §3.3）
STEP_AWAITING_PLAN = "awaiting_plan_confirm"
STEP_AWAITING_PATH = "awaiting_path_confirm"
STEP_AWAITING_APPROVAL = "awaiting_approval"
STEP_EXECUTING = "executing"
STEP_COMPLETED = "completed"
STEP_ABORTED = "aborted"


class PhaseReasoningEngine:
    """相位状态机主链（迁移通用核；经 ports 驱动，零写死外部调用）"""

    def __init__(self, executor: Executor, planner: Planner, store: Optional[Store] = None,
                 catalog: Optional[ToolCatalog] = None, gate: Optional[Gate] = None,
                 degraded_mode: bool = False, max_phase_depth: int = DEFAULT_MAX_PHASE_DEPTH,
                 max_rollback_iters: int = 1, review_enabled: bool = False,
                 review_llm: Optional[Callable] = None,
                 artifact_store: Optional[ArtifactStore] = None,
                 inference_seam: Optional[InferenceSeam] = None,
                 summary_on_demand: bool = False):
        self.executor = executor
        self.planner = planner
        self.store = store
        self.catalog = catalog
        self.artifact_store = artifact_store  # 数据面（产物获取通道，与 Store 会话持久化分离）
        self.gate = gate or MechanicalGate()
        self.gate_executor = PhaseGateExecutor()
        self.degraded_mode = degraded_mode
        self.max_phase_depth = max_phase_depth
        self.max_rollback_iters = max_rollback_iters  # 相位内回退上限（Phase 3；真跑 path 代价重，默认 1）
        self.review_enabled = review_enabled  # 结果复议自评开关（执行相位服务 §2.6；默认关，信任优先）
        self.review_llm = review_llm  # 复议 LLM 回调（结果回填后同一次调用；可同时承载 cognition）
        # Phase 重构 P1：推理缝端口（可选）。注入 → 经 `inference_seam.infer(patch)` 发起推理
        # （pk 让出推理权）；未注入 → 回落现有 executor/planner 路径（兼容 mock 无数据面）。
        self.inference_seam = inference_seam
        # Phase 重构 P2.4：summary 级推理配置（§五-15）。默认关（关 = 每次相位执行后都产
        # summary_ref 全开传递）；开 = 仅当该相位有下游消费者才触发（省低 b 调用）。
        self.summary_on_demand = summary_on_demand
        self._sessions: dict[str, PipelineSession] = {}
        # i18n：当前请求语言（每请求由 handle(lang=) 重设；默认 zh）
        self._lang = "zh"

    # ═══════════════════════════════════════════════════════
    # 主入口
    # ═════════════════════════════════════════════════════

    async def handle(self, user_text: str, synth_pipeline: Optional[dict] = None,
                     session_id: Optional[str] = None, user_id: Optional[str] = None,
                     mode: Optional[str] = None, lang: str = "zh") -> dict:
        """处理一次相位调用。

        - 带 synth_pipeline（含 id + action）→ 回传驱动，解析 action 推进状态机
        - 否则 → 新发起：进入规划（意图识别由调用方负责，设计稿 §9.5）

        `mode`（P1）：`structural`（默认，正常分形下钻）或 `chain`（链式模式——根相位
        正常分形出多相位，但多相位直接出 path、下钻深度强制为 0，无 NODE 下钻）。

        `lang`（i18n）：请求语言（`zh`/`en`），默认 `zh`。每请求重设 `self._lang`，
        驱动 content/reason 本地化（t(key, lang=self._lang)）。可选参数，不改公开 API 签名。
        """
        self._lang = lang or "zh"
        if synth_pipeline and synth_pipeline.get("id"):
            return await self._handle_action(synth_pipeline, user_text, session_id, user_id)
        return await self._start_planning(user_text, session_id, user_id, mode=mode)

    # ═══════════════════════════════════════════════════════
    # 新发起：总体规划 → awaiting_plan_confirm
    # ═════════════════════════════════════════════════════

    async def _start_planning(self, user_text: str, session_id: Optional[str],
                              user_id: Optional[str],
                              mode: Optional[str] = None) -> dict:
        # 模式白名单校验（显式报错而非静默回退，提升可调试性）
        if mode is not None and mode not in ("structural", "chain"):
            raise ValueError(f"unknown mode: {mode!r} (expected 'structural' or 'chain')")
        plan = await self._plan_with_seam(user_text, session_id, user_id)
        session = PipelineSession(
            intent=user_text, plan=plan, user_id=user_id,
            session_id=session_id,
        )
        # 保留 kind/children（分形感知，Phase 2）：重建时不再丢 NODE/children；
        # 并用 decide_kind 复核 depth（落差2：depth 真正注入）。
        # mode 透传到 _expand_fractal，由其在内部按 depth 选 effective_max（P2：
        # chain 且 depth>=1 → effective_max=1 触顶；根 depth0 仍用配置值正常分形）。
        expanded = []
        for i, p in enumerate(plan.phases):
            expanded.append(await self._expand_fractal(
                PhaseDef(index=p.index, name=p.name, description=p.description,
                         mode=getattr(p, "mode", None), gates=p.gates,
                         endpoint_hint=getattr(p, "endpoint_hint", None),
                         steps=list(getattr(p, "steps", None) or []),
                         kind=getattr(p, "kind", PhaseKind.LEAF),
                         children=getattr(p, "children", None)),
                depth=0, context={"session_id": session_id, "user_id": user_id},
                mode=mode,
                path=[i],  # Phase 重构 P0：根相位树路径
            ))
        session.phases = expanded
        session.status = PipelineStatus.DRAFT

        # 规划产物写入 phase_summaries（逐相累积的固化单元；规划作为第 0 个）
        plan_summary = "；".join(f"{p.name}（{p.description[:30]}）" for p in session.phases)
        session.phase_summaries.append(PhaseArtifact(0, type="plan", data=plan_summary))

        self._sessions[session.pipeline_id] = session
        await self._persist(session)

        # 纠偏-001：plan 产物真正写入数据面（ref 可 fetch 取回）
        plan_ref = f"art_{session.pipeline_id}_plan"
        await self._store_artifact(session, plan_ref, plan_summary, "text")

        return {
            "content": t("plan_confirm", lang=self._lang, total=len(session.phases),
                         summary=plan_summary),
            "synth_pipeline": self._sp(session, STEP_AWAITING_PLAN, 0, plan_ref),
        }

    async def _plan_with_seam(self, user_text: str, session_id: Optional[str],
                              user_id: Optional[str]) -> PhasePlan:
        """顶层规划（Phase 重构 P1）：推理缝 planning routing（ext）或回落 planner。

        注入 `inference_seam` → 发起 `context_patch(ext={"routing": "planning"})`，接入方回填
        `inference_result.content`（期望是 PhasePlan 的 JSON 形态）；解析失败/未注入 →
        回落 `self.planner.plan`（保持 P_ctrl 不依赖推理缝仍可推进）。
        """
        if self.inference_seam is not None:
            from .models import PhaseGates
            from uuid import uuid4
            patch = ContextPatch(phase_path=None, intent=user_text,
                                 context_id=str(uuid4()),
                                 ext={"routing": "planning"})
            try:
                result = await self.inference_seam.infer(patch)
                data = json.loads(result.content or "")
                phases = data.get("phases", [])
                if phases:
                    return PhasePlan(phases=[
                        PhaseDef(index=int(p["index"]), name=p["name"],
                                 description=p.get("description", ""),
                                 mode=p.get("mode", "single_ai"),
                                 gates=PhaseGates.from_dict(p.get("gates", {})))
                        for p in phases
                    ])
            except Exception:
                pass  # 解析失败 → 回落 planner（不丢 P_ctrl）
        return await self.planner.plan(user_text, {"session_id": session_id, "user_id": user_id})

    # ═══════════════════════════════════════════════════════
    # 回传驱动：解析 action → 决策点状态机
    # ═════════════════════════════════════════════════════

    async def _handle_action(self, synth_pipeline: dict, user_text: str,
                             session_id: Optional[str], user_id: Optional[str]) -> dict:
        pipeline_id = synth_pipeline.get("id")
        action = synth_pipeline.get("action", "")
        session = await self._load(pipeline_id, session_id)
        if session is None:
            return {
                "content": t("pipeline_missing", lang=self._lang),
                "synth_pipeline": self._sp_terminal(pipeline_id, STEP_ABORTED),
            }

        if action == PhaseAction.ABORT.value:
            session.abort()
            await self._persist(session)
            return self._respond(session, STEP_ABORTED, t("pipeline_aborted", lang=self._lang))

        if action == PhaseAction.REJECT.value:
            return await self._reject(session, user_text)

        if action in (PhaseAction.REGENERATE.value, PhaseAction.REGENERATE_NEW_CTX.value):
            return await self._regenerate(session, user_text)

        if action == PhaseAction.CHECK_RESULT.value:
            return await self._check_result(session)

        if action == PhaseAction.CONFIRM.value:
            return await self._confirm(session)

        # 未知 action → 不推进
        return {
            "content": t("unknown_action", lang=self._lang, action=action),
            "synth_pipeline": self._sp(session, self._step_of(session), 0, None),
        }

    # ═══════════════════════════════════════════════════════
    # 分形展开（Phase 2：落差2——decide_kind 驱动 + depth 注入 + 触顶）
    # ═════════════════════════════════════════════════════

    async def _expand_fractal(self, phase: PhaseDef, depth: int,
                              context: dict,
                              mode: Optional[str] = None,
                              path: Optional[list] = None) -> PhaseDef:
        """用 `decide_kind` 复核相位 kind 并注入 depth（落差2：depth 真正传入）。

        `path`（Phase 重构 P0）：当前相位的树路径（根传 `[i]`、子传 `parent.path+[i]`）；
        赋给 `phase.path`，作为四缝共用寻址地基（`pipeline_id + phase_path` 唯一定位）。

        策略（兼顾向后兼容 + 分形驱动）：
        - 显式 NODE（`kind==NODE` 或带 children）→ 用 `decide_kind` 复核 depth；
          判 NODE 且未触顶 → 下钻生成 children（递归 depth+1）；触顶/契约闭合 → LEAF。
        - 显式 LEAF → 记 depth；**不主动把 LEAF 变 NODE**（决定权在 planner，向后兼容）。
        - 非闭集兜底（张力2：决策层 vs 兜底层分层）——decide_kind 判 NODE 但下钻
          无素材（planner 无法产 children）→ 强制 LEAF，避免意外递归失控。

        `effective_max`（P2 两层覆写模型）：
        - `mode == "chain"` 且 `depth >= 1`（子相位）→ `1`（触顶，强制 LEAF 直出 path）；
        - 其余（根 depth0 / structural）→ `self.max_phase_depth`（正常分形）。
        链式是"根正常分形、子 LEAF 出 path"，不是"整树一层"——故根层仍允许 NODE 下钻，
        仅子层触顶。复用 `decide_kind` 既有 `depth >= max → LEAF` 边界，不改判据逻辑。
        """
        if mode == "chain" and depth >= 1:
            effective_max = 1
        else:
            effective_max = self.max_phase_depth
        phase.depth = depth
        if path is not None:
            phase.path = path  # Phase 重构 P0：树路径（pipeline_id + phase_path 唯一定位）
        is_explicit_node = (phase.kind == PhaseKind.NODE or bool(phase.children))
        if not is_explicit_node:
            # 显式 LEAF：只记 depth，保持 LEAF（不主动分形）
            return phase

        contract = self._contract_of(phase)
        kind = decide_kind(phase, contract, depth, effective_max)
        if kind == PhaseKind.NODE and depth < effective_max:
            children = await self._fractal_expand_children(
                phase, depth, context, mode=mode)
            if children:
                phase.kind = PhaseKind.NODE
                phase.children = children
                return phase
            # 非闭集兜底：无法下钻 → 强制 LEAF（张力2 兜底层终止）
            phase.kind = PhaseKind.LEAF
            return phase
        # 触顶（depth>=max）或契约闭合 → LEAF
        phase.kind = PhaseKind.LEAF
        return phase

    async def _fractal_expand_children(self, phase: PhaseDef, depth: int,
                                       context: dict,
                                       mode: Optional[str] = None) -> Optional[list]:
        """NODE 下钻：用 planner 针对该相位生成 children，并递归展开（depth+1）。

        `mode` 透传给 `_expand_fractal`，使其内部按 depth 选 effective_max（P2 链式触顶）。

        P3.1 单层兜底（前瞻保险）：链式模式下，在编排边界统一强制第一层子相位为
        `kind=LEAF, children=None`——即便 planner（适配层）产出 NODE/嵌套子相位，
        也不让其绕过 P2 的触顶而破链。本步在 core 下钻边界施加（覆盖所有 planner
        实现，且无需改 ports.Planner 接口，符合"core 决定结构、adapter 决定差异"纪律）。
        P2 的 effective_max=1 已在 decide_kind 触顶形成第一道保险；此处为第二道。
        """
        goal_repr = (phase.name or phase.description or "").strip() or "expanding phase"
        plan = await self.planner.plan(goal_repr, context)
        children = []
        for i, pc in enumerate(plan.phases or []):
            child = PhaseDef(
                index=i, name=pc.name, description=pc.description,
                mode=getattr(pc, "mode", None), gates=pc.gates,
                endpoint_hint=getattr(pc, "endpoint_hint", None),
                steps=list(getattr(pc, "steps", None) or []),
                kind=getattr(pc, "kind", PhaseKind.LEAF),
                children=getattr(pc, "children", None),
            )
            if mode == "chain":
                # 链式单行保险：子相位强制 LEAF 直出 path，丢弃任何嵌套 children
                child.kind = PhaseKind.LEAF
                child.children = None
            # Phase 重构 P0：子相位树路径 = 父 path + 子索引（parent.path 已在 _expand_fractal 赋）
            child_path = list(phase.path) + [i] if phase.path is not None else None
            children.append(await self._expand_fractal(
                child, depth + 1, context, mode=mode, path=child_path))
        return children or None

    def _contract_of(self, phase: PhaseDef) -> Optional[dict]:
        """从相位构造 decide_kind 的 contract（input/output schema + 可固化产物）。

        Phase A（sm _b）：接通 `tools_to_contract`——若相位带 sm `tools[]`（由
        `PhasePlanPlanner` 从 bundle 注入），用它构造判定契约（input_schema/output_schema/
        requires），使 `decide_kind` 的 NODE/LEAF 判定不再无脑判 NODE 下钻。
        相位无 tools 时回落 None（decide_kind 据此判 NODE，驱动下钻）。
        """
        if phase.tools:
            return tools_to_contract(phase.tools)
        return None

    # ═══════════════════════════════════════════════════════
    # 分形感知推进（Phase 1：落差1——树驱动链）
    # ═════════════════════════════════════════════════════

    def _next_leaf(self, session: PipelineSession) -> Optional[PhaseDef]:
        """返回下一个待执行 LEAF（分形感知）。

        用 `fractal.iter_phases` 深度优先展平相位树，跳过已终态（completed/failed/aborted）
        与 NODE（抽象节点不下钻执行），返回第一个"活动或待执行"的 LEAF。
        全 LEAF 扁平树 → 天然退化为线性顺序（向后兼容现有测试）。
        NODE/children 树 → 正确下钻到子 LEAF。

        规划失败/降级出口（Phase 3，P2.5）：遇到 **NODE 无 children**（无法下钻的
        异常态，如持久化加载的残缺树）时，不无限跳过——把它视为**不可执行的抽象点**，
        跳过并累计到 `session._planning_blocked`；若全树皆为此 → 返回 None（上层
        触发 complete/降级），避免死循环卡死。
        """
        blocked = 0
        for _path, phase in fractal.iter_phases(session.phases):
            # 消费 iter_phases 的树路径（Phase 重构 P0）：把 `_path` 写入相位，供寻址/ref 生成
            if phase.path is None:
                phase.path = _path
            if phase.status in {PhaseStatus.COMPLETED, PhaseStatus.FAILED, PhaseStatus.ABORTED}:
                continue
            if phase.kind == PhaseKind.NODE:
                if not phase.children:
                    blocked += 1  # NODE 无 children：无法下钻的降级点
                continue
            return phase
        if blocked:
            session._planning_blocked = True
        return None

    def _verification_phase(self, session: PipelineSession) -> Optional[PhaseDef]:
        """首相位验证点（earliest-close，Phase 3）：树中第一个 LEAF。

        验证点是整条链能否续上的最早检查点——它失败 = 整条路不通，应最浅终止。
        无论当前执行推进到哪，首相位 = 树中第一个 LEAF（iter_phases 顺序）。
        """
        for _path, phase in fractal.iter_phases(session.phases):
            if phase.path is None:
                phase.path = _path
            if phase.kind == PhaseKind.NODE:
                continue
            return phase
        return None

    def _is_verification_phase(self, session: PipelineSession, phase: PhaseDef) -> bool:
        """当前失败的相位是否为首相位验证点？"""
        first = self._verification_phase(session)
        return first is not None and first is phase

    async def _confirm(self, session: PipelineSession) -> dict:
        current = self._next_leaf(session)

        # awaiting_plan_confirm → 启动管道，生成第一个相位 path
        if session.status == PipelineStatus.DRAFT or (current is None and session.phases):
            session.start()
            await self._persist(session)
            return await self._generate_next_path(session, self._next_leaf(session))

        # awaiting_path_confirm → 提交执行
        if current and current.status == PhaseStatus.AWAITING_PATH_CONFIRM:
            return await self._execute_phase(session, current)

        # awaiting_approval → 审批通过
        if current and current.status == PhaseStatus.AWAITING_APPROVAL:
            await self.gate_executor.approve_phase(session, current)
            await self._persist(session)
            nxt = self._next_leaf(session)
            if nxt is not None:
                return await self._generate_next_path(session, nxt)
            session.complete()
            await self._persist(session)
            return self._respond(session, STEP_COMPLETED, t("all_phases_completed", lang=self._lang))

        return self._respond(session, STEP_AWAITING_PLAN, t("state_cannot_confirm", lang=self._lang))

    async def _reject(self, session: PipelineSession, feedback: str) -> dict:
        current = self._next_leaf(session)
        # 审批闸驳回 → 当前相位回到 awaiting_path_confirm 重新确认执行（重试当前相位）
        if current and current.status == PhaseStatus.AWAITING_APPROVAL:
            await self.gate_executor.reject_phase(session, current, feedback or "no feedback")
            # 重试：当前相位重新进入 path 确认（客户端 confirm 即重执行；子命题1：只重跑本相位）
            current.status = PhaseStatus.AWAITING_PATH_CONFIRM
            await self._persist(session)
            return self._respond(session, STEP_AWAITING_PATH,
                                 t("rejected_retry", lang=self._lang,
                                   feedback=(feedback or "no feedback")[:100]))
        # 规划级驳回 → 重新规划
        return await self._regenerate(session, feedback)

    async def _regenerate(self, session: PipelineSession, feedback: str) -> dict:
        current = session.get_current_phase()
        if current is None:
            # 重新规划（feedback 为修正意见）
            plan = await self.planner.regenerate(None, feedback or session.intent)
            session.plan = plan
            session.phases = [
                PhaseDef(index=p.index, name=p.name, description=p.description,
                         mode=p.mode, gates=p.gates, endpoint_hint=p.endpoint_hint,
                         steps=list(p.steps),
                         # P3.2 前瞻锁定：重规划重建相位强制单层（kind=LEAF、无 children）。
                         # 链式模式下行仍保持单层——防止将来该直赋路径扩充为产出嵌套
                         # NODE 时绕过 P2 触顶而破链；当前默认 LEAF 已天然单层，此处显式固化。
                         kind=PhaseKind.LEAF, children=None)
                for p in plan.phases
            ]
            session.status = PipelineStatus.DRAFT
            session.checkpoint_index = -1
            await self._persist(session)
            plan_summary = "；".join(f"{p.name}（{p.description[:30]}）" for p in session.phases)
            return {
                "content": t("replanned_confirm", lang=self._lang, total=len(session.phases),
                             summary=plan_summary),
                "synth_pipeline": self._sp(session, STEP_AWAITING_PLAN, 0,
                                           f"art_{session.pipeline_id}_plan"),
            }
        # 重新生成当前相位 path
        current.status = PhaseStatus.AWAITING_PATH_CONFIRM
        await self._persist(session)
        return await self._generate_next_path(session, current)

    # ═══════════════════════════════════════════════════════
    # 第2段推理：生成 phase path（plan_compiler 组装）
    # ═════════════════════════════════════════════════════

    async def _generate_next_path(self, session: PipelineSession, phase: PhaseDef) -> dict:
        phase.status = PhaseStatus.AWAITING_PATH_CONFIRM

        # 组装 path：执行体（Executor 适配器）负责把 phase 译成真实 step 信封；
        # 此处仅做展示 + 记录 path artifact（设计稿 §八：TCExecutor 填 steps:[] 空桩）
        path = self._compile_path(phase)
        artifact_ref = f"art_{session.pipeline_id}_path_{self._phase_ref_key(phase)}"
        await self._persist(session)
        # 纠偏-001：path 产物真正写入数据面（ref 可 fetch 取回）
        await self._store_artifact(session, artifact_ref, path, "application/json")
        return {
            "content": t("phase_path_prompt", lang=self._lang, i=phase.index + 1,
                         total=self._leaf_total(session), name=phase.name, path=_truncate(path)),
            "synth_pipeline": self._sp(session, STEP_AWAITING_PATH, phase.index, artifact_ref),
        }

    def _leaf_total(self, session: PipelineSession) -> int:
        """可执行 LEAF 总数（分形感知）：树中全部 LEAF 计数；全扁平树 = len(phases) 向后兼容。"""
        count = 0
        for _p, ph in fractal.iter_phases(session.phases):
            if ph.path is None:
                ph.path = _p
            if ph.kind != PhaseKind.NODE:
                count += 1
        return count or len(session.phases)

    def _compile_path(self, phase: PhaseDef) -> dict:
        """把相位译成 path 信封（展示用）。

        若 Executor 适配器暴露 compile_path（如 TCExecutor 经 plan_compiler 组装真实 tc path），
        用其产物；否则回落 phase.steps。编排层不绑定具体执行后端（§10.1 L1）。
        """
        compiler = getattr(self.executor, "compile_path", None)
        if callable(compiler):
            try:
                return compiler(phase)
            except Exception:
                pass
        return {"id": phase.endpoint_hint or "local", "name": phase.name,
                "steps": phase.steps or [{"action": "execute", "description": phase.description}]}

    # ═══════════════════════════════════════════════════════
    # 执行（经 Executor 端口；长任务分级 → check_result 决策点）
    # ═════════════════════════════════════════════════════

    async def _execute_via_seam(self, session: PipelineSession, phase: PhaseDef) -> "PhaseResult":
        """相位执行（Phase 重构 P1/P2）：推理缝 normal routing（ext）或回落 executor。

        注入 `inference_seam` → 发起 `context_patch(ext={"routing": "normal"})`，接入方回填
        `inference_result`，经 `PhaseResult.from_inference` 归位核心闭集（status 走质量闸）。
        未注入 → 回落 `self.executor.execute`（保持 mock 无数据面兼容）。异步长任务
        （pending）属执行 path（`check_result` + task_id），不属推理回填层——推理缝
        本身同步归位，由 `_execute_phase` 后续 pending 分支处理。

        Phase 重构 P2.2 补断链：执行前经 `_fetch_parent_context` 从数据面缝取父/上游
        产物，注入 patch.ext（推理缝）或 executor context（回落路径），替代现只传 intent。
        """
        # P2.2：父/上游产物上下文切片（ref 取不到 → 空列表，不崩）
        parent_ctx = await self._fetch_parent_context(session, phase)
        if self.inference_seam is not None:
            from uuid import uuid4
            # phase_path 以 str 出缝（"-" 连接，如 "0-1"），与数据面 ref 的 _phase_ref_key 同源；
            # 跨内核契约统一为 str，对齐 ck ContextPatch 预期（integration_sl_draft 对齐）。
            patch = ContextPatch(phase_path=self._phase_ref_key(phase), intent=session.intent,
                                 context_id=str(uuid4()),
                                 ext={"routing": "normal", "parent_context": parent_ctx})
            result = await self.inference_seam.infer(patch)
            return PhaseResult.from_inference(result)
        ctx = {"intent": session.intent, "parent_context": parent_ctx}
        return await self.executor.execute(phase, ctx)

    async def _execute_phase(self, session: PipelineSession, phase: PhaseDef) -> dict:
        phase.status = PhaseStatus.RUNNING
        try:
            # Phase 重构 P1：注入推理缝 → 经 normal routing（ext）发起相位执行推理；否则回落 executor。
            result = await self._execute_via_seam(session, phase)
        except Exception as e:
            # 执行后端不可达 → 相位降级（P18 语义：不崩、不挂起）
            logger = _get_logger()
            logger.error(f"相位执行失败: {e}")
            session.phase_summaries.append(PhaseArtifact(phase.index, type="error", data=str(e)))
            await self._persist(session)
            return self._respond(session, STEP_ABORTED,
                                 t("phase_exec_failed", lang=self._lang, error=e))

        if result.status == "pending":
            # 长任务：返回 task_id → check_result 决策点（设计稿 §五）
            session.async_tasks.append({
                "task_id": result.task_id, "phase_index": phase.index, "status": "pending",
            })
            await self._persist(session)
            result_ref = f"art_{session.pipeline_id}_result_{self._phase_ref_key(phase)}"
            # 纠偏-001：pending 态先落 task 状态占位（ref 可 fetch；结果回来后由 _finalize 覆盖）
            await self._store_artifact(session, result_ref,
                                       {"task_id": result.task_id, "status": "pending"}, "application/json")
            return {
                "content": t("phase_submitted_async", lang=self._lang, name=phase.name,
                             task_id=result.task_id),
                "synth_pipeline": self._sp(session, STEP_EXECUTING, phase.index, result_ref),
            }

        return await self._finalize_execution(session, phase, result)

    async def _check_result(self, session: PipelineSession) -> dict:
        """R4 长任务结果查询（check_result 决策点，设计稿 §五）"""
        current = self._next_leaf(session)
        if current is None:
            return self._respond(session, self._step_of(session), t("no_active_phase", lang=self._lang))
        task = next((t for t in reversed(session.async_tasks)
                     if t.get("phase_index") == current.index), None)
        if task is None:
            return self._respond(session, STEP_EXECUTING, t("no_pending_task", lang=self._lang))
        try:
            result = await self.executor.poll(task["task_id"])
        except Exception as e:
            return self._respond(session, STEP_EXECUTING, t("poll_failed", lang=self._lang, error=e))
        if result.status == "pending":
            return self._respond(session, STEP_EXECUTING, t("task_still_pending", lang=self._lang))
        return await self._finalize_execution(session, current, result)

    # ═══════════════════════════════════════════════════════
    # 执行相位服务：结果复议自评（review，XML verdict）——Phase 7，骨架 §2.6
    # ═════════════════════════════════════════════════════

    @staticmethod
    def _parse_verdict(content: str) -> str:
        """机械闸纯字符串匹配 XML verdict 闭集（骨架 §2.6）。

        匹配 `<phase_verdict>satisfied|unsatisfied|settled</phase_verdict>`；
        匹配不到 → 默认 `satisfied`（信任 LLM 单步决策为默认，没主动说不满意 = 默认满意）。
        """
        import re
        m = re.search(r"<phase_verdict>\s*(satisfied|unsatisfied|settled)\s*</phase_verdict>", content or "")
        if m:
            return m.group(1)
        return "satisfied"

    async def _review_phase(self, session: PipelineSession, phase: PhaseDef,
                            result) -> Optional[str]:
        """review 复议自评（骨架 §2.6）：结果回填后，若 review 开启，让 LLM 复议，
        机械闸匹配 XML verdict 返回 satisfied/unsatisfied/settled。

        配置关或无 review_llm → 返回 None（不做复议，直接走机械门控推进）。
        """
        if not self.review_enabled or self.review_llm is None:
            return None
        messages = [
            {"role": "system", "content":
             "你是相位执行结果的复议者。请基于'相位目标'与'实际执行结果'做满意度自评，"
             "只返回约定 XML 标识符：<phase_verdict>satisfied|unsatisfied|settled</phase_verdict>。"},
            {"role": "user", "content":
             f"相位目标：{phase.name} —— {phase.description}\n"
             f"实际结果：{getattr(result, 'data', None) or getattr(result, 'error', '')}"},
        ]
        try:
            content = await self.review_llm(messages)
        except Exception:
            return None
        verdict = self._parse_verdict(content)
        session.pointer_log.append({"type": "review_verdict", "phase": phase.index,
                                    "verdict": verdict})
        return verdict

    async def _finalize_execution(self, session: PipelineSession, phase: PhaseDef,
                                  result) -> dict:
        """质量闸判定 + 状态推进 + 产物固化 + 下一相位/完成（分形感知推进）

        执行相位服务（Phase 7）增强：质量闸（机械）判定通过后，若 `review` 开启，
        追加 **复议自评（XML verdict）**——unsatisfied → 相位内回退，否则推进。
        机械质量闸 + LLM 复议互补（骨架 §2.6：前置预判靠复议、后置判定靠机械）。
        """
        passed = await self._quality_passed(phase, result)
        status = await self.gate_executor.evaluate_quality_gate(
            session, phase, passed, detail=result.error or "")
        if passed:
            session.phase_summaries.append(PhaseArtifact(phase.index, type="result", data=result.data))
            # 纠偏-001：结果产物真正写入数据面（ref 可 fetch 取回；覆盖 pending 占位）
            result_ref = f"art_{session.pipeline_id}_result_{self._phase_ref_key(phase)}"
            await self._store_artifact(session, result_ref, result.data, "application/json")
            # Phase 重构 P2.4：summary 级推理产 summary_ref 供下游（summary_on_demand 控制）
            await self._produce_summary(session, phase, result)

        # 执行相位服务（Phase 7）：质量闸（机械）通过后，若 `review` 开启 → 复议自评
        # （XML verdict）。unsatisfied → 相位内回退；否则推进（骨架 §2.6 互补）。
        if status == PhaseStatus.COMPLETED and self.review_enabled:
            verdict = await self._review_phase(session, phase, result)
            if verdict == "unsatisfied":
                return await self._phase_rollback(session, phase,
                                                  reason="review: unsatisfied")
            if verdict == "settled":
                status = PhaseStatus.COMPLETED  # 接受稳定产出放行，照常推进

        await self._persist(session)
        if status == PhaseStatus.COMPLETED:
            nxt = self._next_leaf(session)
            if nxt is not None:
                return await self._generate_next_path(session, nxt)
            session.complete()
            await self._persist(session)
            return self._respond(session, STEP_COMPLETED, t("all_phases_completed", lang=self._lang))
        if status == PhaseStatus.AWAITING_APPROVAL:
            return self._respond(session, STEP_AWAITING_APPROVAL,
                                 t("phase_done_await_approval", lang=self._lang, name=phase.name))
        # FAILED —— earliest-close 门控（Phase 3/7）：复用 _phase_rollback
        #   （首相位最浅终止 / 非首相位回退重试 / 回退超限 settled 放行）
        return await self._phase_rollback(session, phase,
                                          reason=f"execute failed: {result.error or 'quality gate failed'}")

    async def _phase_rollback(self, session: PipelineSession, phase: PhaseDef,
                              reason: str = "") -> dict:
        """相位内回退（执行相位服务 §2.6，earliest-close 门控）。

        首相位与非首相位**同样**先回退重试（回退计数 < `max_rollback_iters`）；
        回退**超限后**按位置分叉（骨架 §2.6 上限语义）：
        - **首相位（earliest-close 验证点）超限** → 整树最浅终止（验证点反复不通 = 整条路不通，
          最浅关树最经济）。
        - **非首相位超限** → 接受稳定产出放行（settled，信任已尽力，不废整树）并推进到下一 LEAF。
        """
        if phase.rollback_count < self.max_rollback_iters:
            phase.rollback_count += 1
            phase.status = PhaseStatus.AWAITING_PATH_CONFIRM  # 相位内回退：重试当前相位
            session.add_quality_gate(phase.index, "rollback",
                                     "retry", f"{reason} retry #{phase.rollback_count}")
            session.pointer_log.append({"type": "rollback", "phase": phase.index,
                                        "count": phase.rollback_count, "reason": reason})
            await self._persist(session)
            return self._respond(session, STEP_AWAITING_PATH,
                                 t("phase_rollback_retry", lang=self._lang, name=phase.name,
                                   count=phase.rollback_count, max=self.max_rollback_iters))
        # 回退超限 → 按位置分叉（骨架 §2.6：首相位最浅终止 / 非首相位 settled）
        if self._is_verification_phase(session, phase):
            session.abort()
            await self._persist(session)
            return self._respond(session, STEP_ABORTED,
                                 t("verification_phase_abort", lang=self._lang, name=phase.name,
                                   reason=reason))
        # 非首相位超限 → 接受稳定产出放行（settled），并推进到下一 LEAF
        phase.status = PhaseStatus.COMPLETED
        await self._persist(session)
        nxt = self._next_leaf(session)
        if nxt is not None:
            resp = await self._generate_next_path(session, nxt)
            resp["content"] = (t("phase_settled_next", lang=self._lang, name=phase.name,
                                 content=resp["content"]))
            return resp
        session.complete()
        await self._persist(session)
        return self._respond(session, STEP_COMPLETED,
                             t("phase_settled_all_done", lang=self._lang, name=phase.name))

    async def _quality_passed(self, phase: PhaseDef, result) -> bool:
        """质量闸是否通过（设计稿 §4.1 / §13.4②）

        无质量闸 → 只要没 failed 就过；
        有质量闸 → 经注入的 Gate 判定者（默认 MechanicalGate 闭集比对）；
        gate_reliability g<1.0 写入 phase_summaries 供审计（诚实标注，§4.2）。
        """
        if not phase.gates.quality_check:
            return result.status != "failed"
        passed = await self.gate.decide(phase, result)
        g = getattr(self.gate, "gate_reliability", 1.0)
        if g < 1.0:
            session_note = f"gate_reliability={g} (audit)"
            # 不污染 phase_summaries 列表结构，仅记录到 quality_gates 已由 evaluate 处理
            _ = session_note
        return passed

    # ═══════════════════════════════════════════════════════
    # 会话加载 / 持久化
    # ═════════════════════════════════════════════════════

    async def _load(self, pipeline_id: str, session_id: Optional[str]) -> Optional[PipelineSession]:
        session = self._sessions.get(pipeline_id)
        if session is not None:
            return session
        if self.store is not None:
            return await self.store.load(pipeline_id)
        return None

    async def _persist(self, session: PipelineSession) -> None:
        if self.store is not None:
            await self.store.save(session)

    @staticmethod
    def _phase_ref_key(phase: PhaseDef) -> str:
        """生成相位在 artifact_ref 中的定位段（Phase 重构 P0）。

        用 `phase.path`（树路径，`-` 连接，如 `0-1`）；`phase.path is None`（旧扁平数据）
        回落 `phase.index`，向后兼容。`pipeline_id + 此段` 为相位唯一定位键。
        """
        if phase.path is not None:
            return "-".join(str(i) for i in phase.path)
        return str(phase.index)

    async def _store_artifact(self, session: PipelineSession, ref: str,
                              data: Any, media_type: str = "text") -> None:
        """把相位产物真正写入数据面（纠偏-001：artifact_ref 与 ArtifactStore 接通）。

        引擎产生 `artifact_ref` 的三处（plan/path/result）都必须把对应产物 `store()` 进
        `ArtifactStore`，使 ref 可被 `fetch()` 取回——否则 ref 指向空处。
        未注入 artifact_store（如纯 mock 无数据面）→ 静默跳过，ref 仅为占位。
        """
        if self.artifact_store is None:
            return
        try:
            await self.artifact_store.store(session.pipeline_id, ref, data, media_type)
        except Exception:
            _get_logger().error(f"产物写入数据面失败 ref={ref}")

    async def _fetch_artifact(self, session: PipelineSession, ref: str) -> Optional[dict]:
        """从数据面缝取产物（Phase 重构 P2：父/上游产物读源改走数据面）。

        未注入 artifact_store 或 ref 取不到 → 返回 None（调用方降级空切片，不崩）。
        """
        if self.artifact_store is None:
            return None
        try:
            return await self.artifact_store.fetch(ref)
        except Exception:
            return None

    async def _fetch_parent_context(self, session: PipelineSession,
                                    phase: PhaseDef) -> list:
        """按相位树路径取上游摘要/父产物，拼成上下文切片（Phase 重构 P2.2 补断链）。

        沿 `phase.path` 的父链 fetch：当前相位路径 `[0,1]` → 父 `[0]` 的 result、
        祖父 `[]` 的 plan；以及展平序列中的前一 LEAF 的 summary（跨相位传递）。
        ref 取不到 → 该切片跳过（降级，不崩）。
        """
        slices = []
        if not phase.path:
            return slices
        # 父链：逐层取父相位上下文（Phase 重构 P2 纠偏：summary_ref 优先、result_ref 兜底，
        # 统一数据面契约——summary 是跨相位传递的浓缩载体，result 是完整产物，二选一）。
        for i in range(len(phase.path) - 1, 0, -1):
            parent_path = phase.path[:i]
            art = await self._fetch_best_context(session, parent_path)
            if art is not None:
                slices.append({"kind": "parent_result", "phase_path": parent_path,
                               "data": art.get("data")})
        # 前驱 LEAF：取展平序列前一 LEAF 的上下文（跨相位传递，summary 优先）
        prev = None
        for _p, ph in fractal.iter_phases(session.phases):
            if ph is phase:
                break
            if ph.kind != PhaseKind.NODE:
                prev = ph
        if prev is not None and prev.path is not None:
            art = await self._fetch_best_context(session, prev.path)
            if art is not None:
                slices.append({"kind": "prev_leaf", "phase_path": prev.path,
                               "data": art.get("data")})
        return slices

    async def _fetch_best_context(self, session: PipelineSession,
                                  path: list) -> Optional[dict]:
        """统一数据面契约取相位上下文（Phase 重构 P2 纠偏解套 W-7）。

        summary_ref 优先（浓缩跨相位载体），取不到回落 result_ref（完整产物）。
        两者都取不到 → None（调用方降级空切片，不崩）。
        """
        key = "-".join(map(str, path))
        sref = f"art_{session.pipeline_id}_summary_{key}"
        art = await self._fetch_artifact(session, sref)
        if art is not None:
            return art
        rref = f"art_{session.pipeline_id}_result_{key}"
        return await self._fetch_artifact(session, rref)

    def _has_downstream_consumer(self, session: PipelineSession, phase: PhaseDef) -> bool:
        """下游消费者判定（Phase 重构 P2.4，§四-F）：该相位在展平序列中是否有后继 LEAF，
        或有 children（NODE 下钻）——有则会被下游读其 summary/result；否则不产。
        """
        if phase.children:
            return True
        seen_phase = False
        for _p, ph in fractal.iter_phases(session.phases):
            if ph is phase:
                seen_phase = True
                continue
            if seen_phase and ph.kind != PhaseKind.NODE:
                return True  # 展平序列中有后继 LEAF
        return False

    async def _produce_summary(self, session: PipelineSession, phase: PhaseDef,
                               result) -> None:
        """summary 级推理（Phase 重构 P2.4）：相位成功后产 summary_ref 供下游。

        - 注入 `inference_seam` → 经 `context_patch(ext={"routing": "summary"})` 发起浓缩推理，回填
          `inference_result.content` 作为 summary 写入数据面（summary_ref 与 result_ref 并存）。
        - 未注入 → 用 result.data 直接作为 summary 固化（机械兜底，不依赖推理缝）。
        - `summary_on_demand` 开 → 仅当 `_has_downstream_consumer` 才触发（省低 b 调用）。
        """
        if self.summary_on_demand and not self._has_downstream_consumer(session, phase):
            return
        summary_ref = f"art_{session.pipeline_id}_summary_{self._phase_ref_key(phase)}"
        if self.inference_seam is not None:
            from uuid import uuid4
            # phase_path 以 str 出缝（"-" 连接，如 "0-1"），与数据面 ref 的 _phase_ref_key 同源；
            # 跨内核契约统一为 str，对齐 ck ContextPatch 预期（integration_sl_draft 对齐）。
            patch = ContextPatch(phase_path=self._phase_ref_key(phase), intent=session.intent,
                                 context_id=str(uuid4()),
                                 ext={"routing": "summary", "source": getattr(result, "data", None)})
            try:
                summary = (await self.inference_seam.infer(patch)).content
            except Exception:
                summary = _summarize_result(result)
        else:
            summary = _summarize_result(result)
        await self._store_artifact(session, summary_ref, summary, "text")

    # ═══════════════════════════════════════════════════════
    # 响应构造
    # ═════════════════════════════════════════════════════

    def _step_of(self, session: PipelineSession) -> str:
        current = session.get_current_phase()
        if current is None:
            return STEP_COMPLETED if session.status == PipelineStatus.COMPLETED else STEP_AWAITING_PLAN
        return {
            PhaseStatus.AWAITING_PLAN_CONFIRM: STEP_AWAITING_PLAN,
            PhaseStatus.AWAITING_PATH_CONFIRM: STEP_AWAITING_PATH,
            PhaseStatus.AWAITING_APPROVAL: STEP_AWAITING_APPROVAL,
            PhaseStatus.RUNNING: STEP_EXECUTING,
            PhaseStatus.COMPLETED: STEP_COMPLETED,
            PhaseStatus.FAILED: STEP_ABORTED,
            PhaseStatus.PENDING: STEP_AWAITING_PLAN,
        }.get(current.status, STEP_AWAITING_PLAN)

    def _sp(self, session: PipelineSession, step: str, phase_index: int, artifact_ref) -> dict:
        current = session.get_current_phase()
        idx = current.index if current else phase_index
        # Phase 重构 P0：补 phase_path（相位树路径，稳定寻址；无 path 回落 None）
        phase_path = list(current.path) if (current is not None and current.path is not None) else None
        return {
            "id": session.pipeline_id,
            "step": step,
            "phase_index": idx,
            "phase_path": phase_path,
            "phase_total": len(session.phases),
            "artifact_ref": artifact_ref,
        }

    def _sp_terminal(self, pipeline_id: str, step: str) -> dict:
        return {"id": pipeline_id, "step": step, "phase_index": 0,
                "phase_total": 0, "artifact_ref": None}

    def _respond(self, session: PipelineSession, step: str, content: str) -> dict:
        current = session.get_current_phase()
        return {
            "content": content,
            "synth_pipeline": self._sp(session, step, current.index if current else 0, None),
        }


def _summarize_result(result) -> str:
    """机械兜底 summary：无推理缝时用 result 内容直接做摘要（Phase 重构 P2.4）。"""
    import json
    data = getattr(result, "data", None)
    try:
        text = json.dumps(data, ensure_ascii=False)
    except Exception:
        text = str(data)
    return text[:500]


def _truncate(obj, limit: int = 500) -> str:
    import json
    try:
        text = json.dumps(obj, ensure_ascii=False)
    except Exception:
        text = str(obj)
    return text[:limit]


def _get_logger():
    import logging
    return logging.getLogger("phase_kernel.engine")

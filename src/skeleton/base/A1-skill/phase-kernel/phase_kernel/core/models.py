"""phase-kernel 纯数据模型（设计稿 §3.1；ported from synth-loop models/pipeline.py）

纪律：本模块零外部依赖（不 import tc / sl / FastAPI / 任何第三方包）。
只依赖标准库。
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4


# ═══════════════════════════════════════════════════════════
# 枚举
# ═══════════════════════════════════════════════════════════

class PhaseStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    AWAITING_PLAN_CONFIRM = "awaiting_plan_confirm"
    AWAITING_PATH_CONFIRM = "awaiting_path_confirm"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
    COMPLETED = "completed"
    ABORTED = "aborted"
    FAILED = "failed"


class PhaseKind(str, Enum):
    """相位种类（设计稿 §五 5.1：运行时自决的分形结构）

    - NODE：抽象节点——继续分形，持有 children（子相位），无 steps。
    - LEAF：可落地叶子——落到 path 执行，持有 steps，无 children。

    **默认 LEAF**：旧扁平数据反序列化后仍是叶子，向后兼容（设计稿 §五 5.3）。
    """
    NODE = "node"
    LEAF = "leaf"


class PipelineStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABORTED = "aborted"


class GateType(str, Enum):
    EXECUTION_RESULT = "execution_result"
    HUMAN_REVIEW = "human_review"
    LLM_SELF_CHECK = "llm_self_check"


class GateResult(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    PENDING = "pending"


# ═══════════════════════════════════════════════════════════
# 三闸配置 + 闸门可靠性 g
# ═══════════════════════════════════════════════════════════

class PhaseGates:
    """相位三闸门配置（设计稿 §3.1 / §4.2）

    - allow_path_edit   闸2：进 RUNNING 前需 confirm path
    - require_human_approval 闸3：执行后需外部 approve
    - quality_check     质量闸：执行结果需过判定（默认开）
    - gate_reliability  g：闸门可靠性（错误时正确 reject 的概率）；
                        子命题2 实测标定参数，默认 1.0（设计稿 §4.2 诚实标注：偏乐观）
    """

    def __init__(self, allow_path_edit: bool = False,
                 require_human_approval: bool = False,
                 quality_check: bool = True,
                 gate_reliability: float = 1.0):
        self.allow_path_edit = allow_path_edit
        self.require_human_approval = require_human_approval
        self.quality_check = quality_check
        self.gate_reliability = gate_reliability

    def to_dict(self) -> dict:
        return {
            "allow_path_edit": self.allow_path_edit,
            "require_human_approval": self.require_human_approval,
            "quality_check": self.quality_check,
            "gate_reliability": self.gate_reliability,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhaseGates":
        return cls(
            allow_path_edit=bool(data.get("allow_path_edit", False)),
            require_human_approval=bool(data.get("require_human_approval", False)),
            quality_check=bool(data.get("quality_check", True)),
            gate_reliability=float(data.get("gate_reliability", 1.0)),
        )


# ═══════════════════════════════════════════════════════════
# 相位定义 / 相位树
# ═══════════════════════════════════════════════════════════

class PhaseDef:
    """相位定义（运行时节点；设计稿 §3.1 + §五 5.2）

    `mode` 由 Planner 定义，kernel 不解释。
    `endpoint_hint` 仅作路由提示，交给 Executor 解释。
    `steps` 为本相位的执行步骤（path 组装产物）；可为空，由 Executor 适配器在
    执行前填充（设计稿 §八：synth-loop 现状 steps:[] 是写死空桩，TCExecutor 负责填）。

    分形演进（设计稿 §五 5.2）：
    - `kind`: PhaseKind——默认 `LEAF`（向后兼容）；`NODE` 表示抽象节点（继续分形）。
    - `children`: Optional[list[PhaseDef]]——NODE 的子相位；LEAF 无 children。
    - 不变式：`kind==NODE` → 无 steps（节点抽象）；`kind==LEAF` → 无 children。
    """

    def __init__(self, index: int, name: str, description: str, mode: str = "single_ai",
                 gates: Optional[PhaseGates] = None, endpoint_hint: Optional[str] = None,
                 status: PhaseStatus = PhaseStatus.PENDING, steps: Optional[list] = None,
                 kind: PhaseKind = PhaseKind.LEAF, children: Optional[list["PhaseDef"]] = None,
                 depth: int = 0, rollback_count: int = 0,
                 tools: Optional[list] = None, skills_prompt: str = "", assets: Any = None,
                 path: Optional[list] = None):
        self.index = index
        self.name = name
        self.description = description
        self.mode = mode
        self.gates = gates or PhaseGates()
        self.endpoint_hint = endpoint_hint
        self.status = status
        self.steps = steps or []
        self.kind = kind
        self.children = children or None
        self.depth = depth  # 分形深度（从根累计；触顶二选一判断依据，Phase 2）
        self.rollback_count = rollback_count  # 相位内回退计数（earliest-close 门控，Phase 3）
        self.tools = tools or []  # 相位可用工具切片（Phase 5：strata 消费 tools[]，供相位模板注入）
        self.skills_prompt = skills_prompt or ""  # 相位技能提示（Phase 5：strata 消费 skills_prompt）
        self.assets = assets or None  # 相位资产（Phase 5：strata 消费 assets）
        self.path = path  # 相位树路径（分形/链式子相位唯一定位；None = 旧扁平数据回落 index，Phase 重构 P0）

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "name": self.name,
            "description": self.description,
            "mode": self.mode,
            "gates": self.gates.to_dict(),
            "endpoint_hint": self.endpoint_hint,
            "status": self.status.value,
            "steps": self.steps,
            "kind": self.kind.value,
            "children": [c.to_dict() for c in self.children] if self.children else None,
            "depth": self.depth,
            "rollback_count": self.rollback_count,
            "tools": self.tools,
            "skills_prompt": self.skills_prompt,
            "assets": self.assets,
            "path": self.path,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhaseDef":
        children_raw = data.get("children") or None
        children = (
            [cls.from_dict(c) for c in children_raw] if children_raw else None
        )
        return cls(
            index=int(data["index"]),
            name=data["name"],
            description=data.get("description", ""),
            mode=data.get("mode", "single_ai"),
            gates=PhaseGates.from_dict(data.get("gates", {})),
            endpoint_hint=data.get("endpoint_hint"),
            status=PhaseStatus(data.get("status", "pending")),
            steps=data.get("steps") or [],
            kind=PhaseKind(data.get("kind", "leaf")),
            children=children,
            depth=int(data.get("depth", 0)),
            rollback_count=int(data.get("rollback_count", 0)),
            tools=data.get("tools"),
            skills_prompt=data.get("skills_prompt", ""),
            assets=data.get("assets"),
            path=data.get("path"),
        )


class PhasePlan:
    """相位树（设计稿 §3.1）

    设计稿称其为「树」（相位可递归为子相位），本移植以扁平 list 承载，
    递归（子相位）由 Planner 产出嵌套结构时自然支持；kernel 只守「相位树形状」，
    「怎么切」交给 Planner（§10.3 放宽 goal_repr）。
    """

    def __init__(self, phases: list[PhaseDef]):
        self.phases = phases

    def to_dict(self) -> dict:
        return {"phases": [p.to_dict() for p in self.phases]}

    @classmethod
    def from_dict(cls, data: dict) -> "PhasePlan":
        return cls(phases=[PhaseDef.from_dict(p) for p in data.get("phases", [])])


# ═══════════════════════════════════════════════════════════
# 相位产物固化单元（子命题3 状态可知性的数据底座）
# ═══════════════════════════════════════════════════════════

class PhaseArtifact:
    """逐相累积的固化产物（设计稿 §3.1 phase_summaries）"""

    def __init__(self, phase_index: int, type: str = "text", ref: Optional[str] = None,
                 data: Any = None):
        self.phase_index = phase_index
        self.type = type
        self.ref = ref
        self.data = data
        self.created_at = datetime.now()

    def to_dict(self) -> dict:
        return {
            "phase_index": self.phase_index,
            "type": self.type,
            "ref": self.ref,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PhaseArtifact":
        return cls(
            phase_index=int(data["phase_index"]),
            type=data.get("type", "text"),
            ref=data.get("ref"),
            data=data.get("data"),
        )


# ═══════════════════════════════════════════════════════════
# 执行结果（闭集信封；设计稿 §3.1）
# ═══════════════════════════════════════════════════════════

class PhaseResult:
    """Executor 返回；status 闭集 success/failed/pending（设计稿 §一.2）"""

    def __init__(self, status: str, data: Any = None, error: str = "",
                 task_id: Optional[str] = None):
        if status not in ("success", "failed", "pending"):
            raise ValueError(f"PhaseResult.status 必须闭集: {status}")
        self.status = status
        self.data = data
        self.error = error
        self.task_id = task_id

    def to_dict(self) -> dict:
        return {"status": self.status, "data": self.data,
                "error": self.error, "task_id": self.task_id}

    @classmethod
    def from_envelope(cls, envelope: dict) -> "PhaseResult":
        """从 tc 统一信封 {rst_types, rst_data, rst_err} 解析为闭集 PhaseResult。

        信任根诚实标注（设计稿 §10.2）：若后端返回非闭集（自由文本「好像成功了」），
        MechanicalGate 比对 status 失效 → P_ctrl 破防。此处只做结构解析，不替后端担保。
        """
        rst_data = envelope.get("rst_data") or {}
        rst_err = envelope.get("rst_err") or ""
        # tc 异步五态：rst_data.status ∈ {ok, pending, failed}
        tc_status = rst_data.get("status") if isinstance(rst_data, dict) else None
        if tc_status == "pending":
            return cls("pending", data=rst_data, task_id=rst_data.get("task_id"), error=rst_err)
        if tc_status == "failed" or rst_err:
            return cls("failed", data=rst_data, error=rst_err or "execution failed")
        # 默认视为成功（ok / 其它闭集）
        return cls("success", data=rst_data, error=rst_err)

    @classmethod
    def from_inference(cls, inference: "InferenceResult") -> "PhaseResult":
        """推理缝结果归位核心闭集（Phase 重构 P1，refactor §五-17）。

        `content` → `data`；`status` **不提前假设**（推理缝不判定成败），由调用方
        （`_finalize_execution`）走质量闸闭集判定 success/failed。`result_ref` 仅作
        推理侧外部回链，`data` 中携带，供数据面 artifact_ref（`_phase_ref_key`）区分。
        """
        return cls("success", data={"content": inference.content,
                                    "result_ref": inference.result_ref},
                   error="")


# ═══════════════════════════════════════════════════════════
# 推理缝数据类（Phase 重构 P1；refactor-inference-seam §一 1.4）
# ═══════════════════════════════════════════════════════════

class ContextPatch:
    """相位推理请求原语（refactor §一 1.4 最小骨架；v3.3 去 tier）。

    pk 让出"上下文组装权 + 推理裁决权"，只声明"我这个相位需要推理，这是输入"。
    `context_id` 为瞬时配对令牌（不入库）：pk 发起时自造（或接入方生成，见 dev plan §五-3），
    接入方执行后带同一 id 回填，pk 凭它归位。`phase_path` 为树路径（四缝共用寻址坐标），
    `ext` 为模态扩展槽（不锁 ck）——"路由标签"经 `ext["routing"]` 透传，pk 内核不解释。
    """

    def __init__(self, phase_path: Optional[list], intent: str,
                 context_id: str, ext: Optional[dict] = None):
        self.phase_path = phase_path
        self.intent = intent
        self.context_id = context_id
        self.ext = ext or {}

    def to_dict(self) -> dict:
        return {"phase_path": self.phase_path, "intent": self.intent,
                "context_id": self.context_id, "ext": self.ext}


class InferenceResult:
    """接入方（serve llm 接收器 / ck）拼装 + 推理后回填的生成结果。

    `content` 为生成结果（文本/结构化）；`result_ref` 可选，仅作推理侧外部回链
    （与数据面 `artifact_ref` 并存、职责不同）；`ext` 模态扩展槽。
    """

    def __init__(self, context_id: str, content: str,
                 result_ref: Optional[str] = None, ext: Optional[dict] = None):
        self.context_id = context_id
        self.content = content
        self.result_ref = result_ref
        self.ext = ext or {}


# ═══════════════════════════════════════════════════════════
# sm 缝数据类（Phase 重构 P3；refactor-inference-seam §四-C）
# ═══════════════════════════════════════════════════════════

class SmRequest:
    """sm 缝请求（Phase 重构 P3）：向 strata-match 取某相位策略内容的定位参数。

    `phase_path` 为树路径（四缝共用寻址坐标），替换旧 `phase_meta` 手工拼 name/description。
    """

    def __init__(self, phase_path: Optional[list], intent: str, lang: str = "en",
                 name: Optional[str] = None, description: Optional[str] = None):
        self.phase_path = phase_path
        self.intent = intent
        self.lang = lang  # 默认对齐 sm _b（缺省 en）；必须真正透传给 sm（StrataHttpSm 构造请求带 lang）
        self.name = name
        self.description = description


class SmStrategyBundle:
    """sm 缝返回的结构化相位策略包（对齐 sm QueryResponse _b 契约）。

    - `primary_prompt`: 按 lang 输出的主提示词。
    - `tools`/`skills`/`assets`: 结构化素材（sm 查询响应已是 compact 单值——`_lang`/`content`
      已按 lang 过滤，pk 直接消费，无需自己解析 `*_lang` 字典）。
    """

    def __init__(self, primary_prompt: str = "", tools: Optional[list] = None,
                 skills: Optional[list] = None, assets: Optional[list] = None,
                 lang: Optional[str] = None):
        self.primary_prompt = primary_prompt
        self.tools = tools or []
        self.skills = skills or []
        self.assets = assets or []
        self.lang = lang

    def to_dict(self) -> dict:
        return {"primary_prompt": self.primary_prompt, "tools": self.tools,
                "skills": self.skills, "assets": self.assets, "lang": self.lang}


class SmResponse:
    """sm 缝响应：取回的策略内容（prompt）。

    Phase A（sm _b 升级）：承载 `SmStrategyBundle`——`prompt` 保留（作为 `primary_prompt`
    别名，向后兼容），并新增 `tools`/`skills`/`assets`/`lang` 字段。
    """

    def __init__(self, prompt: Optional[str] = None,
                 bundle: Optional[SmStrategyBundle] = None,
                 tools: Optional[list] = None, skills: Optional[list] = None,
                 assets: Optional[list] = None, lang: Optional[str] = None):
        self.prompt = prompt
        self.tools = tools if tools is not None else (bundle.tools if bundle else [])
        self.skills = skills if skills is not None else (bundle.skills if bundle else [])
        self.assets = assets if assets is not None else (bundle.assets if bundle else [])
        self.lang = lang if lang is not None else (bundle.lang if bundle else None)

    @classmethod
    def from_bundle(cls, bundle: SmStrategyBundle) -> "SmResponse":
        return cls(prompt=bundle.primary_prompt, tools=bundle.tools, skills=bundle.skills,
                   assets=bundle.assets, lang=bundle.lang)


class PipelineSession:
    """相位会话——跨项目单一真相来源（设计稿 §3.1）

    较 synth-loop 版本新增：
    - `phase_summaries: list[PhaseArtifact]`（逐相固化产物，设计稿 §3.1）
    - `checkpoint_index: int` + `rollback_to(index)`（子命题1 最坏代价 N/k，设计稿 §4.3）
    """

    def __init__(self, intent: str, plan: Optional[PhasePlan] = None,
                 user_id: Optional[str] = None, pipeline_id: Optional[str] = None,
                 session_id: Optional[str] = None):
        self.pipeline_id = pipeline_id or str(uuid4())
        self.intent = intent
        self.user_id = user_id
        self.session_id = session_id
        self.status = PipelineStatus.DRAFT
        self.plan = plan or PhasePlan([])
        self.phases: list[PhaseDef] = []
        self.phase_stack: list[int] = []  # 递归路径（设计稿 §六 6.2：NODE 下钻记录）
        self.phase_summaries: list[PhaseArtifact] = []
        self.checkpoint_index: int = -1
        self.phase_history: list[dict] = []
        self.quality_gates: list[dict] = []
        self.artifacts: list[dict] = []
        self.async_tasks: list[dict] = []
        self.pointer_log: list[dict] = []  # 指针日志（执行相位服务 §2.6/§3：path 指令 ID/远端 URL/pk URL/复议 verdict/回退计数）
        self.created_at = datetime.now()
        self.updated_at = datetime.now()

    # ── 序列化 ──
    def to_dict(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "intent": self.intent,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "status": self.status.value,
            "plan": self.plan.to_dict(),
            "phases": [p.to_dict() for p in self.phases],
            "phase_stack": list(self.phase_stack),
            "phase_summaries": [a.to_dict() for a in self.phase_summaries],
            "checkpoint_index": self.checkpoint_index,
            "phase_history": self.phase_history,
            "quality_gates": self.quality_gates,
            "artifacts": self.artifacts,
            "async_tasks": self.async_tasks,
            "pointer_log": self.pointer_log,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PipelineSession":
        s = cls(
            intent=data["intent"],
            plan=PhasePlan.from_dict(data.get("plan", {"phases": []})),
            user_id=data.get("user_id"),
            pipeline_id=data.get("pipeline_id"),
            session_id=data.get("session_id"),
        )
        s.status = PipelineStatus(data.get("status", "draft"))
        s.phases = [PhaseDef.from_dict(p) for p in data.get("phases", [])]
        s.phase_stack = [int(i) for i in data.get("phase_stack", [])]
        s.phase_summaries = [PhaseArtifact.from_dict(a) for a in data.get("phase_summaries", [])]
        s.checkpoint_index = int(data.get("checkpoint_index", -1))
        s.phase_history = data.get("phase_history", [])
        s.quality_gates = data.get("quality_gates", [])
        s.artifacts = data.get("artifacts", [])
        s.async_tasks = data.get("async_tasks", [])
        s.pointer_log = data.get("pointer_log", [])
        s.created_at = _parse_dt(data.get("created_at"), s.created_at)
        s.updated_at = _parse_dt(data.get("updated_at"), s.updated_at)
        return s

    # ── 管道状态转换（ported from synth-loop）──
    def start(self) -> None:
        if self.status != PipelineStatus.DRAFT:
            raise ValueError(f"Cannot start from status: {self.status}")
        self.status = PipelineStatus.ACTIVE
        self.updated_at = datetime.now()
        # Phase 重构 P0：用 plan.phases 重建结构（保持测试依赖的 planner 原始 children），
        # 但顶层 `path` 从当前 `self.phases`（_start_planning 已设为 _expand_fractal 展开结果，
        # 顶层 path=[i] 已赋）按 index 透传，避免 `start()` 重建丢掉四缝寻址地基。
        # 子相位 path 在 `_next_leaf` 执行定位时经 `iter_phases` 动态赋值；无 path 回落 index。
        cur_paths = {p.index: p.path for p in self.phases if p.path is not None}
        self.phases = [
            PhaseDef(index=pc.index, name=pc.name, description=pc.description,
                     mode=pc.mode, gates=pc.gates, endpoint_hint=getattr(pc, "endpoint_hint", None),
                     steps=getattr(pc, "steps", None) or [],
                     kind=getattr(pc, "kind", PhaseKind.LEAF),
                     children=getattr(pc, "children", None),
                     path=cur_paths.get(pc.index))
            for pc in self.plan.phases
        ]

    def complete(self) -> None:
        if self.status != PipelineStatus.ACTIVE:
            raise ValueError(f"Cannot complete from status: {self.status}")
        self.status = PipelineStatus.COMPLETED
        self.updated_at = datetime.now()

    def abort(self, reason: str = "") -> None:
        if self.status in {PipelineStatus.COMPLETED, PipelineStatus.ABORTED}:
            raise ValueError(f"Cannot abort from terminal status: {self.status}")
        self.status = PipelineStatus.ABORTED
        self.updated_at = datetime.now()
        for p in self.phases:
            if p.status not in {PhaseStatus.COMPLETED, PhaseStatus.FAILED}:
                p.status = PhaseStatus.FAILED

    # ── 相位操作 ──
    def get_current_phase(self) -> Optional[PhaseDef]:
        for p in self.phases:
            if p.status in {PhaseStatus.PENDING, PhaseStatus.RUNNING,
                            PhaseStatus.AWAITING_PATH_CONFIRM, PhaseStatus.AWAITING_APPROVAL}:
                return p
        return None

    def advance_phase(self, phase_index: int, new_status: PhaseStatus, output: str = "") -> None:
        """记录相位状态推进历史（分形感知，Phase 1）。

        注意：**不再用 `phase_index` 反查 `self.phases[phase_index]` 改 status**——
        在分形树里 `phase.index` 是相对索引（NODE 的 children 各自从 0 计数），
        用它反查顶层列表会误改兄弟/父节点。相位 status 由调用方直接操作
        phase 对象完成；此处仅记录历史 + 更新 updated_at。
        """
        self.phase_history.append({
            "index": phase_index,
            "status": new_status.value,
            "output": output or None,
            "at": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    def add_quality_gate(self, phase_index: int, gate_type: str, result: str, detail: str = "") -> None:
        self.quality_gates.append({
            "phase_index": phase_index,
            "gate_type": gate_type,
            "result": result,
            "detail": detail,
            "at": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    def add_artifact(self, phase_index: int, name: str, artifact_type: str,
                     local_path: str, cdn_url: Optional[str] = None) -> None:
        self.artifacts.append({
            "phase_index": phase_index, "name": name, "type": artifact_type,
            "local_path": local_path, "cdn_url": cdn_url,
            "at": datetime.now().isoformat(),
        })
        self.updated_at = datetime.now()

    # ── 检查点 + 回退（设计稿 §4.3 子命题1）──
    def checkpoint(self, phase_index: int) -> None:
        """相位成功固化后推进检查点（子命题1：最坏代价 ≤ N/k）"""
        if phase_index > self.checkpoint_index:
            self.checkpoint_index = phase_index
            self.updated_at = datetime.now()

    def rollback_to(self, index: int) -> None:
        """状态机原生回退：退到指定检查点重入（reject/regenerate 内部调用）。

        把 index 之后的相位重置为 PENDING，当前重入点设为 index+1。
        """
        if index < -1 or index >= len(self.phases):
            raise IndexError(f"checkpoint {index} out of range")
        for p in self.phases:
            if p.index > index:
                p.status = PhaseStatus.PENDING
        self.checkpoint_index = index
        self.updated_at = datetime.now()


def _parse_dt(value: Optional[str], fallback: datetime) -> datetime:
    if not value:
        return fallback
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return fallback

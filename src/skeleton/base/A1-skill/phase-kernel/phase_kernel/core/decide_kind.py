"""`decide_kind` 契约闭合判据（设计稿 §四 4.1 + §4.3；P2a）

把相位判为**节点**（继续分形）还是**叶子**（落到 path 执行）。

原则（设计稿 §四）：
- **可机械判定**，不依赖 LLM 主观——判定独立于制造错误的 LLM，使 LLM 犯错时错误能被可靠看见、被纠正（信任链：错误可见，非判定得准）。
- **默认 LEAF**——不把无限分形的负担压给会犯错的 LLM，让它每次只承担一小段。
- **有界终止**——深度超 `max_phase_depth` 强制 LEAF，不无限分形（参考 path 引擎 `depth≤2`）。

本模块（P2a）只做**纯判定 + path 声明字段**路径，零外部依赖、不依赖 sm。
sm `tools[]` 作为补充真相源（契约缺失时）由 P2b 接入——本模块通过 `contract` 参数接收
path 声明（或 P2b 构造的 sm 工具契约），判定逻辑与真相源解耦。
"""

from __future__ import annotations

from typing import Any, Optional

from .models import PhaseDef, PhaseKind


# 默认递归深度上限（参考 path 引擎 map 的 depth≤2 守卫）
DEFAULT_MAX_PHASE_DEPTH = 2


def _has_input_contract(contract: Optional[dict]) -> bool:
    """输入契约闭合：有明确的输入参数定义。

    path 声明 `input_schema.properties` 非空即可判定有输入契约。
    """
    if not contract:
        return False
    input_schema = contract.get("input_schema")
    if isinstance(input_schema, dict):
        props = input_schema.get("properties")
        if props:
            return True
        # 无 properties 但有 type（如 string/number）也算有输入契约
        if input_schema.get("type"):
            return True
    return False


def _has_output_contract(contract: Optional[dict]) -> bool:
    """输出信封闭合：有明确的输出类型/字段。

    path 声明 `output_schema.type` 存在即可判定有输出信封。
    """
    if not contract:
        return False
    output_schema = contract.get("output_schema")
    if isinstance(output_schema, dict):
        if output_schema.get("type"):
            return True
        if output_schema.get("properties"):
            return True
    return False


def _has_fixable_artifact(phase: PhaseDef) -> bool:
    """可固化产物闭合：有明确的产物固化点。

    `steps[].output_as` 任一存在 → 有产物固化点；或 endpoint_hint 已指向真实落点。
    """
    for step in phase.steps or []:
        if isinstance(step, dict) and step.get("output_as"):
            return True
        if isinstance(step, dict) and step.get("action"):
            # 至少有一条可执行动作 → 可产生产物
            return True
    # 有 endpoint_hint（路由提示）也视为有落点
    if phase.endpoint_hint:
        return True
    return False


def decide_kind(phase: PhaseDef,
                contract: Optional[dict] = None,
                depth: int = 0,
                max_phase_depth: int = DEFAULT_MAX_PHASE_DEPTH) -> PhaseKind:
    """判定相位种类（设计稿 §四 4.1）。

    参数：
    - `phase`: PhaseDef——判定的相位。
    - `contract`: 可选的 path 声明 / sm 工具契约（dict），含 `input_schema`/`output_schema`/`requires`。
    - `depth`: 当前递归深度（由外层调用方传入）。
    - `max_phase_depth`: 递归深度上限，超限强制 LEAF（有界终止）。

    返回：`LEAF`（契约闭合可落地）或 `NODE`（还需分形探索）。
    """
    # 有界性：深度超限 → 强制 LEAF（纯机械极小执行，不无限分形）
    if depth >= max_phase_depth:
        return PhaseKind.LEAF

    # 契约闭合：输入契约 + 输出信封 + 可固化产物 三项全部闭合 → LEAF
    if _has_input_contract(contract) and _has_output_contract(contract) and _has_fixable_artifact(phase):
        return PhaseKind.LEAF

    # 否则 → NODE（还需分形探索，由下层再判）
    return PhaseKind.NODE


def tools_to_contract(tools: Optional[list]) -> Optional[dict]:
    """把 sm `tools[]`（工具切片）构造成 `decide_kind` 的 contract（P2b）。

    职责分层（sm-phase-requirements_zh.md）：sm 是图书馆，只提供工具素材；
    `decide_kind` 判定在 pk 内部。本函数把 sm 返回的工具切片**转换**为判定可用的
    contract（input_schema / output_schema / requires），不感知相位状态。

    sm `tools[]` 项字段（v0.1.2_a 契约锚）：
    - `usage`: `domain;action` 规范标识（可执行性）
    - `command`: 原样透传 tc 指令（可执行性）
    - `params`: 参数占位（输入契约）
    - `definition`: 工具定义（textcli 时含 command）

    返回：非空 tools 且有可执行性 → contract dict；空/不可执行 → None（触发降级）。
    """
    if not tools:
        return None

    # 收集输入参数（params 或 definition.command 里的占位）
    params = {}
    has_executable = False
    for t in tools:
        if not isinstance(t, dict):
            continue
        # 可执行性：有 usage 或 command（纯净 domain;action / 原样 tc 指令）
        if t.get("usage") or t.get("command"):
            has_executable = True
        # 输入参数：params 数组（参数占位）或 definition 里的 command 占位
        t_params = t.get("params")
        if isinstance(t_params, list):
            for p in t_params:
                if isinstance(p, dict) and p.get("name"):
                    params[p["name"]] = {"type": "string"}
                elif isinstance(p, str):
                    params[p] = {"type": "string"}

    # 无可执行工具 → 视为无契约（降级到 path 声明字段）
    if not has_executable:
        return None

    contract = {
        "input_schema": {"properties": params} if params else {"type": "object"},
        # 有可执行工具 → 视为有稳定输出信封（usage/command 即输出落点）
        "output_schema": {"type": "object"},
        "requires": [t.get("usage") for t in tools if isinstance(t, dict) and t.get("usage")],
    }
    return contract

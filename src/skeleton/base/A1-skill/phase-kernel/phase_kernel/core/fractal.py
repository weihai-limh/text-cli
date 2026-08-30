"""分形执行核心（设计稿 §六：递归下钻 + 栈上回退；P3）

提供 NODE/LEAF 分形树的**执行视角**，与线性 orchestrator 解耦：
- `iter_phases`：深度优先遍历相位树，产出 `(path, phase)` 执行顺序——把分形树展平为可执行序列。
- `phase_stack` 维护：下钻 NODE 时 push、子层完成回栈时 pop。
- `rollback_stack`：栈上回退——回退到栈上某层，只重跑该子树，不影响兄弟节点。
- `should_reassess`：反向信号——LEAF 执行出大量 delegated/partial → 重估为 NODE（判错可纠正）。

信任链（设计稿 §二）：反向信号是**核心判据**（非辅助）——认可 LLM 第一次判可能错，
判错不致命，反馈式重估。有界性：深度超 `max_phase_depth` 强制 LEAF，不无限分形。
"""

from __future__ import annotations

from typing import Any, Iterator, Optional, Tuple

from .models import PhaseDef, PhaseKind

# 反向信号阈值：partial/delegated 达到此比例 → 重估为 NODE
REASSESS_DELEGATED_RATIO = 0.5


def iter_phases(plan_phases: list) -> Iterator[Tuple[list, Any]]:
    """深度优先遍历相位树，产出 (path, phase)。

    - `path`: list[int]——从根到当前相位的索引路径（NODE 下钻时 path 增长）。
    - `phase`: PhaseDef——当前要执行的相位。
    - NODE → 递归进入 children；LEAF → 产出自身。

    有界性：NODE 无 children（异常）或 children 为空 → 仍产出 NODE 自身（由上层判定降级）。
    """
    def _walk(phases: list, path: list):
        for i, phase in enumerate(phases):
            child_path = path + [i]
            if phase.kind == PhaseKind.NODE and phase.children:
                yield from _walk(phase.children, child_path)
            else:
                yield child_path, phase

    yield from _walk(list(plan_phases), [])


def current_depth(session) -> int:
    """当前递归深度 = phase_stack 长度（设计稿 §六 6.2）。"""
    return len(getattr(session, "phase_stack", []))


def push(session, child_index: int) -> None:
    """下钻：进入 NODE 的 children，记录当前子索引。"""
    session.phase_stack.append(child_index)


def pop(session) -> Optional[int]:
    """回栈：子层完成，回到父层。返回弹出的父层子索引。"""
    if not session.phase_stack:
        return None
    return session.phase_stack.pop()


def resolve_path(session, path: list) -> Optional[Any]:
    """按 path 从根解析到目标相位（`session.phases` 顶层 + children 递归）。"""
    if not path:
        return None
    node = session.phases
    for i, idx in enumerate(path):
        if isinstance(node, list):
            if idx >= len(node):
                return None
            node = node[idx]
        elif hasattr(node, "children") and node.children and idx < len(node.children):
            node = node.children[idx]
        else:
            return None
    return node if hasattr(node, "kind") else None


def _resolve_container(session, path: list) -> Optional[list]:
    """解析 path 的**父容器**（相位列表），用于重置同层兄弟。

    - `path=[]` → 顶层 `session.phases`。
    - `path=[0]` → 顶层第 0 个相位是 NODE 时，容器 = 它的 children；否则顶层。
    - `path=[0,1]` → 根 NODE 的 children list（path[:-1] 定位到 NODE 后取其 children）。
    """
    if not path:
        return list(session.phases)
    # 定位到 path 的父级 NODE
    node = session.phases
    for idx in path[:-1]:
        if isinstance(node, list):
            if idx >= len(node):
                return None
            node = node[idx]
        if hasattr(node, "children") and node.children:
            node = node.children
        else:
            return None
    # 当前层：若 path 最后一个元素指向 NODE，容器是该 NODE 的 children；否则顶层
    last = path[-1]
    if isinstance(node, list):
        if last >= len(node):
            return None
        cur = node[last]
    else:
        cur = node
    if hasattr(cur, "children") and cur.children:
        return cur.children
    if isinstance(node, list):
        return node
    return list(session.phases)


def rollback_stack(session, path: list, index: int) -> None:
    """栈上回退：回退到 `(path, index)`，只重跑该子树，不影响兄弟节点。

    - 重置目标层 `index` 之后的相位为 PENDING（可重入）。
    - `path` 指向当前执行层：重置该层 `index` 之后的兄弟相位。

    代价界：回退代价 ≤ 当前子树长度（设计稿 §六 6.3，与"只重跑当前相位"一致，
    只是把"当前相位"换成"当前子树"）。
    """
    from .models import PhaseStatus
    container = _resolve_container(session, path)
    if container is None:
        return
    for p in container:
        if getattr(p, "index", 0) > index:
            p.status = PhaseStatus.PENDING


def should_reassess(result) -> bool:
    """反向信号（核心判据）：LEAF 执行后是否应重估为 NODE。

    设计稿 §四 4.2：LEAF 执行后 path 返回大量 `delegated`/`partial`
    （指令未装、部分完成）→ 说明这个"叶子"尚未真正可落地 → 重估为 NODE。

    判定依据：result.data 里的 `delegated` 数量 / `status=="partial"`。
    判错不致命——反馈式重估（信任链：认可第一次判可能错）。

    W-1（P4 登记，预留开关，不阻塞主链路）：本函数保持纯函数、不含 `mode`。
    反向信号当前未被 orchestrator 调用（仅为设计稿预留机制）。一旦将来在
    orchestrator 执行后处理处接线，**链式（chain）模式必须禁用反向重估**——
    否则 should_reassess 会把已触顶的 LEAF 重估为 NODE，绕过 P2/P3 的触顶约束
    而破链。接线处须按 `mode=="chain"` 短路返回 False（详见
    docs/mode-structural-vs-chain_zh.md 的「反向信号」章节）。
    """
    data = getattr(result, "data", None)
    if not isinstance(data, dict):
        return False
    # path 返回 partial 状态 → 部分完成 + 部分委托 → 重估
    if data.get("status") == "partial":
        return True
    # 大量 delegated 指令 → 尚未真正可落地
    delegated = data.get("delegated")
    if isinstance(delegated, (list, int)):
        count = len(delegated) if isinstance(delegated, list) else delegated
        completed = data.get("completed_steps") or []
        total = count + (len(completed) if isinstance(completed, list) else 0)
        if total > 0 and count / total >= REASSESS_DELEGATED_RATIO:
            return True
    return False

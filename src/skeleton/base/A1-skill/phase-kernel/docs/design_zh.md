# phase-kernel 设计文档

> 本文档基于 **真实实现** 回写，以 phase-kernel 自身为**唯一真源**（不再以任何外部编排者为参照系）。

---

## 一、机制基础

### 1.1 核心命题

**相位推理 = 「多次推理 + 多次上下文重组」在规划层的投影**：

> 把「完成一个任务」组织为「一系列在重组上下文中的推理」，使单次推理只承担一小段认知负载（化解长链负载），且任意两次推理之间可重组纠错（化解不可循环）。

phase-kernel 是这个机制的**独立内核**：协议无关、tc 无关的多步可干预调度核。`core/` + `ports/` 零外部依赖（仅标准库 + 自身），所有 tc/strata/LLM 差异全部收口于 `adapters/`。

### 1.2 与 tc 协议三对应面

| tc 协议性质 | 相位机制对应 |
|---|---|
| 一维契约可递归收敛 | 相位递归分层：`Planner` 产出 `PhasePlan`（相位树），`Executor` 执行叶子 |
| 统一信封状态可知 | 相位闸门与回退：`PhaseResult{status}` 闭集，三闸只比对 status 不调 LLM |
| query/install 内省扩展 | 按相位工具目录：`ToolCatalog.list_for_phase` |

### 1.3 三闸与检查点

**三闸**（`PhaseGateExecutor`，零业务耦合的状态操作）：

| 闸 | 触发点 | 语义 |
|---|---|---|
| 闸2 `allow_path_edit` | 进 RUNNING 前 | ON → `AWAITING_PATH_CONFIRM`（等人确认 path）；OFF → 直进 RUNNING |
| 闸3 `require_human_approval` | 执行后质量闸通过时 | ON → `AWAITING_APPROVAL`（执行完等外部 `confirm`/`reject` 人审）；OFF → 直进 COMPLETED |
| 质量闸 `evaluate_quality_gate` | 结果过 `EXECUTION_RESULT` | 判定者注入：默认 `MechanicalGate`（闭集比对），可换 `LLMGate`/`HumanGate` |

**实现注**：`evaluate_quality_gate` 现直接操作**传入的 `phase` 对象**而非按 `phase_index` 反查 `session.phases`——分形树下 `phase.index` 是相对索引（NODE 的 children 各自从 0 计数），反查顶层列表会误改兄弟/父节点。

```python
# gates.py evaluate_quality_gate（质量闸核心；分形感知）
phase_index = phase.index
gate_type = GateType.EXECUTION_RESULT.value
result = GateResult.PASSED.value if execution_passed else GateResult.FAILED.value
session.add_quality_gate(phase_index, gate_type, result, detail)
if not execution_passed:
    phase.status = PhaseStatus.FAILED; return PhaseStatus.FAILED
if phase.gates.require_human_approval:      # 闸3：人审
    phase.status = PhaseStatus.AWAITING_APPROVAL; return PhaseStatus.AWAITING_APPROVAL
phase.status = PhaseStatus.COMPLETED
session.advance_phase(phase_index, PhaseStatus.COMPLETED, output=...)
session.checkpoint(phase_index)   # 检查点推进（子命题1）
return PhaseStatus.COMPLETED
```

**人审闸（闸3）状态转换**：相位执行、质量闸通过后若 `require_human_approval` → 停 `AWAITING_APPROVAL`，等待外部动作：
- `confirm` → `approve_phase`：`COMPLETED` + 检查点推进（`add_quality_gate(HUMAN_REVIEW, passed, "approved by human")`）；
- `reject` → `reject_phase`：相位回 `RUNNING`（反馈注入下一轮），编排层将其置于 `AWAITING_PATH_CONFIRM` 重试当前相位。

**检查点回退**（子命题1）：每相位成功固化后 `checkpoint_index` 推进到该相位；相位内回退（review `unsatisfied` / 执行失败 / 人审 `reject`）的本质是**只重跑当前相位**，最坏失败代价 ≤ 当前相位长度，严格优于一次长程的 N。`rollback_to(checkpoint)` 是内部状态机原语，`action` 是外部驱动信号，两者不冲突。

`gate_reliability g`：显式参数（默认 1.0 偏乐观），真实值待实测标定（`MechanicalGate=1.0`、`LLMGate=0.9` 并写入审计）。

### 1.4 长任务轮询

`execute()` 返回 `status="pending"` + `task_id` → 引擎停 `EXECUTING`，content 提示回传 `action=check_result` → 回传后 `executor.poll(task_id)`：

```
pending → 仍停 EXECUTING（继续等）
success / failed → 推进至质量闸
```

### 1.5 结果复议自评（review）

执行结果回填后，若 `review_enabled`（默认关）→ 让 LLM 做**结果复议自评**，返回约定 XML verdict，机械闸纯字符串匹配闭集：

```xml
<phase_verdict>satisfied</phase_verdict>     <!-- 达到目标 → 照常推进 -->
<phase_verdict>unsatisfied</phase_verdict>   <!-- 未达目标 → 相位内回退 -->
<phase_verdict>settled</phase_verdict>       <!-- 尽力但软性不收敛 → 接受稳定产出放行 -->
```

- 闭集：只认 `satisfied / unsatisfied / settled` 三个值，机械闸只认闭集。
- 匹配不到 XML → 默认 `satisfied`（信任单步决策为默认，没主动说不满意 = 默认满意）。
- `unsatisfied` → 相位内回退（`_phase_rollback`）；`settled` → 照常推进。
- 复议与机械质量闸**互补**：复议是"结果是否达目标"的自评信号（LLM），`rst_err`/质量闸是"path 跑完机器判好坏"的机械信号（后置判定），各用所长、不替代。
- **不做 round=1 前置自评**——首次生成对自己的制品自信，且二次复议看到前置自评会形成"反对自己先前评价"的认知张力。

**实现注**：受 `review_enabled` + `review_llm` 参数控制；`review_enabled=False` 或无 `review_llm` → 结果回来不经 LLM 复议、直接走机械门控。复议 verdict 写入 `PipelineSession.pointer_log`（`{"type":"review_verdict","phase":..,"verdict":..}`）。

### 1.6 strata 与两级回退

- **strata-match 服务**（`StrataMatcher` 适配器）：`POST /api/v1/query{user_ask, phase}` 作为规划 prompt 与工具切片的真相源。
- **两级回退**：一级 = strata-match 不可用/超时/空 → 默认规划 prompt（仍走 LLM 或机械兜底）；二级 = 连 LLM 也失败 → **纯机械极小规划**（`MechanicalPlanner`，零 LLM），P_ctrl 不依赖 LLM。
- **真实相位意图（实现注）**：`StrataMatcher._resolve_phase` 在分形下钻传 `PhaseDef` 时，用其**真实 name/description** 供 strata（不再写死"整体规划"）；LLM 消费的 `tools[]`/`skills_prompt`/`assets` 注入 `PhaseDef`。
- **职责分层**：sm 是图书馆——只按相位意图返回策略/工具，不感知、不维护 pk 的状态（详见 `sm-phase-requirements_zh.md`）。

---

## 二、运行时体系

### 2.1 六边形架构

```
phase_kernel/
  core/        # 通用核：models / gates / actions / orchestrator / decide_kind / fractal（零 tc/FastAPI import）
  ports/       # 6 个抽象 Protocol：Executor / Planner / Gate / Store / ToolCatalog / ArtifactStore（零实现）
  adapters/    # tc_executor / tc_planner / sqlite_store / mechanical_planner / strata_matcher / llm_gate / local_executor / artifact_store
  serve/       # 折叠态门面：BaseHTTPRequestHandler，tc-phase;run 单指令（入口别名，内部归一化为 phase;）+ Service-token + /health + /schema + /packets
  __init__.py  # 公开 API 重导出（双形态）
js/            # core.mjs（同构核）+ server_node.mjs + worker.mjs(CF/D1) + test_core.mjs + test_fractal.mjs + smoke_node.mjs
tests/         # run_all.py + 15 个 test_*.py（mock 闭环统一回归）
```

- **纪律**：`core/` 与 `ports/` 零外部依赖（仅标准库 + 自身）；所有 tc/strata/LLM 差异全在 `adapters/`。
- **端口契约**（`ports/__init__.py`；Phase 重构 P1/P3 增推理缝 + sm 缝）：

```python
class Executor(Protocol):       # execute(phase, context) → PhaseResult；poll(task_id) → PhaseResult（长任务）
class Planner(Protocol):        # plan(goal_repr, context) → PhasePlan；regenerate(phase, feedback) → PhasePlan
class Gate(Protocol):           # decide(phase, result) → bool
class Store(Protocol):          # save(session)；load(pipeline_id)；restore(pipeline_id, session_id=None)
class ToolCatalog(Protocol):    # list_for_phase(phase) → list（可选）
class ArtifactStore(Protocol):  # store(pipeline_id, ref, data) → url；fetch(ref) → dict；transfer(pipeline_id, payload) → dict
class InferenceSeam(Protocol):  # infer(context_patch) → inference_result（推理缝；P1）
class SmSeam(Protocol):         # query(sm_request) → str|None（sm 缝；P3）
```

**实现注**：`ArtifactStore`（产物数据面端口）与 `Store`（session 持久化）**分离**——前者管相位产物，后者管会话快照。**Phase 重构四缝**：`InferenceSeam`（推理缝，pk 让出上下文组装 + 推理裁决权，`context_patch`→`inference_result`）、`SmSeam`（sm 缝，pk 经缝取 strata 策略内容，phase_path 定位）。`PhaseDef` 增 `path` 字段（树路径，`pipeline_id + phase_path` 为四缝共用寻址坐标）。

### 2.2 双后端（Python + JS 同构）

- `js/core.mjs`：Python core 的**逐函数同构**移植（状态机 + 三闸 + 四 action + 分形），**零平台 API**（不 import `node:` / 不碰 D1 / 不 fetch）。
- `js/server_node.mjs`：node 同构服务（纯 `node:http`），与 Python `serve/server.py` 同构，`:28050`。
- `js/worker.mjs`：Cloudflare Worker 形态（D1 Store + fetch 穿透），与 node 版共享同一 JS 核。
- **实现注**：JS 机械规划启发式与 Python 一字不差（`["先","再","然后","最后","分","步骤","阶段"]`），双后端行为一致由测试锁死。

### 2.3 双形态（组件化）

- **形态一：独立 serve**——`python -m phase_kernel.serve.server`（或等价入口），折叠态单指令。
- **形态二：组件集成**——上层应用 `from phase_kernel import PhaseReasoningEngine` 等，用 adapter 装配自己的执行体/规划器后直接驱动；`__init__.py` 公开导出全组件（8 端口 + 适配器 + 核心类），内核与 serve 可剥离。**Phase 重构四缝**：serve 提供四缝默认填缝（llm 推理接收器 / 人闸 HTTP 端点 / sm 默认解析 / 数据面存储），上层经注入替换。

### 2.4 当前形态

- Python：`python tests/run_all.py` → 当前 17/18 全绿（唯一红为 P3 纠偏后待 P6 重构的白盒 `test_phase5_strata.py`；P6 统一重构测试模式后全量回归）。
- node：核心同构 + 冒烟通过。
- **未验面**：CF Worker（`worker.mjs`）未实跑（本地无 wrangler）；live tc 联调未做（`LocalExecutor` 进程内闭环）；`g` 未实测标定；dsh 内化未立项（附录 C）。

---

## 三、分形演进（相位运行时自决）

> 这是 phase-kernel 的核心演进（设计稿 `DESIGN_phase_fractal_zh.md`）：相位从「预先切好的扁平单层」升级为「**运行时自决的分形结构**」。

### 3.1 节点 vs 叶子

- **NODE**（`PhaseKind.NODE`）：抽象节点——继续分形，持有 `children`（子相位），无 steps。
- **LEAF**（`PhaseKind.LEAF`）：可落地叶子——落到 path 执行，持有 steps，无 children。
- **默认 LEAF**：旧扁平数据反序列化后仍是叶子，向后兼容。

### 3.2 `decide_kind` 契约闭合判据（`core/decide_kind.py`）

`decide_kind(phase, contract, depth, max_phase_depth) -> PhaseKind`——**可机械判定、不依赖 LLM**：

| 判据 | 真相源 | 闭合条件 |
|---|---|---|
| 输入契约 | `contract.input_schema.properties/type` | 有明确的输入参数定义 |
| 输出信封 | `contract.output_schema.type/properties` | 有明确的输出类型/字段 |
| 可固化产物 | `steps[].output_as` / `steps[].action` + `endpoint_hint` | 有明确的产物固化点 |

- 三项全闭合 → `LEAF`；否则 → `NODE`（还需分形探索）。
- **有界性**：深度超 `max_phase_depth`（默认 2）→ 强制 `LEAF`，不无限分形。
- **`mode` 请求级覆写（链式模式）**：`max_phase_depth` 是引擎级配置；请求级 `mode=chain` 把"子相位深度上限"钳制为 1（`effective_max`：`mode==chain and depth>=1 → 1`，根 `depth==0` 仍用配置值正常分形），实现"根正常分形、子相位触顶 LEAF 直出 path"。复用 `decide_kind` 既有的 `depth >= max → LEAF` 边界，不改判据逻辑，仅改入参来源（详见 `docs/mode-structural-vs-chain_zh.md`）。`mode` 默认 `structural`（= 不覆写，全树用配置值）。
- **`tools_to_contract`**：sm `tools[]` → contract 的纯数据转换（软依赖，sm 不可用回退 path 声明字段）。

### 3.3 分形展开（`core/orchestrator.py._expand_fractal`）

`_start_planning` 对 planner 产出的每个相位调 `_expand_fractal`，用 `decide_kind` 复核 kind 并注入 `depth`：

- **显式 NODE**（`kind==NODE` 或带 children）→ `decide_kind` 复核：判 NODE 且未触顶 → 下钻生成 children（递归 `depth+1`）；触顶/契约闭合 → LEAF。
- **显式 LEAF** → 记 `depth`，**不主动把 LEAF 变 NODE**（决定权在 planner，向后兼容）。
- **非闭集兜底**：`decide_kind` 判 NODE 但下钻无素材（planner 无法产 children）→ 强制 LEAF，避免意外递归失控。

`PhaseDef.depth`：分形深度（从根累计，触顶二选一判断依据）。

### 3.4 树展平为链（`_next_leaf`）

`_next_leaf` 用 `fractal.iter_phases` 深度优先遍历相位树，跳过已终态（completed/failed/aborted）与 NODE，返回第一个待执行 LEAF：

- 全 LEAF 扁平树 → 天然退化为线性顺序（向后兼容）。
- NODE/children 树 → 正确下钻到子 LEAF。
- **规划失败/降级出口**：遇到 NODE 无 children（无法下钻的异常态，如持久化加载的残缺树）→ 视为不可执行抽象点，跳过并累计 `session._planning_blocked`；若全树皆为此 → 返回 None，上层触发 complete/降级，避免死循环。

### 3.5 栈式递归执行（`core/fractal.py`）

- **`iter_phases`**：深度优先遍历相位树，产出 `(path, phase)` 执行序列——NODE 下钻到 children、LEAF 产出自身。
- **相位栈**：`PipelineSession.phase_stack` 记录递归路径；`push`/`pop` 维护下钻/回栈。
- **栈上回退**：`rollback_stack(session, path, index)` 只重跑目标子树，不影响兄弟节点。
- **反向信号**：`should_reassess(result)`——LEAF 执行出大量 `delegated`/`partial` → 重估为 NODE（判错可纠正，认可 LLM 第一次判可能错）。

### 3.6 信任链（本设计的根）

> **tc 信 LLM → tc调用者 信 tc → tc调用者 信 LLM。** 所有机制的目的不是"判定得准"，而是"**错误可见、可纠正、可回退、可覆盖**"。

- 可机械判定是为了**错误可见**（判定独立于制造错误的 LLM），不是判定得准。
- 反向信号是**核心判据**（判错可纠正与契约闭合并列），不是辅助。
- 默认 LEAF 是为了**不把无限分形的负担压给会犯错的 LLM**。

---

## 四、消费侧——折叠态门面

### 4.1 折叠态：对外只一个指令

**`tc-phase;run,<目标>[,<lang>][,<mode>]`**——一个指令吃目标吐三字段信封；展开态五指令（`phase;enter/state/action/rollback/list`）降级为 run 内部 async 协议流，**不暴露为端口**：

- `tc-phase` 是**对外句柄别名**（P0）：进入 `parse_cli` 后归一化为内部 `phase;`，之后所有内部逻辑（engine/orchestrator/decide_kind）仍是 `phase`，只改入口句柄、不改内部模型名。命名上 `tc-` 标明"tc 生态上游编排组件"（名实匹配，避免 `phase` 过大压不住）。
- `<mode>`（P1，可选，默认 `structural`）：`structural`=正常分形下钻；`chain`=链式模式——根相位正常分形出多相位，子相位直接 LEAF 出 path、无下钻（详见 `docs/mode-structural-vs-chain_zh.md`）。

> 真正自包含的机制，对外收敛到最小表面积、对内才展开全部复杂度。

### 4.2 信封与错误码

- 响应严格走 `{rst_types, rst_data, rst_err}`；`rst_data` 只用受控字段（相位面投影摘要，**不吐内部 `PipelineSession`**）。
- 错误码实际用到 4 个（`ERR_NOT_FOUND` / `SERVICE_DENIED` / `INVALID_PARAMS` / `ERR_EXECUTION`），是 textcli-core 6 码闭集的**子集**——相位服务不跨节点路由、无凭据授权语义，用不到 `ERR_ROUTING`/`ACCESS_DENIED`。
- 鉴权：`Service-token` 头，缺失/不匹配 → `SERVICE_DENIED`（HTTP 恒 200，业务语义走 `rst_err`）。
- Gate 拒绝理由经 `rst_data.reason` 单行结构化透出，**不造 `GateVerdict` 类型**。

### 4.3 后端契约

`/health` 的 `mechanism:["async","discovery"]` 是相位对后端的契约声明面：

> 相位可编排后端 ≡ 该 tc 运行时声明实现了：**async**（异步五态 + tasks/{id} 轮询 + task;cancel 中止）、**discovery**（text-cli;query 可内省能力切片）。

后端未声明 `async`/`discovery` 时，机制仍推进任务但**数学保证失效**，应显式标记 `degraded_mode=True`。

---

## 五、标准运行时——PhaseReasoningEngine

### 5.1 编排循环

```python
class PhaseReasoningEngine:
    def __init__(self, executor, planner, store=None, catalog=None, gate=None,
                 degraded_mode=False, max_phase_depth=2, max_rollback_iters=1,
                 review_enabled=False, review_llm=None): ...
    async def handle(self, user_text, synth_pipeline=None, session_id=None, user_id=None) -> dict:
```

对外单入口 `handle()`，返回含 `pipeline_id/step/phase_index/phase_total/phase_path/artifact_ref` 的驱动信封（Phase 重构 P0 补 `phase_path` 树路径，与 `phase_index` 并存；`phase_index` 保留为兼容显示）。

**新发起（`_start_planning`）**：
```
plan = planner.plan(goal) → 逐相位 _expand_fractal（decide_kind 复核 + depth 注入 + 触顶）
  → PipelineSession(DRAFT) → 规划产物写入 phase_summaries（第 0 个）
  → STEP awaiting_plan_confirm
```

**回传驱动（`_handle_action` → action 决策点）**：
```
action=confirm（三岔决策点）
  ① DRAFT / 无当前相位 → session.start() → _generate_next_path → awaiting_path_confirm
  ② AWAITING_PATH_CONFIRM → _execute_phase（pending 则停 EXECUTING 等 check_result）
  ③ AWAITING_APPROVAL → approve_phase → _next_leaf → 下一相位 path / session.complete() → completed

action=reject → _reject：
  审批闸驳回（AWAITING_APPROVAL）→ reject_phase + 相位回 AWAITING_PATH_CONFIRM 重试当前相位
  规划级驳回 → _regenerate
action=regenerate / regenerate_with_new_context → 重新规划（pipeline id 不变）
action=abort → session.abort()（终态不可中止）
action=check_result → executor.poll(task_id) → pending 仍停 EXECUTING，否则收口质量闸
```

**推进（`_next_leaf`）**：每相位完成后用 `_next_leaf` 找下一个待执行 LEAF（分形感知），代替旧的 `index+1` 线性推进。

### 5.2 执行与质量闸收口（`_finalize_execution`）

```python
result = await self.executor.execute(phase, {"intent": session.intent})
# except Exception → 后端不可达降级：记 PhaseArtifact(type="error") + STEP_ABORTED（不崩、不挂起）

if result.status == "pending":   # 长任务分级
    session.async_tasks.append({...})
    return ... STEP_EXECUTING + 提示 check_result

passed = await self._quality_passed(phase, result)      # 判定者注入（MechanicalGate / LLMGate）
status = await self.gate_executor.evaluate_quality_gate(session, phase, passed, ...)
# COMPLETED → review 复议（enabled 时）→ 下一相位 / complete
# AWAITING_APPROVAL → 停人审（等 confirm/reject）
# FAILED → _phase_rollback（earliest-close 门控）
```

**review 在质量闸之后、推进之前**：`status == COMPLETED and review_enabled` → `_review_phase`（XML verdict）；`unsatisfied` → 相位内回退；`settled` → 照常推进。**人审闸（闸3）打开时相位停在 `AWAITING_APPROVAL`，不进入 review 分支**。

### 5.3 相位内回退（`_phase_rollback`，earliest-close 门控）

首相位与非首相位**同样**先回退重试（回退计数 < `max_rollback_iters`）；回退**超限后**按位置分叉：

- **首相位（earliest-close 验证点）超限** → 整树最浅终止（验证点反复不通 = 整条路不通，最浅关树最经济）。
- **非首相位超限** → 接受稳定产出放行（settled，信任已尽力，不废整树）并推进到下一 LEAF。

```
if phase.rollback_count < max_rollback_iters:
    phase.rollback_count += 1
    phase.status = AWAITING_PATH_CONFIRM   # 相位内回退：重试当前相位
    session.add_quality_gate(phase.index, "rollback", "retry", ...)
    session.pointer_log.append({"type":"rollback", "phase":phase.index, "count":.., "reason":..})
else:
    if 首相位: 整树最浅终止
    else:      settled 放行 → 下一 LEAF
```

**earliest-close 验证点**：`_verification_phase` = 树中第一个 LEAF（`iter_phases` 顺序）。无论当前执行推进到哪，首相位是整条链能否续上的最早检查点——它失败 = 整条路不通，应最浅终止。

### 5.4 path 组装（L1 解耦的关键）

```python
compiler = getattr(self.executor, "compile_path", None)   # Executor 适配器暴露 compile_path → 用其产物
if callable(compiler):
    try: return compiler(phase)
    except Exception: pass
return {"id": phase.endpoint_hint or "local", "name": phase.name,
        "steps": phase.steps or [{"action": "execute", "description": phase.description}]}
```

**实现注**：kernel 只守「相位树形状」，「怎么切」交给 Planner（`goal_repr` 放宽为 Any）；`mode` 由 Planner 定义，kernel 不解释；`endpoint_hint` 仅作路由提示。叶子 path 由 Executor 适配器译成真实 step 信封，kernel 不解释执行细节。

### 5.5 状态机模型（core/models.py）

- `PhaseStatus`：draft / pending / awaiting_plan_confirm / awaiting_path_confirm / running / awaiting_approval / completed / aborted / failed。
- `PhaseKind`：node / leaf（分形演进，默认 leaf 向后兼容）。
- `PhaseDef`：index/name/description/mode/gates/endpoint_hint/status/steps/kind/children + **depth**（分形深度）+ **rollback_count**（相位内回退计数）+ **tools/skills_prompt/assets**（真实相位，strata 注入）。
- `PipelineSession`：跨项目单一真相来源，含 `phase_summaries` / `checkpoint_index` / `phase_stack` / `rollback_to(index)` / **`pointer_log`**（指针日志：path 指令 ID / 远端 URL / pk URL / review verdict / 回退计数）。
- `PhaseResult.status` **强制闭集**（`success/failed/pending`，构造即校验）；`from_envelope` 消费三字段信封：

```python
if tc_status == "pending":  return cls("pending", data=rst_data, task_id=...)
if tc_status == "failed" or rst_err:  return cls("failed", data=rst_data, error=...)
return cls("success", data=rst_data)   # 默认视为成功
```

---

## 六、宿主执行——端口与适配器

### 6.1 适配器八件（差异全在这）

| 适配器 | 端口 | 职责 |
|---|---|---|
| `TCExecutor` | Executor | 封装 tc 运行时（urllib call/discover/poll）→ `AI:text-cli;path,{...}` 一维契约；`compile_path` 填 steps；`poll` 走五态 |
| `TCPlanner` | Planner | 焊死 `_PLANNING_SYSTEM_PROMPT` + LLM → 规划；LLM 缺失/失败回落默认 3 相位 |
| `MechanicalPlanner` | Planner | 纯机械极小规划（零 LLM），启发式拆相位（"先/再/然后/最后/分/步骤/阶段"）——P_ctrl 不依赖 LLM 的底线 |
| `StrataMatcher` | Planner | strata-match 为 prompt 真相源 + 两级回退 + 真实相位意图（PhaseDef name/description）+ 消费 tools[]/skills_prompt/assets |
| `LLMGate` | Gate | LLM 自由文本强制映射回闭集 bool；不可用回落 `MechanicalGate` |
| `SqliteStore` | Store | 独立部署形态：`pipelines` 表 `INSERT OR REPLACE` 存 `session.to_dict()` JSON（标准库 sqlite3） |
| `LocalExecutor` | Executor | 进程内真执行多步（自包含闭环）；`slow` 演示长任务 pending→poll |
| `InMemoryArtifactStore` | ArtifactStore | 数据面内存实现：`store`/`fetch`/`transfer`（透传/拉取转存分流 + 降级）+ 滚动窗口 + 终态清理 |

### 6.2 规划回退链

```
一级：strata-match 不可用/超时/空 → 默认规划 prompt（仍走 LLM 或机械兜底）
二级：连 LLM 也失败 → 纯机械极小规划（按 endpoint_hint 直发 tc path）
```

### 6.3 数据面（ArtifactStore / /packets 端点）

**职责**：跨相位传递相位产物。`ArtifactStore`（端口）与 `Store`（session 持久化）分离；`InMemoryArtifactStore`（内存实现）满足代码层闭环。

**引擎产物**：`PhaseReasoningEngine` 产生 `artifact_ref` 的多处都经 `_store_artifact` 真正写入 `ArtifactStore`，按 ref 可 `fetch()` 取回。**Phase 重构 P0 升级：ref 定位段改接 `phase_path` 树路径**（`PhaseDef.path`，`-` 连接；无 path 回落扁平 index），四缝共用该寻址坐标：
- `_start_planning` → `art_{pid}_plan`（plan 产物，无 path）；
- `_generate_next_path` → `art_{pid}_path_{phase_path}`（path 产物，如 `art_{pid}_path_0-1`）；
- `_finalize_execution` / `_execute_phase` pending → `art_{pid}_result_{phase_path}`（结果产物，pending 先落 task 占位、完成后覆盖）；
- `_finalize_execution`（summary）→ `art_{pid}_summary_{phase_path}`（Phase 重构 P2.4 summary 级推理产物）。
引擎 `__init__` 新增 `artifact_store` 端口；未注入时 `_store_artifact` 静默跳过（兼容纯 mock 无数据面）。

**透传/转存分流**（`transfer`）：读数据形态——
- `payload` 是 http/https URL **且** `allow_passthrough=True` → 透传（不落盘，返回远端 URL，`passthrough=True`）；
- 否则 → 拉取转存（落盘生成 pk 自有 URL `pk://artifacts/{ref}`，`passthrough=False`）；
- 拉取失败 → 降级直用远端 URL + `degraded=True`。

**数据驻留**：滚动窗口（`max_artifacts`，默认 200，超限淘汰最旧）+ 终态清理（`finalize_pipeline`：整树收束时保留最终产出物表、清理中间产物）。

**serve 端点**：
- `POST /packets/update`：请求体 `{"pipeline_id","data"|"url","media_type"}` → 经 `transfer` 分流 → 返回 `{url, passthrough, degraded}`。
- `GET /packets/artifacts/{ref}`：按 ref 拉取产物 → `{ref, data, media_type}`。

### 6.4 折叠态门面（serve/server.py）

- 纯标准库 `ThreadingHTTPServer`（不引 FastAPI），`/text-cli/cli` + 三字段信封 + `Service-token`。
- `do_POST /text-cli/cli`：鉴权 → `parse_cli` → `_dispatch`（`tc-phase;run,<goal>[,<lang>][,<mode>]` 新发起 / `tc-phase;run,<pipeline_id>,<action>[,<feedback>]` 回传）→ `_to_envelope`（受控相位面：`pending_gate`/`available_actions` 按 step 映射）。`parse_cli` 入口把 `tc-phase;` 归一化为内部 `phase;`，之后逻辑全用 `phase`。
- `do_GET`：`/text-cli/health`（`mechanism:["async","discovery"]` + `degraded_mode`）、`/text-cli/schema`（`PHASE_SCHEMA`：id/type/mechanism/auth/directives/internal_flows）、`/packets/artifacts/{ref}`、`/pipelines/{pid}/phases/{phase_path}/gate`（**人闸只读查询**，与 `_handle_gate` POST 决策对称——复用 `_to_envelope` 受控面，按 `phase_path` 定位相位返回 `status`/`pending_gate`/`available_actions`/`artifact_ref`，只读不落盘，供 gate_manager / 外挂服务查询待闸状态）。
- `build_engine` 装配点：有 `PHASE_TC_URL` → `TCExecutor`+`TCPlanner`；无 → `LocalExecutor`+`MechanicalPlanner`（`no_strata=True` 默认），`degraded_mode=(tc_base_url is None)`。
- 异常映射：`ValueError` → `INVALID_PARAMS`；其它 → `ERR_EXECUTION`（**不泄露堆栈**）。

---

## 七、集成设计（dsh 内化蓝图）

> 依据 `dsh_phase_integration_plan_zh.md`（Phase 0~6 全部 ⏳ 待执行）。本仓库当前与 dsh-tc-runtime **无代码耦合**（不 import dsh 任何东西），以下为已核准的整合形态。

### 7.1 整合形态（ts + js）

**`runtime-phase` 为 TS 薄壳包，`phase-kernel/js/core.mjs` 引擎 vendored 为其内部内核**；`src/core.mjs`（vendored 引擎）+ `src/index.ts`（类型壳）+ `src/bridge.ts`（Cordis 注册/委托）+ `src/ports.ts`。

### 7.2 层叠拓扑

```
dsh（宿主 + agent-loop）
  └─ runtime-phase（相位编排 + 三闸）          ← 新增
       └─ dsh-tc-runtime（tc 执行：沙箱/凭据/审批/环检测/审计）  ← 既有
            └─ text-cli 指令包 → 真实工具
```

- Planner 默认 `MechanicalPlanner`（零 LLM），与 dsh-tc-runtime「部署禁用 llm」姿态一致。
- `phase;run` 经保留域注册（仿 `pro`/`meta`），不污染 `ctx.tools`（红线⑤）。注：此处 `phase` 是**内部保留域**；对外句柄在 P0 改为 `tc-phase`（入口归一化回 `phase`），红线描述的是内部注册名，不变。

### 7.3 红线 7 条保证

| # | 红线 | runtime-phase 保证方式 |
|---|---|---|
| ① | 不侵入 dsh 内核 | 仅增 `runtime-phase` 包 + 根配置 |
| ② | 凭据明文不进 JS 执行环境 | `Executor` 只委托 dsh-tc-runtime dispatch |
| ③ | 沙箱默认拒绝 | 每步经 `runtime-path`/`guardDispatch`，fail-closed |
| ④ | 协议闭集 | 复用 `runtime-contract` 信封（6 码），`mapSignal` 未知回退 `ERR_EXECUTION` |
| ⑤ | 保留域不污染 `ctx.tools` | `phase;run` 经保留域注册（仿 `pro`/`meta`） |
| ⑥ | 审批 answerer 归属过滤 | 人闸 → `runtime-approval`；`req.agent` 存在 → `next()` 委托 |
| ⑦ | tc 审计独立 JSONL | 每相位/每 step 经 `runtime-audit`（traceId+seq），不写 `ctx.sessions` |

契约测试断言：`phase.ok(d) === runtimeContract.ok(d)`（信封同源 `textcli-core`，零重写）。

---

## 附录 A：关键文件索引（基于实现）

| 主题 | 文件 |
|---|---|
| 数据模型（PhaseStatus/PhaseKind/PhaseDef/PhasePlan/PipelineSession/PhaseResult/PhaseArtifact） | `phase_kernel/core/models.py` |
| 三闸状态操作 + 机械判定 | `phase_kernel/core/gates.py` |
| 契约闭合判据 + tools_to_contract | `phase_kernel/core/decide_kind.py` |
| 分形遍历 / 栈 / 回退 / 反向信号 | `phase_kernel/core/fractal.py` |
| action 枚举 | `phase_kernel/core/actions.py` |
| 状态机主链（PhaseReasoningEngine） | `phase_kernel/core/orchestrator.py`（包根重导出 `phase_kernel/orchestrator.py`） |
| 六端口契约 | `phase_kernel/ports/__init__.py` |
| 适配器八件 | `phase_kernel/adapters/*.py`（含 `artifact_store.py`） |
| 折叠态门面 + 数据面端点 | `phase_kernel/serve/server.py` |
| 公开 API（双形态重导出） | `phase_kernel/__init__.py` |
| JS 同构核 / node 服务 / CF Worker | `js/{core,server_node,worker}.mjs` |
| 测试 | `tests/{run_all,test_*}.py`（15 个）、`js/{test_core,test_fractal,smoke_node}.mjs` |



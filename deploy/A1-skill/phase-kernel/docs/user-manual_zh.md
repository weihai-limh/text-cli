# phase-kernel 使用手册

> 本手册面向 **phase-kernel 的操作者 / Agent / 集成方**——你通过折叠态指令驱动相位推理时，读这一份即可。
> 手册随 phase-kernel 仓库分发。修订：2026-08-26。
> 本仓库是「相位推理机制」的独立自包含实现（Python + JS 双后端），协议部分与 text-cli 一致（信封三字段、错误码闭集）。
> 风格参考：`dsh-tc-runtime/docs/user-manual_zh.md`。

---

## 零、概念速览

phase-kernel 是**相位推理机制**的独立实现：把「完成一个任务」组织为「一系列在重组上下文中的推理」，单次推理只承担一小段认知负载，任意两次推理之间可重组纠错。

```
  用户目标 ──▶ planner.plan ──▶ decide_kind 判定 ──▶ 相位树（NODE/LEAF）
                          （depth 注入 + 触顶强制 LEAF）        │
   confirm 规划 ──▶ earliest-close 门控（首相位验证点优先）──▶ 逐 LEAF 执行
                          │
              ├── 质量闸（闭集比对，不调 LLM）          ┌── 能力层（机器内部做对）
              ├── review 复议（XML verdict，review 开启时）┘
              └── 失败 → 相位内回退重试（max_rollback_iters=1，超限按位置分叉）
                          │
              ├── 【责任闸】人闸 require_human_approval（awaiting_approval：
              │      人对该相位产出拍板 confirm/reject，confirm → 固化，
              │      reject → 回退重跑当前相位；默认关，与信任 LLM 正交、不取消）
                          │
                   全部 LEAF 固化 ──▶ completed（checkpoint 逐相位推进）
```

| 名词 | 含义 |
|------|------|
| **相位（Phase）** | 一次在重组上下文中的推理（`PhaseDef`：index/name/description/mode/gates/endpoint_hint/steps/kind/children） |
| **节点 / 叶子** | `PhaseKind.NODE` 继续分形（有 children）；`PhaseKind.LEAF` 落到 path 执行（有 steps）；默认 LEAF 向后兼容 |
| **三闸** | 闸2 `allow_path_edit`（进 RUNNING 前）、闸3 `require_human_approval`（执行后，**责任闸**）、质量闸（结果判定） |
| **信任 vs 责任** | **能力层（信任）**：LLM 单步判断 + 机器代执行 + 有界回退；**责任层（人闸，闸3）**：每个相位最终产出由人拍板负责。人闸是**上层**——信任 LLM 不取消人闸，任何机器机制（质量闸 / review / reflection）都不替代人闸 |
| **检查点（checkpoint）** | 每相位成功固化后推进；驳回/重试回退到检查点——**只重跑当前相位** |
| **折叠态** | 对外只暴露 `tc-phase;run` 单指令（入口句柄别名，P0；内部等价前缀 `phase;run` 仍可用）；展开态五指令（enter/state/action/rollback/list）降级为 run 内部协议流 |
| **降级模式** | `degraded_mode=True` = 后端未满足 async/discovery 契约，机制仍推进但 P_ctrl 数学保证失效 |

**关键设计**：`core/` 与 `ports/` 零外部依赖；所有 tc/strata/LLM 差异在 `adapters/`；机械规划器（`MechanicalPlanner`）**零 LLM 兜底**，P_ctrl 不依赖 LLM。

---

## 一、部署

### 1.1 Python 服务（独立部署形态）

```bash
# 默认：LocalExecutor + MechanicalPlanner（自包含，零外部依赖）
PHASE_SERVICE_TOKEN=phase-secret PHASE_NO_STRATA=1 python -m phase_kernel.serve.server
# 监听 0.0.0.0:28050（text-cli 协议 Service 档约定端口）

# 服务级默认语言（i18n）：请求未带 <lang> 时，content/reason 用 en（缺省 zh）
PHASE_LANG=en PHASE_SERVICE_TOKEN=phase-secret python -m phase_kernel.serve.server

# 接入真实 tc 运行时（TCExecutor + TCPlanner）——PHASE_TC_URL 指向真实 tc 运行时
# Service 的地址（独立部署，协议 Service 档同为 28050；跨终端可达，非本机回环）
PHASE_TC_URL=http://<tc-运行时>:28050 PHASE_SERVICE_TOKEN=phase-secret python -m phase_kernel.serve.server
```

### 1.2 node 同构服务

```bash
node js/server_node.mjs        # :28050（纯 node:http，协议与 Python 版一致）
```

### 1.3 Cloudflare Worker 形态

`js/worker.mjs` 为 CF 形态忠实实现（D1 `pipelines` 表 + fetch 穿透），部署时配合 `wrangler.toml` 绑定 D1 数据库、`env.PHASE_SERVICE_TOKEN` 鉴权。**本地无 wrangler 未实跑**，行为与 node 版共享同一 JS 核。

### 1.4 验证（mock 闭环，不接真实 LLM）

```bash
python tests/run_all.py --js            # 统一回归：全部 Python 测试 + JS 核心同构（17/17）
python tests/test_engine.py             # 8 流转（状态机等价性）
python tests/test_serve.py              # 3 折叠态服务冒烟
python tests/test_fractal_iter.py       # 分形链路激活（iter_phases 展平）
python tests/test_phase2_depth_fractal.py  # decide_kind depth + 触顶二选一
python tests/test_phase3_gate.py        # earliest-close 门控 + 相位内回退
python tests/test_phase4_packets.py     # 数据面 ArtifactStore + /packets
python tests/test_phase5_strata.py      # 真实相位意图
python tests/test_phase6_dual_form.py   # 双形态固化
python tests/test_phase7_exec_service.py  # 执行相位服务（review XML verdict）
node js/test_core.mjs                   # 核心同构
node js/smoke_node.mjs                  # HTTP 冒烟
```

---

## 二、指令表面

### 2.1 折叠态单指令：`tc-phase;run`

> 对外标准句柄为 `tc-phase`（P0 入口句柄别名）；`parse_cli` 同时接受内部等价前缀 `phase`（如 `AI:phase;run,...` 与 `AI:tc-phase;run,...` 解析结果一致），下文示例统一用 `tc-phase`。`<mode>` 维度（默认 `structural`，可选 `chain` 链式模式）见附录 A。

**新发起**：

```bash
curl http://127.0.0.1:28050/text-cli/cli \
  -H "Content-Type: application/json" -H "Service-token: phase-secret" \
  -d '{"prompt":"AI:tc-phase;run,写一份季度报告"}'
```

响应（受控相位面，不吐内部会话）：

```json
{"rst_types":"text","rst_data":{
  "content":"相位规划如下（共 3 个相位）：\n需求分析（分析用户需求）；数据收集（收集所需数据）；撰写报告（撰写季度报告）\n\n请确认（回传 action=confirm）或提出修改意见（action=reject/regenerate）。",
  "pipeline_id":"p1","phase_index":0,"phase_total":3,
  "status":"awaiting_plan_confirm","pending_gate":"plan_confirm",
  "available_actions":["confirm","reject","regenerate"],"artifact_ref":"art_p1_plan"
},"rst_err":""}
```

**回传驱动**（带 pipeline_id + action）：

```bash
curl ... -d '{"prompt":"AI:tc-phase;run,p1,confirm"}'
curl ... -d '{"prompt":"AI:tc-phase;run,p1,confirm"}'        # 再 confirm：path 确认 → 执行
curl ... -d '{"prompt":"AI:tc-phase;run,p1,reject,<反馈>"}'   # 驳回 → 重跑当前相位
curl ... -d '{"prompt":"AI:tc-phase;run,p1,regenerate,<反馈>"}' # 重新规划（pipeline id 不变）
curl ... -d '{"prompt":"AI:tc-phase;run,p1,abort"}'
curl ... -d '{"prompt":"AI:tc-phase;run,p1,check_result"}'   # 长任务轮询（executing 态提示）
```

### 2.2 状态与可行动作

| status | 含义 | 可行动作 |
|--------|------|---------|
| `awaiting_plan_confirm` | 规划待确认 | `confirm` / `reject` / `regenerate` |
| `awaiting_path_confirm` | path 待确认（闸2 ON） | `confirm` / `reject` |
| `awaiting_approval` | 执行完待人审批（闸3 ON，责任闸：人对该相位产出负责） | `confirm` / `reject` |
| `executing` | 执行中（含长任务 pending） | `check_result` / `abort` |
| `completed` | 全部相位固化 | — |
| `aborted` | 中止/后端不可达降级 | — |

> 未知 action → content「未知 action: ...」，状态机不推进；不存在的 pipeline → content「不存在」+ step `aborted`。

### 2.3 分形执行（节点相位 + 门控推进）

**NODE/LEAF 判定**：规划后引擎经 `decide_kind` 判定每相位是节点（NODE，继续下钻）还是叶子（LEAF，落到 path 执行），并注入 `depth`——触顶（`depth==max_phase_depth`）强制 LEAF，不无限分形。

**earliest-close 门控**：执行沿相位树展平为一维链逐 LEAF 推进，**首相位是验证点，优先执行**；前一棒未完成不 dispatch 下一棒。首相位失败（回退超限）→ 整树最浅终止；非首相位失败 → 相位内回退重试（`max_rollback_iters`，超限接受稳定产出放行）。

**review 复议自评**（`review` 开启时）：执行结果回填后，引擎让 LLM 返回约定 XML verdict（`<phase_verdict>satisfied|unsatisfied|settled</phase_verdict>`），机械闸纯字符串匹配闭集判定——`unsatisfied` → 相位内回退；匹配不到默认 `satisfied`（信任优先，关则不复议、直接走机械门控）。

**判错可纠正**：子层执行中若出现大量 `delegated`/`partial`，会触发反向信号——将该子相位重估为节点再分形。

### 2.4 后端契约（集成方注意）

`GET /text-cli/health` 声明 `mechanism:["async","discovery"]`——相位可编排后端 ≡ 该 tc 运行时实现了：

- **async**：异步五态 + tasks/{id} 轮询 + task;cancel 中止；
- **discovery**：text-cli;query 可内省能力切片。

后端未满足时任务仍推进，但应接受 `degraded_mode=True`（P_ctrl 数学保证失效）。

---

## 三、协议与信封

所有响应统一为三字段信封（与 text-cli 一致）：

```json
{"rst_types":"text","rst_data":{...},"rst_err":""}
```

- `rst_types`：当前恒为 `text`。
- `rst_data`：**受控相位面**（`content`/`pipeline_id`/`phase_index`/`phase_total`/`status`/`pending_gate`/`available_actions`/`artifact_ref`），不吐内部 `PipelineSession` 对象。
- `rst_err`：空串 = 成功；非空 = 失败（闭集码）。

**错误码（4 码子集，textcli-core 6 码闭集的子集）**：

| 错误码 | 触发场景 |
|--------|---------|
| `ERR_NOT_FOUND` | 路径不存在（`/text-cli/xxx`） |
| `SERVICE_DENIED` | `Service-token` 缺失/不匹配 |
| `INVALID_PARAMS` | `tc-phase;run` 指令解析失败（参数非法，含非法 `<mode>`） |
| `ERR_EXECUTION` | 引擎内部异常（不泄露堆栈） |

**i18n**：`tc-phase;run,<目标>[,<lang>][,<mode>]`——`lang`（zh/en）驱动状态文本与 reason 本地化；机制契约（端口名/模型字段/错误码/机制词表）默认英语。`lang` 缺省时回落**服务级默认** `PHASE_LANG`（env，默认 `zh`，见 §4.1）。`<mode>` 仅 `structural`（默认）/`chain`，非法值抛 `INVALID_PARAMS`。

---

## 四、配置

### 4.1 环境变量（serve 门面）

| 变量 | 默认 | 说明 |
|------|------|------|
| `PHASE_SERVICE_TOKEN` | `phase-secret` | Service-token（鉴权；生产必换） |
| `PHASE_TC_URL` | 空 | 接入真实 tc 运行时 → `TCExecutor` + `TCPlanner`；空 → `LocalExecutor` + `MechanicalPlanner`（自包含） |
| `PHASE_DB` | `phase.db` | SQLite 持久化路径（`SqliteStore`） |
| `PHASE_NO_STRATA` | `1` | 非 `0` 时跳过 strata-match（直走两级回退） |
| `PHASE_LANG` | `zh` | 服务级默认语言（`zh`/`en`，i18n）；请求未带 `<lang>` 时回落此值驱动 content/reason 本地化 |

### 4.2 相位配置（代码注入）

| 项 | 默认 | 说明 |
|------|------|------|
| `PhaseGates.allow_path_edit` | `false` | 闸2：进 RUNNING 前是否等人确认 path |
| `PhaseGates.require_human_approval` | `false` | 闸3（**责任闸**）：执行后是否等人审批——人作为最终责任主体为相位产出负责；**与信任 LLM 无关，不因"信任"而省略，也不被 review/质量闸替代** |
| `PhaseGates.quality_check` | `true` | 质量闸开关 |
| `PhaseGates.gate_reliability` | `1.0` | 闸可靠性（`MechanicalGate=1.0`；`LLMGate=0.9` 写入审计；真实值待实测标定） |
| `endpoint_hint` | 无 | 路由提示（phase 执行的落点） |
| `kind` / `children` | `leaf` / 无 | 分形：节点持有 children、叶子持有 steps；默认 leaf 向后兼容 |
| `max_phase_depth` | `2` | 分形递归深度上限（超限强制叶子，不无限分形） |
| `max_rollback_iters` | `1` | 相位内回退上限（真跑 path 代价重；超限首相位最浅终止 / 非首相位 settled） |
| `review`（`review_enabled`） | `false` | 结果复议自评（XML verdict）；关则不复议、直接走机械门控 |
| `tools` / `skills_prompt` / `assets` | 空 | 相位可用工具切片 / 技能提示 / 资产（strata 消费，供相位模板注入） |

### 4.3 strata-match（可选）

`StrataMatcher(base_url=..., llm=..., no_strata=False)`：`POST {base_url}/api/v1/query` 取规划 prompt 与工具切片（`prompt_cn`/`prompt` 按 lang 取）；不可用/超时/空 → 默认规划 prompt；连 LLM 也失败 → 纯机械极小规划。sm 是图书馆——只按意图返回，不感知 pk 状态。

---

## 五、红线与安全

| # | 红线 | 操作者可见表现 |
|:---:|------|------|
| ① | 不侵入 dsh 内核 | `core/`+`ports/` 零外部依赖；集成时仅增 `runtime-phase` 包 |
| ② | 凭据明文不进 JS 执行环境 | `Executor` 只委托 tc 运行时 dispatch，不接触凭据 |
| ③ | 沙箱默认拒绝 | 每步经 `runtime-path`/`guardDispatch`，fail-closed |
| ④ | 协议闭集 | 信封 4 码子集；未知码兜底 `ERR_EXECUTION`，不静默放行 |
| ⑤ | 保留域不污染 `ctx.tools` | 集成时 `phase;run` 经保留域注册（仿 pro/meta；对外句柄为 `tc-phase`，入口归一化回 `phase`，红线描述内部注册名不变） |
| ⑥ | 审批归属过滤 | 人闸委托 `runtime-approval`；`req.agent` 存在 → 委托不替决策 |
| ⑦ | 审计独立 | 每相位/每 step 走 `runtime-audit`（traceId+seq），不写 `ctx.sessions` |

**兜底原则**：任何未预见失败走 `ERR_EXECUTION`；后端不可达降级（不崩、不挂起）；`PhaseResult.status` 构造即强制闭集。

---

## 附录

### A. 指令速查

| 形态 | 示例 |
|------|------|
| 新发起（structural，默认） | `AI:tc-phase;run,写一份季度报告` |
| 带语言 | `AI:tc-phase;run,写一份季度报告,en` |
| 链式模式（chain） | `AI:tc-phase;run,写一份季度报告,zh,chain` |
| 确认规划 | `AI:tc-phase;run,p1,confirm` |
| 驳回重跑 | `AI:tc-phase;run,p1,reject,缺少数据支撑` |
| 重新规划 | `AI:tc-phase;run,p1,regenerate,预算需细化` |
| 中止 | `AI:tc-phase;run,p1,abort` |
| 长任务轮询 | `AI:tc-phase;run,p1,check_result` |

> **`<mode>` 维度（P1，可选，默认 `structural`）**：`structural`=正常分形下钻（多相位层层展开）；`chain`=链式模式——根相位正常分形出多相位，但子相位直接 LEAF 出 path、不再下钻（适合"一次性把整条路径铺出来"的场景）。`INVALID_PARAMS` 会在 `<mode>` 取非 `structural`/`chain` 值时抛出。
>
> **句柄别名（P0）**：对外标准句柄为 `tc-phase`；`parse_cli` 同时接受内部等价前缀 `phase`（如 `AI:phase;run,...` 与 `AI:tc-phase;run,...` 解析结果一致）。

### B. 错误码速查

| 错误码 | 含义 | 常见场景 |
|--------|------|---------|
| `ERR_NOT_FOUND` | 路径不存在 | 错误端点 |
| `SERVICE_DENIED` | 鉴权失败 | 无 token / token 不符 |
| `INVALID_PARAMS` | 参数非法 | `tc-phase;run` 解析失败（含非法 `<mode>`） |
| `ERR_EXECUTION` | 引擎异常 | 后端不可达 / 内部错误 |

### C. 端点 / 环境变量

| 项 | 说明 |
|------|------|
| `POST /text-cli/cli` | 折叠态指令入口（body `{"prompt":"AI:tc-phase;run,..."}`） |
| `GET /text-cli/health` | `mechanism:["async","discovery"]` + `degraded_mode` |
| `GET /text-cli/schema` | 相位服务 schema（id/type/mechanism/auth/directives/internal_flows） |
| `POST /packets/update` | 数据面：产物写入（叶子 path 注入数据面 URL；`{pipeline_id, data|url, media_type}`） |
| `GET /packets/artifacts/{ref}` | 数据面：拉取产物（ArtifactStore，pk://artifacts/{ref}） |
| `GET /pipelines/{pid}/phases/{phase_path}/gate` | 人闸只读查询（`0-1` 定位相位；返回 `status`/`pending_gate`/`available_actions`/`artifact_ref`） |
| `POST /pipelines/{pid}/phases/{phase_path}/gate` | 人闸决策（body `{"verdict":"approve"\|"retry"\|"abort_tree","feedback"?:str}`） |
| `PHASE_SERVICE_TOKEN` / `PHASE_TC_URL` / `PHASE_DB` / `PHASE_NO_STRATA` / `PHASE_LANG` | 见 §四 |

**双形态**（Phase 6）：形态一独立 serve（`python -m phase_kernel.serve.server`）；形态二组件集成（`from phase_kernel import PhaseReasoningEngine` + 装配自己的 executor/planner，sl 只改 import 不碰内核）。

### D. 构建 / 验证命令

```bash
python tests/run_all.py --js           # 统一回归（mock 闭环，17/17）
node js/test_core.mjs && node js/smoke_node.mjs
```

> 当前进度（2026-08-26）：Phase 1–8 已完成，**代码层功能闭环**（mock 验证，不接真实 LLM）——
> 分形链路激活（iter_phases）/ decide_kind depth+触顶 / earliest-close 门控 / 数据面 /packets /
> **artifact_ref 数据面闭环（纠偏-001：引擎 plan/path/result 产物经 ArtifactStore 可 fetch 取回）**/
> 真实相位意图 / 双形态 / 执行相位服务（review XML verdict）/ **i18n（`i18n/*.json` + `core/i18n.py`
> 加载器 + `handle(lang=)` + `PHASE_LANG` 服务级默认；zh/en 驱动 content/reason 本地化，机制契约恒英语）**/
> 全套测试。CF Worker 未实跑（无 wrangler）；live tc 联调待补；**真实 LLM 推理实证留待发布后
> 集成阶段**；dsh 内化待立项（见 `docs/design_zh.md` 附录 C）。

# 基于text-cli的DeepSeek Harness整合示例

> 源码位置：
> - 桥：`src/skeleton/bypass-service/dsh/dsh-tc-bridge/`（五个工具：call_tc / wait_tc / run_tc_js / tool_avatar / find_tc）
> - 运行时：`src/skeleton/bypass-service/dsh/dsh-tc-runtime/`（15 个 runtime-* 包）


---

## 第一章 dsh：everything is a plugin 的自洽 agent

dsh（DeepSeek Harness）是本文的第一个主角。这一章先把它讲清楚——它是谁、靠什么世界观运转、有哪些能力、为什么称得上"深"。理解了它，后面三章的"整合"才有落点。

### 1.1 一句话定位

dsh 是一个**开源 Agent 运行时**。官方公式：

> **Model + Harness = Agent**

模型是大脑，Harness 负责把"模型、工具、工作区、权限、会话记忆、任务循环"串成一个能干活的主体。它和 Claude Code / Codex 同赛道，但定位更靠下：**可配置、可重配置的 agent runtime environment**——不是"一个编程工具"，而是"一个可以长出任何 agent 的骨架"。

它最显著的世界观只有一句话：

> **Everything is a plugin（一切皆插件）。**

没有特权内核——bash 是普通插件，模型适配器是插件，连 agent loop 本身都是可替换的插件。扩展永远靠"在旁边挂一个插件"，不靠"改内核"；卸载即回收，不留残余。

### 1.2 世界观：三条铁律

"一切皆插件"不是口号，它由三条工程铁律支撑：

**① Registrations are effects（注册即效果）**

每个贡献都走 `ctx.effect()` / `ctx.on()` 注册，`register()` 返回 disposer（卸载器）。插件被卸载时，它注册的一切都被回收——没有"装了拆不干净"的残余状态。

**② Model-visible ⟺ logged（模型可见必可重建）**

凡到达模型请求的任何东西，都必须能从 session 日志重建；任何新的模型可见输入，必须有对应的 session 事件。这条铁律是 dsh 全部可靠性的地基：**模型看到的每一字节，都对应一条可重放的事件**。

**③ 能力缝三角色齐全**

一个合格能力 = Service Definition（机器契约）/ Service Provider（实现）/ Consumer（调用方）三角色齐全，且只在包内闭环。它强制"接口长什么样"与"怎么干活"分离，实现细节不泄漏给调用方。

### 1.3 骨架：一个 agent 怎么运转

dsh 的"脊椎"在 `core` 组，一条 turn 流程把它串起来：

**agent loop**：一个 turn（轮次）= 零或多个 step（步骤）；一个 step = 一次模型请求 + 它调用的工具。事件流固定为：

```
turn/start → step/start → llm/stream → assistant/message → tool/call
→ tools/pre-execute → tools/execute → tools/post-execute → tool/result
→ step/end →（需要再请求？）→ turn/end
```

**事件溯源会话**：整个交互历史是一条只追加的 `SessionEvent` 日志（raw log，永不删），模型真正看到的消息是它的派生投影（surface）。上下文过长时用 compaction 做"替换式压缩"——把旧区间替换成摘要 checkpoint，而不是追加截断。**token 真减、raw log 不丢、可重放可审计**，且保住 KV 前缀缓存。

**工具注册表**：受作用域隔离的注册表 + 带护栏的执行管道。工具经 `defineTool` 定义（强类型契约），注册进 `ctx.tools`，执行时经过护栏（超时、审批、作用域过滤）。

### 1.4 能力地图

能力全部以插件形态挂在中轴上，按职责分五组：

| 组 | 能力包 |
|---|---|
| 执行环境 | llm / shell / subprocess / terminal / fs / lsp / code-runtime / sandbox / e2b |
| 编排智能 | subagent / workflow / plan / todo / goal / compaction / context |
| 知识外部 | skill / web / mcp / storage / attachment |
| 治理护栏（上） | guard / hooks / interaction（审批）/ credentials / settings / identity / session / session-query |
| 治理护栏（下） | self-modification / acp / schedule / jobs / feedback / spill |
| 组装分发 | bundle / preset / boot / api / typert / sdk / client / extensions |

与人的交互面有六层：CLI（headless 一次性任务）、浏览器 GUI（`dsh --profile web`）、审批 / 命令 / 问询协议（`interaction` 组）、ACP（自动化专用，人不在回路）、SDK / JSON-RPC（把 dsh 嵌进别家产品）、cordis.yml（平台层组装整个 agent 树）。

### 1.5 深的表现

"深"不是堆功能，而是把几个关键机制做透：

**fail-safe 审批**：工具执行前 `PreToolDecision` 三态 `allow / deny / ask`。`ask` 在挂了审批通道时由人处理，**没挂时退化为 deny**——危险操作必经人，否则默认拒绝。这是人和 agent 之间的"刹车"。

**长链任务**：不靠"一个超长 turn"，靠拆 + 续 + 控——拆（subagent / workflow / ralph 把长任务切成有界单元）、续（compaction + durable checkpoint，崩溃可续）、控（round cap / barrier / turn-stopping 给"该停"的硬边界）。

**记忆四层**：没有向量库 / RAG。会话记忆（raw log 可重放）/ 跨会话记忆（session-reference 只读快照，限 3 条、当不可信）/ 长期知识（AGENTS.md 文件链，"文件即记忆"）/ 用户身份（settings / identity / credentials）。立场：记忆 = 可重建状态，拒绝自动模糊召回——自动召回 = 不可控上下文注入 = 投毒面。

### 1.6 深 = 约束类胜利

dsh 展示的全是"约束类"胜利，没有一个"功能炫技"：

| 它得意的设计 | 内容 |
|---|---|
| 无特权内核 | 连内核 bash 都是普通插件，可被 sandbox 无缝替换 |
| 可重建上下文 | Model-visible ⟺ logged，压缩后仍可 replay、可审计 |
| 崩溃安全压缩 | durable 锁（事件对）而非内存 mutex，压到一半崩溃留可检测孤儿锁 |
| KV 缓存自觉 | 每包强制申报 KV Cache effect，压缩用 replace 保前缀复用 |
| 人令不扰模型 | `/compact` 等命令走 command plane，不进模型消息、不耗 token |
| 作用域克制 | 两级扁平 + shadowing，拒绝作用域爆炸 |
| 目标即状态 | goal 折叠进 session 状态机，不造独立"目标引擎" |

工程纪律上：包边界显式、misconfiguration 就地 loud fail、跨边界用 Branded 不透明 id、每文件 100% 覆盖门禁。**所有机制回溯同一套纪律：可重建、可审计、可替换、不污染、不崩、不泄。**

### 1.7 预告：深与广正交

到这里可以给 dsh 定个性：**它回答的是"一个能力怎么被可靠执行"**——沙箱、凭据、审计、压缩，都是为了让每一次操作可靠。

而本文所基于的 text-cli（tc）回答的是另一个问题：**"能力怎么被广泛供给和消费"**。深与广是正交的两个维度——dsh 深，tc 广。

dsh 先自洽地是它自己，不依赖外部补全。接下来的三章，讲它与 tc 的三种整合形态：桥（消费）、运行时（承载）、混合（合体）。

---

## 第二章 桥：深借广——dsh agent 接入 tc 指令生态

tc（text-cli）以一行 `AI:域;动作,参数` 为原语，把"能力繁殖门槛压到会说话的人"——它的指令包生态（算术、天气、地图，甚至花店老板的经验）是天然的"指令市场"。这一章讲第一种整合形态：**桥**——dsh agent 主动去这个市场买东西。

### 2.1 定位

桥是**消费层**整合：

| 维度 | 桥 |
|---|---|
| 方向 | dsh 往外拿能力（outbound） |
| dsh 角色 | 消费者 |
| 面向 | dsh agent（可信主体） |
| 护栏需求 | 薄（agent 可信，不需要沙箱 / 审批） |

一句话：**"吃工具的人"遇到"指令市场"**。dsh 的 agent 是吃工具的人——它在自己的循环里决定调什么；tc 是海量指令市场——它提供能调的东西。桥就是两者之间的那条缝：把 tc 市场缝进 dsh，且让 LLM 始终只记住一个前缀（`AI:`）。

第一章的"深与广"在这里第一次合流：dsh 的深保证"吃掉的能力被可靠地编排进自己的循环"，tc 的广提供"吃不完的能力"。

### 2.2 核心决策：一个插件 = 能力缝

桥的第一个设计决策直接决定它的形状：**不把 tc 的每条指令注册成 dsh 工具，而是让一个插件扮演能力缝，内部挂三个能力源，对 dsh 暴露固定、闭集、稳定的五个工具。**

为什么不能"每条指令一个工具"？

- **tc 指令包是动态的**：安装即声明、卸载即消失，端点也会变。若每条指令都静态注册成 dsh 工具，dsh 的插件树会随 tc 端点变化而漂移——dsh 就得不停重装插件。
- **tc 的包 schema、`AI:` 语法、信封、双令牌**——这些是 tc 的内部语言。若泄漏给 dsh 契约，dsh 内核就"看见"了它不该看见的东西。

桥把这一切封在自己实现层。它满足第一章的能力缝三角色：

| 角色 | 桥的落地 |
|---|---|
| Service Definition | 五个工具的强类型接口 |
| Service Provider | 三个能力源实现（远程 HTTP / 本地 JS 引擎 / dsh tool 代理） |
| Consumer | dsh agent |

桥是**适配器（adapter）而非穿透器（passthrough）**：它吸收 tc 薄协议与 dsh 能力平面的哲学差异，不让任一方改内核。dsh 不因 tc 端点变化而重装插件——tc 的动态性被桥完整保住。

### 2.3 三个能力源 → 五个工具

桥内部挂三个能力源：

1. **tc 远程端点**（HTTP，封装 A0 SDK）——调远端已注册的指令
2. **tc 本地 JS 引擎**（`textcli-core`，进程内零网络）——执行本地 `tc-math` 类 JS 包
3. **dsh 自身 tool**（含 mcp tool，同进程代理）——复用 dsh 已注册的工具

三个源分别由五个工具暴露给 LLM：

| 工具 | 能力源 | 用途 |
|---|---|---|
| `call_tc` | 远程（或短路本地） | 调一条 tc 指令，`prompt` 传 `AI:域;动作,参数` |
| `run_tc_js` | 本地 JS 引擎 | 进程内零网络执行本地 JS 指令包，返回与 `call_tc` 同构信封 |
| `tool_avatar` | dsh 自身 tool | 同进程代理 dsh 原生 / mcp 工具，省 token |
| `find_tc` | 三源聚合 | 统一发现面：返回扁平字典，每条自带 `call_tool` |
| `wait_tc` | 远程 | 轮询异步长任务（tc 的 tracked 语义：真人三天回一次也能接住） |

`find_tc` 的返回形状就是"消费闭环"——不是按源分组的裸清单，而是每条能力自带消费方式：

```json
{
  "tc-math_eval": { "cli": "AI:tc-math;eval,<expr>", "call_tool": "call_tc", "rank": 90 },
  "github.create_issue": { "cli": "github.create_issue", "call_tool": "tool_avatar", "rank": 50 }
}
```

LLM 一次拿到"能力 → cli 模板 → 用哪个工具"，不必自己猜。`rank` 只决定返回顺序，不决定"该不该调"——选指令的语义责任始终在调用方。

### 2.4 一维体验

桥对 LLM 的唯一承诺是：**你永远只写 `AI:域;动作,参数`**。`tc__` 前缀、端点切换、信封转换——全是桥内部的事，LLM 感知不到、也不该感知。

五个工具的 `description` 就是 model-visible 的强类型契约；但模型不会自动知道"怎么调才对"，配套 SKILL 把它压成几条纪律：

- **先发现再调用**：拿不准指令时先 `find_tc`，不猜 `AI:` 语法
- **白名单即边界**：只调 `find_tc` 里看到的指令
- **一维体验**：任何 tc 指令都用一句话表达，从不拆成 JSON 字段
- **异步要接**：`call_tc` 返回异步任务 → 立即 `wait_tc` 轮询
- **方向单向**：`tool_avatar` 只调 dsh 自身 / mcp 工具，不反向暴露
- **失败先看信封**：返回 `{ok:false, err}` 时，先看 `err`（6 码闭集）再决定降级或换指令
- **省 token**：`find_tc` 一次取尽，不绕回 dsh 原生通道

一个反例最说明"一维"的意义：`call_tc({domain:'weather', action:'query', params:[...]})` 破坏了 `AI:` 一维契约——正确做法是 `call_tc({prompt:'AI:weather;query,北京'})`。

### 2.5 信封双分支与单向纪律

桥的转换层有**两个信封分支**：

| 分支 | 转换 | 输入 → 输出 |
|---|---|---|
| tc 家族 | `tcToDsh` | tc 闭集信封 `{rst_types, rst_data, rst_err}` → dsh 强类型结果（`ok = (rst_err === '' && status 非 not_found-like)`） |
| dsh tool 家族 | `toolToDsh` | dsh 原生 / mcp 工具结果 → `{ok, data, err?}` |

两套返回语义不同构，但都被桥在自己的转换层吸收——**dsh 内核只看到干净强类型的 tool 结果**，tc 的信封歧义（如 `status:"ok"` 但 `error` 字段写着没找到）在 `tcToDsh` 里被消化，不泄漏到循环里。

两条纪律贯穿始终：

- **方向单向**：桥是"dsh → 外"的适配器。`tool_avatar` 只被 dsh agent 调用、只调 dsh 已注册工具，不提供把 dsh 能力反向暴露给 tc 的路径——桥不越界成双向桥。
- **Model-visible ⟺ logged**：每次 `call_tc` 的 prompt 与返回都写进 session 事件——tc 信封成为 dsh session 日志里一段普通 tool 结果，第一章的铁律在桥侧继续成立。

### 2.6 桥的内部结构

桥的源码组织与它的设计一一对应（源码位置：`src/skeleton/bypass-service/dsh/dsh-tc-bridge/`）：

```
dsh-tc-bridge/
├── src/
│   ├── index.ts          # apply(ctx) 装配 + makeBridgeDeps
│   ├── tools.ts          # 五个工具（createBridgeTools）
│   ├── config.ts         # 配置（端点三态 / 双令牌 / 白名单 / jsPkgDirs）
│   ├── envelope.ts       # 双分支转换：tc 信封 ↔ dsh tool 结果
│   ├── tc_client.ts      # 远程 tc 端点（call / discover / poll / wait，A0 SDK）
│   ├── js_engine.ts      # 本地 textcli-core 引擎（load / execute / discover）
│   ├── tool_proxy.ts     # tool_avatar 同进程代理（含 mcp tool）
│   ├── runtime_detect.ts # 模式探测（bridging / hybrid）
│   ├── mapper.ts         # 前缀双射 tc__ ↔ AI:
│   ├── allowlist.ts      # tc 指令白名单
│   ├── session.ts        # session 透写（Model-visible ⟺ logged）
│   └── types.ts          # 桥内部类型 + ToolRegistry 依赖注入接口
```

模块与五工具的对应：

| 模块 | 对应工具 / 职责 |
|---|---|
| `tools.ts` | 五个工具的注册入口 |
| `tc_client.ts` | `call_tc` / `wait_tc` / `find_tc`（远程源） |
| `js_engine.ts` | `run_tc_js`（本地源） |
| `tool_proxy.ts` | `tool_avatar`（dsh tool 源） |
| `envelope.ts` | 信封双分支（`tcToDsh` / `toolToDsh`） |
| `runtime_detect.ts` + `mapper.ts` + `allowlist.ts` | 混合模式三件套（短路 / 前缀双射 / 白名单） |
| `session.ts` | 每次调用写 session 事件 |

到这里，消费层的全貌清晰了：**桥用一个插件、五个工具、两个信封分支，把 tc 的"广"缝进 dsh 的"深"，而 LLM 始终只见一个前缀。** 下一章讲第二种整合形态——运行时：dsh 不再是买方，而是卖方。

---

## 第三章 运行时：深载广——dsh 成为 tc 的运行时节点

第二章里 dsh 是买方。这一章它换一个角色：**dsh 变成 tc 的运行时节点**——对外暴露 tc 协议端点，执行 tc 的 JS 指令包。买方变成卖方。

### 3.1 定位

运行时是**承载层**整合：

| 维度 | 桥（第二章） | 运行时（本章） |
|---|---|---|
| 方向 | dsh 往外拿能力（outbound） | 外面往里打指令（inbound） |
| dsh 角色 | 消费者 | 承载者 |
| 执行对象 | dsh agent 调 tc 指令 | dsh 执行 tc 的 JS 指令包 |
| 面向 | dsh agent（可信） | tc 调用方（不可信） |
| 护栏 | 薄 | 厚（沙箱 / 凭据 / 审批 / 审计全套） |

一句话：**dsh-tc-runtime 是 tc 的一个 JS 实现变体——作为承载者，它选择承载 9 机制全集，用 dsh 的"深"为少约束的 JS 包提供可靠执行。**

tc 协议刻意留白——不抢做凭证、目录、沙箱，只守一维契约。留白是协议的设计，不是缺口；运行时作为承载者，选择在实现层补上这些工程护栏。运行时让 dsh 对外暴露 `POST /text-cli/cli`，把 tc 指令路由进 dsh 的能力：沙箱执行宿主、凭据按包隔离、审批、审计。调用方用 tc 协议说话，享受 dsh 的工程护栏——他们不需要、也不在意的护栏。

### 3.2 为什么"厚"治"少约束"

tc 的 JS 指令包**易造但少约束**：裸 `require` 加载任意代码、任意文件副作用、凭据全局共享、执行无痕。繁殖门槛极低（会说话的人就能造），但执行护栏近乎为零：

| JS 指令包的"少约束" | dsh 运行时的"厚" |
|---|---|
| 裸 `require` 加载任意代码 | 沙箱执行宿主，拦文件 / 网络 / 进程副作用 |
| 凭据全局共享、随便拿 | 凭据按包隔离，包只能拿自己被授权的引用 |
| 执行无痕、不可追 | session 全量审计，可重放、可重建 |

关键的认识：**dsh 选择成为 tc 的运行时实现——而承载"少约束"的 JS 包需要"厚"，dsh 恰好是那个厚的东西。**

转化后 dsh 在跑什么？外面发 `AI:域;动作,参数` 进来，dsh 解析、鉴权、用沙箱执行宿主跑对应的指令包、包上 tc 信封返回。dsh 不重写协议、不改造 tc——它只是把 tc 的指令包生态，接进自己可靠的执行链路里。

### 3.3 15 包结构与 7 条红线

运行时是**旁路形态**：只挂插件、不侵入 dsh 内核，不宣称"标准运行时"身份。挂载方式是一个 profile 组合包（`dsh-tc` = base + host-webserver + runtime-bundle），同时禁用 dsh 原生 `agent` / `agent-default-model` / `llm` 三行——**tc 只提供指令执行能力，不接管 dsh 的对话 / 模型内核**。

实现是 15 包 monorepo（源码位置：`src/skeleton/bypass-service/dsh/dsh-tc-runtime/`），物理结构如下：

```
dsh-tc-runtime/
├── runtime-inbound/      # 入站 HTTP：POST /text-cli/cli → 信封；六段管道；保留域拦截
├── runtime-mapper/       # 指令映射：tc 指令 ↔ ctx.tools；tcToDsh / dshToTc
├── runtime-sandbox/      # 沙箱执行宿主（受限子进程 + policy 7 类分层护栏）
├── runtime-credentials/  # 凭据按包隔离（CredentialRef + env 白名单注入）
├── runtime-audit/        # 审计通道：独立 append-only JSONL（traceId + seq）
├── runtime-approval/     # 审批 answerer（归属过滤 / HMAC / fail-closed）
├── runtime-meta/         # text-cli;* 元指令（install / query / path / pro / ...）
├── runtime-quota/        # dsh-quota：周期窗口 + 原子 check+consume
├── runtime-host/         # 宿主指令：dsh-sandbox / credential / approval / ...
├── runtime-path/         # path 引擎：声明层解释器 + workflow 编译
├── runtime-aggregate/    # 聚合 try-in-order 降级 + 异步任务桥
├── runtime-mesh/         # mesh 转发：路由表 / 防环 / 退避
├── runtime-bridge/       # 协议桥：mcp-client → mcp__<server>__<tool>
├── runtime-pro/          # 门面注册表：简名 → path / aggregate
└── runtime-contract/     # 全局验收：规范信封 + 16 行映射契约
```

按职责分五层：

| 层 | 包 |
|---|---|
| 接入层 | runtime-inbound（入站六段管道：解析→路由→执行→信封→审计）、runtime-mapper（tc↔dsh 翻译 + 发现） |
| 安全护栏 | runtime-sandbox（环检测 + 沙箱策略 + 执行宿主）、runtime-credentials（凭据隔离）、runtime-audit（独立 JSONL）、runtime-approval（审批） |
| 调度编排 | runtime-path（声明层解释器）、runtime-aggregate（聚合降级 + 异步任务）、runtime-mesh（跨节点）、runtime-pro（门面）、runtime-host（宿主指令）、runtime-quota（配额） |
| 协议桥 | runtime-bridge（mcp-client 协议桥） |
| 契约验收 | runtime-contract（信封 + 16 行映射契约）、runtime-meta（元指令 + 生命周期） |

7 条红线（防回潮）：

① 不侵入 dsh 内核；② 凭据明文不进 JS 执行环境；③ 沙箱默认拒绝；④ 协议闭集；⑤ 保留域不污染 `ctx.tools`；⑥ 审批归属过滤（dsh agent 审批不被 tc webhook 劫持）；⑦ 审计独立 JSONL，不写 `ctx.sessions`。

**兜底原则**：任何未预见失败都走 `ERR_EXECUTION` 而非静默成功；审批 / 沙箱 / 凭据缺失在缺能力时一律 fail-closed 拒止。

### 3.4 协议闭集与 16 行映射

运行时**不重新发明协议**——它复用 `textcli-core` 的信封（parser / envelope / alias / registry / loader），并用契约测试断言逐字段一致。这是"协议零重写"的硬证据，也是防止 tc 侧偏离真源的回归闸。

信封三字段：`{rst_types, rst_data, rst_err}`。错误码 6 码闭集，任何 dsh 侧信号必须落到闭集，否则回退 `ERR_EXECUTION`——**协议永不静默放行**。

关键机制是 **dsh→协议 16 行映射**：dsh 侧的各种信号，逐一翻译成协议语言（选取代表性的几行）：

| dsh 侧信号 | 协议码 | 语义 |
|---|---|---|
| 工具未注册 | `ERR_NOT_FOUND` | 指令不存在 |
| 沙箱 policy 拒绝 | `ACCESS_DENIED` | 能力未授权 |
| 审批 deny / 无通道 | `ACCESS_DENIED` | 人机门拒绝，fail-closed |
| 凭据缺失 | `SERVICE_DENIED` | 服务侧凭据不可用 |
| 环检测命中 | `ERR_EXECUTION` | `CYCLE_DETECTED`，结构性拒绝 |
| mesh 不可达 | `ERR_ROUTING` | 跨节点失败 |
| 配额超限 | （非错误） | `rst_data.status="stop"` 降级信号 |
| 聚合降级耗尽 | （非错误） | `rst_data.status="error"` + reason |
| 未知 / 未列入 | `ERR_EXECUTION` | 兜底 |

注意配额超限与降级耗尽**不是错误**——它们走 `rst_data.status` 的降级信号，不污染 6 码闭集，同时给调用方结构化语义。这是 dsh 的"深"（可审计的降级语义）与 tc 的"广"（调用方语义不被破坏）在协议层的一次显式合流。

### 3.5 深广对齐映衬

运行时不是"顺便托管"tc 的包，而是 **dsh 宿主的深机制，经 `dsh-tc-runtime`（tc 的实现变体）与 tc 协议的广机制逐项对齐映衬**。合并之后，每一对都同时开出"深"和"广"两面：

| dsh 的机制（深） | tc 协议的机制（广） | 合并后：如何有广有深 |
|---|---|---|
| 事件溯源会话（raw log→surface→compaction） | 异步任务 / tracked 长链 | 长链每步有可重放 session；因此敢接 tracked 长任务 |
| subagent / workflow（拆链） | 聚合降级 aggregate（并链） | 多 provider 逐降、stop/error 语义可审计；一条指令挂多能力源，聚合不崩 |
| fail-safe 审批（默认拒绝） | 闭集信封 stop/error 降级信号 | 危险操作必经人；被拒也以 tc 信封规整返回 |
| 凭据按包隔离（引用非明文） | 协议留白（不抢做凭据） | 能安全托管任意第三方少约束 JS 包 |
| 记忆四层 / 会话重建 | 协议的跨调用上下文 | 复杂多轮的 tc 指令也能被可靠承载 |
| 门面抽象（短名 + 环检测） | 协议机制集 | 多包多域统一在一个 tc 协议入口下被发现 |

**核心逻辑**：每一行的"深"和"广"不是分开的，是**同一个机制合并后的两面**——深保证"可靠"，广保证"敢接、接得住、接得广"。深是广的底气，广是深的用武之地。

到这里，桥与运行时的对照完整了：**桥薄、运行时厚；桥消费、运行时承载；桥面向可信的 dsh agent，运行时面向不可信的 tc 调用方。** 前两章把它们分开讲——下一章，它们住进同一个进程。

---

## 第四章 混合：深广同体——桥 + 运行时并存

前两章，桥（消费）和运行时（承载）是两个插件、两种形态、两种面向。这一章它们共存于同一个 dsh 进程——而且不是简单并存：**桥会感知到运行时，主动改变自己的行为**。这是整个体系的合体形态。

### 4.1 三种模式

桥与运行时的关系，由"当前 dsh 是否同时挂了 `dsh-tc-runtime`"决定，共三种形态：

| 模式 | dsh 角色 | 触发条件 | 桥的形态 |
|---|---|---|---|
| 桥接 | agent（消费 tc） | 无 runtime 插件 | `call_tc` 走远端 HTTP；`find_tc` 三源全暴露 |
| 服务 | tc 协议宿主（生产） | dsh 仅作 runtime | 桥不介入，runtime 独立对外服务 |
| 混合 | agent + runtime | 同 dsh 内同时有 runtime | 桥做运行时感知：短路 + 白名单 + 前缀映射 |

前两章各讲了一种：第二章是桥接模式（dsh 纯消费），第三章是服务模式（dsh 纯承载）。这一章讲混合——也是这套整合真正的新增量。

### 4.2 桥的运行时感知

桥的模式检测是一个**纯探测**：启动 / 运行时查 `ctx.tools` 是否已有 `tc__` 前缀工具（或 runtime 插件注入的标记），返回 `bridging` / `hybrid`。探测结果决定 `call_tc` 与 `find_tc` 的默认行为——全部走 Config，LLM 侧始终一维。

混合模式下，桥有三处特化：

**① `call_tc` 自请求直通短路**。不把 `AI:d;a` 经 `POST 127.0.0.1:<port>/text-cli/cli` 环回（那会无谓地两次进程内 HTTP 往返），而是解析出 `domain;action` → 映射到 runtime 已注册的 `tc__domain__action` 工具 → 同进程直接调用。这复用了 runtime 的全部护栏（沙箱 / 审批 / 审计 / 配额 / 环检测），且不重复执行。

**② `find_tc` 白名单过滤 + 前缀双射**。tc 指令按可配置白名单隐藏（粒度到 `domain;action`，支持域级通配），并做 `tc__d__a` → `AI:d;a` 前缀映射——LLM 只发现允许的 tc 能力，且字典里永远是 `AI:` 原语形态。白名单空 = 全部暴露（向后兼容桥接模式）。

**③ `tool_avatar` 全量暴露**。白名单只作用于 tc 源，不作用于 `dsh_tool` 源——因为 tc 原语比原生 JSON tool 调用每次节约约 5 倍 token，`tool_avatar` 是省 token 的核心通道，不能被削弱。

### 4.3 LLM 永远只见一个前缀

三种模式下，LLM 的体验完全一致：**永远只写 `AI:域;动作,参数`**。`tc__` 前缀、短路还是远端、白名单过滤——模式差异全部在桥的接缝处被吸收，LLM 不知道也不需要知道。

两个约束让"一维"成立：

- **前缀双射**：`AI:d;a` ↔ `tc__d__a` 必须是双射。`domain` / `action` 命名不含 `__`（与 mcp-client 双下划线命名对齐），否则 mapper 拒绝而非静默错映射。
- **白名单是"藏名不藏执行"**：白名单只作用于 `find_tc` 发现面（藏名），`call_tc` 收到白名单外的指令默认放行——这是软限制，与 tc 一维契约一致：语义责任在调用方。需要硬限制再开执行层校验。

SKILL 在混合模式下追加两条纪律：**LLM 永远只写 `AI:` 原语**（不见 `tc__` 前缀）、**只调 `find_tc` 里看到的指令**（白名单即边界）。

### 4.4 合体全景

一个进程里，dsh 同时是 agent 和 tc 的运行时实现（`dsh-tc-runtime`）：

- 作为 **agent**，它在自己的 agent loop 里思考、决策，决定调什么工具
- 作为 **runtime**，它对外暴露 `POST /text-cli/cli`，承载 tc 调用方的指令
- 当 agent 自己决定调一条 tc 指令时，桥短路到同进程的 runtime——**它吃自己做的饭**

第一章说深与广正交——正交不是隔离。同一个进程里，深与广各安其位：dsh 的循环负责决策，tc 的协议负责表达，桥在中间负责翻译与感知，运行时在底下负责可靠执行。

到这里全文收束：**dsh 先自洽（深），再深借广（桥）、深载广（运行时）、最终深广同体（混合）。这不是两套系统的对峙，而是基于 text-cli 协议的承载——dsh 既是消费方又是承载方，薄协议与厚实现联成一体。**

---

## 附录：从 dsh 集成看自然原语的普适性

### 命题

> **协议的普适性来自它继承的语言基底：任何能用自然语言表达的能力，天然就在协议的语义空间里。协议不融合任何东西——因为它与语言同构。**

协议的根原语是自然语言**说出即兑现**：人把内心图景表达出来的瞬间，就是同维原语的兑现。自然语言（含编程语言——它也是语言的一种，是受控光谱上更严格的一档）是这个语义空间的**同维表达**，不是异维编码。写代码的开发者也是说话者：native 包（代码）与 nocode 包（口述）没有物种差别，都是语言的兑现，只是光谱档位不同。

### dsh 为什么是最强证据

tc 与 dsh 是价值观层面的对立——tc 赌"机器适配 LLM 吐文本"（边界不校验、校验推 handler），dsh 赌"强类型能力缝"（Service Definition 是机器契约）。而三种形态的整合（桥 / 运行时 / 混合）没有一条要求 dsh 改变信仰：dsh 的能力缝、session 日志、agent-loop 完整保留。

关键认识：**dsh 用 TS（编程语言）兑现了 tc 协议**——`dsh-tc-runtime` 就是 tc 的一个 JS 实现变体（与 pypi 是 Python 实现、npm 是 JS 实现、cloudbase 是云函数实现平列，同属旁路运行时家族）。两个哲学对立的系统能互相寻址，不是因为 tc 能融合 dsh，而是因为**它们都在用语言兑现图景**——协议只是让它们在同一个语义空间里互相可见。

**连价值观对立的系统都天然同构，普适性就不依赖对方认同你。**

### 逻辑机制：语言是基底，不是接缝

协议不需要"入口"或"接缝"，因为：

> 任何系统，只要最终服务于人或 AI，就必须以语言为媒介——人的使用通过语言表达，AI 的输入输出本质是语言。而"在语言中"本身就是参与条件，不需要被接入。

协议只是把已存在的语义空间投影成可寻址的形式：`AI:域;动作,参数` + 信封。它不触碰对方内部——它只是提供一个句柄，让语言平面上的东西互相可寻址。

### 边界与代价

- **边界**：凡能说出的，皆已在其中；说不出的，不属于语义空间。纯物理过程、无接口的封闭系统不在内——但它们可经中介转译后纳入（这正是桥的职责）。
- **代价**：协议不征收"接缝税"。最小基线只需"指令运行 + 三字段信封"，接入可以很轻——pypi 纯函数调用、npm 进程内执行即是一例。dsh-tc-runtime 的 15 包厚度，是它作为 tc 运行时的一个 JS 实现变体、选择承载 9 机制全集（均为可选增强）的自我加压：**厚度属于运行时的选择，不属于协议的代价，也不属于 tc 的债务。**

### 收束

> **协议是语义空间的投影 / 句柄——普适性来自语言基底本身，而非 tc 的能力；轻或重，由运行时自行选择，协议从不征收。** dsh 的集成证明的不是"tc 能融合一切"，而是：凡在语言中的，本就同维存在，协议只是让它们互相可见。

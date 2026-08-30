# dsh-tc-bridge

> 让使用 dsh 的 LLM 以统一原语形式调用 tc 指令生态。
> 版本：0.1.0（开发中）｜2026-08-19

`dsh-tc-bridge` 是 dsh（DeepSeek Harness）的一个**能力缝插件**：它把 tc 指令生态（远程 tc 端点 + 本地 `textcli-core` JS 引擎）与 dsh 自身/mcp tool 统一到一个调度平面，对 dsh agent 暴露 **五个闭集工具**，让 LLM 永远以 `AI:<域>;<动作>,<参数>` 原语消费 tc 能力。

**一句话**：dsh agent 是"吃工具的人"，tc 是"海量指令市场"——桥是把 tc 市场缝进 dsh 的那条缝，且让 LLM 始终只记住一个前缀（`AI:`）。

---

## 零、概念速览

```
dsh agent (LLM)
  │  只认识 AI:<域>;<动作>,<参数>  和 五个桥工具
  ▼
dsh-tc-bridge（本插件）
  ├─ call_tc    远程 tc 端点  /  混合模式短路 runtime tc__ 工具
  ├─ wait_tc     异步长任务轮询
  ├─ run_tc_js   本地 textcli-core JS 包执行
  ├─ tool_avatar dsh 自身 tool 同进程代理（省 token）
  └─ find_tc     桥内能力统一发现面（白名单 + 前缀映射）
```

| 五种运行形态 | 触发 | 桥的行为 |
|------|------|---------|
| **桥接模式** | dsh 无 tc runtime | `call_tc` 走远端 tc 端点（HTTP），`find_tc` 全暴露 |
| **服务模式** | dsh 仅作 tc runtime | 桥不介入（`dsh-tc-runtime` 独立对外服务）|
| **混合模式** | dsh 同时是 agent + runtime | `call_tc` 短路调 `tc__` 工具；`find_tc` 白名单过滤 + 前缀映射 |

---

## 一、安装

```bash
# 依赖：node >= 22；桥是纯 TS 插件，不依赖 dsh 内核（依赖注入解耦）
cd other/dsh-tc-bridge
npm install
```

桥通过 `@deepseek-ai/dsh-tc-bridge` 作为 dsh 插件装配（P9 完成 `apply(ctx)` 真注册）。

---

## 二、五个工具

| 工具 | 参数 | 用途 |
|------|------|------|
| `call_tc` | `prompt`（`AI:<域>;<动作>,<参数>`）、`endpoint?`、`wait?` | 调 tc 指令。混合模式短路调 `tc__` 工具；桥接模式走远端 |
| `wait_tc` | `task_id`、`endpoint?`、`timeout_ms?` | 轮询异步长任务（指数退避）|
| `run_tc_js` | `pkg_dir`、`prompt`、`reload?` | 进程内零网络执行本地 JS 包（`textcli-core`）|
| `tool_avatar` | `name`、`args` | 同进程代理 dsh 自身 tool（含 mcp tool），省 token |
| `find_tc` | `source?`、`endpoint?`、`key?`、`limit?` | 桥内能力发现面（tc 源按白名单，dsh_tool 全量）|

**LLM 使用纪律**（见 SKILL.md）：永远只写 `AI:` 原语；只调 `find_tc` 里看到的指令（白名单即边界）。

---

## 三、配置（`config.ts`）

| 配置 | 说明 | 默认 |
|------|------|------|
| `endpoint` | 端点三态：`auto-self` / URL / 省略 | `auto-self` |
| `accessToken` / `serviceToken` | tc 双令牌 | 环境变量 |
| `rankEndpoints` | rank 降级链端点列表 | `[DEFAULT_ENDPOINT]` |
| `jsPkgDirs` | `run_tc_js` 的 pkg_dir 白名单（防 RCE/目录穿越）| `[]` |
| `tcAllowlist` | tc 指令白名单（仅 tc 源；空 = 全暴露）| `[]` |
| `runtimeAutoDetect` | 是否检测 `ctx.tools` 的 `tc__` 工具决定混合模式 | `true` |

优先级：环境变量 > 配置 > 默认。

---

## 四、目录结构

```
other/dsh-tc-bridge/
├── package.json / tsconfig.json / vitest.config.ts
├── src/
│   ├── index.ts          # apply(ctx) 装配 + makeBridgeDeps
│   ├── tools.ts          # 五个工具（createBridgeTools）
│   ├── config.ts         # 配置
│   ├── envelope.ts       # tc 闭集信封 → ToolResult
│   ├── tc_client.ts      # 远程 tc 端点（call/discover/poll/wait，A0 SDK）
│   ├── js_engine.ts      # 本地 textcli-core（load/execute/discover）
│   ├── tool_proxy.ts     # tool_avatar 同进程代理
│   ├── runtime_detect.ts # 模式检测（bridging/hybrid）
│   ├── mapper.ts         # 前缀双射 tc__ ↔ AI:
│   ├── allowlist.ts      # tc 指令白名单
│   ├── session.ts        # session 透写（Model-visible ⟺ logged）
│   └── types.ts          # 桥内部类型 + ToolRegistry 依赖注入接口
└── tests/                # 89 单测 + P8 真实联调
```

---

## 五、测试

```bash
npx tsc --noEmit     # strict 类型检查
npx vitest run       # 单测（envelope/tc_client/js_engine/mapper/allowlist/runtime_detect/tool_proxy/tools/session）
npx vitest run tests/integration/live.test.ts   # P8 真实联调（需盆栽急救 tc 服务）
```

- 本环境：89 单测全绿 + P8 联调 5/5（对齐 runtime 裸开发优先策略）。
- 覆盖门禁 100%：归 ubuntu `pnpm -w test --coverage`（dsh CI 门禁）。

---

## 六、参考实现

桥的核心依赖与参考实现（见 `dsh-tc-bridge.md` §8）：

| 模块 | 参考源码 |
|------|---------|
| `tc_client.ts` | `text-cli/src/skeleton/base/A0-protocol/js/call.js` |
| `js_engine.ts` | `other/tc-js-skeleton/packages/textcli-core/{loader.node,index}.js` |
| `tool_avatar` | tc A7-mcp 桥（`python-dev-guide` §五）|
| `run_tc_js` 白名单 | copilot `WhitelistIndex`（`python-dev-guide` §六）|

---

_版本：v0.1.0｜2026-08-19｜P0~P6 纯逻辑完成，P8 真实联调通过；P7 覆盖门禁 / P9 dsh 装配归 ubuntu 统一测试_

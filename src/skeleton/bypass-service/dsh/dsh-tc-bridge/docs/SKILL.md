---
name: dsh-tc-bridge
description: Use when the agent needs to call tc directive ecosystem (weather, math, maps, plant first-aid, etc.) through the bridge, or to discover/aggregate tc + dsh native/mcp tools. This skill governs how to correctly call call_tc / wait_tc / run_tc_js / tool_avatar / find_tc.
---

# dsh-tc-bridge 使用纪律（Agent 侧）

> 桥是 dsh 的能力缝插件。你（LLM）永远以 `AI:<域>;<动作>,<参数>` 原语消费 tc 能力，只认识五个工具。本纪律约束你**怎么调才正确**，不是桥的实现说明。

## 第一原则：永远只写 `AI:` 原语

- 你只写 `AI:<域>;<动作>,<参数>`，**从不**感知 runtime 的 `tc__<域>__<动作>` 前缀。
- `tc__` 是桥内部的事——你永远看不到它，也不该写它。

## 五个工具的调用规矩

| 工具 | 用它的场景 | 不要 |
| --- | --- | --- |
| `find_tc` | 不确定桥内有哪些能力时，先发现再调用 | 假设指令一定存在；绕过发现直接猜 `AI:` |
| `call_tc` | 调一条 tc 指令（`prompt` 传 `AI:域;动作,参数`）| 把结构化字段塞进 `prompt` 以外的参数 |
| `wait_tc` | `call_tc` 返回异步任务（有 `task_id`）时轮询完成 | 在 `call_tc` 里 wait 到卡死 |
| `run_tc_js` | 执行**本地 JS 包**（如 `tc-math`），传 `pkg_dir` | 拿远端指令硬套 `run_tc_js` |
| `tool_avatar` | 调 **dsh 自身/mcp tool**（如 `github.create_issue`），省 token | 用它调桥自身五个工具（会被拒）|

## 九条规则

1. **先发现再调用**：拿不准指令时，先 `find_tc`，再按结果调 `call_tc`/`run_tc_js`。不要瞎猜 `AI:` 语法。
2. **白名单即边界**：只调 `find_tc` 里**看到的**指令。看不到的（白名单外 / 桥接模式不可达）一律不调。
3. **一维体验**：任何 tc 指令都用 `AI:域;动作,参数` 一句话表达，从不拆成 JSON 字段。
4. **异步要接**：`call_tc` 返回异步任务 → 立即 `wait_tc` 轮询，不中途放弃。
5. **方向单向**：`tool_avatar` 只调 dsh 自身/mcp tool，**不反向**把 dsh 能力暴露给 tc。
6. **不猜语法**：参数用逗号分隔；含逗号/引号的复杂值用 JSON（`{}`/`[]` 内的逗号不拆）。
7. **失败先看信封**：返回 `{ok:false, err}` 时，先看 `err`（闭集错误码），再决定降级或换指令。
8. **本地包才用 run_tc_js**：远端已注册的指令用 `call_tc`，别用 `run_tc_js` 重复执行。
9. **省 token**：`find_tc` 一次取尽 + `tool_avatar` 经桥统一调度，不绕回原生通道。

## 反例表

| 错误做法 | 为什么错 | 正确做法 |
| --- | --- | --- |
| `call_tc({domain:'weather', action:'query', params:[...]})` | 破坏了 `AI:` 一维契约 | `call_tc({prompt:'AI:weather;query,北京'})` |
| 直接调 `tc__weather__query` | 你感知不到 `tc__` 前缀 | 永远写 `AI:weather;query` |
| 不 `find_tc` 就猜 `AI:map;query,beijing` | 指令可能不存在 / 白名单外 | 先 `find_tc(source:'all')` |
| `tool_avatar({name:'call_tc'})` | 桥自身工具被拒绝（防环）| 直接用 `call_tc` |
| `run_tc_js({prompt:'AI:weather;query'})` 但 weather 是远端指令 | 本地没这包，会 NOT_FOUND | 用 `call_tc` 走远端 |

## 失败处理

- `err` 是协议闭集码：`ERR_NOT_FOUND`（指令不存在，别重试同指令）、`ERR_EXECUTION`（执行失败，看返回原因）、`INVALID_PARAMS`（参数错，改参数）、`ACCESS_DENIED`/`SERVICE_DENIED`（权限，别绕）。
- `call_tc` 内部会按 rank 降级，你不用手动切端点。

## 落点

- 桥实现文档：同目录 `dsh-tc-bridge.md`（§0.4 混合模式 / §2 五工具 / §5 风险）。
- 用户手册：同目录 `README_zh.md`。

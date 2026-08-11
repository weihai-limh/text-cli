# JavaScript 标准运行时 — 指令包开发指南

> 本文档是 JavaScript 标准运行时（service）指令包的开发指南。
> schema.json 字段规范见 [package-publish-guide_zh.md](package-publish-guide_zh.md)。
> nocode 文档型指令包见 [package-nocode-guide_zh.md](package-nocode-guide_zh.md)。

---

## 一、指令包形态

| 形态 | 能力来源 | 本文档覆盖 | 说明 |
|------|------|:--:|------|
| **工具函数** | 本地 JavaScript 函数 | §二 | 纯计算/处理，零外部依赖 |

> JS 运行时支持更多形态（在线 API 包等），本文档仅覆盖最基础的工具函数包。更多形态见后续指南。

---

## 二、工具函数包：从零到一

> 以"日期计算器"为例——输入日期和天数，输出偏移后的新日期。目标运行时：service。

### 2.1 目录结构

```
date-calc/
├── schema.json    ← 对外声明：我是谁、能做什么
└── handler.js     ← 内部实现：声明式导出，实际执行的代码
```

### 2.2 schema.json

```json
{
  "id": "date-calc",
  "type": "native",
  "name": "Date Calculator",
  "name_zh": "日期计算器",
  "runtime": "js",
  "version": "1.0.0",
  "category": "utility",
  "locales": ["zh", "en"],
  "trust": "community",
  "description": "Date offset calculation utilities.",
  "description_zh": "日期偏移计算工具。",
  "directives": [
    {
      "domain": "date-calc",
      "domain_zh": "日期计算",
      "action": "add",
      "action_zh": "加天数",
      "usage": "date-calc;add,<date>,<days>",
      "usage_zh": "日期计算;加天数,<日期>,<天数>",
      "description": "Add N days to a date. Returns the result date string.",
      "description_zh": "给指定日期加上 N 天，返回结果日期",
      "params": ["date", "days"],
      "params_desc": {
        "date": "Date in YYYY-MM-DD format",
        "days": "Number of days to add (can be negative)"
      },
      "outputs": ["result"]
    }
  ]
}
```

### 2.3 handler.js

JS 包使用**声明式导出结构**——通过 `module.exports` 导出 domain 别名和 directives 映射表。运行时加载时自动注册。

```javascript
module.exports = {
  domainAlias: "日期计算",
  directives: {
    add: {
      handler: (params) => {
        // date-calc;add,<date>,<days>
        try {
          const dateStr = params[0].trim();
          const days = parseInt(params[1]);
          const dt = new Date(dateStr);
          if (isNaN(dt.getTime())) {
            return {
              status: "error",
              reason: `invalid date: ${dateStr}`
            };
          }
          dt.setDate(dt.getDate() + days);
          const result = dt.toISOString().split("T")[0];
          return {
            status: "ok",
            result: result,
            detail: `${dateStr} + ${days}d = ${result}`
          };
        } catch (e) {
          return {
            status: "error",
            reason: `date calculation failed: ${e.message}`
          };
        }
      },
      actionAliases: ["加天数"]
    }
  }
};
```

### 2.4 handler.js 关键约定

| 约定 | 说明 |
|------|------|
| 声明式导出 | `module.exports = { domainAlias, directives }`——运行时加载 `handler.js` 后自动注册 |
| `domainAlias` | 中文域别名，与 schema.json 的 `domain_zh` 保持一致 |
| `directives` 的 key | 对应 schema.json 的 `action` 字段（canonical 英文名） |
| `handler(params, context)` | `params` 为 `string[]`——运行时按顶层逗号拆分参数传入；`context` 为可选参数，由平台注入（如 CloudBase 的事件对象），普通 handler 可忽略 |
| 返回类型是 `object` | handler 必须返回 **object**——运行时将其直接放入响应信封的 `rst_data` 中 |
| 返回信封约定 | 成功 `{status: "ok", ...}`；失败 `{status: "error", reason: "..."}` |
| `actionAliases` | 中文动作别名数组，运行时别名归一化后路由（双向、大小写不敏感） |
| `usage` 仅供发现 | `usage` 是纯文档字段，供 AI/用户发现指令用；**不参与路由、不参与参数解析** |
| 业务数据不嵌套 | 不要 `{data: {data: ...}}`，展开在 `status` 同级 |
| 不存密钥 | 密钥走框架的 key registry，不硬编码在 handler 中 |

### 2.5 与 Python 包的对比

| 维度 | Python 包 | JS 包 |
|------|------|------|
| handler 文件 | `handler.py` | `handler.js` |
| 注册方式 | `@directive(domain, action, ...)` 装饰器 | `module.exports = { domainAlias, directives }` 声明式导出 |
| 别名声明 | 装饰器参数 `domain_alias` / `action_aliases` | 导出对象的 `domainAlias` / `actionAliases` |
| handler 签名 | `def handler(params: list[str]) -> dict` | `handler(params, context)`——`context` 为可选平台注入参数 |
| schema.json | `"runtime": "python"` | `"runtime": "js"` |

### 2.6 多语言

`locales` 声明包支持的输出语言（ISO 639-1，中文 `zh`）。`schema.json` 中 canonical 字段为英文 / 中立；以 `_zh` 为本地化覆盖示例：

- 包级：`name` / `description` 为 canonical，`name_zh` / `description_zh` 提供中文覆盖
- 指令级：`domain` / `action` / `usage` / `description` 为 canonical，`domain_zh` / `action_zh` / `usage_zh` / `description_zh` 提供中文覆盖

`_zh` 字段缺失时回退 canonical。

### 2.7 安装与验证（service 运行时）

```bash
# 1. 启动 service 运行时

# 2. 安装包
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,date-calc"}'

# 3. 验证指令
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:date-calc;add,2026-01-01,30"}'

# 期望响应
# {"rst_types":"text","rst_data":{"status":"ok","result":"2026-01-31","detail":"2026-01-01 + 30d = 2026-01-31"},"rst_err":""}
```

### 2.8 旁路运行时兼容性

符合本指南的 `native-js` 包可直接被 **textcli-core**（npm）加载——不需要部署标准运行时：

```javascript
const { loadPackage } = require("textcli-core/loader.node");
loadPackage("./date-calc/");

// 加载后指令已注册到内存注册表，可通过 dispatch 调用
const { dispatch } = require("textcli-core/registry");
const result = dispatch("date-calc", "add", ["2026-01-01", "30"]);
```

同一份包同时兼容标准运行时（`text-cli;install`）和旁路运行时（`textcli-core`）——一次编写，两种部署方式。

### 2.9 字段速查

**包级必填**：`id` / `type` / `name` / `runtime` / `version` / `category` / `locales` / `trust` / `description`

**包级推荐**：`name_zh` / `description_zh`

**指令级必填**：`domain` / `action` / `usage` / `description`

**指令级推荐**：`domain_zh` / `action_zh` / `usage_zh` / `description_zh`

**可选**：`params` / `params_desc` / `outputs` / `estimated_time` / `estimated_time_note` / `requires`

### 2.10 常见问题

**Q: 我的函数需要额外的 npm 包怎么办？**

在 schema.json 中声明 `requires.npm`：

```json
"requires": {
  "npm": ["axios@^1.0"]
}
```

安装时 text-cli 会自动执行 `npm install`。

**Q: `module.exports` 注册和 `usage` 不一致会怎样？**

路由不受影响——`usage` 是纯文档字段，不参与路由和参数解析。路由只看 `module.exports` 中 `directives` 的 key 与 `actionAliases`；参数由运行时按顶层逗号拆成 `string[]` 传入 handler。但 `usage` 与实际实现漂移会误导 AI/用户发现和调用，应保持二者同步。

**Q: 中文域和动作名是怎么起作用的？**

用户发 `AI:日期计算;加天数,2026-01-01,30` 时，运行时通过 `module.exports` 中的 `domainAlias` 和 `actionAliases` 归一化到 `date-calc;add`，然后路由到 handler。别名匹配双向且大小写不敏感。schema.json 的 `domain_zh`/`action_zh` 是声明面（供发现与意图匹配展示），与导出对象中的别名应保持一致。

**Q: 如何让 AI Agent 发现我的包？**

安装后 AI 调 `AI:text-cli;query` 获取全量指令清单（含 `domain_zh`/`action_zh` 中文别名）。不需要额外注册。

**Q: 一个包可以有多个指令吗？**

可以。在 `directives` 数组中加多条，每条对应 `handler.js` 中 `directives` 对象的一个 key。

**Q: `handler(params, context)` 的第二个参数 `context` 是什么？**

`context` 是平台注入的可选参数——标准 service 运行时调用时不传此参数（为 `undefined`），CloudBase 等云平台会注入事件对象。handler 可以安全地忽略它：`(params) => { ... }`。

**Q: 这个包和 Python 的 `tc-math` 模板是什么关系？**

`src/text_cli/base_text-cli/template/runtime_js/tc-math/` 是 JS 工具函数包的完整模板——schema.json + handler.js 即用即改。`weather/` 和 `web-utils/` 也是可参考的 JS 包模板。

---

## 三、更多形态

> JS 运行时的在线 API 包、容器 API 包等形态见后续指南。
> Python 标准运行时的 MCP 桥接包（§五）和 copilot 包（§六）仅适用于 Python 运行时。

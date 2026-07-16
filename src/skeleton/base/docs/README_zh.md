# base 分组

## 定位

base 分组下的骨架层**不绑定任何运行时**——它们是所有上层的基础。A0 提供零依赖的协议级调用，A1 提供 Agent 可消费的 Skill 封装和指令编译工具。

## 层级

| 层 | 名称 | 内容 | 备注 |
|:---:|------|------|------|
| A0 | protocol | 协议规范 + 零依赖调用示例（shell/python/js/ps1） | 不参与骨架累积链，直通模式 |
| A1 | skill | Agent Skill 封装层——编译（cli.py）+ 消费（skill.py）+ NoCode + Skill 定义 | 不参与骨架累积链，直通模式 |

## A0 与 A1 的关系

A0 是"怎么调"，A1 是"怎么造 + 怎么让 AI 调"。

---

## A0 — 协议级调用示例

零依赖——`shell/call.sh` + `shell/call.ps1` + `python/call.py` + `js/call.js` 四种实现，任何人拿到就能用。

### 三种调用方式

| 方式 | 文件 | 平台 | 用法 |
|------|------|------|------|
| Shell | `A0-protocol/shell/call.sh` | Linux/macOS | `echo "AI:weather;query,北京" \| ./call.sh` |
| PowerShell | `A0-protocol/shell/call.ps1` | Windows | `.\call.ps1 "AI:weather;query,北京"` |
| Python | `A0-protocol/python/call.py` | 跨平台 | `from call import call_directive` → `call_directive("AI:...")` |
| JavaScript | `A0-protocol/js/call.js` | 跨平台 | `const {callDirective} = require('./call'); await callDirective("AI:...")` |

### 配置

统一从同目录 `conf.json` 读取：

```json
{
  "endpoint": "http://127.0.0.1/text-cli/cli",
  "service_token": "",
  "access_token": ""
}
```

优先级：环境变量（`TEXT_CLI_ENDPOINT` / `TEXT_CLI_SERVICE_TOKEN` / `TEXT_CLI_ACCESS_TOKEN`） > `conf.json` > 内置默认。

### 响应解析

所有实现统一解析 SPEC v1.3 响应：`rst_types == "text"` → 提取 `rst_data.text`。

---

## A1 — Agent Skill 封装层

A1 提供三条路径：编译（造指令）、消费（调指令）、NoCode（写文档造指令）。

```
A1-skill/
├── python/
│   ├── cli.py              ← 编译路径：@register → SPEC v1.3 schema.json
│   ├── skill.py            ← 消费路径：Skill 基类 + @skill 装饰器
│   ├── handlers/           ← 示例处理器
│   └── skills/             ← 预置技能库（weather、translator）
├── nocode/
│   ├── README.md
│   └── zh/                 ← 中文 NoCode
│       ├── markdown_converter.py
│       └── 盆栽急救手册.md
├── skill/                  ← Agent Skill 定义模板
└── README_zh.md
```

### 编译路径（cli.py）

Agent 开发者用 `@register` 装饰器将既有函数包装为 text-cli 指令，自动生成 SPEC v1.3 兼容的 `schema.json`：

```python
from cli import register, serve

@register(domain="天气", action="查询", category="工具", trust="community")
def weather(params):
    return f"{params[0]}: 晴, 20°C"

serve(package_id="my-weather")
```

生成的 Schema 含 `id`/`type`/`runtime`/`category`/`trust`/`version`/`directives[]`，可直接 `AI:text-cli;install,my-weather` 安装。

### 消费路径（skill.py）

AI Agent 用 `@skill` 装饰器将指令封装为可复用的语义技能：

```python
from skill import Skill, skill

@skill("天气查询", domain="天气", action="查询")
class WeatherSkill(Skill):
    def format_result(self, raw):
        return f"[OK] {raw}"

    def on_error(self, params, error):
        return f"暂时无法查询{params[0]}的天气"

result = WeatherSkill.run("北京", "明天")
```

Skill 默认通过 `urllib` 直调 text-cli endpoint（零跨层依赖），解析 SPEC v1.3 响应格式。可通过 `call_fn` 参数注入自定义调用函数。

### NoCode 路径（nocode/）

非开发者写结构化 Markdown → `markdown_converter.py` 自动解析 → 注册为指令。`盆栽急救手册.md` 是一个花店老板的六篇笔记：

```bash
cd nocode/zh
python markdown_converter.py 盆栽急救手册.md
```

启动后 `AI:家庭园艺;盆栽急救,绿萝,叶片发黄` 返回养护建议。

### Agent Skill 定义（skill/）

| 文件 | 内容 |
|------|------|
| `SKILL.md` | 元指令调度 + 精品目录 + 多模态渲染 |
| `text-cli-core_zh.md` | System Prompt 模板 v2.0——含 tool 定义 |
| `text-cli-sync-skill.md` | 同步 Skill（概念设计） |
| `agent-text-cli-schema.example.json` | 聚合 Schema 示例（SPEC v1.3） |

## 构建

A0 和 A1 不参与骨架累积链。通过 `build-all.py` 直通模式从 `src/skeleton/base/` 同步到 `deploy/`。

---

_2026-07-16_

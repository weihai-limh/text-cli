# A1 — Agent Skill 封装层

> 将 text-cli 协议级调用封装为 AI Agent 可消费的 Skill。A0 是"怎么调"，A1 是"怎么让 AI 调"和"怎么造新指令"。

## 目录

```
A1-skill/
├── python/
│   ├── cli.py          ← @register 编译器（Agent 既有资源 → text-cli 指令）
│   ├── skill.py        ← Skill 基类 + @skill 装饰器（AI 消费侧）
│   ├── handlers/       ← 示例处理器（sample.py）
│   └── skills/         ← 预置技能库（weather、translator）
├── nocode/
│   ├── README.md       ← NoCode 入口说明
│   └── zh/             ← 中文 NoCode 内容
│       ├── markdown_converter.py  ← Markdown → 指令转化引擎
│       └── 盆栽急救手册.md         ← 结构化经验文档示例
├── skill/              ← Agent Skill 定义（System Prompt 模板）
│   ├── SKILL.md        ← Tide 核心调度 Skill
│   ├── text-cli-core_zh.md       ← 核心调度 v2.0（含 tool 定义）
│   ├── text-cli-sync-skill.md    ← 同步 Skill（概念设计）
│   └── agent-text-cli-schema.example.json  ← 聚合 Schema 示例
└── README_zh.md        ← 本文件
```

## 两条路径

| 路径 | 入口 | 受众 | 产物 |
|------|------|------|------|
| `cli.py` | `@register(domain, action, ...)` 装饰器 | Agent 开发者 | SPEC v1.3 `schema.json` |
| `nocode/zh/markdown_converter.py` | 结构化 Markdown 文档 | 非开发者（花店老板式用户） | SPEC v1.3 `schema.json` |

两者殊途同归——都生成 text-cli service 可安装的指令包 Schema。

## python/cli.py — 编译路径

```python
from cli import register, serve

@register(domain="天气", action="查询", category="工具", trust="community")
def weather(params):
    city = params[0]
    return f"{city}: 晴, 20°C"

serve(package_id="my-weather")  # 启动 HTTP 服务，自动生成 SPEC v1.3 Schema
```

生成的 Schema 包含 `id`/`type`/`runtime`/`category`/`trust`/`version`/`directives[]`——完全兼容 SPEC v1.3，可被 `AI:text-cli;install,my-weather` 直接安装。

## python/skill.py — 消费路径

```python
from skill import Skill, skill

@skill("天气查询", domain="天气", action="查询")
class WeatherSkill(Skill):
    def format_result(self, raw: str) -> str:
        return f"[OK] {raw}"

    def on_error(self, params, error):
        return f"暂时无法查询{params[0]}的天气"

result = WeatherSkill.run("北京", "明天")
```

Skill 默认通过 `urllib` 直接调用 text-cli endpoint（零跨层依赖），解析 SPEC v1.3 响应格式 `{"rst_types": "text", "rst_data": {"text": "..."}}`。可通过 `call_fn` 参数注入自定义调用函数。

## nocode/ — NoCode 路径

非开发者写 Markdown 经验文档 → `markdown_converter.py` 自动解析 → 注册为 text-cli 指令。

```markdown
## 指令定义
- 领域: 家庭园艺
- 动作: 盆栽急救
- 触发词: 盆栽, 叶子黄, 烂根

## 经验内容
### 绿萝
#### 叶片发黄
- 原因：浇水过多
- 急救：停止浇水，移到散射光处
```

```bash
cd nocode/zh
python markdown_converter.py 盆栽急救手册.md
```

启动后 `AI:家庭园艺;盆栽急救,绿萝,叶片发黄` 返回基于文档的养护建议。

## skill/ — Agent Skill 定义

| 文件 | 内容 |
|------|------|
| `SKILL.md` | 元指令调度 + 精品目录 + 多模态渲染规则 |
| `text-cli-core_zh.md` | System Prompt 模板 v2.0——含 `fetch_available_directives` 和 `text_cli` tool 定义 |
| `text-cli-sync-skill.md` | 同步 Skill（概念设计）——端点注册 + 多源拉取 + 聚合写入 |
| `agent-text-cli-schema.example.json` | 聚合 Schema 示例（SPEC v1.3 `directives[]` 格式） |

## 与 A0 的关系

A0 提供零依赖的协议级调用（`call.sh`/`call.ps1`/`call.py`/`call.js`）。A1 在 A0 之上构建两层：**生产侧**（`cli.py` + `nocode/`）让开发者造出新指令，**消费侧**（`skill.py` + `skill/`）让 AI 调用已有指令。A0 是"怎么调"，A1 是"怎么造 + 怎么让 AI 调"。

---

_2026-07-16_

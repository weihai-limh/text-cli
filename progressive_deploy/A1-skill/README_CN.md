# agent — Agent 侧 text-cli 工具包

> 让任何 AI Agent 都能调用和发布 text-cli 文本指令。
> — Tide 🌊

## 这是什么

`text_cli/agent/` 是面向 **AI Agent** 的工具包。它和 `text_cli/python/`（面向人类开发者的完整服务端模板）互补——开发者构建指令端点，Agent 消费和发布指令。

## 两种角色

| 角色 | 模块 | 场景 |
|------|------|------|
| **消费者** | [`call/README_CN.md`](call/README_CN.md) | 我是一个 Agent，我想调用已有的 text-cli 指令 |
| **生产者** | [`cli/README_CN.md`](cli/README_CN.md) | 我是一个 Agent，我想把我的能力发布为 text-cli 指令 |

实际使用中，一个 Agent 通常同时扮演两种角色。

## 按实现方式组织

| 实现方式 | call/（消费者） | cli/（生产者） |
|----------|----------------|----------------|
| **Python** | `call/python/` — SDK + Skill 技能封装 | `cli/python/` — @register 装饰器 + HTTP 服务 |
| **JS** | `call/js/` — Node.js fetch 调用 | 待扩展 |
| **Shell** | `call/shell/` — 最简 curl 调用 | — |
| **NoCode** | `CN/call/nocode/` — Agent 技能定义模板 | `CN/cli/nocode/` — Markdown → 指令转化引擎 |

## 60 秒上手

### 作为消费者：调用一条指令

```bash
# Shell 最简调用
cd call/shell
export TEXT_CLI_TOKEN="your-token"
./call.sh "AI:weather;query,明天,威海"
```

```python
# Python SDK
from call.python.call import call_directive
result = call_directive("AI:weather;query,明天,威海")
```

```js
// Node.js
const { callDirective } = require('./call/js/call');
const result = await callDirective('AI:weather;query,明天,威海');
```

### 作为生产者：发布一条指令

```python
# 用 @register 将既有函数变为指令
from cli.python.cli import register

@register("天气", "查询")
def weather(params):
    city = params[0]
    return f"{city}: 晴, 22°C"
```

### 非开发者：Markdown → 指令

```bash
# 写好你的经验 Markdown，一行启动
cd CN/cli/nocode
python markdown_converter.py 盆栽急救手册.md
# → 自动解析、注册、启动 HTTP 服务
```

## 文件索引

```
agent/
├── README.md                  ← 你在这里
├── call/                      ← 消费者：调用指令
│   ├── README_CN.md
│   ├── python/                ← Python SDK + Skill
│   │   ├── call.py            ← 函数式调用（单次 + 批量）
│   │   ├── skill.py           ← Skill 基类 + @skill 装饰器
│   │   └── skills/            ← 预置技能（天气、翻译）
│   ├── shell/
│   │   └── call.sh            ← 最简 curl 封装
│   ├── js/
│   │   └── call.js            ← Node.js fetch 调用（零依赖）
├── CN/                      ← 中文本地化实现
│   ├── README.md            ← CN 目录说明
│   ├── call/nocode/
│   │   └── text-cli-agent-skill.md  ← Agent 技能定义模板
│   └── cli/nocode/
│       ├── markdown_converter.py    ← Markdown → 指令 转化引擎
│       └── 盆栽急救手册.md          ← 结构化经验文档示例
└── cli/                       ← 生产者：发布指令
    ├── README_CN.md
    └── python/                ← Python 指令服务器
        ├── cli.py             ← @register + Schema + HTTP
        └── handlers/          ← 指令处理器（自动发现）
```

## 与其他模块的关系

```
text_cli/
├── python/          ← 面向上手的人类开发者（FastAPI 完整模板）
├── agent/           ← 面向 AI Agent（你在这里）
│   ├── call/        ← 消费指令，降低调用成本
│   └── cli/         ← 生产指令，将 Agent 能力开放出去
└── ...              ← 未来更多指令服务实现
```

`agent/cli` 可以和 `python/` 互操作——它们输出相同格式的指令服务，调用方无需区分来源。

## 设计原则

1. **零依赖优先**：Python 模块仅用标准库（除按需的 FastAPI 路径外）
2. **多层不互斥**：shell / python / nocode 各层独立，按场景选择
3. **协议即文档**：指令格式 `AI:领域;动作,参数...` 是人机共读的 API 约定（`指令:` 仍兼容）
4. **按实现方式组织**：`python/` `js/` `nocode/` 分层，不做 All-in-One

---

*Tide 🌊 — 思想的压力测试者，方案的共同设计者*

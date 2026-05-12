# CN — 中文本地化实现

此目录存放面向中文场景的 text-cli Agent 工具实现。与上层的 `call/` `cli/`（语言无关的通用实现）互补。

## 目录

```
CN/
├── README.md                      ← 你在这里
└── cli/
    └── nocode/
        ├── markdown_converter.py    ← Markdown → 指令 转化引擎
        └── 盆栽急救手册.md          ← 结构化经验文档示例
```

## 与通用实现的关系

| | 通用实现（call/ cli/） | CN 本地化（CN/） |
|---|---|---|
| **语言** | 代码和注释为英文 | 文档、注释、示例为中文 |
| **受众** | 全球 Agent 开发者 | 中文社区的非开发者、花店老板式用户 |
| **内容** | Python/JS/Shell SDK | Markdown 经验文档 + 转化引擎 |
| **扩展** | 按实现方式（python/js/shell） | 按场景（nocode / 未来可加其他中文场景） |

## 使用

### 非代码模式：Markdown → 指令

```bash
cd CN/cli/nocode
python markdown_converter.py 盆栽急救手册.md
```

启动后可立即通过 `curl -X POST http://localhost:8000/cli/text_cli` 调用指令。

### Agent 技能定义模板

`CN/call/nocode/text-cli-agent-skill.md` 是一份完整的 Agent 技能定义模板，包含 System Prompt + 工具描述 + 编排示例。将其复制到 Agent 的工作区即可使用。

---

*此目录由 Tide 🌊 维护，接受中文社区的贡献。*

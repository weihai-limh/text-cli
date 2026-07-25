# 文本差异（tc-diff）

路径管道用文本差异处理工具。行级统一差异、相似度比、补丁应用、词级差异。**零外部依赖，纯 stdlib difflib。**

## 安装

```
AI:text-cli;install,tc-diff
```

## 依赖

无。Python stdlib only（`difflib`、`re`、`json`）。

## 指令

| 指令 | 说明 |
|------|------|
| `tc-diff;unified,<文本A>,<文本B>[,<上下文行数>,<标签A>,<标签B>]` | 生成两段文本的统一差异 |
| `tc-diff;similarity,<文本A>,<文本B>` | 计算相似度比 (0.0-1.0) 和行数 |
| `tc-diff;patch,<原始文本>,<差异文本>` | 将差异应用到原始文本，还原目标 |
| `tc-diff;word-diff,<文本A>,<文本B>[,<格式>]` | 词级差异对比，输出 ops 或 HTML |

## 原理

```
                    ┌─────────────────┐
    文本A ──────→   │                 │
    文本B ──────→   │     tc-diff     │ ──→ unified diff / similarity / ops[]
                    │   (stdlib only)  │
    原始文本 ──→    │                 │ ──→ patched text
    差异文本 ──→    └─────────────────┘
```

差异不是终点——它是管道中间值。`unified` 产出差异，`patch` 消费并还原目标文本。形成完整的差异—还原闭环。

## 示例

### unified — 行级差异

```
AI:tc-diff;unified,第一行\n第二行\n第三行,第一行\n修改行\n第三行
→ {"status":"ok","has_diff":true,"diff":"--- a\n+++ b\n@@ -1,3 +1,3 @@\n 第一行\n-第二行\n+修改行\n 第三行"}
```

### similarity — 快速判断

```
AI:tc-diff;similarity,{step1.content},{step2.content}
→ {"status":"ok","ratio":0.873,"lines_a":42,"lines_b":45,"equal":false}

# ratio > 0.8 → 值得细看差异
# ratio < 0.3 → 文档大幅重写，跳过细看直接报告
```

### patch — 差异—还原闭环

```
AI:tc-markdown;read,original.md → {step1.content}
AI:tc-markdown;read,modified.md → {step2.content}
AI:tc-diff;unified,{step1.content},{step2.content} → {step3.diff}
AI:tc-diff;patch,{step1.content},{step3.diff}
→ {"status":"ok","patched":"(还原后的完整文本)","hunks_applied":2,"hunks_total":2}
```

### word-diff — 词级精细对比

```
AI:tc-diff;word-diff,The quick brown fox,The quick red fox jumps
→ {"status":"ok","format":"ops","ratio":0.72,"operations":[
    {"type":"equal","value":"The quick "},
    {"type":"replace","old":"brown","new":"red"},
    {"type":"equal","value":" fox"},
    {"type":"insert","value":" jumps"}
  ]}
```

## 架构

```
tc-diff/
├── DESIGN.md               ← 设计文档
├── schema.json             ← 4 条指令声明
├── handler.py              ← handler 实现
└── README_CN.md            ← 本文件
```

纯无状态管道处理器。不读文件、不写磁盘、不依赖外部模块。

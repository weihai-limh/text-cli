# tc-markdown 阅读器

读取和解析 Markdown 文件：全文提取、标题结构、章节内容。

## 安装

```
AI:text-cli;install,tc-markdown
```

## 依赖

零依赖（纯 Python stdlib）。

## 指令

| 指令 | 说明 |
|------|------|
| `tc-markdown;读取,<路径>` | 读取 Markdown 文件全文 |
| `tc-markdown;标题,<路径>` | 提取标题结构（级别/文本/行号） |
| `tc-markdown;章节,<路径>,<标题>` | 提取指定标题下的内容 |

## 示例

```
AI:tc-markdown;读取,/root/docs/README.md
AI:tc-markdown;标题,/root/docs/README.md
AI:tc-markdown;章节,/root/docs/README.md,安装
```

## 安全

文件访问限制在初始化时配置的基础目录范围内，防止路径穿越。

## 架构

```
tc-markdown/
├── schema.json
├── handler.py
└── README_CN.md
```

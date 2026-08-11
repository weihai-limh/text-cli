# 压缩归档（tc-archive）

路径管道用压缩归档处理工具。创建、解压、列出归档文件。**零外部依赖，纯 stdlib zipfile + tarfile。**

## 安装

```
AI:text-cli;install,tc-archive
```

## 依赖

无。Python stdlib only（`zipfile`、`tarfile`、`pathlib`）。

## 指令

| 指令 | 说明 |
|------|------|
| `tc-archive;create,<包路径>,<源路径>[,<格式>]` | 创建压缩归档 |
| `tc-archive;extract,<包路径>,<目标目录>` | 解压归档 |
| `tc-archive;list,<包路径>` | 列出归档内容 |

## 支持格式

| 格式 | 扩展名 |
|------|--------|
| ZIP | `.zip` |
| TAR（无压缩） | `.tar` |
| TAR + Gzip | `.tar.gz` `.tgz` |
| TAR + Bzip2 | `.tar.bz2` `.tbz2` |
| TAR + LZMA | `.tar.xz` |

## 安全

- **路径白名单**：所有操作限制在配置的目录内（默认 `./`）
- **路径穿越防御**：拒绝包含 `..` 或绝对路径的归档条目
- **zip bomb 防御**：限制总解压大小（500MB）、文件数（10000）、单文件大小（100MB）

配置见 `config/tc_archive.json`。

## 示例

### create — 创建归档

```
AI:tc-archive;create,project.zip,./my_project
→ {"status":"ok","path":"project.zip","format":"zip","size_human":"1.95 MB","files":42}

AI:tc-archive;create,data.tar.gz,./data,tar.gz
→ {"status":"ok","path":"data.tar.gz","format":"tar.gz","size_human":"850.32 KB","files":15}
```

### extract — 解压

```
AI:tc-archive;extract,project.zip,./extracted
→ {"status":"ok","path":"./extracted","files":42,"size_human":"4.88 MB"}
```

### list — 列出内容

```
AI:tc-archive;list,project.zip
→ {"status":"ok","path":"project.zip","format":"zip","files":42,
    "entries":[{"name":"README.md","size":1024,"type":"file"},...]}
```

## 架构

```
tc-archive/
├── DESIGN.md               ← 设计文档
├── schema.json             ← 3 条指令声明
├── handler.py              ← handler 实现
├── config/
│   └── tc_archive.json     ← 安全白名单配置
└── README_CN.md            ← 本文件
```

# tc MCP 桥接 — GitHub

通过 MCP 桥接调用 GitHub API，使用官方 `@modelcontextprotocol/server-github` 服务端。委托 mcporter 进行 MCP 通信。7 条指令覆盖仓库搜索、文件读取、Issue/PR 管理和提交记录。

> **runtime: `mcp`** — 经 service A7 MCP dispatch 管线，不依赖 Python handler。`install` 前需在 mcporter 中配置好 GitHub server。

## 安装

```
AI:text-cli;install,tc-mcp-github
```

## 依赖

- `mcporter` CLI（MCP 客户端）
- GitHub MCP 服务端：`@modelcontextprotocol/server-github`
- 凭据：GitHub Personal Access Token (classic)，需 repo + read:org 权限
- 无 pip 依赖

## 指令

| 指令 | 说明 |
|------|------|
| `comcp-github;search_repos,<关键词>[,<页码>[,<每页>]]` | 搜索仓库(中文别名:搜索仓库) |
| `comcp-github;get_file,<owner>,<repo>,<路径>[,<分支>]` | 读取文件内容(中文别名:获取文件) |
| `comcp-github;list_commits,<owner>,<repo>[,<sha>[,<页码>]]` | 分支提交记录(中文别名:提交记录) |
| `comcp-github;search_issues,<查询>[,<排序>[,<页码>]]` | 搜索 Issue/PR(中文别名:搜索工单) |
| `comcp-github;list_issues,<owner>,<repo>[,<状态>[,<标签>]]` | 仓库 Issue 列表(中文别名:工单列表) |
| `comcp-github;create_issue,<owner>,<repo>,<标题>[,<正文>[...]]` | 创建 Issue(中文别名:创建工单) |
| `comcp-github;create_pr,<owner>,<repo>,<标题>,<head>,<base>[...]` | 创建 Pull Request(中文别名:创建PR) |

> 规范入口使用英文 action(如上);中文别名(搜索仓库等)经运行时归一化到规范名,二者等效。

## 示例

```
comcp-github;search_repos,text-cli language:python
comcp-github;get_file,weihai-limh,text-cli,README.md
comcp-github;create_issue,weihai-limh,text-cli,发现一个bug,问题描述
```

## 架构

```
tc-mcp-github/
├── schema.json              ← 指令声明（7 条指令，runtime: mcp）
└── service-descriptor.json  ← mcporter 路由映射（action → MCP tool）
```

执行路径：
1. service MCP dispatch 管线命中 `comcp-github` 域
2. `decide_backend()` 查 `routing_preferences.json`，返回 `mcp`
3. `adapt_params()` 将 text-cli 参数映射为 MCP 命名参数
4. `mcporter call github tools/call` 与 MCP 服务端通信
5. MCP content 数组解包后作为文本返回

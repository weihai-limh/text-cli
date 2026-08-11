# tc MCP Bridge — GitHub

GitHub API via MCP bridge using the official `@modelcontextprotocol/server-github` server. Delegates to mcporter for MCP communication. 7 directives covering repository search, file access, issue/PR management, and commit listing.

> **runtime: `mcp`** — routed through service A7 MCP dispatch pipeline. No Python handler needed. Configure GitHub server in mcporter before `install`.

## Install

```
AI:text-cli;install,tc-mcp-github
```

## Dependencies

- `mcporter` CLI (MCP client)
- GitHub MCP server: `@modelcontextprotocol/server-github`
- Credential: GitHub Personal Access Token (classic, with repo + read:org scopes)
- No pip dependencies

## Directives

| Instruction | Description |
|-------------|-------------|
| `comcp-github;search_repos,<query>[,<page>[,<perPage>]]` | Search repositories |
| `comcp-github;get_file,<owner>,<repo>,<path>[,<branch>]` | Read file contents |
| `comcp-github;list_commits,<owner>,<repo>[,<sha>[,<page>]]` | List branch commits |
| `comcp-github;search_issues,<query>[,<order>[,<page>]]` | Search issues/PRs |
| `comcp-github;list_issues,<owner>,<repo>[,<state>[,<labels>]]` | List repo issues |
| `comcp-github;create_issue,<owner>,<repo>,<title>[,<body>[...]]` | Create issue |
| `comcp-github;create_pr,<owner>,<repo>,<title>,<head>,<base>[...]` | Create pull request |

## Example

```
comcp-github;search_repos,text-cli language:python
comcp-github;get_file,weihai-limh,text-cli,README.md
comcp-github;create_issue,weihai-limh,text-cli,Found a bug,Description here
```

## Architecture

```
tc-mcp-github/
├── schema.json              ← directive declarations (7 directives, runtime: mcp)
└── service-descriptor.json  ← mcporter route mapping (action → MCP tool)
```

Execution path:
1. service MCP dispatch pipeline matches `comcp-github` domain
2. `decide_backend()` consults `routing_preferences.json`, returns `mcp`
3. `adapt_params()` maps text-cli positional params to MCP named params
4. `mcporter call github tools/call` communicates with the MCP server
5. MCP content array is unwrapped and returned as text

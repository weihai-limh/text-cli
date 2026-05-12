# text-cli-copilot · Base Handlers

**Pure protocol layer — zero Agent framework dependencies.**

These handlers use only Python stdlib + the copilot `core` module. They work with any AI Agent that can make HTTP calls and handle JSON responses. No framework-specific imports.

## Handlers

| File       | Directives                                                     | Description                           |
|------------|----------------------------------------------------------------|---------------------------------------|
| `media.py` | `media;load` (媒体;加载), `media;download` (媒体;下载)          | Load media from URL or local path     |
| `render.py`| `resource;render` (资源;渲染)                                   | Output `rst_types` + URL for Agent    |
| `proxy.py` | `proxy;dispatch` (聚合;分发)                                    | Route to multiple text-cli endpoints  |
| `mcp.py`   | `mcp;deploy` (MCP;部署)                                         | Compile MCP config → text-cli schema  |

## Config Templates

| File                            | Description                                           |
|---------------------------------|-------------------------------------------------------|
| `terminal_render.example.json`  | Trigger→render instruction mapping. Copy and populate.|

## Tools

| Path                    | Description                                              |
|-------------------------|----------------------------------------------------------|
| `tools/mcp2textcli/`    | MCP config → schema compiler. Required by `mcp.py`.      |

## Install

```bash
cp examples/text-cli-copilot/base/*.py copilot_handlers/
# If using mcp.py:
cp -r examples/text-cli-copilot/base/tools/ copilot_tools/
```

---

# text-cli-copilot · 基础处理器

**纯协议层——零 Agent 框架依赖。**

这些处理器仅使用 Python 标准库 + copilot `core` 模块。任何能够发起 HTTP 调用并处理 JSON 响应的 AI Agent 都可使用。无框架特定导入。

## 处理器

| 文件       | 指令                                                            | 说明                               |
|------------|----------------------------------------------------------------|------------------------------------|
| `media.py` | `media;load` (别名: 媒体;加载), `media;download` (别名: 媒体;下载)| 从 URL 或本地路径加载媒体           |
| `render.py`| `resource;render` (别名: 资源;渲染)                              | 输出 `rst_types` + URL 供 Agent 使用 |
| `proxy.py` | `proxy;dispatch` (别名: 聚合;分发)                               | 路由到多个 text-cli 端点           |
| `mcp.py`   | `mcp;deploy` (别名: MCP;部署)                                    | 编译 MCP 配置 → text-cli schema    |

## 配置模板

| 文件                            | 说明                                              |
|---------------------------------|--------------------------------------------------|
| `terminal_render.example.json`  | 触发→渲染指令映射表模板。复制后填充即可。           |

## 工具

| 路径                    | 说明                                                   |
|-------------------------|--------------------------------------------------------|
| `tools/mcp2textcli/`    | MCP 配置 → schema 编译器。`mcp.py` 依赖此工具。         |

## 安装

```bash
cp examples/text-cli-copilot/base/*.py copilot_handlers/
# 如使用 mcp.py:
cp -r examples/text-cli-copilot/base/tools/ copilot_tools/
```

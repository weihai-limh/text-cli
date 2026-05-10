# text-cli-copilot · Base Handlers

**Pure protocol layer — zero Agent framework dependencies.**

These handlers use only Python stdlib + the copilot `core` module. They work with any AI Agent that can make HTTP calls and handle JSON responses. No framework-specific imports.

## Handlers

| File       | Directives                        | Description                           |
|------------|-----------------------------------|---------------------------------------|
| `media.py` | `图片;加载`, `视频;加载` etc.     | Load media from URL or local path     |
| `render.py`| `资源;渲染`                       | Output `rst_types` + URL for Agent    |
| `proxy.py` | `聚合;分发`                       | Route to multiple text-cli endpoints  |

## Install

```bash
cp examples/text-cli-copilot/base/*.py copilot_handlers/
```

---

# text-cli-copilot · 基础处理器

**纯协议层——零 Agent 框架依赖。**

这些处理器仅使用 Python 标准库 + copilot `core` 模块。任何能够发起 HTTP 调用并处理 JSON 响应的 AI Agent 都可使用。无框架特定导入。

## 处理器

| 文件       | 指令                              | 说明                               |
|------------|-----------------------------------|------------------------------------|
| `media.py` | `图片;加载`, `视频;加载` 等       | 从 URL 或本地路径加载媒体           |
| `render.py`| `资源;渲染`                       | 输出 `rst_types` + URL 供 Agent 使用 |
| `proxy.py` | `聚合;分发`                       | 路由到多个 text-cli 端点           |

## 安装

```bash
cp examples/text-cli-copilot/base/*.py copilot_handlers/
```

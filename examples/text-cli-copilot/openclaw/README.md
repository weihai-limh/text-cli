# text-cli-copilot · OpenClaw Handlers

**Framework-specific — requires OpenClaw Agent runtime.**

These handlers leverage OpenClaw-specific tools (`lightclaw_upload_file`, channel-aware rendering) that are not available in generic Agent frameworks. Install only if your copilot runs under OpenClaw.

## Handlers

| File        | Directives      | Description                                    |
|-------------|-----------------|------------------------------------------------|
| `render.py` | `资源;渲染`     | Channel-aware media rendering (localfile://)    |

## Install

```bash
cp examples/text-cli-copilot/openclaw/render.py copilot_handlers/render.py
```

## Channel Rendering Rules

| Channel       | Rendering Method                          |
|---------------|-------------------------------------------|
| lightclawbot  | `lightclaw_upload_file` → `localfile://`  |
| Discord       | `message(media=url)`                      |
| Telegram      | `message(media=url)`                      |
| Other         | Plain URL text                            |

---

# text-cli-copilot · OpenClaw 处理器

**框架特定——需要 OpenClaw Agent 运行时。**

这些处理器利用 OpenClaw 专属工具（`lightclaw_upload_file`、渠道感知渲染），不适用于通用 Agent 框架。仅在 copilot 运行在 OpenClaw 环境中时安装。

## 处理器

| 文件        | 指令          | 说明                                    |
|-------------|---------------|-----------------------------------------|
| `render.py` | `资源;渲染`   | 渠道感知媒体渲染（localfile://）         |

## 安装

```bash
cp examples/text-cli-copilot/openclaw/render.py copilot_handlers/render.py
```

## 渠道渲染规则

| 渠道          | 渲染方法                                   |
|---------------|-------------------------------------------|
| lightclawbot  | `lightclaw_upload_file` → `localfile://`  |
| Discord       | `message(media=url)`                      |
| Telegram      | `message(media=url)`                      |
| 其他          | 纯 URL 文本                               |

# text-cli-copilot · OpenClaw Handlers

**Framework-specific — requires OpenClaw Agent runtime.**

These handlers leverage OpenClaw-specific tools (e.g. `lightclaw_upload_file`, channel-aware dispatch) that are not available in generic Agent frameworks. Install only if your copilot runs under OpenClaw.

## Available Handlers

| File | Directives | Description |
|------|-----------|-------------|
| *(empty)* | — | Placeholder. Add your OpenClaw-specific handlers here. |

## Adding a Handler

```bash
cp your_openclaw_handler.py copilot_handlers/
```

## Channel Rendering Rules (reference)

| Channel | Rendering Method |
|---------|-----------------|
| lightclawbot | `lightclaw_upload_file` → `localfile://` |
| Discord | `message(media=url)` |
| Telegram | `message(media=url)` |

---

# text-cli-copilot · OpenClaw 处理器

**框架特定——需要 OpenClaw Agent 运行时。**

这些处理器利用 OpenClaw 专属工具（如 `lightclaw_upload_file`、渠道感知分发），不适用于通用 Agent 框架。仅在 copilot 运行在 OpenClaw 环境中时安装。

## 可用处理器

| 文件 | 指令 | 说明 |
|------|------|------|
| *（空）* | — | 占位目录。将你的 OpenClaw 专属处理器放这里。 |

## 添加处理器

```bash
cp your_openclaw_handler.py copilot_handlers/
```

## 渠道渲染规则（参考）

| 渠道 | 渲染方法 |
|------|---------|
| lightclawbot | `lightclaw_upload_file` → `localfile://` |
| Discord | `message(media=url)` |
| Telegram | `message(media=url)` |

# Media Loading

**Directives:** `图片;加载`, `视频;加载`, `音频;加载`, `文件;加载`
**Dependencies:** None (stdlib only)
**Configuration:** `PATH_WHITELIST` (edit handler.py)

Load and serve media files. Public URLs are passed through directly. Local files are validated against a whitelist and served via the copilot's `/media/` endpoint.

## Install

```bash
cp examples/text-cli/media/handler.py server/python/handlers/media.py
# Edit PATH_WHITELIST in handler.py — add your media directories
```

## Usage

```
AI:图片;加载,https://example.com/photo.jpg
AI:图片;加载,/local/path/to/photo.jpg
```

---

# 媒体加载

**指令:** `图片;加载`, `视频;加载`, `音频;加载`, `文件;加载`
**依赖:** 无（仅用标准库）
**配置:** `PATH_WHITELIST`（编辑 handler.py）

加载和提供媒体文件。公网 URL 直接透传。本地文件经白名单校验后通过 copilot 的 `/media/` 端点提供。

## 安装

```bash
cp examples/text-cli/media/handler.py server/python/handlers/media.py
# 编辑 handler.py 中的 PATH_WHITELIST — 添加媒体文件目录
```

## 使用

```
指令:图片;加载,https://example.com/photo.jpg
指令:图片;加载,/local/path/to/photo.jpg
```

# tc-media · tc媒体

加载和下载媒体文件。公网 URL 直接透传，本地文件经白名单校验。

## 安装

```
AI:text-cli;install,tc-media
```

## 依赖

- `requests`（pip）：HTTP 下载支持。

## 配置

编辑 handler.py 中的 `PATH_WHITELIST` 添加本地媒体目录。
设置 `MEDIA_DOWNLOAD_DIR` 环境变量更改下载目标（默认 `/tmp/media`）。

## 指令

| 指令 | 说明 |
|------|------|
| `image;load,<URL或路径>` | 加载/透传图片 |
| `video;load,<URL或路径>` | 加载/透传视频 |
| `audio;load,<URL或路径>` | 加载/透传音频 |
| `file;load,<URL或路径>` | 加载/透传文件 |
| `media;download,<URL>[,<保存名>]` | 下载媒体到本地 |

中文别名：`图片;加载` `视频;加载` `音频;加载` `文件;加载` `媒体;下载`

## 示例

```
AI:图片;加载,https://example.com/photo.jpg
→ {"status": "ok", "type": "picture", "url": "https://example.com/photo.jpg"}

AI:媒体;下载,https://example.com/video.mp4
→ {"status": "ok", "type": "video", "name": "abc123.mp4", "size": 5242880}
```

## 架构

```
Python 包（含 pip 依赖）
  ├── handler.py    — @directive 注册 + HTTP + 文件系统
  └── schema.json   — 5 条指令
```

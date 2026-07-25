# image · 图片处理

图片信息读取、base64 编码、格式转换与缩放（基于 Pillow）。

## 安装

```
AI:text-cli;install,image
```

## 依赖

- `Pillow`（pip）：图片处理库。

## 指令

| 指令 | 说明 |
|------|------|
| `image;info,<路径>[,json]` | 读取尺寸、格式、EXIF。加 `json` 返回结构化数据 |
| `image;encode,<路径>[,<最大尺寸>[,json]]` | Base64 编码存入缓存，供 VL 管道使用 |
| `image;convert,<输入>,<格式>[,<质量>[,json]]` | 格式转换（png/jpg/webp/bmp） |
| `image;resize,<输入>,<宽>,<高>[,json]` | 等比缩放 |

中文别名：`图片;信息` `图片;编码` `图片;转换` `图片;缩放`

## 示例

### 给人/AI 看（默认）

```
AI:image;info,/tmp/photo.jpg
→ 4032x3024  JPEG  3.2MB  mode=RGB
  GPS: 37.4219°N, 122.0840°W
  Capture time: 2026:05:15 14:30:00
  Device: iPhone 15 Pro

AI:image;encode,/tmp/photo.jpg
→ cache:a1b2c3d4e5f6a7b8
  original: 4032x3024 JPEG 3.2MB
  encoded:  1024x768 JPEG base64 1.8MB
  expires:  300s

AI:image;convert,/tmp/photo.jpg,png,90
→ Converted → /tmp/photo.png  (4032x3024  PNG)

AI:image;resize,/tmp/photo.jpg,800,600
→ Resized 4032x3024 → 800x600  → /tmp/photo_800x600.jpg
```

### 给管道用（加 `json`）

```
AI:image;info,/tmp/photo.jpg,json
→ {"status":"ok","width":4032,"height":3024,"format":"JPEG","size_bytes":3200000,"mode":"RGB"}

AI:image;encode,/tmp/photo.jpg,1024,json
→ {"status":"ok","cache_key":"a1b2c3d4e5f6a7b8","original":"4032x3024 JPEG 3.2MB","encoded":"1024x768 JPEG base64 1.8MB","expires_seconds":300}

AI:image;convert,/tmp/photo.jpg,png,90,json
→ {"status":"ok","path":"/tmp/photo.png","width":4032,"height":3024,"format":"PNG"}

AI:image;resize,/tmp/photo.jpg,800,600,json
→ {"status":"ok","path":"/tmp/photo_800x600.jpg","width":800,"height":600,"original_width":4032,"original_height":3024}
```

## 架构

```
Python 包（含 pip 依赖）
  ├── handler.py    — @directive 注册 + Pillow 操作
  └── schema.json   — 4 条指令
  └── config/       — 可选：路径白名单配置

## 已知改进方向（2026-06-03）

以下问题已通过 test 验证、功能正确，但 AI 使用体验有摩擦，留待后续迭代：

### 1. `allowed_paths` 白名单对 AI 不透明

安装后默认无可读路径，AI 调用时收到 `image not configured. Edit allowed_paths` 后不知道哪些路径允许。

**改进方向**：考虑默认开放常用临时目录（如 `/tmp/`），或提供 `image;paths` 指令列出已允许的路径。

### 2. `encode` 返回缓存 key 而非 base64 本体

`image;encode` 返回 `cache:xxx` 键名，base64 数据存在 A3 内存缓存中（300s TTL）。管道下一步无法直接消费图片内容——必须先理解 `cache:xxx` 协议。

**改进方向**：考虑提供 `image;encode,<path>,inline` 直接返回 base64，跳过缓存层；或让 A3 支持 `cache:xxx` 自动解析。

### 3. `convert`/`resize` 输出路径不可预测

输出文件名由 `with_suffix` / `{stem}_{w}x{h}{suffix}` 自动生成，AI 在调用前无法预判输出路径。管道消费依赖 JSON 模式的 `path` 字段回传。

**改进方向**：支持显式输出路径参数 `image;convert,<in>,<fmt>,<quality>,<out_path>`。
```

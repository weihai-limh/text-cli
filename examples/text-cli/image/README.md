# Image Processing

**Directives:** `图片;信息` / `image;info`, `图片;编码` / `image;encode`
**Dependencies:** Pillow (`pip install Pillow`)
**Configuration:** None (no secrets)

Extract EXIF metadata (GPS, time, device, dimensions) and encode images for AI vision API consumption. Cache layer returns `cache:<sha256>` references to avoid passing base64 in payloads.

## Install

```bash
cp examples/text-cli/image/handler.py server/python/handlers/image.py
pip install Pillow
```

## Usage

```
AI:image;info,/path/to/photo.jpg
AI:image;encode,/path/to/photo.jpg
AI:ai_inference;vision,Describe the scene,cache:<sha256>
```

---

# 图像处理

**指令:** `图片;信息` / `image;info`, `图片;编码` / `image;encode`
**依赖:** Pillow (`pip install Pillow`)
**配置:** 无（不含密钥）

提取 EXIF 元数据（GPS、时间、设备、尺寸）并将图像编码供 AI 视觉 API 使用。缓存层返回 `cache:<sha256>` 引用，避免在请求中传输 base64。

## 安装

```bash
cp examples/text-cli/image/handler.py server/python/handlers/image.py
pip install Pillow
```

## 使用

```
指令:image;info,/path/to/photo.jpg
指令:image;encode,/path/to/photo.jpg
指令:AI辅助;视觉,描述这个场景,cache:<sha256>
```

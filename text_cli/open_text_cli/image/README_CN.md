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
| `image;info,<路径>` | 读取尺寸、格式、EXIF |
| `image;encode,<路径>[,<最大尺寸>]` | Base64 编码存入缓存 |
| `image;convert,<输入>,<格式>[,<质量>]` | 格式转换（png/jpg/webp/bmp） |
| `image;resize,<输入>,<宽>,<高>` | 等比缩放 |

中文别名：`图片;信息` `图片;编码` `图片;转换` `图片;缩放`

## 示例

```
AI:图片;信息,/tmp/photo.jpg
→ {"format": "JPEG", "width": 4032, "height": 3024, "mode": "RGB"}

AI:图片;转换,/tmp/photo.jpg,png,90
→ Converted: /tmp/photo.png (PNG, quality=90)
```

## 架构

```
Python 包（含 pip 依赖）
  ├── handler.py    — @directive 注册 + Pillow 操作
  └── schema.json   — 4 条指令
```

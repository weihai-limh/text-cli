# image

Image inspection, base64 encoding, format conversion, and resizing via Pillow.

## Install

```
AI:text-cli;install,image
```

## Dependencies

- `Pillow` (pip): image processing library.

## Directives

| Directive | Description |
|-----------|-------------|
| `image;info,<path>[,json]` | Read dimensions, format, EXIF. Add `json` for structured output |
| `image;encode,<path>[,<max_size>[,json]]` | Base64-encode to cache for VL pipeline |
| `image;convert,<in>,<fmt>[,<q>[,json]]` | Convert format (png/jpg/webp/bmp) |
| `image;resize,<in>,<w>,<h>[,json]` | Proportional resize |

## Example

### Human/AI consumption (default)

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

### Pipeline consumption (add `json`)

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

## Architecture

```
Python package with pip dependency
  ├── handler.py    — @directive registration + Pillow operations
  ├── schema.json   — 4 directives
  └── config/       — optional: path whitelist configuration
```

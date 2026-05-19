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
| `image;info,<path>` | Read dimensions, format, EXIF |
| `image;encode,<path>[,<max_size>]` | Base64-encode to cache |
| `image;convert,<in>,<fmt>[,<q>]` | Convert format (png/jpg/webp/bmp) |
| `image;resize,<in>,<w>,<h>` | Proportional resize |

## Example

```
AI:image;info,/tmp/photo.jpg
→ {"format": "JPEG", "width": 4032, "height": 3024, "mode": "RGB"}

AI:image;convert,/tmp/photo.jpg,png,90
→ Converted: /tmp/photo.png (PNG, quality=90)

AI:image;resize,/tmp/photo.jpg,800,600
→ Resized: /tmp/photo_800x600.jpg (800x600)
```

## Architecture

```
Python package with pip dependency
  ├── handler.py    — @directive registration + Pillow operations
  └── schema.json   — 4 directives
```

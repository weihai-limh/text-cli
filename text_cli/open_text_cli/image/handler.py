"""
image — Open text-cli image capability plugin handler.

Extends the protocol's image vocabulary beyond basic inspection (A3 skeleton image.py).
Depends on Pillow for format conversion, resizing, and advanced operations.

Directives:
    图片:信息,<path>
    图片:转换,<path>,<format>[,<quality>]
    图片:缩放,<path>,<width>,<height>
    image:info,<path>
    image:convert,<in_path>,<out_format>[,<quality>]
    image:resize,<in_path>,<width>,<height>
"""
from __future__ import annotations

import io
import logging
import pathlib

from PIL import Image

from core.registry import directive

logger = logging.getLogger("text-cli.image")

SUPPORTED_FORMATS = frozenset({"png", "jpeg", "jpg", "webp", "gif", "bmp"})
SUPPORTED_OUTPUT = frozenset({"png", "jpg", "webp", "bmp"})


def _normalize_format(fmt: str) -> str:
    """Normalise format name to lowercase, map aliases."""
    mapping = {"jpeg": "jpg", "jpe": "jpg"}
    return mapping.get(fmt, fmt)


@directive("图片", "信息")
@directive("image", "info")
def picture_info(params: list[str]) -> str:
    """Return extended image metadata including EXIF if available."""
    if not params:
        return "image:info — usage: <path>"
    path = pathlib.Path(params[0])
    if not path.exists():
        return f"Error: file not found — {path}"
    try:
        img = Image.open(path)
        info = {
            "path": str(path),
            "format": img.format or "unknown",
            "mode": img.mode,
            "size": f"{img.width}x{img.height}",
            "frames": getattr(img, "n_frames", 1),
        }
        # Attempt EXIF extraction (JPEG/TIFF only)
        exif = img.getexif()
        if exif:
            readable = {}
            for tag_id, value in exif.items():
                from PIL.ExifTags import TAGS
                tag_name = TAGS.get(tag_id, str(tag_id))
                if isinstance(value, bytes):
                    continue  # skip raw binary tags
                readable[tag_name] = str(value)
            if readable:
                info["exif"] = readable
        img.close()
        lines = [f"{k}: {v}" for k, v in info.items() if k != "exif"]
        if "exif" in info:
            lines.append("exif:")
            for k, v in info["exif"].items():
                lines.append(f"  {k}: {v}")
        return "\n".join(lines)
    except Exception as exc:
        return f"Error reading image: {exc}"


@directive("图片", "转换")
@directive("image", "convert")
def picture_convert(params: list[str]) -> str:
    """Convert an image to another format.  Usage: <in_path>,<out_format>[,<quality>]"""
    if len(params) < 2:
        return "image:convert — usage: <in_path>,<out_format>[,<quality>]"
    in_path = pathlib.Path(params[0])
    out_fmt = _normalize_format(params[1].lower())
    quality = int(params[2]) if len(params) > 2 else 85
    if out_fmt not in SUPPORTED_OUTPUT:
        return f"Error: unsupported output format — {out_fmt}. Supported: {', '.join(sorted(SUPPORTED_OUTPUT))}"
    if quality < 1 or quality > 100:
        return "Error: quality must be 1–100"
    if not in_path.exists():
        return f"Error: file not found — {in_path}"
    try:
        img = Image.open(in_path)
        out_path = in_path.with_suffix(f".{out_fmt}")
        # Ensure RGB for formats that don't support alpha
        if out_fmt in ("jpg", "bmp") and img.mode in ("RGBA", "P", "LA"):
            rgb = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                rgb.paste(img, mask=img.split()[-1])
            else:
                rgb.paste(img)
            img.close()
            img = rgb
        img.save(out_path, format="JPEG" if out_fmt == "jpg" else None,
                 quality=quality if out_fmt in ("jpg", "webp") else None)
        img.close()
        return f"Converted → {out_path} ({img.width}x{img.height})"
    except Exception as exc:
        return f"Error converting image: {exc}"


@directive("图片", "缩放")
@directive("image", "resize")
def picture_resize(params: list[str]) -> str:
    """Resize an image.  Usage: <in_path>,<width>,<height>"""
    if len(params) < 3:
        return "image:resize — usage: <in_path>,<width>,<height>"
    in_path = pathlib.Path(params[0])
    try:
        width = int(params[1])
        height = int(params[2])
    except ValueError:
        return "Error: width and height must be integers"
    if width < 1 or height < 1:
        return "Error: dimensions must be positive"
    if not in_path.exists():
        return f"Error: file not found — {in_path}"
    try:
        img = Image.open(in_path)
        original = img.size
        img = img.resize((width, height), Image.LANCZOS)
        out_path = in_path.parent / f"{in_path.stem}_{width}x{height}{in_path.suffix}"
        img.save(out_path, quality=85)
        img.close()
        return f"Resized {original[0]}x{original[1]} → {width}x{height} → {out_path}"
    except Exception as exc:
        return f"Error resizing image: {exc}"

"""
Image capability handler — text-cli instruction package.

Covers basic inspection (EXIF, dimensions), base64 encoding for VL pipeline,
format conversion, and resizing.  Depends on Pillow.

Directives:
    image;info,<path>                    → dimensions, format, EXIF
    image;encode,<path>[,<max_size>]     → base64 cache entry
    image;convert,<in_path>,<fmt>[,<q>]  → format conversion
    image;resize,<in_path>,<w>,<h>       → proportional resize

"""

from __future__ import annotations

import base64
import hashlib
import io
import logging
import pathlib
import time

from PIL import Image

from core.registry import directive

logger = logging.getLogger("text-cli.image")

# ── Constants ────────────────────────────────────

SUPPORTED_OUTPUT = frozenset({"png", "jpg", "webp", "bmp"})

_PATH_WHITELIST = [
    "/root/.openclaw/workspace/",
    "/root/text-cli/copilot/",
    "/root/text-cli/media/",
    "/root/.openclaw/media/",
]

# ── Path validation ──────────────────────────────

def _check_path(path_str: str) -> pathlib.Path | None:
    """Resolve and validate a path against the whitelist."""
    try:
        p = pathlib.Path(path_str).resolve()
    except (OSError, ValueError):
        return None
    for entry in _PATH_WHITELIST:
        try:
            p.relative_to(entry)
            return p
        except ValueError:
            continue
    return None


# ── In-memory cache ──────────────────────────────

_cache: dict[str, dict] = {}
_CACHE_TTL = 300  # seconds


def _cache_put(data: str) -> str:
    """Store data in cache, return a 16-char key."""
    key = hashlib.sha256(data.encode()).hexdigest()[:16]
    _cache[key] = {"data": data, "expires_at": time.time() + _CACHE_TTL}
    now = time.time()
    for k in list(_cache):
        if _cache[k]["expires_at"] < now:
            del _cache[k]
    return key


def cache_get(key: str) -> str | None:
    """Retrieve cached data; returns None if expired or missing."""
    entry = _cache.get(key)
    if not entry or entry["expires_at"] < time.time():
        _cache.pop(key, None)
        return None
    return entry["data"]


# ── Helpers ──────────────────────────────────────

def _human_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f}KB"
    return f"{n}B"


def _normalise_format(fmt: str) -> str:
    mapping = {"jpeg": "jpg", "jpe": "jpg"}
    return mapping.get(fmt, fmt)


# ── EXIF helpers ─────────────────────────────────

def _extract_gps(exif) -> str | None:
    gps_ifd_key = 34853
    gps_data = exif.get_ifd(gps_ifd_key) if hasattr(exif, "get_ifd") else exif.get(gps_ifd_key)
    if not gps_data:
        return None

    def _to_decimal(values, ref):
        d, m, s = map(float, values)
        dec = d + m / 60.0 + s / 3600.0
        return -dec if ref in ("S", "W") else dec

    try:
        lat = _to_decimal(gps_data[2], gps_data[1])
        lon = _to_decimal(gps_data[4], gps_data[3])
        return f"{abs(lat):.4f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.4f}°{'E' if lon >= 0 else 'W'}"
    except (KeyError, TypeError, IndexError, ValueError):
        return None


def _extract_datetime(exif) -> str | None:
    for tag in (36867, 306):  # DateTimeOriginal, DateTime
        val = exif.get(tag)
        if val:
            return str(val).strip()
    return None


def _extract_device(exif) -> str | None:
    make = exif.get(271)
    model = exif.get(272)
    if make and model:
        m, o = str(make).strip(), str(model).strip()
        return o if o.startswith(m) else f"{m} {o}"
    return str(model).strip() if model else (str(make).strip() if make else None)


# ── Directive: info ──────────────────────────────

@directive("image", "info")
@directive("图片", "信息")
def image_info(params: list[str]) -> str:
    """Return image dimensions, format, size, and EXIF metadata."""
    if not params or not params[0]:
        return "Usage: image;info,<path>"

    p = _check_path(params[0])
    if p is None:
        return f"Path not in whitelist: {params[0]}"
    if not p.exists():
        return f"File not found: {params[0]}"
    if not p.is_file():
        return f"Not a file: {params[0]}"

    try:
        img = Image.open(p)
        w, h = img.size
        fmt = img.format or p.suffix.lstrip(".").upper()
        size = p.stat().st_size

        lines = [f"{w}x{h}  {fmt}  {_human_size(size)}  mode={img.mode}"]
        frames = getattr(img, "n_frames", 1)
        if frames > 1:
            lines.append(f"Frames: {frames}")

        exif = img.getexif()
        if exif:
            gps_text = _extract_gps(exif)
            if gps_text:
                lines.append(f"GPS: {gps_text}")
            dt_text = _extract_datetime(exif)
            if dt_text:
                lines.append(f"Capture time: {dt_text}")
            device_text = _extract_device(exif)
            if device_text:
                lines.append(f"Device: {device_text}")

        return "\n".join(lines)
    except Exception as e:
        return f"Cannot read image: {e}"


# ── Directive: encode ────────────────────────────

@directive("image", "encode")
@directive("图片", "编码")
def image_encode(params: list[str]) -> str:
    """Resize, re-encode to JPEG base64, store in cache."""
    if not params or not params[0]:
        return "Usage: image;encode,<path>[,<max_size>]"

    p = _check_path(params[0])
    if p is None:
        return f"Path not in whitelist: {params[0]}"
    if not p.exists():
        return f"File not found: {params[0]}"

    max_size = 1024
    if len(params) > 1 and params[1]:
        try:
            max_size = int(params[1])
        except ValueError:
            return f"max_size must be an integer: {params[1]}"

    try:
        img = Image.open(p)
        original_w, original_h = img.size
        original_fmt = img.format or "UNKNOWN"

        if img.size[0] > max_size or img.size[1] > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")

        key = _cache_put(encoded)
        encoded_size = len(encoded)
        original_size = p.stat().st_size

        return (
            f"cache:{key}\n"
            f"original: {original_w}x{original_h} {original_fmt} {_human_size(original_size)}\n"
            f"encoded:  {img.size[0]}x{img.size[1]} JPEG base64 {_human_size(encoded_size)}\n"
            f"expires:  {_CACHE_TTL}s\n"
            f"data_url: data:image/jpeg;base64,{encoded[:40]}..."
        )
    except Exception as e:
        return f"Encode failed: {e}"


# ── Directive: convert ───────────────────────────

@directive("image", "convert")
@directive("图片", "转换")
def image_convert(params: list[str]) -> str:
    """Convert an image between formats (PNG, JPEG, WebP, BMP)."""
    if len(params) < 2:
        return "Usage: image;convert,<in_path>,<out_format>[,<quality>]"

    in_path = pathlib.Path(params[0])
    out_fmt = _normalise_format(params[1].lower())
    quality = int(params[2]) if len(params) > 2 else 85

    if out_fmt not in SUPPORTED_OUTPUT:
        return f"Unsupported output format: {out_fmt}. Supported: {', '.join(sorted(SUPPORTED_OUTPUT))}"
    if quality < 1 or quality > 100:
        return "Quality must be 1–100"
    if not in_path.exists():
        return f"File not found: {in_path}"

    try:
        img = Image.open(in_path)
        out_path = in_path.with_suffix(f".{out_fmt}")

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

        save_format = "JPEG" if out_fmt == "jpg" else None
        save_kwargs = {"quality": quality} if out_fmt in ("jpg", "webp") else {}
        img.save(out_path, format=save_format, **save_kwargs)
        w, h = img.size
        img.close()

        return f"Converted → {out_path}  ({w}x{h}  {out_fmt.upper()})"
    except Exception as e:
        return f"Convert failed: {e}"


# ── Directive: resize ────────────────────────────

@directive("image", "resize")
@directive("图片", "缩放")
def image_resize(params: list[str]) -> str:
    """Resize an image to exact dimensions."""
    if len(params) < 3:
        return "Usage: image;resize,<in_path>,<width>,<height>"

    in_path = pathlib.Path(params[0])
    try:
        width = int(params[1])
        height = int(params[2])
    except ValueError:
        return "Width and height must be integers"
    if width < 1 or height < 1:
        return "Dimensions must be positive"
    if not in_path.exists():
        return f"File not found: {in_path}"

    try:
        img = Image.open(in_path)
        original = img.size
        img = img.resize((width, height), Image.LANCZOS)
        out_path = in_path.parent / f"{in_path.stem}_{width}x{height}{in_path.suffix}"
        img.save(out_path, quality=85)
        img.close()
        return f"Resized {original[0]}x{original[1]} → {width}x{height}  → {out_path}"
    except Exception as e:
        return f"Resize failed: {e}"

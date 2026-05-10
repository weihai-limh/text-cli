"""
Basic image processing handler.
image;info (alias: 图片;信息) — read dimensions/format/size + EXIF (GPS/time/device)
image;encode (alias: 图片;编码) — resize + JPEG + base64 → cache → return cache key
"""

import hashlib
import time
import base64
import io
from pathlib import Path

from PIL import Image
from core.registry import directive


# ═══════════════════════════════════════
# Path whitelist
# ═══════════════════════════════════════

_PATH_WHITELIST = [
    "/root/.openclaw/workspace/",
    "../text-cli-copilot/",
    "/root/.openclaw/media/",
]


def _check_path(path_str: str) -> Path | None:
    """Check path is in whitelist"""
    try:
        p = Path(path_str).resolve()
    except (OSError, ValueError):
        return None
    for entry in _PATH_WHITELIST:
        try:
            p.relative_to(entry)
            return p
        except ValueError:
            continue
    return None


# ═══════════════════════════════════════
# In-memory cache
# ═══════════════════════════════════════

_cache: dict[str, dict] = {}
_CACHE_TTL = 300  # seconds


def _cache_put(data: str) -> str:
    """Store in cache, return SHA256 key (16-char truncated)"""
    key = hashlib.sha256(data.encode()).hexdigest()[:16]
    _cache[key] = {
        "data": data,
        "expires_at": time.time() + _CACHE_TTL,
    }
    # Clean expired entries
    now = time.time()
    for k in list(_cache):
        if _cache[k]["expires_at"] < now:
            del _cache[k]
    return key


def cache_get(key: str) -> str | None:
    """Read from cache, return None if expired"""
    entry = _cache.get(key)
    if not entry:
        return None
    if entry["expires_at"] < time.time():
        del _cache[key]
        return None
    return entry["data"]


# ═══════════════════════════════════════
# Directive handlers
# ═══════════════════════════════════════

@directive("image", "info", domain_alias="图片", action_aliases={"info": "信息"})
def image_info(params: list[str]) -> str:
    """image;info (alias: 图片;信息),<path> → dimensions format size + EXIF (GPS/time/device)"""
    if not params or not params[0]:
        return "Missing parameter: image path"

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
        fmt = img.format or p.suffix.lstrip('.').upper()
        size = p.stat().st_size

        lines = [f"{w}x{h} {fmt} {_human_size(size)}"]

        # EXIF extraction
        exif = img.getexif()
        if exif:
            gps_text = _extract_gps(exif)
            if gps_text:
                lines.append(f"GPS: {gps_text}")

            dt_text = _extract_datetime(exif)
            if dt_text:
                lines.append(f"Taken: {dt_text}")

            device_text = _extract_device(exif)
            if device_text:
                lines.append(f"Device: {device_text}")

        return "\n".join(lines)
    except Exception as e:
        return f"Cannot read image: {e}"


# ═══════════════════════════════════════
# EXIF helpers
# ═══════════════════════════════════════

def _extract_gps(exif) -> str | None:
    """Extract GPS coordinates in decimal format"""
    gps_ifd_key = 34853  # GPSInfo IFD pointer
    gps_data = exif.get_ifd(gps_ifd_key) if hasattr(exif, 'get_ifd') else exif.get(gps_ifd_key)
    if not gps_data:
        return None

    def _to_decimal(values, ref):
        d, m, s = [float(v) for v in values]
        dec = d + m / 60.0 + s / 3600.0
        if ref in ("S", "W"):
            dec = -dec
        return dec

    try:
        lat = _to_decimal(gps_data[2], gps_data[1])
        lon = _to_decimal(gps_data[4], gps_data[3])
        return f"{abs(lat):.4f}°{'N' if lat>=0 else 'S'}, {abs(lon):.4f}°{'E' if lon>=0 else 'W'}"
    except (KeyError, TypeError, IndexError, ValueError):
        return None


def _extract_datetime(exif) -> str | None:
    """Extract capture time"""
    for tag in (36867, 306):  # DateTimeOriginal, DateTime
        val = exif.get(tag)
        if val:
            return str(val).strip()
    return None


def _extract_device(exif) -> str | None:
    """Extract device info"""
    make = exif.get(271)  # Make
    model = exif.get(272)  # Model
    if make and model:
        m = str(make).strip()
        o = str(model).strip()
        if o.startswith(m):
            return o
        return f"{m} {o}"
    if model:
        return str(model).strip()
    if make:
        return str(make).strip()
    return None


@directive("image", "encode", domain_alias="图片", action_aliases={"encode": "编码"})
def image_encode(params: list[str]) -> str:
    """image;encode (alias: 图片;编码),<path>[,max_size] → cache key"""
    if not params or not params[0]:
        return "Missing parameter: image path [,max_size]"

    p = _check_path(params[0])
    if p is None:
        return f"Path not in whitelist: {params[0]}"
    if not p.exists():
        return f"File not found: {params[0]}"

    # Parse max_size (default 1024)
    max_size = 1024
    if len(params) > 1 and params[1]:
        try:
            max_size = int(params[1])
        except ValueError:
            return f"max_size must be integer: {params[1]}"

    try:
        img = Image.open(p)
        original_w, original_h = img.size
        original_fmt = img.format or "UNKNOWN"

        # Proportional resize
        if img.size[0] > max_size or img.size[1] > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)

        # Convert to JPEG (uniform format, reduce size)
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
            f"original:{original_w}x{original_h} {original_fmt} {_human_size(original_size)}\n"
            f"encoded:{img.size[0]}x{img.size[1]} JPEG base64 {_human_size(encoded_size)}\n"
            f"expires:{_CACHE_TTL}s\n"
            f"data_url:data:image/jpeg;base64,{encoded[:40]}..."
        )
    except Exception as e:
        return f"Encode failed: {e}"


def _human_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f}KB"
    return f"{n}B"

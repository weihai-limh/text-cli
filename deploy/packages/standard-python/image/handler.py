"""
Image capability handler — text-cli instruction package.

Covers basic inspection (dimensions, EXIF), base64 encoding for VL pipeline,
format conversion, and resizing.  Depends on Pillow.

Directives:
    image;info,<path>[,json]              → human-readable or JSON metadata
    image;encode,<path>[,<max_size>]      → cache key for base64 JPEG
    image;convert,<in_path>,<fmt>[,<q>]   → format conversion
    image;resize,<in_path>,<w>,<h>        → proportional resize
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import pathlib
import time

from PIL import Image

from core.registry import directive

logger = logging.getLogger("text-cli.image")


_CONFIG: dict = {}
_PATH_WHITELIST: list[str] = []
_PROJECT_ROOT: pathlib.Path | None = None
_CACHE: dict[str, dict] = {}
_CACHE_TTL = 300  # seconds


_JSON_FLAGS = frozenset({"json", "j", "--json", "-j"})


def init_image_handler(project_root: str = None):
    """Load config from service/config/image.json.

    Config defines allowed file paths.  No config = no paths allowed.
    User must create/edit service/config/image.json before using directives.
    """
    global _CONFIG, _PATH_WHITELIST, _PROJECT_ROOT
    if project_root:
        _PROJECT_ROOT = pathlib.Path(project_root)
        config_path = pathlib.Path(project_root) / "config" / "image.json"
        if config_path.exists():
            try:
                _CONFIG = json.loads(config_path.read_text(encoding="utf-8"))
                _PATH_WHITELIST = _CONFIG.get("allowed_paths", [])[:]
                logger.info("image config loaded, allowed_paths: %s", _PATH_WHITELIST)
            except Exception as e:
                logger.warning("Failed to load image config: %s", e)
    if not _PATH_WHITELIST:
        logger.warning("image: no allowed_paths configured in service/config/image.json")


def runtime_config(action: str, payload: dict | None = None) -> dict | None:
    """live-config hook（可选钩子契约，issues ISS-02）。

    get  → {"status": "ok", "config": <当前配置>}（包自行脱敏）
    post → merge 校验 + 落盘 service/config/image.json + 更新模块态，
           返回应用后配置回显（写后读语义，LLM 可在同一步确认生效）。
    返回 None = 不支持该 action。错误走 reason。
    """
    global _CONFIG
    if action == "get":
        return {"status": "ok", "config": dict(_CONFIG)}

    if action == "post":
        if not isinstance(payload, dict):
            return {"status": "error", "reason": "post payload must be a JSON object"}
        new_config = dict(_CONFIG)
        new_config.update(payload)
        allowed = new_config.get("allowed_paths")
        if not isinstance(allowed, list) or not all(isinstance(p, str) for p in allowed):
            return {"status": "error", "reason": "allowed_paths must be a list of strings"}
        if _PROJECT_ROOT is None:
            return {"status": "error", "reason": "handler not initialised, cannot persist config"}
        config_path = _PROJECT_ROOT / "config" / "image.json"
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(new_config, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            return {"status": "error", "reason": f"failed to persist config: {e}"}
        _CONFIG = new_config
        _PATH_WHITELIST[:] = allowed  # 就地更新模块态，承担"重载"
        logger.info("image config updated via live-config, allowed_paths: %s", allowed)
        return {"status": "ok", "config": dict(_CONFIG)}

    return None


def _check_path(path_str: str) -> tuple[pathlib.Path | None, str | None]:
    """Resolve and validate a path against the whitelist.

    Returns (resolved_path, None) on success,
            (None, error_reason) on failure.
    """
    if not _PATH_WHITELIST or all(p.strip() == "" for p in _PATH_WHITELIST):
        return None, "image not configured. Edit allowed_paths in service/config/image.json"
    try:
        p = pathlib.Path(path_str).resolve()
    except (OSError, ValueError):
        return None, f"Invalid path: {path_str}"
    for entry in _PATH_WHITELIST:
        try:
            base = pathlib.Path(entry).resolve()  # 相对条目按 cwd 解析（runtime 根），与 resolve 后的 p 同基比较
            p.relative_to(base)
            return p, None
        except (ValueError, OSError):
            continue
    return None, f"Path not in allowed_paths: {path_str}"


def _cache_put(data: str) -> str:
    """Store data in cache, return a 16-char key."""
    key = hashlib.sha256(data.encode()).hexdigest()[:16]
    _CACHE[key] = {"data": data, "expires_at": time.time() + _CACHE_TTL}
    now = time.time()
    for k in list(_CACHE):
        if _CACHE[k]["expires_at"] < now:
            del _CACHE[k]
    return key


def cache_get(key: str) -> str | None:
    """Retrieve cached data; returns None if expired or missing."""
    entry = _CACHE.get(key)
    if not entry or entry["expires_at"] < time.time():
        _CACHE.pop(key, None)
        return None
    return entry["data"]


def _human_size(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}MB"
    if n >= 1_000:
        return f"{n / 1_000:.1f}KB"
    return f"{n}B"


def _normalise_format(fmt: str) -> str:
    mapping = {"jpeg": "jpg", "jpe": "jpg"}
    return mapping.get(fmt, fmt)


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


@directive("image", "info", domain_alias="图片", action_aliases={"info": "信息"})
def image_info(params: list[str]) -> dict:
    """Return image metadata: human-readable by default, JSON with 'json' param."""
    if not params or not params[0]:
        return {"status": "error", "reason": "Usage: image;info,<path>[,json]"}

    p, err = _check_path(params[0])
    if err:
        return {"status": "error", "reason": err}
    if not p.exists():
        return {"status": "error", "reason": f"File not found: {params[0]}"}
    if not p.is_file():
        return {"status": "error", "reason": f"Not a file: {params[0]}"}

    try:
        img = Image.open(p)
        w, h = img.size
        fmt = img.format or p.suffix.lstrip(".").upper()
        size = p.stat().st_size
        mode = img.mode
        frames = getattr(img, "n_frames", 1)
        exif = img.getexif()
        gps_text = _extract_gps(exif)
        dt_text = _extract_datetime(exif)
        device_text = _extract_device(exif)
        img.close()

        want_json = len(params) > 1 and params[1].lower() in _JSON_FLAGS

        info: dict[str, object] = {
            "status": "ok",
            "width": w,
            "height": h,
            "format": fmt,
            "size_bytes": size,
            "mode": mode,
            "frames": frames,
        }
        if gps_text:
            info["gps"] = gps_text
        if dt_text:
            info["capture_time"] = dt_text
        if device_text:
            info["device"] = device_text

        if want_json:
            return info

        lines = [f"{w}x{h}  {fmt}  {_human_size(size)}  mode={mode}"]
        if frames > 1:
            lines.append(f"Frames: {frames}")
        if gps_text:
            lines.append(f"GPS: {gps_text}")
        if dt_text:
            lines.append(f"Capture time: {dt_text}")
        if device_text:
            lines.append(f"Device: {device_text}")
        info["result"] = "\n".join(lines)
        return info

    except Exception as e:
        return {"status": "error", "reason": f"Cannot read image: {e}"}


@directive("image", "encode", domain_alias="图片", action_aliases={"encode": "编码"})
def image_encode(params: list[str]) -> dict:
    """Resize, re-encode to JPEG base64, store in cache."""
    if not params or not params[0]:
        return {"status": "error", "reason": "Usage: image;encode,<path>[,<max_size>]"}

    p, err = _check_path(params[0])
    if err:
        return {"status": "error", "reason": err}
    if not p.exists():
        return {"status": "error", "reason": f"File not found: {params[0]}"}

    max_size = 1024
    if len(params) > 1 and params[1]:
        try:
            max_size = int(params[1])
        except ValueError:
            return {"status": "error", "reason": f"max_size must be an integer: {params[1]}"}

    try:
        img = Image.open(p)
        original_w, original_h = img.size
        original_fmt = img.format or "UNKNOWN"
        original_size = p.stat().st_size

        if img.size[0] > max_size or img.size[1] > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)

        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        encoded = base64.b64encode(buf.getvalue()).decode("ascii")
        img.close()

        key = _cache_put(encoded)
        encoded_size = len(encoded)

        result: dict[str, object] = {
            "status": "ok",
            "cache_key": key,
            "original": f"{original_w}x{original_h} {original_fmt} {_human_size(original_size)}",
            "encoded": f"{img.size[0]}x{img.size[1]} JPEG base64 {_human_size(encoded_size)}",
            "expires_seconds": _CACHE_TTL,
        }

        want_json = len(params) > 2 and params[2].lower() in _JSON_FLAGS

        if want_json:
            return result

        result["result"] = (
            f"cache:{key}\n"
            f"original: {original_w}x{original_h} {original_fmt} {_human_size(original_size)}\n"
            f"encoded:  {img.size[0]}x{img.size[1]} JPEG base64 {_human_size(encoded_size)}\n"
            f"expires:  {_CACHE_TTL}s"
        )
        return result
    except Exception as e:
        return {"status": "error", "reason": f"Encode failed: {e}"}


SUPPORTED_OUTPUT = frozenset({"png", "jpg", "webp", "bmp"})


@directive("image", "convert", domain_alias="图片", action_aliases={"convert": "转换"})
def image_convert(params: list[str]) -> dict:
    """Convert an image between formats (PNG, JPEG, WebP, BMP)."""
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: image;convert,<in_path>,<out_format>[,<quality>[,json]]"}

    p, err = _check_path(params[0])
    if err:
        return {"status": "error", "reason": err}
    in_path = p
    out_fmt = _normalise_format(params[1].lower())
    quality = int(params[2]) if len(params) > 2 and params[2] else 85

    if out_fmt not in SUPPORTED_OUTPUT:
        return {"status": "error", "reason": f"Unsupported output format: {out_fmt}. Supported: {', '.join(sorted(SUPPORTED_OUTPUT))}"}
    if quality < 1 or quality > 100:
        return {"status": "error", "reason": "Quality must be 1–100"}
    if not in_path.exists():
        return {"status": "error", "reason": f"File not found: {in_path}"}

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

        result: dict[str, object] = {
            "status": "ok",
            "path": str(out_path),
            "width": w,
            "height": h,
            "format": out_fmt.upper(),
        }

        want_json = any(p.lower() in _JSON_FLAGS for p in params[3:])

        if want_json:
            return result

        result["result"] = f"Converted → {out_path}  ({w}x{h}  {out_fmt.upper()})"
        return result
    except Exception as e:
        return {"status": "error", "reason": f"Convert failed: {e}"}


@directive("image", "resize", domain_alias="图片", action_aliases={"resize": "缩放"})
def image_resize(params: list[str]) -> dict:
    """Resize an image to exact dimensions."""
    if len(params) < 3:
        return {"status": "error", "reason": "Usage: image;resize,<in_path>,<width>,<height>[,json]"}

    p, err = _check_path(params[0])
    if err:
        return {"status": "error", "reason": err}
    in_path = p
    try:
        width = int(params[1])
        height = int(params[2])
    except ValueError:
        return {"status": "error", "reason": "Width and height must be integers"}
    if width < 1 or height < 1:
        return {"status": "error", "reason": "Dimensions must be positive"}
    if not in_path.exists():
        return {"status": "error", "reason": f"File not found: {in_path}"}

    try:
        img = Image.open(in_path)
        original = img.size
        img = img.resize((width, height), Image.LANCZOS)
        out_path = in_path.parent / f"{in_path.stem}_{width}x{height}{in_path.suffix}"
        img.save(out_path, quality=85)
        img.close()

        result: dict[str, object] = {
            "status": "ok",
            "path": str(out_path),
            "width": width,
            "height": height,
            "original_width": original[0],
            "original_height": original[1],
        }

        want_json = len(params) > 3 and params[3].lower() in _JSON_FLAGS

        if want_json:
            return result

        result["result"] = f"Resized {original[0]}x{original[1]} → {width}x{height}  → {out_path}"
        return result
    except Exception as e:
        return {"status": "error", "reason": f"Resize failed: {e}"}

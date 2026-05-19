"""
Media handler — load, download, and serve media files.

Public URLs are passed through directly. Local files are validated
against a configured whitelist. Supports image, video, audio, and
file domains.

Directives:
    image;load,<URL or path>                     → media passthrough
    video;load,<URL or path>                     → media passthrough
    audio;load,<URL or path>                     → media passthrough
    file;load,<URL or path>                      → media passthrough
    media;download,<URL>[,<save_name>]           → download to local

Dependencies: requests (pip)
"""

import hashlib
import os
from pathlib import Path

import requests

from core.registry import directive

# ── Configuration ─────────────────────────────────

DOWNLOAD_DIR = Path(os.environ.get("MEDIA_DOWNLOAD_DIR", "/tmp/media"))
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
DOWNLOAD_TIMEOUT = 60

PATH_WHITELIST = [
    "/path/to/your/media",
]

EXT_TYPE_MAP = {
    '.jpg': 'picture', '.jpeg': 'picture', '.png': 'picture',
    '.gif': 'picture', '.webp': 'picture',
    '.mp4': 'video', '.webm': 'video', '.mov': 'video',
    '.mp3': 'audio', '.wav': 'audio', '.ogg': 'audio',
    '.flac': 'audio', '.aac': 'audio', '.m4a': 'audio',
    '.pdf': 'file',
}

def _guess_type(path_or_ext: str) -> str:
    lower = path_or_ext.lower()
    for ext, t in EXT_TYPE_MAP.items():
        if ext in lower:
            return t
    return 'file'

def _check_path(path: str) -> Path | None:
    p = Path(path).resolve()
    for allowed in PATH_WHITELIST:
        try:
            p.relative_to(allowed)
            return p
        except ValueError:
            continue
    return None

# ── Shared load logic ────────────────────────────

def _media_load(params: list) -> str:
    import json
    if not params or not params[0]:
        return json.dumps({"status": "error", "reason": "Missing media path or URL"})

    path_or_url = params[0]

    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        mtype = _guess_type(path_or_url)
        return json.dumps({"status": "ok", "type": mtype, "url": path_or_url})

    p = _check_path(path_or_url)
    if p is None:
        return json.dumps({"status": "error", "reason": f"Path not in whitelist: {path_or_url}"})
    if not p.exists():
        return json.dumps({"status": "error", "reason": f"File not found: {path_or_url}"})
    if not p.is_file():
        return json.dumps({"status": "error", "reason": f"Not a file: {path_or_url}"})

    mtype = _guess_type(p.suffix)
    return json.dumps({"status": "ok", "type": mtype, "name": p.name, "path": str(p)})

# ── Directives ───────────────────────────────────

@directive("image", "load", domain_alias="图片", action_aliases={"load": "加载"})
def image_load(params: list[str]) -> str:
    return _media_load(params)

@directive("video", "load", domain_alias="视频", action_aliases={"load": "加载"})
def video_load(params: list[str]) -> str:
    return _media_load(params)

@directive("audio", "load", domain_alias="音频", action_aliases={"load": "加载"})
def audio_load(params: list[str]) -> str:
    return _media_load(params)

@directive("file", "load", domain_alias="文件", action_aliases={"load": "加载"})
def file_load(params: list[str]) -> str:
    return _media_load(params)

@directive("media", "download", domain_alias="媒体", action_aliases={"download": "下载"})
def media_download(params: list[str]) -> str:
    import json
    if not params or not params[0]:
        return json.dumps({"status": "error", "reason": "Missing media URL"})

    url = params[0].strip()
    if not url.startswith('http://') and not url.startswith('https://'):
        return json.dumps({"status": "error", "reason": "Only http/https URLs supported"})

    mtype = _guess_type(url)
    if mtype == 'file':
        return json.dumps({"status": "error", "reason": "Cannot determine media type from URL"})

    ext = '.bin'
    for known_ext, t in EXT_TYPE_MAP.items():
        if t == mtype and known_ext in url.lower():
            ext = known_ext
            break
    if ext == '.bin':
        url_path = url.split('?')[0]
        ext = os.path.splitext(url_path)[1] or '.bin'

    try:
        resp = requests.get(
            url,
            headers={'User-Agent': 'text-cli/1.0', 'Accept': 'image/*,video/*,audio/*,*/*'},
            timeout=DOWNLOAD_TIMEOUT,
        )
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')
        if content_type:
            if content_type.startswith('image/'): mtype = 'picture'
            elif content_type.startswith('video/'): mtype = 'video'
            elif content_type.startswith('audio/'): mtype = 'audio'

        if len(resp.content) > MAX_DOWNLOAD_BYTES:
            return json.dumps({"status": "error", "reason": f"File too large: {len(resp.content)} bytes"})

    except requests.exceptions.Timeout:
        return json.dumps({"status": "error", "reason": "Download timeout"})
    except requests.exceptions.ConnectionError:
        return json.dumps({"status": "error", "reason": "Connection failed"})
    except requests.exceptions.HTTPError as e:
        return json.dumps({"status": "error", "reason": f"HTTP {e.response.status_code}"})
    except Exception as e:
        return json.dumps({"status": "error", "reason": str(e)})

    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    save_name = params[1].strip() if len(params) > 1 and params[1].strip() else url_hash
    save_path = DOWNLOAD_DIR / f"{save_name}{ext}"
    save_path.write_bytes(resp.content)

    return json.dumps({
        "status": "ok",
        "type": mtype,
        "name": save_path.name,
        "size": len(resp.content),
        "local_path": str(save_path),
    })

"""
Media loading handlers (base edition) — pure protocol layer, no Agent framework dependency

Directives:
  media;load   (alias: 媒体;加载),<path_or_url>     → load media from URL or local path
  media;download (alias: 媒体;下载),<url>[,<name>]   → download external media to local workspace

Handles image / video / audio / file in a single unified handler.
- HTTP(S) URLs → transparent passthrough (keep original URL)
- Local paths → serve via /media?path= route (requires copilot media server)
- Download → fetch external URL → save locally → return local URL

Image: reads binary → detects MIME → base64 encodes → data URI (50MB limit).
Video/Audio: verifies existence → returns resolved path.
File: reads UTF-8 text (10MB limit).

Usage:
  from media import media_load, media_download
  media_load(['/photos/coast.jpg'])   → {'rst_types': 'picture', ...}
  media_download(['https://example.com/chart.png']) → {'rst_types': 'picture', 'url': 'local://...'}

This is the reference implementation. Install into copilot by copying to handlers/media.py.
"""

import base64
import hashlib
import mimetypes
import os
from pathlib import Path

from core import ok, error

# ═══ MIME ═══

_MIME_OVERRIDES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
    '.gif': 'image/gif',
    '.bmp': 'image/bmp',
    '.svg': 'image/svg+xml',
    '.avif': 'image/avif',
    '.heic': 'image/heic', '.heif': 'image/heif',
}


def _mime(path: str) -> str:
    ext = Path(path).suffix.lower()
    return _MIME_OVERRIDES.get(ext) or mimetypes.guess_type(path)[0] or 'application/octet-stream'


# ═══ Type inference ═══

EXT_TYPE_MAP = {
    '.jpg': 'picture', '.jpeg': 'picture', '.png': 'picture',
    '.gif': 'picture', '.webp': 'picture', '.svg': 'picture',
    '.bmp': 'picture', '.ico': 'picture',
    '.mp4': 'video', '.webm': 'video', '.avi': 'video',
    '.mov': 'video', '.mkv': 'video',
    '.mp3': 'audio', '.wav': 'audio', '.ogg': 'audio',
    '.flac': 'audio', '.aac': 'audio', '.m4a': 'audio',
    '.pdf': 'file',
}


def _guess_type(path_or_ext: str) -> str:
    """Infer media type from file extension or URL."""
    lower = path_or_ext.lower()
    for ext, t in EXT_TYPE_MAP.items():
        if ext in lower:
            return t
    return 'file'


# ═══ Handlers ═══

def media_load(params: list, host: str = 'localhost', port: int = 28050) -> dict:
    """Load media from URL or local path.

    HTTP(S) URL → transparent passthrough (returns original URL + inferred type).
    Local path → verify existence → return /media?path= URL (requires copilot media server).
    """
    if not params or not params[0]:
        return error('missing_param', 'Need media path or URL')

    path_or_url = params[0]

    # ── HTTP(S) URL → transparent passthrough ──
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        media_type = _guess_type(path_or_url)
        name = path_or_url.rstrip('/').split('/')[-1] or 'media'
        return ok(name, type=media_type, url=path_or_url)

    # ── Local path → verify + /media/ route ──
    p = Path(path_or_url).resolve()
    if not p.exists():
        return error('file_not_found', f'File not found: {path_or_url}')
    if not p.is_file():
        return error('not_file', f'Path is not a file: {path_or_url}')

    media_type = _guess_type(p.suffix)
    url = f"http://{host}:{port}/media?path={p}"

    return ok(p.name, type=media_type, url=url, size=p.stat().st_size)


def media_download(params: list,
                   download_dir: str = '/tmp/text-cli-media',
                   host: str = 'localhost', port: int = 28050,
                   max_bytes: int = 100 * 1024 * 1024) -> dict:
    """Download external media URL to local workspace.

    Returns local /media?path= URL for reliable cross-platform rendering.
    Files are SHA256-deduped by URL hash.

    Requires: pip install requests
    """
    import requests

    if not params or not params[0]:
        return error('missing_param', 'Need media URL')

    url = params[0].strip()
    if not url.startswith('http://') and not url.startswith('https://'):
        return error('invalid_param', 'Only http/https URLs supported')

    media_type = _guess_type(url)
    if media_type == 'file':
        return error('unknown_type', 'Cannot infer media type from URL')

    # Determine extension
    ext = '.bin'
    for known_ext, t in EXT_TYPE_MAP.items():
        if t == media_type and known_ext in url.lower():
            ext = known_ext
            break
    if ext == '.bin':
        url_path = url.split('?')[0]
        ext = os.path.splitext(url_path)[1] or '.bin'

    try:
        resp = requests.get(
            url,
            headers={
                'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36',
                'Accept': 'image/*,video/*,audio/*,*/*',
            },
            timeout=60,
        )
        resp.raise_for_status()

        content_type = resp.headers.get('Content-Type', '')
        if content_type:
            if content_type.startswith('image/'):
                media_type = 'picture'
            elif content_type.startswith('video/'):
                media_type = 'video'
            elif content_type.startswith('audio/'):
                media_type = 'audio'
            else:
                return error('invalid_type', f'Unsupported content type: {content_type}')

        if len(resp.content) > max_bytes:
            return error('too_large', f'File exceeds {max_bytes} bytes')

        data = resp.content
    except requests.exceptions.Timeout:
        return error('download_failed', 'Download timeout')
    except requests.exceptions.HTTPError as e:
        return error('download_failed', f'HTTP {e.response.status_code}')
    except Exception as e:
        return error('download_failed', str(e))

    # Save with SHA256 dedup
    os.makedirs(download_dir, exist_ok=True)
    url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
    save_name = params[1].strip() if len(params) > 1 and params[1].strip() else url_hash
    save_path = os.path.join(download_dir, f"{save_name}{ext}")
    with open(save_path, 'wb') as f:
        f.write(data)

    media_url = f"http://{host}:{port}/media?path={save_path}"

    return ok(
        os.path.basename(save_path),
        type=media_type,
        url=media_url,
        size=len(data),
        local_path=save_path,
    )


# ═══ Legacy per-type handlers (kept for backward compatibility) ═══

def image_load(params: list) -> dict:
    """Load local image → base64 data URI."""
    if not params:
        return error('missing_param', 'Need image path')
    p = Path(params[0]).resolve()
    if not p.exists():
        return error('file_not_found', f'Image not found: {params[0]}')
    if p.stat().st_size > 50 * 1024 * 1024:
        return error('file_too_large', 'Image exceeds 50MB')

    try:
        data = p.read_bytes()
        encoded = base64.b64encode(data).decode('ascii')
        mime = _mime(str(p))
        return {
            'rst_types': 'picture',
            'rst_data': {
                'url': f'data:{mime};base64,{encoded}',
                'path': str(p),
                'size': len(data),
                'mime': mime,
            },
        }
    except Exception as e:
        return error('load_error', f'Failed: {e}')


def video_load(params: list) -> dict:
    """Verify video exists → return resolved path."""
    if not params:
        return error('missing_param', 'Need video path')
    p = Path(params[0]).resolve()
    if not p.exists():
        return error('file_not_found', f'Video not found: {params[0]}')
    return {
        'rst_types': 'video',
        'rst_data': {
            'url': f'file://{p}',
            'path': str(p),
            'size': p.stat().st_size,
        },
    }


def audio_load(params: list) -> dict:
    """Verify audio exists → return resolved path."""
    if not params:
        return error('missing_param', 'Need audio path')
    p = Path(params[0]).resolve()
    if not p.exists():
        return error('file_not_found', f'Audio not found: {params[0]}')
    return {
        'rst_types': 'audio',
        'rst_data': {
            'url': f'file://{p}',
            'path': str(p),
            'size': p.stat().st_size,
        },
    }


def file_load(params: list) -> dict:
    """Load text file content."""
    if not params:
        return error('missing_param', 'Need file path')
    p = Path(params[0]).resolve()
    if not p.exists():
        return error('file_not_found', f'File not found: {params[0]}')
    if p.stat().st_size > 10 * 1024 * 1024:
        return error('file_too_large', 'File exceeds 10MB')
    try:
        content = p.read_text(encoding='utf-8')
        return {
            'rst_types': 'file',
            'rst_data': {
                'text': content,
                'path': str(p),
                'size': len(content.encode('utf-8')),
            },
        }
    except UnicodeDecodeError:
        return error('encoding_error', f'File not UTF-8: {params[0]}')
    except Exception as e:
        return error('load_error', f'Failed: {e}')

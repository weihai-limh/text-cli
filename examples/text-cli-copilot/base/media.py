"""
Media loading handler (base edition) — pure protocol layer, no Agent framework dependency

Directives:
  image;load (alias: 图片;加载),<path>  → base64 data URI
  video;load (alias: 视频;加载),<path>  → file path reference
  audio;load (alias: 音频;加载),<path>  → file path reference
  file;load  (alias: 文件;加载),<path>  → text content

Image: reads binary → detects MIME type → base64 encodes → returns data URI (50MB limit).
Video/Audio: verifies existence → returns resolved path (rendering delegated).
File: reads UTF-8 text directly (10MB limit).

Usage:
  from media import image_load, video_load, audio_load, file_load
  image_load(['/photos/coast.jpg'])  → {'rst_types': 'picture', 'rst_data': {...}}

This is the reference implementation. Install into copilot by copying to handlers/media.py.
"""

import base64
import mimetypes
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


# ═══ Handlers ═══

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

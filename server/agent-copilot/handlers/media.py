"""
Media handling mixin — load local media files for text-cli protocol.

image;load (alias: 图片;加载), <path>  → base64 data URI
video;load (alias: 视频;加载), <path>  → resolved path + metadata
audio;load (alias: 音频;加载), <path>  → resolved path + metadata
file;load  (alias: 文件;加载), <path>  → resolved path + metadata

Image: reads binary → detects MIME type → base64 encodes → returns data URI.
Video/Audio/File: verifies existence → returns resolved path (rendering delegated to render handler).
"""

import base64
import os
from pathlib import Path

from core import ok, error


# ═══════════════════════════════════════
# MIME detection
# ═══════════════════════════════════════

_MIME_TYPES = {
    '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.webp': 'image/webp',
    '.bmp': 'image/bmp',
    '.svg': 'image/svg+xml',
    '.tiff': 'image/tiff', '.tif': 'image/tiff',
    '.ico': 'image/x-icon',
    '.avif': 'image/avif',
    '.heic': 'image/heic', '.heif': 'image/heif',
}


def _detect_mime(filepath: str) -> str:
    """Detect MIME type by extension."""
    ext = Path(filepath).suffix.lower()
    return _MIME_TYPES.get(ext, 'application/octet-stream')


# ═══════════════════════════════════════
# Base handler (shared for video/audio/file)
# ═══════════════════════════════════════

class MediaHandlers:
    """
    Media loading handlers.

    image;load (alias: 图片;加载),<path>
      Reads image binary → base64 → data URI.
      Returns: rst_types=picture, rst_data.url=data:image/xxx;base64,...

    video;load (alias: 视频;加载),<path>
      Verifies file exists and is within whitelist.
      Returns: rst_types=video, rst_data.url=file:///<resolved_path>

    audio;load (alias: 音频;加载),<path>
      Same pattern as video.
      Returns: rst_types=audio, rst_data.url=file:///<resolved_path>

    file;load (alias: 文件;加载),<path>
      Reads text content directly.
      Returns: rst_types=file, rst_data.text=<content>
    """

    # ── image;load ──

    def _handle_image_load(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: image path')
        path_str = params[0]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {path_str}')
        if not p.exists():
            return error('file_not_found', f'Image not found: {path_str}')
        if p.stat().st_size > 50 * 1024 * 1024:
            return error('file_too_large', f'Image exceeds 50MB limit: {path_str}')

        try:
            data = p.read_bytes()
            encoded = base64.b64encode(data).decode('ascii')
            mime = _detect_mime(str(p))
            url = f'data:{mime};base64,{encoded}'
            return {
                'rst_types': 'picture',
                'rst_data': {
                    'url': url,
                    'path': str(p.resolve()),
                    'size': len(data),
                    'mime': mime,
                },
            }
        except Exception as e:
            return error('load_error', f'Failed to load image: {e}')

    # ── video;load ──

    def _handle_video_load(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: video path')
        path_str = params[0]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {path_str}')
        if not p.exists():
            return error('file_not_found', f'Video not found: {path_str}')
        resolved = str(p.resolve())
        return {
            'rst_types': 'video',
            'rst_data': {
                'url': f'file://{resolved}',
                'path': resolved,
                'size': p.stat().st_size,
            },
        }

    # ── audio;load ──

    def _handle_audio_load(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: audio path')
        path_str = params[0]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {path_str}')
        if not p.exists():
            return error('file_not_found', f'Audio not found: {path_str}')
        resolved = str(p.resolve())
        return {
            'rst_types': 'audio',
            'rst_data': {
                'url': f'file://{resolved}',
                'path': resolved,
                'size': p.stat().st_size,
            },
        }

    # ── file;load ──

    def _handle_file_load(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: file path')
        path_str = params[0]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {path_str}')
        if not p.exists():
            return error('file_not_found', f'File not found: {path_str}')
        if p.stat().st_size > 10 * 1024 * 1024:
            return error('file_too_large', f'File exceeds 10MB limit: {path_str}')
        try:
            content = p.read_text(encoding='utf-8')
            return {
                'rst_types': 'file',
                'rst_data': {
                    'text': content,
                    'path': str(p.resolve()),
                    'size': len(content.encode('utf-8')),
                },
            }
        except UnicodeDecodeError:
            return error('encoding_error',
                        f'File is not UTF-8 encoded: {path_str}')
        except Exception as e:
            return error('load_error', f'Failed to load file: {e}')

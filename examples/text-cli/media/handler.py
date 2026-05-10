"""
Media load handler — public passthrough + local mount

Directives:
  image;load (alias: 图片;加载),<URL or path>
  video;load (alias: 视频;加载),<URL or path>
  audio;load (alias: 音频;加载),<URL or path>
  file;load (alias: 文件;加载),<URL or path>

Public URL → direct passthrough
Local path → whitelist check → /media/ route

Install: cp to handlers/ directory, service auto-discovers
Dependency: core (parser, registry, response)
"""

from pathlib import Path
from core import ok, error


EXT_TYPE_MAP = {
    '.jpg': 'picture', '.jpeg': 'picture', '.png': 'picture',
    '.gif': 'picture', '.webp': 'picture',
    '.mp4': 'video', '.webm': 'video', '.mov': 'video',
    '.mp3': 'audio', '.wav': 'audio', '.ogg': 'audio',
    '.pdf': 'file',
}

# Modify to your local whitelist paths at deploy time
PATH_WHITELIST = [
    "/path/to/your/media",
]


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


def media_load(params: list) -> dict:
    """Handle image;load (alias: 图片;加载) / video;load (alias: 视频;加载) / audio;load (alias: 音频;加载) / file;load (alias: 文件;加载)"""
    if not params or not params[0]:
        return error('missing_param', 'Please provide media path or URL')

    path_or_url = params[0]

    # ── Public URL → passthrough ──
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        mtype = _guess_type(path_or_url)
        return ok(path_or_url, type=mtype, url=path_or_url)

    # ── Local path → security check + /media/ route ──
    p = _check_path(path_or_url)
    if p is None:
        return error('path_denied', path_or_url)
    if not p.exists():
        return error('not_found', path_or_url)
    if not p.is_file():
        return error('not_file', path_or_url)

    mtype = _guess_type(p.suffix)
    return ok(p.name, type=mtype, url=f"/media/{p.name}")

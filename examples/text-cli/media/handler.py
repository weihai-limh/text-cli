"""
媒体加载 handler — 公网透传 + 本地挂载

指令:
  图片;加载,<URL或路径>
  视频;加载,<URL或路径>
  音频;加载,<URL或路径>
  文件;加载,<URL或路径>

公网 URL → 直接透传
本地路径 → 白名单校验 → /media/ 路由

安装: cp 到 handlers/ 目录，service 自动发现
依赖: core（parser, registry, response）
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

# 部署时修改为你的本地白名单路径
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
    """处理 图片;加载 / 视频;加载 / 音频;加载 / 文件;加载"""
    if not params or not params[0]:
        return error('missing_param', '请提供媒体路径或 URL')

    path_or_url = params[0]

    # ── 公网 URL → 透传 ──
    if path_or_url.startswith('http://') or path_or_url.startswith('https://'):
        mtype = _guess_type(path_or_url)
        return ok(path_or_url, type=mtype, url=path_or_url)

    # ── 本地路径 → 安全校验 + /media/ 路由 ──
    p = _check_path(path_or_url)
    if p is None:
        return error('path_denied', path_or_url)
    if not p.exists():
        return error('not_found', path_or_url)
    if not p.is_file():
        return error('not_file', path_or_url)

    mtype = _guess_type(p.suffix)
    return ok(p.name, type=mtype, url=f"/media/{p.name}")

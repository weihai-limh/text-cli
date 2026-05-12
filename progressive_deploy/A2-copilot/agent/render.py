"""
Resource render handler (base edition) — pure protocol layer, no Agent framework dependency

Directive:
  resource;render (alias: 资源;渲染),<type>,<url>[,<alt>]

  type: picture | video | audio | file | text  (supports Chinese/Japanese aliases)
  url:  resource address (local path, data URI, or remote URL)
  alt:  optional description text — falls back to filename extracted from URL

Output: rst_types + url — Agent receives a renderable media response and decides
how to display it. No rendering logic in the handler.

The companion terminal_render.json (copilot/config/) adds a config layer above this:
it maps trigger types → proxy + render instructions, so the same handler works
across different terminal environments by swapping the config file.

Usage:
  from render import resource_render
  resource_render(['picture', 'https://example.com/chart.png', 'Quarterly Report'])
"""

from core import ok, error

_VALID_TYPES = {'picture', 'video', 'audio', 'file', 'text'}
_TYPE_ALIASES = {
    '图片': 'picture', '画像': 'picture',
    '视频': 'video', '動画': 'video',
    '音频': 'audio', '音声': 'audio',
    '文件': 'file', 'ファイル': 'file',
}


def resource_render(params: list, public_base_url: str = None) -> dict:
    """Render a resource for Agent display.

    Converts (type, url, alt) into a typed response the Agent can render directly.
    For text type: url is the text content itself (passthrough).
    For media types: url is the resource address.

    If public_base_url is set, localhost URLs in the response are rewritten
    to the public base for cross-network access.
    """
    if len(params) < 2:
        return error('missing_param', 'Need type and url params')

    raw_type = params[0].rstrip(':')
    url = params[1]
    alt = params[2] if len(params) > 2 else url.rstrip('/').split('/')[-1]

    mtype = _TYPE_ALIASES.get(raw_type.lower(), raw_type.lower())
    if mtype not in _VALID_TYPES:
        return error('invalid_type', mtype, hint=sorted(_VALID_TYPES))

    # Rewrite localhost URL to public base if configured
    if public_base_url and url.startswith('http://localhost'):
        url = url.replace(
            url.split('/', 3)[0] + '//' + url.split('/', 3)[2],
            public_base_url.rstrip('/')
        )

    return ok(alt, type=mtype, url=url)

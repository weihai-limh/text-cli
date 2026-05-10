"""
Resource render handler (base edition) — pure protocol layer, no Agent framework dependency

Directive:
  资源;渲染,<type>,<url>[,<alt>]

type: picture | video | audio | file | text
url:  resource address
alt:  optional description text

Output: rst_types + url, Agent decides rendering method
"""

from core import ok, error

_VALID_TYPES = {'picture', 'video', 'audio', 'file', 'text'}
_TYPE_ALIASES = {
    '图片': 'picture', '视频': 'video',
    '音频': 'audio', '文件': 'file',
}


def resource_render(params: list) -> dict:
    if len(params) < 2:
        return error('missing_param', 'Need type and url params')

    raw_type = params[0].rstrip(':')
    url = params[1]
    alt = params[2] if len(params) > 2 else url.rstrip('/').split('/')[-1]

    mtype = _TYPE_ALIASES.get(raw_type.lower(), raw_type.lower())
    if mtype not in _VALID_TYPES:
        return error('invalid_type', mtype, hint=list(_VALID_TYPES))

    return ok(alt, type=mtype, url=url)

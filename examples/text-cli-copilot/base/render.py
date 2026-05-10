"""
资源渲染 handler（基础版）— 纯协议层，不依赖 Agent 框架

指令:
  资源;渲染,<type>,<url>[,<alt>]

type: picture | video | audio | file | text
url:  资源地址
alt:  可选描述文本

输出: rst_types + url，由 Agent 自行决定渲染方式
"""

from core import ok, error

_VALID_TYPES = {'picture', 'video', 'audio', 'file', 'text'}
_TYPE_ALIASES = {
    '图片': 'picture', '视频': 'video',
    '音频': 'audio', '文件': 'file',
}


def resource_render(params: list) -> dict:
    if len(params) < 2:
        return error('missing_param', '需要 type 和 url 参数')

    raw_type = params[0].rstrip(':')
    url = params[1]
    alt = params[2] if len(params) > 2 else url.rstrip('/').split('/')[-1]

    mtype = _TYPE_ALIASES.get(raw_type.lower(), raw_type.lower())
    if mtype not in _VALID_TYPES:
        return error('invalid_type', mtype, hint=list(_VALID_TYPES))

    return ok(alt, type=mtype, url=url)

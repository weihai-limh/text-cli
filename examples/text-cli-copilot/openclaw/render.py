"""
OpenClaw 媒体渲染 handler — 依赖 OpenClaw lightclaw_upload_file 工具

指令:
  资源;渲染,<type>,<url>[,<alt>]

渲染策略（按 channel）:
  lightclawbot (DM/WebChat)  → lightclaw_upload_file → localfile://
  Discord                     → message(media=url)
  Telegram                    → message(media=url)
  其他                        → 纯 URL 文本

安装:
  cp examples/text-cli-copilot/openclaw/render.py copilot_handlers/render.py
  同时需要 base/render.py 作为基础协议层
"""

from core import ok, error

_VALID_TYPES = {'picture', 'video', 'audio', 'file', 'text'}
_TYPE_ALIASES = {
    '图片': 'picture', '视频': 'video', '音频': 'audio', '文件': 'file',
}

# 部署者根据实际 channel 定制
DEFAULT_CHANNEL = "lightclawbot"


def resource_render(params: list, context: dict | None = None) -> dict:
    """
    params: [type, url, alt?]
    context: Agent 传来的上下文 {channel, sender, session}
    """
    if len(params) < 2:
        return error('missing_param', '需要 type 和 url 参数')

    raw_type = params[0].rstrip(':')
    url = params[1]
    alt = params[2] if len(params) > 2 else url.rstrip('/').split('/')[-1]

    mtype = _TYPE_ALIASES.get(raw_type.lower(), raw_type.lower())
    if mtype not in _VALID_TYPES:
        return error('invalid_type', mtype)

    channel = (context or {}).get('channel', DEFAULT_CHANNEL)

    # OpenClaw 专属: lightclawbot 使用 localfile:// 协议
    if channel == 'lightclawbot':
        return ok(alt, type=mtype, url=f"localfile://{{result_from_upload}}")
    # 其他 channel: 透传 URL，由渠道插件自行渲染
    return ok(alt, type=mtype, url=url)

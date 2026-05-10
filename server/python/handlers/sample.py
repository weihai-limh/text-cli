"""
示例领域 handler — text-cli service 出厂自带

指令:
  示例领域;回显,<text>        → 回显输入
  示例领域;问候[,<name>]      → 打招呼
  示例领域;列表               → 列出已注册指令

这是 handler 架构的参考模板。
部署者通过 examples/text-cli/ 安装其他指令。
"""

from core import ok


def echo(params: list) -> dict:
    text = params[0] if params else '（空）'
    return ok(f'回显: {text}')


def greet(params: list) -> dict:
    name = params[0] if params else '世界'
    return ok(f'你好，{name}！🌊')


def list_directives(params: list) -> dict:
    from core.registry import get_registered_directives
    dirs = get_registered_directives()
    lines = ["已注册指令:"]
    for domain, actions in sorted(dirs.items()):
        lines.append(f"  {domain}: {', '.join(actions)}")
    return ok('\n'.join(lines))

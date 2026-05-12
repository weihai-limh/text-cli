"""
Sample domain handler — text-cli service ships with this

Directives:
  示例领域;回显,<text>        → echo input
  示例领域;问候[,<name>]      → greet
  示例领域;列表               → list registered directives

This is a reference template for the handler architecture.
Deployers install additional directives via examples/text-cli/.
"""

from core import ok


def echo(params: list) -> dict:
    text = params[0] if params else '(empty)'
    return ok(f'Echo: {text}')


def greet(params: list) -> dict:
    name = params[0] if params else 'World'
    return ok(f'Hello, {name}! 🌊')


def list_directives(params: list) -> dict:
    from core.registry import get_registered_directives
    dirs = get_registered_directives()
    lines = ["Registered directives:"]
    for domain, actions in sorted(dirs.items()):
        lines.append(f"  {domain}: {', '.join(actions)}")
    return ok('\n'.join(lines))

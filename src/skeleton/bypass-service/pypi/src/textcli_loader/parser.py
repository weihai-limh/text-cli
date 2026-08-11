"""
Directive parser — isomorphic with text-cli service core/parser.py.

Extracted to zero-dependency module for pip-installable textcli-loader.
"""

import re
from dataclasses import dataclass

_DIRECTIVE_PATTERN = re.compile(
    r"^\s*(?:AI|指令)[：:]([^;]+);([^,]+)(?:,(.+))?\s*$"
)
_MAX_LENGTH = 2048
_MAX_PARAMS = 50


@dataclass
class ParsedDirective:
    domain: str
    action: str
    params: list[str]
    raw: str

    @property
    def directive_key(self) -> str:
        """Return directive key preserving original prefix."""
        for prefix in ("AI:", "指令:"):
            if self.raw.startswith(prefix):
                return f"{prefix[:-1]}:{self.domain};{self.action}"
        return f"AI:{self.domain};{self.action}"


class DirectiveParseError(Exception):
    def __init__(self, message: str, code: str = "INVALID_PARAMS"):
        self.message = message
        self.code = code
        super().__init__(message)


def _split_params(raw: str) -> list[str]:
    """Split params by comma, respecting JSON brackets and string quotes."""
    result = []
    buf = []
    depth = 0
    in_string = False
    escape = False
    for ch in raw:
        if escape:
            buf.append(ch)
            escape = False
            continue
        if ch == '\\':
            buf.append(ch)
            escape = True
            continue
        if ch == '"' and depth == 0:
            in_string = not in_string
            buf.append(ch)
            continue
        if in_string:
            buf.append(ch)
            continue
        if ch in ('[', '{'):
            depth += 1
            buf.append(ch)
            continue
        if ch in (']', '}'):
            depth -= 1
            buf.append(ch)
            continue
        if ch == ',' and depth == 0:
            val = ''.join(buf).strip()
            if val:
                result.append(val)
            buf = []
            continue
        buf.append(ch)
    val = ''.join(buf).strip()
    if val:
        result.append(val)
    return result


def parse(prompt: str | None) -> ParsedDirective:
    """Parse a text-cli directive string.

    Raises DirectiveParseError on invalid input.
    """
    if not prompt or not prompt.strip():
        raise DirectiveParseError("prompt is required")

    prompt = prompt.strip()

    if len(prompt) > _MAX_LENGTH:
        raise DirectiveParseError(
            f"directive exceeds max length ({_MAX_LENGTH})"
        )

    match = _DIRECTIVE_PATTERN.match(prompt)
    if not match:
        raise DirectiveParseError(f"invalid directive format: {prompt}")

    domain = match.group(1).strip()
    action = match.group(2).strip()
    raw_params = match.group(3)

    params: list[str] = []
    if raw_params:
        params = _split_params(raw_params)

    if len(params) > _MAX_PARAMS:
        raise DirectiveParseError(
            f"too many parameters ({len(params)}), max {_MAX_PARAMS}"
        )

    if not domain:
        raise DirectiveParseError("domain is empty")
    if not action:
        raise DirectiveParseError("action is empty")

    return ParsedDirective(
        domain=domain,
        action=action,
        params=params,
        raw=prompt,
    )

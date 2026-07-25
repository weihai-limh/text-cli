import re
from dataclasses import dataclass

# 双前缀协议：中文 `指令:` 和英文 `AI:` 同等效力
# 兼容 v1.0 `指令:` 格式，同时支持 v1.1+ `AI:` 国际化前缀
DIRECTIVE_PATTERN = re.compile(
    r"^(?:指令|AI)[：:]([^;]+);([^,]+)(?:,(.+))?$"
)

# Extract prefix for directive_key reconstruction
_PREFIX_PATTERN = re.compile(r"^(指令|AI)[：:]")

MAX_DIRECTIVE_LENGTH = 512
MAX_PARAMS = 10


@dataclass
class ParsedDirective:
    domain: str
    action: str
    params: list[str]
    raw: str

    @property
    def directive_key(self) -> str:
        """返回带原始前缀的指令键，用于 schema 匹配"""
        m = _PREFIX_PATTERN.match(self.raw)
        prefix = m.group(1) if m else "指令"
        return f"{prefix}:{self.domain};{self.action}"


class DirectiveParseError(Exception):
    def __init__(self, message: str, code: str = "INVALID_DIRECTIVE_FORMAT"):
        self.message = message
        self.code = code
        super().__init__(message)


def parse_directive(prompt: str | None) -> ParsedDirective:
    if not prompt or not prompt.strip():
        raise DirectiveParseError("prompt is required")

    prompt = prompt.strip()

    if len(prompt) > MAX_DIRECTIVE_LENGTH:
        raise DirectiveParseError(
            f"directive exceeds max length ({MAX_DIRECTIVE_LENGTH})"
        )

    match = DIRECTIVE_PATTERN.match(prompt)
    if not match:
        raise DirectiveParseError(f"invalid directive format: {prompt}")

    domain = match.group(1).strip()
    action = match.group(2).strip()
    raw_params = match.group(3)

    params = []
    if raw_params:
        for p in raw_params.split(","):
            p = p.strip()
            if p:
                params.append(p)

    if len(params) > MAX_PARAMS:
        raise DirectiveParseError(
            f"too many parameters ({len(params)}), max {MAX_PARAMS}"
        )

    for p in params:
        if any(c in p for c in (",", ";", "\n", "\r")):
            raise DirectiveParseError(f"parameter contains forbidden characters: {p}")

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

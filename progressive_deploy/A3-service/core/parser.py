import re
from dataclasses import dataclass

# Dual-prefix protocol: Chinese `指令:` and English `AI:` have equal standing
DIRECTIVE_PATTERN = re.compile(
    r"^\s*(?:指令|AI)[：:]([^;]+);([^,]+)(?:,(.+))?\s*$"
)

_PREFIX_PATTERN = re.compile(r"^(指令|AI)")

MAX_DIRECTIVE_LENGTH = 512
MAX_PARAMS = 20


@dataclass
class ParsedDirective:
    domain: str
    action: str
    params: list[str]
    raw: str

    @property
    def directive_key(self) -> str:
        """Return directive key preserving original prefix."""
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

    params: list[str] = []
    if raw_params:
        for p in raw_params.split(","):
            p = p.strip()
            if p:
                params.append(p)

    if len(params) > MAX_PARAMS:
        raise DirectiveParseError(
            f"too many parameters ({len(params)}), max {MAX_PARAMS}"
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

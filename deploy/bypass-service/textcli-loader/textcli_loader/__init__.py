"""
textcli-loader — zero-dependency text-cli instruction package loader.

Usage:
    from textcli_loader import load_package, execute

    meta = load_package("./my-package/")
    result = execute("AI:date-calc;add-days,2026-01-01,30")
    print(result["rst_data"]["text"])  # → "2026-01-31"

Design:
    - Zero external dependencies (stdlib only)
    - Compatible with text-cli service envelope format
    - Any Python environment that can pip install can run this
    - Loads schema.json + handler.py from a package directory
"""

from textcli_loader.parser import parse, ParsedDirective, DirectiveParseError
from textcli_loader.loader import load_package, list_directives, LoadError
from textcli_loader.registry import dispatch as _dispatch, get_registered
from textcli_loader.envelope import ok, error


__all__ = [
    "load_package",
    "execute",
    "list_directives",
    "get_registered",
    "parse",
    "ok",
    "error",
    "DirectiveParseError",
    "LoadError",
    "ParsedDirective",
]


def execute(prompt: str) -> dict:
    """Parse and execute a text-cli directive string.

    Args:
        prompt: e.g. "AI:date-calc;add-days,2026-01-01,30"

    Returns:
        Envelope dict: {"rst_types": "text", "rst_data": {"text": ...}, "rst_err": ""}

    Requires load_package() to have been called first.
    """
    try:
        parsed = parse(prompt)
    except DirectiveParseError as e:
        return error(e.message, e.code)

    result = _dispatch(parsed.domain, parsed.action, parsed.params)

    if result is None:
        return error(f"No handler registered for: {parsed.directive_key}", "not_found")

    if isinstance(result, dict):
        # Handler returned a dict (e.g. for MCP/aggregate packages)
        import json as _json
        result = _json.dumps(result, ensure_ascii=False)

    return ok(str(result))


def info(meta: dict) -> dict:
    """Return loader info including loaded package and registered directives."""
    return {
        "loader": "textcli-loader",
        "package_id": meta.get("id", ""),
        "package_path": meta.get("path", ""),
        "directives": meta.get("directives", []),
        "registered": get_registered(),
    }

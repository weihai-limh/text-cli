"""
textcli-loader — zero-dependency text-cli instruction package loader.

Usage:
    from textcli_loader import load_package, execute, discover, health

    meta = load_package("./my-package/")
    result = execute("AI:date-calc;add-days,2026-01-01,30")
    print(result["rst_data"]["result"])  # → "2026-01-31"

    all_dirs = discover()
    h = health()  # → {"status": "ok", "body": "textcli-loader", "version": "0.1.2", ...}

Design:
    - Zero external dependencies (stdlib only)
    - Compatible with text-cli service envelope format
    - Any Python environment that can pip install can run this
    - Loads schema.json + handler.py from a package directory
"""

__version__ = "0.1.2"

from textcli_loader.envelope import error, ok
from textcli_loader.loader import LoadError, list_directives, load_package
from textcli_loader.parser import DirectiveParseError, ParsedDirective, parse
from textcli_loader.registry import dispatch as _dispatch
from textcli_loader.registry import get_registered

# Cache loaded package schemas for discover()
_schemas: dict[str, dict] = {}

__all__ = [
    "DirectiveParseError",
    "LoadError",
    "ParsedDirective",
    "__version__",
    "discover",
    "error",
    "execute",
    "get_registered",
    "health",
    "list_directives",
    "load_package",
    "ok",
    "parse",
]


def execute(prompt: str) -> dict:
    """Parse and execute a text-cli directive string.

    Args:
        prompt: e.g. "AI:date-calc;add-days,2026-01-01,30"

    Returns:
        Envelope dict: {"rst_types": "text", "rst_data": {...}, "rst_err": ""}

    Requires load_package() to have been called first.
    """
    try:
        parsed = parse(prompt)
    except DirectiveParseError as e:
        return error(e.message, e.code)

    result = _dispatch(parsed.domain, parsed.action, parsed.params)

    if result is None:
        return error(f"No handler registered for: {parsed.directive_key}", "ERR_NOT_FOUND")

    if isinstance(result, dict):
        return ok(result)

    if isinstance(result, str):
        return ok({"status": "ok", "result": result})

    return error(f"Handler returned unexpected type: {type(result).__name__}", "ERR_EXECUTION")


def discover(filter: str | None = None) -> dict:
    """Return all registered directives from loaded packages. SPEC §1.2.7.

    Args:
        filter: optional filter string (future use, currently no-op)

    Returns:
        {"directives": [{domain, action, usage, domain_zh, action_zh, params, ...}, ...]}
        Empty result: {"directives": []}

    Each entry includes the mandatory baseline (domain, action) plus any
    optional fields declared in the package schema.json (domain_zh, action_zh,
    usage, usage_zh, description, description_zh, params, package, etc.).
    """
    all_directives = []
    for pkg_id, schema in _schemas.items():
        directives_raw = schema.get("directives", [])
        if isinstance(directives_raw, dict):
            directives_raw = list(directives_raw.values())
        for d in directives_raw:
            entry = {
                "domain": d.get("domain", ""),
                "action": d.get("action", ""),
            }
            # Optional fields — present only if declared in schema
            for key in (
                "domain_zh", "action_zh",
                "usage", "usage_zh",
                "description", "description_zh",
                "params", "outputs", "estimated_time",
                "source", "verified", "stale_after", "doc_status",
            ):
                if key in d:
                    entry[key] = d[key]
            # Package origin
            entry["package"] = pkg_id
            all_directives.append(entry)
    return {"directives": all_directives}


def health() -> dict:
    """Return loader version and supported protocol version.

    Returns:
        {"status": "ok", "body": "textcli-loader", "version": "...",
         "spec_version": "1.3.2", "runtime": "python"}
    """
    return {
        "status": "ok",
        "body": "textcli-loader",
        "version": __version__,
        "spec_version": "1.3.2",
        "runtime": "python",
    }


def info(meta: dict) -> dict:
    """Return loader info including loaded package and registered directives."""
    return {
        "loader": "textcli-loader",
        "package_id": meta.get("id", ""),
        "package_path": meta.get("path", ""),
        "directives": meta.get("directives", []),
        "registered": get_registered(),
    }

"""
Package loader — dynamically load schema.json + handler.py from a package directory.
"""

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


class LoadError(Exception):
    """Raised when a package cannot be loaded."""
    pass


def load_package(package_dir: str | Path) -> dict[str, Any]:
    """Load a text-cli instruction package.

    Returns metadata dict with:
        - id: package id
        - schema: parsed schema.json content
        - directives: list of {domain, action, description, ...}
        - path: resolved package directory

    Side effect: imports handler.py which registers @directive handlers
                 into the global registry.

    Raises LoadError on missing files or invalid schema.
    """
    pkg_dir = Path(package_dir).resolve()
    if not pkg_dir.is_dir():
        raise LoadError(f"Package directory not found: {pkg_dir}")

    # 1. Load schema.json
    schema_path = pkg_dir / "schema.json"
    if not schema_path.is_file():
        raise LoadError(f"Missing schema.json in {pkg_dir}")

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise LoadError(f"Invalid schema.json: {e}")

    pkg_id = schema.get("id", pkg_dir.name)

    # 2. Load handler.py (if exists)
    handler_path = pkg_dir / "handler.py"
    if handler_path.is_file():
        _import_handler(pkg_id, handler_path)

    # 3. Extract directive list
    directives_raw = schema.get("directives", [])
    if isinstance(directives_raw, dict):
        directives_raw = list(directives_raw.values())
    directives = [
        {
            "domain": d.get("domain", ""),
            "action": d.get("action", ""),
            "description": d.get("description", ""),
            "directive_zh": d.get("directive_zh", ""),
        }
        for d in directives_raw
    ]

    return {
        "id": pkg_id,
        "schema": schema,
        "directives": directives,
        "path": str(pkg_dir),
    }


def _import_handler(pkg_id: str, handler_path: Path):
    """Import handler.py as a module to trigger @directive registration."""
    module_name = f"_textcli_pkg_{pkg_id.replace('-', '_').replace('.', '_')}"

    spec = importlib.util.spec_from_file_location(
        module_name, handler_path,
        submodule_search_locations=[],
    )
    if spec is None:
        raise LoadError(f"Failed to load handler: {handler_path}")

    module = importlib.util.module_from_spec(spec)

    # Inject textcli_loader.registry into handler module namespace
    # so `from textcli_loader.registry import directive` works
    sys.modules.setdefault("textcli_loader.registry", __import__("textcli_loader.registry", fromlist=["directive"]))

    spec.loader.exec_module(module)


def list_directives(meta: dict) -> list[str]:
    """Return human-readable directive list from package metadata."""
    lines = []
    for d in meta.get("directives", []):
        domain = d["domain"]
        action = d["action"]
        zh = d.get("directive_zh", "")
        desc = d.get("description", "")
        key = f"AI:{domain};{action}"
        label = zh if zh else desc
        lines.append(f"  {key:<45} {label}")
    return lines

"""
Path file loader and registration handler.

Loads path definitions from JSON files (or inline JSON), resolves names,
registers paths as discoverable capabilities via schema output.
All comments and messages are in English.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib

logger = logging.getLogger(__name__)

# Path schema output directory
_SCHEMA_DIR = pathlib.Path(__file__).parent / "schema"

# Config paths
_CONFIG_DIR = pathlib.Path(__file__).parent.parent / "config"
_MESSAGES_EN_PATH = _CONFIG_DIR / "path_messages_en.json"
_MESSAGES_ZH_PATH = _CONFIG_DIR / "path_messages_zh.json"

# In-memory cache: (lang, mtime_en, mtime_zh) -> messages dict
_messages_cache: dict[str, dict] = {}


def load_messages(lang: str) -> dict:
    """Load internationalized messages for the given language, with caching."""
    try:
        en_mtime = _MESSAGES_EN_PATH.stat().st_mtime if _MESSAGES_EN_PATH.exists() else 0
        zh_mtime = _MESSAGES_ZH_PATH.stat().st_mtime if _MESSAGES_ZH_PATH.exists() else 0
    except OSError:
        en_mtime = zh_mtime = 0

    cache_key = f"{lang}:{en_mtime}:{zh_mtime}"
    if cache_key in _messages_cache:
        return _messages_cache[cache_key]

    messages: dict = {}
    # Always load English as fallback
    if _MESSAGES_EN_PATH.exists():
        try:
            messages.update(json.loads(_MESSAGES_EN_PATH.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load path messages (en): %s", e)

    # Overlay requested language
    if lang == "zh":
        zh_path = _MESSAGES_ZH_PATH
        if zh_path.exists():
            try:
                messages.update(json.loads(zh_path.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load path messages (zh): %s", e)

    _messages_cache[cache_key] = messages
    return messages


def fmt(key: str, messages: dict, **kwargs) -> str:
    """Format a message template with keyword arguments."""
    template = messages.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template


def resolve_var(text: str, variables: dict[str, str]) -> str:
    """Replace {var} placeholders with values from variables dict."""
    import re
    return re.sub(r'\{(\w+)\}', lambda m: variables.get(m.group(1), m.group(0)), text)


def register_path(path_def: dict, source_file: str, messages: dict) -> tuple[bool, str]:
    """Register a path as a discoverable schema in handlers/schema/<id>_schema.json.

    Returns (ok, msg).
    """
    from .path_schema import validate_declaration, check_requires

    ok, msg = validate_declaration(path_def, source_file, messages)
    if not ok:
        return False, msg

    all_ok, missing = check_requires(path_def)
    if not all_ok:
        logger.warning(
            "Path %s requires unavailable directives: %s",
            path_def.get("id", "?"), ", ".join(missing),
        )

    path_id = path_def.get("id", "")
    if not path_id:
        return False, fmt("REGISTER_ERR_NO_ID", messages)

    safe = path_id.replace("-", "_")
    schema_path = _SCHEMA_DIR / f"{safe}_schema.json"

    # Build registry-compatible schema entry
    inputs = path_def.get("input_schema", {}).get("properties", {})
    param_names = list(inputs.keys()) if inputs else []
    outputs = path_def.get("output_schema", {}).get("type", "text")

    schema_entry = {
        "id": path_id,
        "name": path_def.get("name", path_id),
        "name_zh": path_def.get("name", path_id),
        "runtime": "pipeline",
        "type": path_def.get("type", "pipeline"),
        "version": path_def.get("version", "0.1.0"),
        "mode": path_def.get("mode", "toolchain"),
        "locales": path_def.get("locales", ["en", "cn"]),
        "description": path_def.get("description", ""),
        "description_zh": path_def.get("description_zh", ""),
        "directives": [{
            "domain": "text-cli",
            "domain_zh": "文本指令",
            "action": "path",
            "action_zh": "路径",
            "usage": f"text-cli;path,{path_id},<input>",
            "usage_zh": f"文本指令;路径,{path_id},<input>",
            "description": f"Execute path: {path_def.get('name', path_id)}",
            "description_zh": f"执行路径: {path_def.get('name', path_id)}",
            "params": param_names,
            "params_desc": {p: inputs.get(p, {}).get("description", "") for p in param_names} if inputs else {},
            "outputs": [outputs],
        }],
    }

    _SCHEMA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        schema_path.write_text(json.dumps(schema_entry, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as e:
        return False, f"Failed to write schema: {e}"

    return True, str(schema_path)


def discover_path_file(path_name: str) -> pathlib.Path | None:
    """Discover a path JSON file by name (id, name, or name_zh) in TEXT_CLI_HOME/paths/."""
    paths_dir = pathlib.Path(os.environ.get(
        "TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli"))) / "paths"
    if not paths_dir.is_dir():
        return None

    for pf in sorted(paths_dir.glob("*.json")):
        try:
            pd = json.loads(pf.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        names = {pd.get("id", ""), pd.get("name", ""), pd.get("name_zh", "")}
        if path_name in names:
            return pf

    return None

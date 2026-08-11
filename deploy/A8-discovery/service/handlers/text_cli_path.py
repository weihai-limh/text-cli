"""
text-cli;path — Path interpreter entry point.

Thin facade that orchestrates path_schema, path_loader, and path_executor.
Supports file-based paths, inline JSON, name discovery, and --register mode.
All comments and messages are in English.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib

from core.registry import directive

from .path_loader import (
    discover_path_file,
    load_messages,
    register_path,
    fmt,
)
from .path_schema import validate_declaration, check_requires
from .path_executor import execute_path

logger = logging.getLogger(__name__)


@directive("text-cli", "path", domain_alias="text-cli", action_aliases={"path": "path"})
def text_cli_path(params: list[str]) -> str:
    """Execute or register a path definition.

    Modes:
      AI:text-cli;path,<file>[,<input>]          -> execute
      AI:text-cli;path,<file>,--register         -> register declaration
      AI:text-cli;path,<file>,--register,<input> -> register + execute
      AI:text-cli;path,{...json...}[,...]        -> execute inline JSON
    """
    if not params:
        msgs = load_messages("en")
        return fmt("USAGE", msgs)

    path_file = params[0].strip()

    # Parse flags and initial input
    register = False
    output_format = "text"
    initial_input = ""
    for p in params[1:]:
        ps = p.strip()
        if ps == "--register":
            register = True
        elif ps == "--json":
            output_format = "json"
        else:
            initial_input = ps

    # 1. Load path — inline JSON, file path, or name discovery
    inline_path = False
    if path_file.startswith("{"):
        try:
            path_def = json.loads(path_file)
            inline_path = True
        except json.JSONDecodeError as e:
            msgs = load_messages("en")
            return fmt("LOAD_ERR_PARSE", msgs, e=f"Inline JSON: {e}")
    else:
        path_def = None

    if not inline_path:
        p = pathlib.Path(path_file)
        if not p.is_file():
            p = discover_path_file(path_file)
            if p is None:
                msgs = load_messages("en")
                return fmt("LOAD_ERR_NOT_FOUND", msgs, path=path_file)

        try:
            path_def = json.loads(p.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            msgs = load_messages("en")
            return fmt("LOAD_ERR_PARSE", msgs, e=str(e))

    lang = path_def.get("lang", "en")
    messages = load_messages(lang)

    # 2. Register mode
    if register:
        source = "<inline>" if inline_path else str(path_file)
        ok, msg = validate_declaration(path_def, source, messages)
        if not ok:
            return fmt("REGISTER_ERR_VALIDATION", messages, msg=msg)

        all_ok, missing = check_requires(path_def)
        if not all_ok:
            logger.warning(
                "Path %s requires unavailable directives: %s",
                path_def.get("id", "?"), ", ".join(missing),
            )

        ok, msg = register_path(path_def, source, messages)
        if not ok:
            return msg

        path_id = path_def["id"]
        ver = path_def.get("version", "?")
        ptype = path_def.get("type", "?")
        reqs = path_def.get("requires", [])
        registry_path = msg

        result = (
            fmt("REGISTER_OK", messages, name=path_def.get('name', path_id), ver=ver) + "\n" +
            fmt("REGISTER_OK_DETAIL", messages, id=path_id, type=ptype,
                reqs=', '.join(reqs) if reqs else '(none)') + "\n" +
            fmt("REGISTER_OK_PATH", messages, path=registry_path)
        )

        if not initial_input:
            return result
        result += "\n"

    # 3. Execute path
    mode = path_def.get("mode", "toolchain")
    if mode not in ("toolchain", "parallel"):
        return fmt("LOAD_ERR_UNSUPPORTED_MODE", messages, mode=mode)

    steps = path_def.get("steps", [])
    if not steps:
        return fmt("LOAD_ERR_NO_STEPS", messages)

    exec_result = execute_path(path_def, initial_input,
                               messages=messages, output_format=output_format)

    if register:
        return result + "\n" + exec_result
    return exec_result

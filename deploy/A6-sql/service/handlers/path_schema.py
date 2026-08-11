"""
Path schema validation and directive parsing.

Handles path definition validation, requirement checking, and
low-level directive string parsing (no execution logic).
All comments and messages are in English.
"""

from __future__ import annotations

import json
import logging
import re

logger = logging.getLogger(__name__)

# Required fields for path declaration
_REQUIRED_DECLARATION = frozenset({"id", "name", "version", "type", "steps"})

# Accepted path types
_ACCEPTED_TYPES = frozenset({"skill", "pipeline"})

# Accepted execution modes
_ACCEPTED_MODES = frozenset({"toolchain", "parallel"})


def validate_declaration(path_def: dict, path_file: str, messages: dict) -> tuple[bool, str]:
    """Validate that a path definition has the required declaration fields."""
    missing = [f for f in _REQUIRED_DECLARATION if f not in path_def]
    if missing:
        hint = " (expected: id, name, version, type, steps)"
        return False, _fmt_local("REGISTER_ERR_MISSING_FIELDS", messages,
                                 fields=', '.join(missing)) + hint

    ptype = path_def.get("type", "")
    if ptype not in _ACCEPTED_TYPES:
        return False, _fmt_local("REGISTER_ERR_UNSUPPORTED_TYPE", messages, type=ptype)

    mode = path_def.get("mode", "toolchain")
    if mode not in _ACCEPTED_MODES:
        return False, _fmt_local("REGISTER_ERR_UNSUPPORTED_MODE", messages, mode=mode)

    # Step-level map validation: scan steps[] recursively for mode:"map"
    ok, err = _validate_map_steps(path_def.get("steps", []))
    if not ok:
        return False, err

    return True, ""


def _validate_map_steps(steps: list) -> tuple[bool, str]:
    """Recursively validate mode:'map' steps have required items/steps fields."""
    for i, step in enumerate(steps, 1):
        mode = step.get("mode", "toolchain")
        if mode == "map":
            if "items" not in step:
                return False, f"step {i}: mode='map' requires 'items' field"
            if "steps" not in step:
                return False, f"step {i}: mode='map' requires 'steps' field"
        # Recurse into sub-steps (parallel, map body, etc.)
        sub_steps = step.get("steps", [])
        if sub_steps:
            ok, err = _validate_map_steps(sub_steps)
            if not ok:
                return False, err
    return True, ""


def check_requires(path_def: dict) -> tuple[bool, list[str]]:
    """Check which required directives exist in the current registry.

    Returns (all_available, missing_list).
    """
    from core.registry import get_registered_directives

    requires = path_def.get("requires", [])
    if not requires:
        return True, []

    registered = get_registered_directives()
    all_known: set[str] = set()
    for domain, actions in registered.items():
        for action in actions:
            all_known.add(f"{domain};{action}")

    missing = [r for r in requires if r not in all_known]
    return len(missing) == 0, missing


def parse_directive(raw: str) -> tuple[str, str, list[str]]:
    """Parse a raw directive string into (domain, action, params)."""
    raw = raw.strip()
    if ';' not in raw:
        return raw, "", []
    domain, rest = raw.split(';', 1)
    if ',' not in rest:
        return domain, rest, []
    action, params_str = rest.split(',', 1)
    return domain, action, _split_params(params_str)


def _split_params(params_str: str) -> list[str]:
    """Split comma-separated params, preserving nested structures."""
    parts = []
    current = []
    depth = 0
    for ch in params_str:
        if ch in ('{', '['):
            depth += 1
            current.append(ch)
        elif ch in ('}', ']'):
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            parts.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append(''.join(current).strip())
    return parts


def _fmt_local(key: str, messages: dict, **kwargs) -> str:
    """Format a message template with keyword arguments."""
    template = messages.get(key, key)
    if kwargs:
        return template.format(**kwargs)
    return template

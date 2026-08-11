"""
tc-markdown handler — Read and parse Markdown files.

Directives:
    tc-markdown;read,<path>                  → full file content
    tc-markdown;headings,<path>              → heading tree
    tc-markdown;section,<path>,<heading>     → extract section by heading

Author: Tide 🌊 — 2026-05-17
"""

import logging
import os
import re
from pathlib import Path

from core.registry import directive

logger = logging.getLogger(__name__)

_BASE_DIR: Path | None = None

HEADING_RE = re.compile(r'^(#{1,6})\s+(.+)$', re.MULTILINE)


def _auto_init():
    """Auto-initialise on module import (workaround for __import__ hyphen bug)."""
    global _BASE_DIR
    if not _BASE_DIR:
        project_root = Path(__file__).resolve().parent.parent.parent
        _BASE_DIR = project_root
        logger.info("tc-markdown auto-initialised, base dir: %s", _BASE_DIR)
_auto_init()


def init_tc_markdown_handler(base_dir: str = None):
    """Initialise with allowed base directory (called by handler_inits)."""
    global _BASE_DIR
    _BASE_DIR = Path(base_dir).resolve() if base_dir else Path(os.getcwd())
    logger.info("tc-markdown initialised, base dir: %s", _BASE_DIR)


def _resolve_path(path_str: str) -> Path:
    """Resolve and validate file path. Supports:
    - Absolute paths (must be under _BASE_DIR or a configured allowed dir)
    - Relative paths (resolved against _BASE_DIR)
    """
    if not _BASE_DIR:
        raise RuntimeError("tc-markdown not initialised")
    p = Path(path_str)
    if not p.is_absolute():
        p = (_BASE_DIR / path_str)
    p = p.resolve()
    allowed = [
        str(_BASE_DIR),
        "/tmp",
    ]
    if any(str(p).startswith(prefix) for prefix in allowed):
        pass
    else:
        raise ValueError(f"Path traversal denied: {path_str}")
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path_str}")
    if not p.is_file():
        raise ValueError(f"Not a file: {path_str}")
    return p


def _read_file(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _parse_headings(text: str) -> list[dict]:
    """Extract heading structure as [{level, text, line}]."""
    headings = []
    for m in HEADING_RE.finditer(text):
        headings.append({
            "level": len(m.group(1)),
            "text": m.group(2).strip(),
            "line": text[:m.start()].count('\n') + 1,
        })
    return headings


def _find_section(text: str, heading_name: str) -> str | None:
    """Extract content under a specific heading until next same/higher-level heading."""
    lines = text.split('\n')
    in_section = False
    section_level = None
    result = []

    for line in lines:
        m = HEADING_RE.match(line)
        if m:
            level = len(m.group(1))
            title = m.group(2).strip()
            if title == heading_name:
                in_section = True
                section_level = level
                continue
            if in_section and level <= section_level:
                break
        if in_section:
            result.append(line)

    return '\n'.join(result).strip() if result else None



@directive("tc-markdown", "read", domain_alias=None, action_aliases={"read": "读取"})
def markdown_read(params: list[str]) -> dict:
    """tc-markdown;read,<path> — read full markdown file."""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: tc-markdown;read,<path>"
        }
    try:
        path = _resolve_path(params[0])
        content = _read_file(path)
        return {
            "status": "ok",
            "path": str(path),
            "content": content,
            "size": len(content),
        }
    except FileNotFoundError as e:
        return {"status": "error", "reason": str(e)}
    except ValueError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-markdown read failed")
        return {"status": "error", "reason": f"Read failed: {e}"}


@directive("tc-markdown", "headings", domain_alias=None, action_aliases={"headings": "标题"})
def markdown_headings(params: list[str]) -> dict:
    """tc-markdown;headings,<path> — extract heading structure."""
    if not params:
        return {
            "status": "error",
            "reason": "Usage: tc-markdown;headings,<path>"
        }
    try:
        path = _resolve_path(params[0])
        content = _read_file(path)
        headings = _parse_headings(content)
        return {
            "status": "ok",
            "path": str(path),
            "headings": headings,
        }
    except FileNotFoundError as e:
        return {"status": "error", "reason": str(e)}
    except ValueError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-markdown headings failed")
        return {"status": "error", "reason": f"Heading extraction failed: {e}"}


@directive("tc-markdown", "section", domain_alias=None, action_aliases={"section": "章节"})
def markdown_section(params: list[str]) -> dict:
    """tc-markdown;section,<path>,<heading> — extract content under a heading."""
    if len(params) < 2:
        return {
            "status": "error",
            "reason": "Usage: tc-markdown;section,<path>,<heading>"
        }
    try:
        path = _resolve_path(params[0])
        heading = params[1]
        content = _read_file(path)
        section = _find_section(content, heading)
        if section is None:
            return {
                "status": "error",
                "reason": f"Heading '{heading}' not found in {params[0]}"
            }
        return {
            "status": "ok",
            "path": str(path),
            "heading": heading,
            "content": section,
        }
    except FileNotFoundError as e:
        return {"status": "error", "reason": str(e)}
    except ValueError as e:
        return {"status": "error", "reason": str(e)}
    except Exception as e:
        logger.exception("tc-markdown section failed")
        return {"status": "error", "reason": f"Section extraction failed: {e}"}

"""
text-cli;nocode — A4 knowledge engine handler (skeleton).

Loads embedded knowledge files (Markdown) from service/knowledge/<domain>/
and returns file list + index for AI-driven diagnosis/recommendation.

Formats:
    text-cli;nocode,<domain>                   → list files + index
    text-cli;nocode,<domain>,<filename>.md     → read specific file

Knowledge files are deployed by path packages (runtime=path) via
_deploy_path_resources() during install.

Author: Tide
"""

import json
import logging
from pathlib import Path

from core.registry import directive

logger = logging.getLogger(__name__)

_PROJECT_ROOT: Path | None = None
_KNOWLEDGE_DIR: Path | None = None


def init_text_cli_nocode_handler(project_root: str = None):
    global _PROJECT_ROOT, _KNOWLEDGE_DIR
    if project_root:
        _PROJECT_ROOT = Path(project_root)
        _KNOWLEDGE_DIR = _PROJECT_ROOT / "knowledge"
    logger.info("text-cli;nocode initialised")


@directive("text-cli", "nocode", domain_alias="文本指令", action_aliases={"nocode": "无代码"})
def text_cli_nocode(params: list[str]) -> dict:
    if not params:
        return {
            "status": "error",
            "reason": "Usage: text-cli;nocode,<knowledge_domain>[,<file>]"
        }

    domain = params[0]
    if not _KNOWLEDGE_DIR:
        return {"status": "error", "reason": "knowledge directory not configured"}

    domain_dir = _KNOWLEDGE_DIR / domain
    if not domain_dir.is_dir():
        return {
            "status": "error",
            "reason": f"knowledge domain not found: {domain}",
            "available": [d.name for d in _KNOWLEDGE_DIR.iterdir() if d.is_dir()],
        }

    # Specific file requested
    if len(params) > 1:
        file_name = params[1]
        file_path = domain_dir / file_name
        if not file_path.suffix:
            file_path = file_path.with_suffix(".md")
        if not file_path.exists():
            return {
                "status": "error",
                "reason": f"file not found: {file_name}",
                "domain": domain,
            }
        content = file_path.read_text(encoding="utf-8")
        return {
            "status": "ok",
            "domain": domain,
            "file": file_path.name,
            "content": content,
        }

    # List all knowledge files
    files = []
    for f in sorted(domain_dir.rglob("*.md")):
        rel = f.relative_to(domain_dir)
        files.append({
            "name": str(rel).replace("\\", "/"),
            "size": f.stat().st_size,
        })

    # Try to read an index file if present
    index_content = ""
    index_path = domain_dir / "knowledge-index.md"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")[:2000]

    return {
        "status": "ok",
        "domain": domain,
        "files": files,
        "index": index_content,
    }

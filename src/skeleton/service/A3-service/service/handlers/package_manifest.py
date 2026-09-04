"""
Package manifest — tracks installed instruction packages.

Manages the installed_packages.json manifest file.
Each entry records what files belong to which package,
enabling export, uninstall, and list operations.

Author: Tide 🌊 — 2026-05-17
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).resolve().parent.parent / "config" / "installed_packages.json"


def _load() -> dict:
    """Load manifest dict. Returns {} on first run."""
    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("packages", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(packages: dict):
    """Persist manifest to disk."""
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(MANIFEST_PATH, 'w', encoding='utf-8') as f:
        json.dump({"packages": packages}, f, ensure_ascii=False, indent=2)


def get(package_id: str) -> dict | None:
    return _load().get(package_id)


def register(package_id: str, domain: str, pkg_type: str, source: str,
             files: dict, directives: list[str]) -> bool:
    """Register a package in the manifest. Returns True if new, False if updated."""
    packages = _load()
    is_new = package_id not in packages
    packages[package_id] = {
        "id": package_id,
        "domain": domain,
        "type": pkg_type,
        "source": source,
        "files": files,
        "directives": directives,
        "installed_at": _now(),
    }
    _save(packages)
    logger.info("package manifest: %s %s", "registered" if is_new else "updated", package_id)
    return is_new


def remove(package_id: str) -> bool:
    """Remove a package from the manifest. Returns True if existed."""
    packages = _load()
    existed = package_id in packages
    if existed:
        del packages[package_id]
        _save(packages)
        logger.info("package manifest: removed %s", package_id)
    return existed


def mark_fields(package_id: str, **fields) -> bool:
    """Merge extra fields into an existing manifest entry (no-op if absent).

    Used for install-time capability probes (e.g. live_config flag, ISS-02).
    """
    packages = _load()
    entry = packages.get(package_id)
    if not entry:
        return False
    entry.update(fields)
    _save(packages)
    return True


def list_all() -> list[dict]:
    """List all installed packages."""
    return list(_load().values())


def _now() -> str:
    from datetime import datetime, timedelta, timezone
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).isoformat(timespec="seconds")

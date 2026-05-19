"""
handler mixin aggregation — all domain handlers gathered here.

Built-in handlers are imported directly. Package handlers are
discovered dynamically from the packages/ directory.
"""

import importlib
import logging
import pathlib

logger = logging.getLogger("copilot.handlers")

# ── Built-in handlers (always loaded) ──────────

from handlers.codec import CodecHandlers
from handlers.key import KeyHandlers
from handlers.skill_bridge import SkillBridgeHandlers
from handlers.package_manager import PackageManagerHandlers

# ── Dynamic package discovery ──────────────────

_packages_dir = pathlib.Path(__file__).resolve().parent.parent / "packages"
_discovered = []

if _packages_dir.is_dir():
    for _pkg_dir in sorted(_packages_dir.iterdir()):
        if _pkg_dir.name.startswith("_"):
            continue
        if not _pkg_dir.is_dir():
            continue
        _handler = _pkg_dir / "handler.py"
        if not _handler.is_file():
            continue
        _name = _pkg_dir.name
        try:
            _mod = importlib.import_module(f"packages.{_name}.handler")
            # Find the handler class (any public class ending with Handlers)
            for _attr in dir(_mod):
                if _attr.endswith("Handlers") and not _attr.startswith("_"):
                    _cls = getattr(_mod, _attr)
                    globals()[_attr] = _cls
                    _discovered.append(_attr)
                    break
            else:
                logger.warning("No Handlers class found in packages.%s.handler", _name)
        except Exception as e:
            logger.warning("Failed to load package '%s': %s", _name, e)

__all__ = [
    'CodecHandlers',
    'KeyHandlers',
    'SkillBridgeHandlers',
    'PackageManagerHandlers',
] + _discovered

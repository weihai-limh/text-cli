"""
Fault-tolerant handler auto-discovery.

Scans this directory for handler modules and imports them.
Missing dependencies are caught per-module so a single broken
dependency (e.g. missing PIL, openai) does not crash the whole
service.  Degraded handlers are logged but the service continues.
"""
import importlib
import logging
import pathlib
import pkgutil

logger = logging.getLogger("text-cli.handlers")

package_dir = pathlib.Path(__file__).parent
packages_dir = package_dir.parent / "packages"
degraded: list[str] = []

# ── Skeleton handlers ──
for _, module_name, _ in pkgutil.iter_modules([str(package_dir)]):
    if module_name == "__init__":
        continue
    try:
        importlib.import_module(f".{module_name}", package=__name__)
    except ImportError as exc:
        degraded.append(module_name)
        logger.warning(
            "Handler degraded — %s (missing: %s)", module_name, exc.name
        )
    except Exception:
        logger.exception("Handler failed to load — %s", module_name)

# ── Package handlers (service/packages/<id>/handler.py) ──
if packages_dir.is_dir():
    for pkg_dir in sorted(packages_dir.iterdir()):
        if not pkg_dir.is_dir():
            continue
        handler_file = pkg_dir / "handler.py"
        if not handler_file.is_file():
            continue
        pkg_id = pkg_dir.name
        # Build dotted import path: service.packages.<pkg_id>.handler
        import_path = f"packages.{pkg_id}.handler"
        try:
            importlib.import_module(import_path)
            logger.debug("Package loaded: %s", pkg_id)
        except ImportError as exc:
            degraded.append(pkg_id)
            logger.warning(
                "Package degraded — %s (missing: %s)", pkg_id, exc.name
            )
        except Exception:
            logger.exception("Package failed to load — %s", pkg_id)

if degraded:
    logger.info("Degraded handlers: %s", ", ".join(degraded))

# ── JS handler dynamic registration ──
# For runtime=node packages, create wrapper functions that route
# directives to Node.js subprocesses (stdin JSON → stdout text).
try:
    import json as _json
    from pathlib import Path as _Path
    from core.registry import directive as _register
    from .js_bridge import make_js_handler

    _js_registered = 0

    # ── Scan schemas: handlers/schema/ (legacy) + packages/*/schema.json ──
    _schema_paths: list[_Path] = []
    _legacy_schema_dir = _Path(__file__).parent / "schema"
    if _legacy_schema_dir.is_dir():
        _schema_paths.extend(sorted(_legacy_schema_dir.glob("*_schema.json")))
    _packages_schema_dir = _Path(__file__).parent.parent / "packages"
    if _packages_schema_dir.is_dir():
        _schema_paths.extend(sorted(_packages_schema_dir.glob("*/schema.json")))

    for _sf in _schema_paths:
        try:
            _schema = _json.loads(_sf.read_text(encoding="utf-8"))
        except (_json.JSONDecodeError, OSError):
            continue

        if not isinstance(_schema, dict):
            continue

        if _schema.get("runtime") != "node":
            continue

        _js_file = f"{_schema['id']}.js"
        _js_handler_dir = _Path(__file__).parent.parent / "packages" / _schema['id']
        if not (_js_handler_dir / _js_file).exists() and not (_Path(__file__).parent / _js_file).exists():
            logger.warning("JS handler file missing: %s", _js_file)
            continue

        for _d in _schema.get("directives", []):
            _dom = _d.get("domain", "")
            _act = _d.get("action", "")
            if _dom and _act:
                _register(_dom, _act)(
                    make_js_handler(_js_file, _dom, _act)
                )
                _js_registered += 1

            _dc = _d.get("domain_cn", "")
            _ac = _d.get("action_cn", "")
            if _dc and _ac:
                _register(_dc, _ac)(
                    make_js_handler(_js_file, _dc, _ac)
                )
                _js_registered += 1

    if _js_registered:
        logger.info("JS directives registered: %d", _js_registered)
except Exception:
    logger.exception("JS dynamic registration failed")

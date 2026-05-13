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
degraded: list[str] = []

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

if degraded:
    logger.info("Degraded handlers: %s", ", ".join(degraded))

"""
Package manager handler — co-install, co-uninstall, co-list.

Manages copilot instruction packages in the packages/ directory.
Each package is a self-contained directory with schema.json and handler.py.

Install also copies adapters/ (if present) to copilot/adapters/.
"""

import importlib
import json
import logging
import pathlib
import shutil

from core import ok, error

logger = logging.getLogger("copilot.package_manager")

# Default package source directories
DEFAULT_SOURCE_DIRS = [
    pathlib.Path("/root/tide/new_package"),
    pathlib.Path("/root/.openclaw/workspace/tide-scripts/text-cliV1"),
]


class PackageManagerHandlers:
    """Mixin: copilot package install, uninstall, and list."""

    def _resolve_package(self, name: str) -> pathlib.Path | None:
        """Find a package directory by name across source dirs."""
        for sdir in DEFAULT_SOURCE_DIRS:
            candidate = sdir / name
            if candidate.is_dir() and (candidate / "schema.json").is_file():
                return candidate
        return None

    def _handle_text_cli_co_install(self, params: list) -> dict:
        """text-cli;co-install,<package_name>

        Install a copilot instruction package from source to packages/.
        Copies schema.json, handler.py, and adapters/ (if present).
        """
        if not params or not params[0]:
            return error("missing_param",
                         "Usage: text-cli;co-install,<package_name>")

        name = params[0].strip()
        packages_dir = pathlib.Path(__file__).resolve().parent.parent / "packages"

        # Resolve source
        src_dir = self._resolve_package(name)
        if src_dir is None:
            searched = ", ".join(str(d) for d in DEFAULT_SOURCE_DIRS)
            return error("not_found",
                         f"Package '{name}' not found in source dirs: {searched}")

        # Validate schema.json
        schema_path = src_dir / "schema.json"
        if not schema_path.is_file():
            return error("invalid_package",
                         f"Package '{name}' missing schema.json")
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            return error("invalid_schema", f"schema.json parse failed: {e}")

        pkg_id = schema.get("id", name)
        target_dir = packages_dir / pkg_id

        # Check existing
        if target_dir.exists():
            return error("already_installed",
                         f"Package '{pkg_id}' already installed. "
                         f"Use text-cli;co-uninstall,{pkg_id} first, "
                         f"or text-cli;co-install,{pkg_id},--force to overwrite")

        force = len(params) > 1 and params[1].strip() == "--force"

        try:
            # Copy handler.py
            handler_src = src_dir / "handler.py"
            handler_dst = target_dir / "handler.py"
            if handler_src.is_file():
                target_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(handler_src, handler_dst)

            # Copy schema.json
            schema_dst = target_dir / "schema.json"
            shutil.copy2(schema_path, schema_dst)

            # Copy adapters/ if present
            adapters_src = src_dir / "adapters"
            if adapters_src.is_dir():
                adapters_dst = (pathlib.Path(__file__).resolve().parent.parent
                                / "adapters")
                for f in adapters_src.rglob("*.py"):
                    rel = f.relative_to(adapters_src)
                    dst = adapters_dst / rel
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    if dst.exists() and not force:
                        return error("adapter_conflict",
                                     f"Adapter '{rel}' already exists. "
                                     "Use --force to overwrite.")
                    shutil.copy2(f, dst)

        except OSError as e:
            return error("install_failed", f"File copy failed: {e}")

        # Reload handlers to pick up the new package
        try:
            mod = importlib.import_module(f"packages.{pkg_id}.handler")
            importlib.reload(mod)
        except Exception:
            pass  # Will be picked up on next copilot restart

        return ok(f"Package '{pkg_id}' installed. Restart copilot to activate.")

    def _handle_text_cli_co_uninstall(self, params: list) -> dict:
        """text-cli;co-uninstall,<package_name>"""
        if not params or not params[0]:
            return error("missing_param",
                         "Usage: text-cli;co-uninstall,<package_name>")

        name = params[0].strip()
        packages_dir = pathlib.Path(__file__).resolve().parent.parent / "packages"
        target_dir = packages_dir / name

        if not target_dir.is_dir():
            return error("not_installed",
                         f"Package '{name}' is not installed")

        try:
            # Remove package adapters (look up from source for file list)
            src_dir = self._resolve_package(name)
            if src_dir:
                adapters_src = src_dir / "adapters"
                if adapters_src.is_dir():
                    adapters_dst = (pathlib.Path(__file__).resolve().parent.parent
                                    / "adapters")
                    for f in adapters_src.rglob("*.py"):
                        rel = f.relative_to(adapters_src)
                        dst = adapters_dst / rel
                        if dst.is_file():
                            dst.unlink()

            shutil.rmtree(target_dir)
        except OSError as e:
            return error("uninstall_failed", f"Remove failed: {e}")

        return ok(f"Package '{name}' uninstalled. Restart copilot to complete.")

    def _handle_text_cli_co_list(self, params: list) -> dict:
        """text-cli;co-list — list installed copilot packages."""
        packages_dir = pathlib.Path(__file__).resolve().parent.parent / "packages"
        installed = []

        if packages_dir.is_dir():
            for pkg_dir in sorted(packages_dir.iterdir()):
                if pkg_dir.name.startswith("_") or not pkg_dir.is_dir():
                    continue
                schema_file = pkg_dir / "schema.json"
                if schema_file.is_file():
                    try:
                        schema = json.loads(schema_file.read_text(encoding="utf-8"))
                        installed.append({
                            "id": schema.get("id", pkg_dir.name),
                            "name_cn": schema.get("name_cn", ""),
                            "runtime": schema.get("runtime", ""),
                            "directives": len(schema.get("directives", [])),
                        })
                    except Exception:
                        installed.append({"id": pkg_dir.name, "error": "schema parse failed"})

        if not installed:
            return ok("No copilot packages installed.")

        lines = [f"{p['id']}  {p.get('name_cn', '')}  ({p.get('runtime', '')}, {p.get('directives', 0)} directives)"
                 for p in installed]
        return ok("\n".join(lines))

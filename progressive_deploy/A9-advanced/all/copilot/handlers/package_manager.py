"""
Package manager handler — co-install, co-uninstall, co-list.

Manages copilot instruction packages in the packages/ directory.
Each package is a self-contained directory with schema.json and handler.py.

Install also copies adapters/ (if present) to copilot/adapters/.
"""

import importlib
import json
import logging
import os
import pathlib
import shutil
import types

from core import ok, error

logger = logging.getLogger("copilot.package_manager")


def _get_source_dirs() -> list[pathlib.Path]:
    raw = os.environ.get("TEXT_CLI_PACKAGE_SOURCE_DIRS", "")
    if raw:
        return [pathlib.Path(d.strip()) for d in raw.split(":") if d.strip()]
    return [
        pathlib.Path(os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli"))) / "copilot" / "packages",
    ]


class PackageManagerHandlers:
    """Mixin: copilot package install, uninstall, and list."""

    # ── auxiliary_config.json ops management ──

    def _write_package_ops(self, pkg_id: str, schema: dict) -> int:
        """Write package directives into auxiliary_config.json operations.

        Returns number of operation entries written.
        On restart, handlers/__init__.py discovers *Handlers class from
        packages/<pkg_id>/handler.py and mixes it into CopilotCore MRO.
        _register_handlers() auto-discovers _handle_* methods.
        """
        directives = schema.get("directives", [])
        if not directives:
            return 0

        config_path = pathlib.Path(__file__).resolve().parent.parent / "auxiliary_config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Cannot read auxiliary_config.json")
            return 0

        operations = config.setdefault("security", {}).setdefault("operations", {})
        written = 0

        for d in directives:
            op_domain = d.get("domain", "")
            op_action = d.get("action", "")
            if not op_domain or not op_action:
                continue
            op_id = f"{op_domain};{op_action}"

            # Don't overwrite existing ops
            if op_id in operations:
                continue

            # Build aliases: English canonical + Chinese
            aliases = [op_id]
            domain_cn = d.get("domain_cn", "")
            action_cn = d.get("action_cn", "")
            if domain_cn and action_cn:
                aliases.append(f"{domain_cn};{action_cn}")

            # Build parameters list
            param_names = d.get("params", [])
            params_desc = d.get("params_desc", {})
            # Describe required vs optional
            params_display = []
            for p in param_names:
                desc = params_desc.get(p, "")
                if desc:
                    params_display.append(f"{p}({desc})")
                else:
                    params_display.append(p)

            operations[op_id] = {
                "level": "read",
                "aliases": aliases,
                "description": d.get("description_cn", d.get("description", "")),
                "description_en": d.get("description", d.get("description_cn", "")),
                "parameters": params_display,
                "parameters_en": param_names,
                "returns": "rst_data.text = result output",
            }
            written += 1

        if written:
            try:
                config_path.write_text(
                    json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
                logger.info("Wrote %d ops to auxiliary_config.json for package '%s'",
                            written, pkg_id)
            except OSError as e:
                logger.warning("Failed to write auxiliary_config.json: %s", e)
                return 0

        return written

    def _remove_package_ops(self, pkg_id: str) -> int:
        """Remove package operations from auxiliary_config.json on uninstall."""
        config_path = pathlib.Path(__file__).resolve().parent.parent / "auxiliary_config.json"
        try:
            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception:
            return 0

        operations = config.get("security", {}).get("operations", {})
        removed = 0

        # Find package's schema to get directive list (it's about to be deleted)
        packages_dir = pathlib.Path(__file__).resolve().parent.parent / "packages" / pkg_id
        schema_file = packages_dir / "schema.json"
        if schema_file.is_file():
            try:
                schema = json.loads(schema_file.read_text(encoding="utf-8"))
                for d in schema.get("directives", []):
                    op_id = f"{d.get('domain', '')};{d.get('action', '')}"
                    if op_id in operations:
                        del operations[op_id]
                        removed += 1
            except Exception:
                pass

        if removed:
            try:
                config_path.write_text(
                    json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
            except OSError:
                pass

        return removed

    def _wire_package_handlers(self, pkg_id: str, mod) -> bool:
        """Dynamically attach _handle_* methods from a *Handlers mixin class.

        For immediate use after co-install (before restart).
        On restart, handlers/__init__.py properly mixes *Handlers into Copilot MRO.
        """
        for attr in dir(mod):
            if attr.endswith("Handlers") and not attr.startswith("_"):
                cls = getattr(mod, attr)
                for method_name in dir(cls):
                    if method_name.startswith("_handle_") and not method_name.startswith("__"):
                        method = getattr(cls, method_name)
                        if callable(method):
                            # Bind to self (CopilotCore instance)
                            import types
                            bound = types.MethodType(method, self)
                            setattr(self, method_name, bound)
                            logger.debug("Wired %s → %s", method_name, pkg_id)
                return True
        return False

    # ── Resolve package source ──

    def _resolve_package(self, name: str) -> pathlib.Path | None:
        for sdir in _get_source_dirs():
            for candidate in sdir.rglob("schema.json"):
                if candidate.parent.name == name:
                    return candidate.parent
                try:
                    schema = json.loads(candidate.read_text(encoding="utf-8"))
                    if schema.get("id") == name:
                        return candidate.parent
                except Exception:
                    pass
        return None

    def _handle_text_cli_co_install(self, params: list) -> dict:
        """text-cli;co-install,<package_name>

        Install a copilot instruction package from source to packages/.
        Copies handler.py, schema.json, and ALL accessory files/dirs
        (whitelists/, config/, data/, adapters/, README.md, etc.).
        Reloads handlers so @directive-registered instructions are
        available immediately without a restart.
        """
        if not params or not params[0]:
            return error("missing_param",
                         "Usage: text-cli;co-install,<package_name>")

        name = params[0].strip()
        packages_dir = pathlib.Path(__file__).resolve().parent.parent / "packages"

        # Resolve source
        src_dir = self._resolve_package(name)
        if src_dir is None:
            searched = ", ".join(str(d) for d in _get_source_dirs())
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
        force = len(params) > 1 and params[1].strip() == "--force"
        if target_dir.exists() and not force:
            return error("already_installed",
                         f"Package '{pkg_id}' already installed. "
                         f"Use text-cli;co-uninstall,{pkg_id} first, "
                         f"or text-cli;co-install,{pkg_id},--force to overwrite")
        if target_dir.exists() and force:
            shutil.rmtree(target_dir)

        target_dir.mkdir(parents=True, exist_ok=True)

        copied = []
        try:
            # Copy ALL files and subdirs from source, except __pycache__ / .git
            for item in sorted(src_dir.iterdir()):
                name_l = item.name
                if name_l.startswith(('.', '__pycache__')):
                    continue

                dst = target_dir / name_l

                # adapters/ → copilot/adapters/ (merged)
                if name_l == 'adapters' and item.is_dir():
                    adapters_dst = (pathlib.Path(__file__).resolve().parent.parent
                                    / "adapters")
                    for f in item.rglob("*.py"):
                        rel = f.relative_to(item)
                        adst = adapters_dst / rel
                        adst.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(f, adst)
                    copied.append(f"adapters/ → copilot/adapters/")
                    continue

                # whitelists/ → copilot/whitelists/ (merged)
                if name_l == 'whitelists' and item.is_dir():
                    wl_dst = (pathlib.Path(__file__).resolve().parent.parent
                              / "whitelists")
                    for f in item.iterdir():
                        shutil.copy2(f, wl_dst / f.name)
                    copied.append(f"whitelists/ → copilot/whitelists/")
                    continue

                # Regular file or directory → packages/<pkg_id>/
                if item.is_dir():
                    shutil.copytree(item, dst)
                else:
                    shutil.copy2(item, dst)
                copied.append(name_l)

        except OSError as e:
            return error("install_failed", f"File copy failed: {e}")

        # ── Register directives in auxiliary_config.json ──
        # Auto-generate operations entries from schema.json directives
        # so _register_handlers auto-discovers _handle_* methods
        ops_written = self._write_package_ops(pkg_id, schema)

        # ── Reload handlers ──
        # Dynamic attach + re-register for immediate availability
        try:
            mod = importlib.import_module(f"packages.{pkg_id}.handler")
            importlib.reload(mod)
            # Discover *Handlers mixin class and attach _handle_ methods
            handler_wired = self._wire_package_handlers(pkg_id, mod)
            # Re-run _register_handlers so dispatcher picks up new directives
            self._register_handlers()
            logger.info("co-install %s: handlers reloaded (ops=%d, wired=%s)",
                        pkg_id, ops_written, handler_wired)
        except Exception as e:
            logger.warning("co-install %s: reload failed, will need restart: %s", pkg_id, e)

        restart_hint = "" if ops_written else " Restart copilot to load."
        return ok(
            f"Package '{pkg_id}' installed ({len(copied)} files, {ops_written} ops). "
            f"Instructions available immediately.{restart_hint}")

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

        # ── Remove operations from auxiliary_config.json ──
        self._remove_package_ops(name)

        # ── Re-register (reload not needed since module is already gone) ──
        # Remove any dynamically attached _handle_ methods
        for attr in list(dir(self)):
            if attr.startswith(f'_handle_{name.replace("-", "_")}_'):
                try:
                    delattr(self, attr)
                except Exception:
                    pass
        self._register_handlers()

        return ok(f"Package '{name}' uninstalled. Instructions removed immediately.")

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

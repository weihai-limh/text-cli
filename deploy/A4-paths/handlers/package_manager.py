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


# ── Skill bridge routes management ──

ROUTES_PATH = pathlib.Path(__file__).resolve().parent.parent / "config" / "skill_bridge_routes.json"

# Known package → skill directory name mappings
SKILL_DIR_MAP = {
    "skill-websearch": "tavily-search",
    "skill-csv2json": "csv2json",
    "skill-bdmap": "baidu-ai-map",
}


def _load_skill_routes_file() -> dict:
    """Load current skill_bridge_routes.json, return {routes} dict."""
    try:
        with open(ROUTES_PATH) as f:
            return json.load(f).get("routes", {})
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_skill_routes_file(routes: dict) -> bool:
    """Save routes dict to skill_bridge_routes.json, return True on success."""
    try:
        ROUTES_PATH.write_text(
            json.dumps({"routes": routes}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8")
        return True
    except OSError as e:
        logger.warning("Failed to write skill_bridge_routes.json: %s", e)
        return False


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
                # Sync in-memory config so _register_handlers sees new ops
                if hasattr(self, 'config'):
                    self.config = config
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
                if hasattr(self, 'config'):
                    self.config = config
            except OSError:
                pass

        return removed

    def _wire_package_handlers(self, pkg_id: str, mod) -> bool:
        """Dynamically attach _handle_* methods from a *Handlers mixin class.

        For immediate use after co-install (before restart).
        On restart, handlers/__init__.py properly mixes *Handlers into Copilot MRO.
        Also calls init_* function if present, passing project_root from config.
        """
        # ── Auto-call init function ──
        safe = pkg_id.replace("-", "_")
        for init_name in (f"init_{safe}_handler", f"init_{pkg_id.replace('-', '_')}_handler"):
            init_fn = getattr(mod, init_name, None)
            if init_fn and callable(init_fn):
                try:
                    pkg_dir = pathlib.Path(__file__).resolve().parent.parent / "packages" / pkg_id
                    init_fn(project_root=str(pkg_dir))
                    logger.info("co-install %s: called %s(project_root=%s)", pkg_id, init_name, pkg_dir)
                except Exception as e:
                    logger.warning("co-install %s: %s failed: %s", pkg_id, init_name, e)
                break

        # ── Wire _handle_* methods ──
        for attr in dir(mod):
            if attr.endswith("Handlers") and not attr.startswith("_"):
                cls = getattr(mod, attr)
                for method_name in dir(cls):
                    if method_name.startswith("_handle_") and not method_name.startswith("__"):
                        method = getattr(cls, method_name)
                        if callable(method):
                            # Bind to self (CopilotCore instance)
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

    # ── Skill bridge route inferral ──

    @staticmethod
    def _infer_skill_script(skill_name: str) -> tuple:
        """Infer script path and runtime from skill name.

        Returns (script_path, runtime_command).
        """
        KNOWN = {
            "tavily-search": ("scripts/search.mjs", "node"),
            "csv2json": ("scripts/convert.py", "python3"),
            "baidu-ai-map": ("scripts/baidumap.py", "python3"),
        }
        if skill_name in KNOWN:
            return KNOWN[skill_name]
        return ("scripts/main.py", "python3")

    def _read_skill_routes(self, schema: dict) -> dict:
        """Build skill bridge route entries from package schema + handler.

        Scans handler.py for a *Handlers.skill_routes class attribute
        and returns fully-formed route entries for skill_bridge_routes.json.
        Returns empty dict if package is not a skill bridge package.
        """
        requires = schema.get("requires", {})
        modules = requires.get("modules", [])
        if "handlers/skill_bridge" not in modules:
            return {}

        pkg_id = schema.get("id", "")
        if not pkg_id:
            return {}

        # Locate handler.py in source dirs
        src_dir = None
        for sdir in _get_source_dirs():
            candidate = sdir / pkg_id
            if candidate.is_dir():
                src_dir = candidate
                break
        if src_dir is None:
            return {}

        handler_py = src_dir / "handler.py"
        if not handler_py.is_file():
            return {}

        # Extract skill_routes class attribute
        skill_route_defs = {}
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                f"_pkg_scan_{pkg_id.replace('-', '_')}",
                str(handler_py),
            )
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            for attr in dir(mod):
                if attr.endswith("Handlers") and not attr.startswith("_"):
                    cls = getattr(mod, attr)
                    routes = getattr(cls, "skill_routes", None)
                    if routes is not None:
                        skill_route_defs = routes
                        break
        except Exception as e:
            logger.debug("Failed to extract skill_routes from %s: %s", handler_py, e)
            return {}

        if not skill_route_defs:
            return {}

        # Build full route entries
        skill_name = SKILL_DIR_MAP.get(pkg_id,
                                        pkg_id[6:] if pkg_id.startswith("skill-") else pkg_id)
        directives = {f"{d.get('domain', '')};{d.get('action', '')}": d
                      for d in schema.get("directives", [])}

        result = {}
        for op_id, route_def in skill_route_defs.items():
            directive = directives.get(op_id, {})
            params = []
            for i, pn in enumerate(directive.get("params", [])):
                if pn:
                    params.append({"name": pn, "position": i})

            script, runtime = self._infer_skill_script(skill_name)
            param_part = " ".join(f"'{{{p['name']}}}'" for p in params)

            entry = {
                "skill": skill_name,
                "command": f"{runtime} {{skill_dir}}/{script} {param_part}".strip(),
                "params": params,
                "adapter": route_def.get("adapter", "passthrough"),
                "timeout_ms": route_def.get("timeout_ms", 30000),
                "description": directive.get("description", ""),
                "description_cn": directive.get("description_cn", ""),
            }
            if route_def.get("adapter_config"):
                entry["adapter_config"] = route_def["adapter_config"]
            if route_def.get("output_adapter"):
                entry["output_adapter"] = route_def["output_adapter"]

            result[op_id] = entry

        return result

    def _write_skill_routes(self, pkg_id: str, src_dir: pathlib.Path) -> int:
        """Read skill_routes from handler.py and write to skill_bridge_routes.json.

        Returns number of route entries written, or 0 if not applicable.
        """
        schema_path = src_dir / "schema.json"
        if not schema_path.is_file():
            return 0
        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            return 0

        route_entries = self._read_skill_routes(schema)
        if not route_entries:
            return 0

        routes = _load_skill_routes_file()
        written = 0
        for op_id, entry in route_entries.items():
            if op_id not in routes:
                routes[op_id] = entry
                written += 1

        if written:
            if _save_skill_routes_file(routes):
                logger.info("Wrote %d skill route(s) to skill_bridge_routes.json for '%s'",
                            written, pkg_id)
            else:
                return 0

        # Reload handlers so dispatch picks up new skill routes
        try:
            self._register_handlers()
        except Exception:
            pass

        return written

    def _remove_skill_routes(self, pkg_id: str) -> int:
        """Remove routes belonging to a package from skill_bridge_routes.json.

        Returns number of route entries removed.
        """
        handler_py = pathlib.Path(__file__).resolve().parent.parent / "packages" / pkg_id / "handler.py"
        schema_path = pathlib.Path(__file__).resolve().parent.parent / "packages" / pkg_id / "schema.json"
        if not handler_py.is_file() or not schema_path.is_file():
            return 0

        try:
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
        except Exception:
            return 0

        route_entries = self._read_skill_routes(schema)
        if not route_entries:
            return 0

        routes = _load_skill_routes_file()
        removed = 0
        for op_id in route_entries:
            if op_id in routes:
                del routes[op_id]
                removed += 1

        if removed:
            if _save_skill_routes_file(routes):
                logger.info("Removed %d skill route(s) from skill_bridge_routes.json for '%s'",
                            removed, pkg_id)

        return removed

    def _handle_text_cli_co_install(self, params: list) -> dict:
        """text-cli;co-install,<package_name>

        Install a copilot instruction package from source to packages/.
        Copies handler.py, schema.json, and ALL accessory files/dirs
        (whitelists/, config/, data/, adapters/, README.md, etc.).
        Reloads handlers so @directive-registered instructions are
        available immediately without a restart.
        Auto-writes skill_bridge_routes.json for skill bridge packages.
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

        # ── Write skill_bridge_routes.json ──
        routes_written = self._write_skill_routes(pkg_id, src_dir)

        restart_hint = "" if ops_written else " Restart copilot to load."
        route_msg = f", {routes_written} skill route(s)" if routes_written else ""
        return ok(
            f"Package '{pkg_id}' installed ({len(copied)} files, {ops_written} ops{route_msg}). "
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

        # ── Remove operations from auxiliary_config.json FIRST ──
        # (must happen before rmtree since _remove_package_ops reads schema.json)
        self._remove_package_ops(name)

        # ── Remove skill bridge routes ──
        self._remove_skill_routes(name)

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

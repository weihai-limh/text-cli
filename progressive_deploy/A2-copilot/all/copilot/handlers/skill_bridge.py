"""
Skill Bridge handler — universal bridge from ClawHub skills to text-cli instructions.

One handler for all skill routes. Routes defined in config/skill_bridge_routes.json.
Each route maps a text-cli instruction (e.g. web;search) to a skill's CLI command.

Response normalization is handled by adapters (handlers/adapters.py), keeping
the bridge skeleton free of skill-specific logic.
"""

import json
import os
import shlex
import subprocess
from pathlib import Path

from handlers.adapters import ADAPTERS

SKILLS_DIR = Path(os.environ.get("SKILLS_DIR", str(Path.home() / ".openclaw" / "workspace" / "skills")))
ROUTES_PATH = Path(__file__).resolve().parent.parent / "config" / "skill_bridge_routes.json"


class SkillBridgeHandlers:
    """Skill bridge — single universal handler for all skill-backed instructions."""

    def _load_skill_routes(self) -> dict:
        """Load skill bridge route definitions."""
        try:
            with open(ROUTES_PATH) as f:
                return json.load(f).get("routes", {})
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _try_skill_bridge(self, canonical: str, params: list) -> dict | None:
        """Try to execute an instruction via skill bridge.

        Returns None if no route found (caller should try other handlers).
        Returns a dict result on success or error.
        """
        routes = self._load_skill_routes()
        route = routes.get(canonical)
        if route is None:
            return None

        from core import ok, error

        # Build command from template
        cmd = route["command"]
        skill_name = route["skill"]
        skill_dir = SKILLS_DIR / skill_name

        if not skill_dir.is_dir():
            return error("skill_missing",
                        f"Skill not found: {skill_name} at {skill_dir}")

        # Replace {skill_dir} placeholder
        cmd = cmd.replace("{skill_dir}", str(skill_dir))

        # Fill parameters
        for pdef in route.get("params", []):
            placeholder = f"{{{pdef['name']}}}"
            if pdef["position"] < len(params):
                val = params[pdef["position"]]
            else:
                val = pdef.get("default", "")
                if not val:
                    return error("missing_param",
                               f"Missing required parameter: {pdef['name']}")
            cmd = cmd.replace(placeholder, shlex.quote(str(val)))

        timeout_ms = route.get("timeout_ms", 30000)

        # Execute skill
        try:
            result = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_ms / 1000.0,
                env={**os.environ},
            )
        except subprocess.TimeoutExpired:
            return error("skill_timeout",
                        f"Skill {canonical} timed out after {timeout_ms}ms")
        except Exception as e:
            return error("skill_error",
                        f"Skill {canonical} execution failed: {e}")

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        if result.returncode != 0:
            return error("skill_failed",
                        f"Skill {canonical} exited {result.returncode}: {stderr or stdout}")

        # Normalize via adapter
        adapter_name = route.get("adapter", "passthrough")
        adapter = ADAPTERS.get(adapter_name)
        if adapter is None:
            return error("adapter_missing",
                        f"Adapter '{adapter_name}' not found. Available: {', '.join(ADAPTERS.keys())}")

        adapter_config = route.get("adapter_config", {})
        try:
            normalized = adapter(stdout, adapter_config)
        except Exception as e:
            return error("adapter_error",
                        f"Adapter '{adapter_name}' failed: {e}")

        # Apply output adapter (provider-specific field mapping)
        output_adapter_name = route.get("output_adapter")
        if output_adapter_name:
            try:
                adapter_dir = Path(__file__).resolve().parent.parent / "adapters"
                adapter_file = adapter_dir / f"{output_adapter_name}.py"
                if adapter_file.exists():
                    import importlib.util
                    spec = importlib.util.spec_from_file_location("output_adapter", str(adapter_file))
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    normalized = mod.normalize(normalized)
            except Exception as e:
                return error("output_adapter_error",
                            f"Output adapter '{output_adapter_name}' failed: {e}")

        return ok(json.dumps(normalized, ensure_ascii=False))

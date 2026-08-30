"""
skill.py — Agent skill base class: wraps text-cli directives as reusable semantic skills.

Core idea:
    Directives are atomic (AI:weather;query,Beijing)
    Skills are semantic wrappers ("query weather" → pick endpoint → call → format → degrade)

Skill = intent mapping + directive composition + result formatting + degradation

Uses A0 SDK (call.py) for all HTTP and envelope handling — no manual HTTP code.
"""

import json
import logging
import os
import pathlib
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ── A0 SDK import ──────────────────────────────

# Deploy layout: build_dependent_layer injects A0 into the skill/ subdir, so
# A0's call.py lands in the SAME directory as skill.py (deploy/A1-skill/skill/python/).
try:
    from A0_protocol.python.call import call as a0_call, DirectiveResult
except ImportError:
    # Fallback: import A0 from the sibling directory (deploy: same dir as this file)
    _A0_DIR = pathlib.Path(__file__).resolve().parent
    if str(_A0_DIR) not in __import__("sys").path:
        __import__("sys").path.insert(0, str(_A0_DIR))
    from call import call as a0_call, DirectiveResult


# ── Aggregation helpers ────────────────────────

def _resolve_sources(directive_key: str) -> list[dict]:
    """Look up directive in agent-text-cli-schema.json, return sources ranked."""
    schema_path = _find_config("agent-text-cli-schema.json")
    if not schema_path or not schema_path.exists():
        return []
    try:
        data = json.loads(schema_path.read_text(encoding="utf-8"))
        sources = data.get("directives", {}).get(directive_key, [])
        return sorted(sources, key=lambda s: s.get("rank", 99))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read agent-text-cli-schema.json: %s", e)
        return []


def _load_endpoint(source_name: str) -> dict | None:
    """Load endpoint config from agent-endpoints.json by source name."""
    ep_path = _find_config("agent-endpoints.json")
    if not ep_path or not ep_path.exists():
        return None
    try:
        data = json.loads(ep_path.read_text(encoding="utf-8"))
        return data.get("endpoints", {}).get(source_name)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read agent-endpoints.json: %s", e)
        return None


def _resolve_token(raw: str | None) -> str | None:
    """Resolve token value: ${VAR} → os.environ, literal → passthrough, None → None."""
    if raw is None:
        return None
    if raw.startswith("${") and raw.endswith("}"):
        var = raw[2:-1]
        return os.environ.get(var)
    return raw


# Config directory anchored to this file (deploy: deploy/A1-skill/skill/config/),
# independent of cwd so the skill works from any working directory.
_CONFIG_DIR = pathlib.Path(__file__).resolve().parent.parent / "config"


def _find_config(filename: str) -> pathlib.Path | None:
    """Find config file in the A1 skill config directory."""
    candidate = _CONFIG_DIR / filename
    if candidate.exists():
        return candidate
    return None


# ── SkillResult ────────────────────────────────

@dataclass
class SkillResult:
    """Result of a skill call."""
    ok: bool
    data: Any = None          # formatted result or async task data
    error: str = ""           # formatted error message
    err_code: str = ""        # protocol error code
    skill_name: str = ""
    directive: str = ""
    is_async: bool = False    # True if task is pending/running
    task_id: str = ""         # async task ID (when is_async=True)


# ── Skill base class ───────────────────────────

class Skill:
    """
    Skill base class.

    Subclasses define:
    - domain / action → which directive to invoke
    - format_result()  → how to format the result
    - on_error()       → fallback message on failure

    Uses A0 SDK for HTTP and envelope parsing. No manual HTTP code.
    call_fn injection preserved for testing/custom scenarios.
    """

    domain: str = ""
    action: str = ""
    name: str = ""

    def make_directive(self, *params: str) -> str:
        """Compose params into a text-cli directive string."""
        return f"AI:{self.domain};{self.action},{','.join(params)}"

    def call(self, *params: str, call_fn: Callable | None = None) -> SkillResult:
        """
        Execute skill: check aggregation schema → resolve endpoint → call → degrade.

        call_fn signature: fn(directive, endpoint, access_token, service_token) → DirectiveResult
        When omitted, A0.call() is used directly.
        """
        directive = self.make_directive(*params)
        sources = _resolve_sources(f"{self.domain};{self.action}")

        # Fallback: if no aggregation schema, try local default
        if not sources:
            try:
                result = (call_fn or a0_call)(directive)
                return self._process_result(result, directive, params)
            except Exception as e:
                return SkillResult(ok=False, error=self.on_error(params, str(e)),
                                  err_code="ERR_EXECUTION", skill_name=self.name,
                                  directive=directive)

        # Degradation: try sources in rank order
        last_err_code = ""
        for src in sources:
            ep = _load_endpoint(src["source"])
            if not ep:
                logger.warning("Endpoint not found in agent-endpoints.json: %s", src["source"])
                continue

            url = ep.get("url", "")
            at = _resolve_token(ep.get("access_token"))
            st = _resolve_token(ep.get("service_token"))

            try:
                if call_fn:
                    result = call_fn(directive, endpoint=url, access_token=at, service_token=st)
                else:
                    result = a0_call(directive, endpoint=url, access_token=at, service_token=st)
            except Exception as e:
                logger.info("Skill %s source %s failed: %s", self.name, src["source"], e)
                last_err_code = "ERR_ROUTING"
                continue

            if result.is_async:
                return SkillResult(ok=True, data=result.data, is_async=True,
                                  task_id=result.task_id, skill_name=self.name,
                                  directive=directive)

            if result.ok:
                return self._process_result(result, directive, params)

            # Don't degrade on auth or param errors
            if result.err_code in ("INVALID_PARAMS", "ACCESS_DENIED", "SERVICE_DENIED"):
                return SkillResult(ok=False, error=self.on_error(params, result.err_code),
                                  err_code=result.err_code, skill_name=self.name,
                                  directive=directive)

            last_err_code = result.err_code

        return SkillResult(ok=False,
                          error=f"All {len(sources)} endpoints exhausted. Last error: {last_err_code}",
                          err_code=last_err_code or "ERR_NOT_FOUND",
                          skill_name=self.name, directive=directive)

    def _process_result(self, dr: DirectiveResult, directive: str, params: tuple) -> SkillResult:
        """Process a successful DirectiveResult into SkillResult."""
        formatted = self.format_result(dr.data, params)
        return SkillResult(ok=True, data=formatted, skill_name=self.name, directive=directive)

    def format_result(self, data: Any, params: tuple = ()) -> Any:
        """Format raw result. Override in subclass for custom formatting."""
        return data

    def on_error(self, params: tuple, err_code: str) -> str:
        """Return fallback text on failure. Override in subclass."""
        return f"[{self.name}] instruction execution failed: {err_code}"

    @classmethod
    def run(cls, *params: str) -> SkillResult:
        """Convenience: one-line skill invocation."""
        return cls().call(*params)


# ── Skill registry ─────────────────────────────

_skills: dict[str, type[Skill]] = {}


def skill(name: str, domain: str, action: str):
    """
    Decorator: register a Skill subclass as a discoverable skill.

    @skill("weather", domain="weather", action="query")
    class WeatherSkill(Skill):
        ...
    """
    def decorator(cls: type[Skill]):
        cls.name = name
        cls.domain = domain
        cls.action = action
        _skills[name] = cls
        return cls
    return decorator


def list_skills() -> dict[str, dict]:
    """List all registered skills."""
    return {
        name: {"domain": s.domain, "action": s.action}
        for name, s in _skills.items()
    }


def get_skill(name: str) -> type[Skill] | None:
    """Get a skill class by name."""
    return _skills.get(name)

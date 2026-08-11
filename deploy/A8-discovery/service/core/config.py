"""text-cli configuration loader — single YAML file for all runtimes.

Priority: env var > YAML > built-in defaults.

Usage:
    from core.config import load_config
    config = load_config()
    port = config["server"]["port"]
"""

from __future__ import annotations

import logging
import os
import pathlib

logger = logging.getLogger(__name__)

# ── Built-in defaults (applied when YAML is absent or key is missing) ──
_DEFAULTS: dict = {
    "server": {
        "port": 28050,
        "log_level": "info",
        "instance_id": "text-cli",
        "instructions_language": "auto",
    },
    "auth": {
        "allow_anonymous": True,
        "service_token": "",
        "count_calls": False,
    },
    "paths": {
        "packages": "",
        "service_db": "",
        "state_db": "",
        "media": "",
        "aggregate": "",
        "map_enabled": False,
        "map_max_iter": 100,
    },
    "mcp": {
        "service_url": "",
        "service_token": "",
        "port": 9020,
    },
    "mesh": {
        "require_credentials": False,
        "multi_hop_enabled": False,
        "multi_hop_max_depth": 3,
    },
}

# ── Env var → config key mapping (env var takes priority over YAML) ──
_ENV_OVERRIDES: list[tuple[str, tuple[str, ...]]] = [
    ("PORT",                         ("server", "port")),
    ("LOG_LEVEL",                    ("server", "log_level")),
    ("TEXT_CLI_INSTANCE_ID",         ("server", "instance_id")),
    ("A3_ALLOW_ANONYMOUS",           ("auth", "allow_anonymous")),
    ("SERVICE_TOKEN",                ("auth", "service_token")),
    ("A3_COUNT_CALLS",               ("auth", "count_calls")),
    ("TEXT_CLI_PACKAGE_SOURCE_DIRS", ("paths", "packages")),
    ("TEXT_CLI_SERVICE_DB",          ("paths", "service_db")),
    ("TEXT_CLI_DB",                  ("paths", "state_db")),
    ("TEXT_CLI_MEDIA_DIR",           ("paths", "media")),
    ("AGGREGATE_DIR",                ("paths", "aggregate")),
    ("MAP_ENABLED",                  ("paths", "map_enabled")),
    ("MAP_MAX_ITER",                 ("paths", "map_max_iter")),
    ("MULTI_HOP_ENABLED",            ("mesh", "multi_hop_enabled")),
    ("MULTI_HOP_MAX_DEPTH",          ("mesh", "multi_hop_max_depth")),
    ("TEXTCLI_SERVICE_URL",          ("mcp", "service_url")),
    ("TEXTCLI_SERVICE_TOKEN",        ("mcp", "service_token")),
    ("MCP_PORT",                     ("mcp", "port")),
    ("MESH_REQUIRE_CREDENTIALS",      ("mesh", "require_credentials")),
]


def _resolve_config_path() -> pathlib.Path | None:
    """Find text_cli.yaml: $TEXT_CLI_HOME/service/config/text_cli.yaml."""
    home = os.environ.get("TEXT_CLI_HOME", "")
    if home:
        p = pathlib.Path(home) / "service" / "config" / "text_cli.yaml"
        if p.is_file():
            return p
    return None


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base. Returns new dict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config() -> dict:
    """Load configuration with priority: env var > YAML > defaults.

    Returns a dict with sections: server, auth, paths, mcp.
    Callers access as config["server"]["port"], etc.
    """
    config = _deep_merge({}, _DEFAULTS)

    # Layer 2: YAML
    yaml_path = _resolve_config_path()
    if yaml_path:
        try:
            import yaml as _yaml_mod
        except ImportError:
            logger.warning("PyYAML not installed, skip %s", yaml_path)
        else:
            try:
                with open(yaml_path, encoding="utf-8") as f:
                    yaml_data = _yaml_mod.safe_load(f) or {}
                config = _deep_merge(config, yaml_data)
                logger.debug("Loaded config from %s", yaml_path)
            except Exception as e:
                logger.warning("Failed to load %s: %s", yaml_path, e)

    # Layer 3 (highest priority): environment variables
    for env_var, keys in _ENV_OVERRIDES:
        val = os.environ.get(env_var)
        if val is not None:
            # Type coercion for known fields
            section, key = keys[0], keys[1]
            if key in ("port", "count_calls", "allow_anonymous", "require_credentials", "map_enabled"):
                if key == "allow_anonymous" or key == "map_enabled":
                    config[section][key] = val.lower() == "true"
                else:
                    try:
                        config[section][key] = int(val) if key == "port" else val.lower() == "true"
                    except ValueError:
                        pass
            elif key == "map_max_iter":
                try:
                    config[section][key] = int(val)
                except ValueError:
                    pass
            else:
                config[section][key] = val

    return config

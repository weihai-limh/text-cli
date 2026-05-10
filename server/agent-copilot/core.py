"""
text-cli-copilot core — configuration loading, instruction parser, response helpers, dispatch engine
Zero dependencies, Python stdlib only.
"""

import json
import os
import re
import resource
import subprocess
import time
from fnmatch import fnmatch
from pathlib import Path
from typing import Any


# ═══════════════════════════════════════════════════════════════
# Configuration Loading
# ═══════════════════════════════════════════════════════════════

def _resolve_env(value: Any) -> Any:
    """Recursively replace ${VAR_NAME} placeholders in strings (resolved once at startup)"""
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            var_name = m.group(1)
            resolved = os.environ.get(var_name, "")
            if not resolved:
                print(f"[copilot] ⚠ env var {var_name} not set, using empty string")
            return resolved
        return re.sub(r'\$\{([^}]+)\}', _replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items() if not k.startswith('_')}
    elif isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


def load_config(config_path: str) -> dict:
    """Load and resolve config file"""
    with open(config_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return _resolve_env(raw)


# ═══════════════════════════════════════════════════════════════
# Instruction Parser
# ═══════════════════════════════════════════════════════════════

PREFIXES = ['指令:', '指令：', 'AI:', 'AI：']


def parse_instruction(prompt: str) -> dict | None:
    """
    Parse a text-cli directive.
    Returns:
        {'domain': str, 'action': str, 'params': list} | None (parse failure)
    """
    if not prompt or not isinstance(prompt, str):
        return None

    prompt = prompt.strip()

    # 1. Match prefix
    prefix_matched = None
    for prefix in PREFIXES:
        if prompt.startswith(prefix):
            prefix_matched = prefix
            break

    if prefix_matched is None:
        return None

    body = prompt[len(prefix_matched):].strip()
    if not body:
        return None

    # 2. Split domain from action+params on first semicolon
    parts = body.split(';', 1)
    if len(parts) != 2:
        return None

    domain = parts[0].strip()
    tail = parts[1].strip()

    if not domain or not tail:
        return None

    # 3. Split on first comma — do a preliminary split; dispatch will re-split with maxsplit
    comma_idx = tail.find(',')
    if comma_idx == -1:
        action = tail
        params = []
        _raw_params = ''
    else:
        action = tail[:comma_idx].strip()
        _raw_params = tail[comma_idx + 1:]
        # Preliminary split — dispatch will re-process with maxsplit
        param_parts = _raw_params.split(',')
        if len(param_parts) == 1:
            params = [param_parts[0].strip()] if param_parts[0].strip() else []
        else:
            params = [p.strip() for p in param_parts[:-1]]
            params.append(param_parts[-1])  # Last param left as-is, preserving original content

    if not action:
        return None

    return {
        'domain': domain,
        'action': action,
        'params': params,
        '_raw_params': _raw_params,
    }


# ═══════════════════════════════════════════════════════════════
# Response Helpers
# ═══════════════════════════════════════════════════════════════

def ok(text: str, **extra) -> dict:
    """text-cli standard success response"""
    rst_data = {'text': text}
    rst_data.update(extra)
    return {
        'rst_types': 'text',
        'rst_data': rst_data,
    }


def error(code: str, detail: str) -> dict:
    """text-cli standard error response"""
    return {
        'rst_types': 'text',
        'rst_data': {'text': f'[{code}] {detail}'},
        'rst_err': code,
    }


# ═══════════════════════════════════════════════════════════════
# Copilot Core Engine (handler implementations excluded)
# ═══════════════════════════════════════════════════════════════

class CopilotCore:
    """Directive copilot server core — dispatch, credentials, security checks"""

    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.token = self.config['server']['token']
        self.start_time = time.time()
        self._request_count = 0
        self._error_count = 0
        self._ai_status: dict = {}
        self.cache_dir = Path(config_path).parent / '.cache'
        self._handlers: dict[str, callable] = {}
        self._alias_map: dict[str, str] = {}
        self._injected_creds: dict = {}
        self._register_handlers()
        self._setup_git_workdir()

    # ── Handler Registration (auto-register by naming convention) ──

    def _register_handlers(self):
        operations = self.config['security']['operations']
        for op_id, op_config in operations.items():
            # Check enabled field (default true)
            if op_config.get('enabled') is False:
                print(f"[copilot] ⏸ Disabled: {op_id}")
                continue
            # Derive handler name from first English alias; fall back to canonical ID
            aliases = op_config.get('aliases', [])
            source_id = aliases[0] if aliases else op_id
            handler_name = '_handle_' + source_id.replace(';', '_').replace(':', '_')
            if hasattr(self, handler_name):
                self._handlers[op_id] = getattr(self, handler_name)
            else:
                print(f"[copilot] ⚠ Handler not found: {handler_name}, skipping {op_id}")

            for alias in op_config.get('aliases', []):
                self._alias_map[alias] = op_id
            self._alias_map[op_id] = op_id

        print(f"[copilot] Registered {len(self._handlers)} handler(s), "
              f"{len(self._alias_map)} alias mapping(s)")

    def _smart_split_params(self, parsed: dict, canonical: str) -> list:
        """Re-split params based on expected parameter count from handler spec,
        preserving commas in the last parameter."""
        raw = parsed.get('_raw_params', '')
        if not raw:
            return parsed.get('params', [])

        op_config = self.config['security']['operations'].get(canonical, {})
        param_specs = op_config.get('parameters', op_config.get('parameters_en', []))
        expected = len(param_specs)

        if expected <= 1:
            return [raw] if raw.strip() else []

        parts = raw.split(',', maxsplit=expected - 1)
        if len(parts) == 1:
            return [parts[0].strip()] if parts[0].strip() else []
        params = [p.strip() for p in parts[:-1]]
        params.append(parts[-1])
        return params

    def _setup_git_workdir(self):
        git_cfg = self.config.get('git', {})
        wd = git_cfg.get('workdir')
        self.git_workdir = wd if wd else os.getcwd()
        self.git_remote_name = git_cfg.get('remote_name', 'origin')

    # ── Dispatch ──

    def dispatch(self, parsed: dict) -> dict:
        """Route parsed directive to the matching handler"""
        self._request_count += 1
        lookup = f"{parsed['domain']};{parsed['action']}"

        # Check if disabled (look in config directly, since disabled ops are not in _alias_map)
        for op_id, op_cfg in self.config['security']['operations'].items():
            if op_id == lookup or lookup in op_cfg.get('aliases', []):
                if op_cfg.get('enabled') is False:
                    self._error_count += 1
                    return error('disabled',
                                f'Directive {op_id} is temporarily disabled: {op_cfg.get("_comment", "")}')
                break

        canonical = self._alias_map.get(lookup)

        if canonical is None:
            self._error_count += 1
            return error('unknown_instruction',
                        f'Unrecognized directive: {lookup}. '
                        f'Available directives: {", ".join(self._handlers.keys())}')

        handler = self._handlers.get(canonical)
        if handler is None:
            self._error_count += 1
            return error('unknown_instruction',
                        f'Directive {canonical} is registered but has no handler')

        # Re-split parameters using maxsplit based on handler's expected param count,
        # so that commas in the last parameter are preserved
        params = self._smart_split_params(parsed, canonical)

        try:
            result = handler(params)
            if 'rst_err' in result:
                self._error_count += 1
            return result
        except Exception as e:
            self._error_count += 1
            return error('internal_error', f'{type(e).__name__}: {e}')

    def track_error(self):
        self._request_count += 1
        self._error_count += 1

    # ── Security Checks ──

    def check_branch(self, branch: str, op_id: str = "Git;推送") -> bool:
        operations = self.config['security']['operations']
        op_cfg = operations.get(op_id, {})
        allowed = op_cfg.get('allowed_branches', [])
        for pattern in allowed:
            if fnmatch(branch, pattern):
                return True
        return False

    def get_remote_url(self) -> str | None:
        creds = self.config.get('credentials', {})
        git_creds = creds.get('Git;推送', {})
        remote_url = git_creds.get('remote_url')
        if remote_url:
            return remote_url
        try:
            result = subprocess.run(
                ['git', 'remote', 'get-url', self.git_remote_name],
                cwd=self.git_workdir, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def resolve_credential(self, cred_value: str | None) -> dict:
        if cred_value is None or cred_value == '':
            return {'mode': 'ssh'}
        if cred_value.startswith('http://') or cred_value.startswith('https://'):
            return {'mode': 'inject', 'url': cred_value}
        return {'mode': 'https', 'token': cred_value}

    def check_path(self, path_str: str) -> Path | None:
        try:
            p = Path(path_str).resolve()
        except (OSError, ValueError):
            return None
        whitelist = self.config['security'].get('path_whitelist', [])
        for entry in whitelist:
            wl_path = Path(entry).resolve()
            try:
                if entry.endswith('/'):
                    p.relative_to(wl_path)
                    return p
                else:
                    if p == wl_path:
                        return p
            except ValueError:
                continue
        return None

    def _get_mem_mb(self) -> float:
        return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024

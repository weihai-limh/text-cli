"""
text-cli-copilot 核心 — 配置加载、指令解析、响应辅助、dispatch 引擎
零依赖，Python stdlib only。
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
# 配置加载
# ═══════════════════════════════════════════════════════════════

def _resolve_env(value: Any) -> Any:
    """递归替换字符串中的 ${VAR_NAME} 占位符（启动时一次性）"""
    if isinstance(value, str):
        def _replace(m: re.Match) -> str:
            var_name = m.group(1)
            resolved = os.environ.get(var_name, "")
            if not resolved:
                print(f"[copilot] ⚠ 环境变量 {var_name} 未设置，使用空字符串")
            return resolved
        return re.sub(r'\$\{([^}]+)\}', _replace, value)
    elif isinstance(value, dict):
        return {k: _resolve_env(v) for k, v in value.items() if not k.startswith('_')}
    elif isinstance(value, list):
        return [_resolve_env(item) for item in value]
    return value


def load_config(config_path: str) -> dict:
    """加载并解析配置文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    return _resolve_env(raw)


# ═══════════════════════════════════════════════════════════════
# 指令解析器
# ═══════════════════════════════════════════════════════════════

PREFIXES = ['指令:', 'directive:']


def parse_instruction(prompt: str) -> dict | None:
    """
    解析 text-cli 指令。
    返回:
        {'domain': str, 'action': str, 'params': list} | None (解析失败)
    """
    if not prompt or not isinstance(prompt, str):
        return None

    prompt = prompt.strip()

    # 1. 识别前缀
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

    # 2. 分号分割领域和动作+参数
    parts = body.split(';', 1)
    if len(parts) != 2:
        return None

    domain = parts[0].strip()
    tail = parts[1].strip()

    if not domain or not tail:
        return None

    # 3. 逗号分割参数 — 最后一个参数贪婪匹配
    comma_idx = tail.find(',')
    if comma_idx == -1:
        action = tail
        params = []
    else:
        action = tail[:comma_idx].strip()
        params_str = tail[comma_idx + 1:]
        param_parts = params_str.split(',')
        if len(param_parts) == 1:
            params = [param_parts[0].strip()] if param_parts[0].strip() else []
        else:
            params = [p.strip() for p in param_parts[:-1]]
            params.append(param_parts[-1])  # 最后一个不 strip，保留原始内容

    if not action:
        return None

    return {
        'domain': domain,
        'action': action,
        'params': params,
    }


# ═══════════════════════════════════════════════════════════════
# 响应辅助
# ═══════════════════════════════════════════════════════════════

def ok(text: str, **extra) -> dict:
    """text-cli 标准成功响应"""
    rst_data = {'text': text}
    rst_data.update(extra)
    return {
        'rst_types': 'text',
        'rst_data': rst_data,
    }


def error(code: str, detail: str) -> dict:
    """text-cli 标准错误响应"""
    return {
        'rst_types': 'text',
        'rst_data': {'text': f'[{code}] {detail}'},
        'rst_err': code,
    }


# ═══════════════════════════════════════════════════════════════
# Copilot 核心引擎（不含 handler 实现）
# ═══════════════════════════════════════════════════════════════

class CopilotCore:
    """指令辅助服务器核心 — dispatch、凭据、安全校验"""

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
        self._register_handlers()
        self._setup_git_workdir()

    # ── Handler 注册（命名约定自动注册） ──

    def _register_handlers(self):
        operations = self.config['security']['operations']
        for op_id, op_config in operations.items():
            # 用首个英文 alias 派生 handler 名；无 alias 时回退 canonical ID
            aliases = op_config.get('aliases', [])
            source_id = aliases[0] if aliases else op_id
            handler_name = '_handle_' + source_id.replace(';', '_').replace(':', '_')
            if hasattr(self, handler_name):
                self._handlers[op_id] = getattr(self, handler_name)
            else:
                print(f"[copilot] ⚠ 未找到 handler: {handler_name}，跳过 {op_id}")

            for alias in op_config.get('aliases', []):
                self._alias_map[alias] = op_id
            self._alias_map[op_id] = op_id

        print(f"[copilot] 已注册 {len(self._handlers)} 个 handler，"
              f"{len(self._alias_map)} 个别名映射")

    def _setup_git_workdir(self):
        git_cfg = self.config.get('git', {})
        wd = git_cfg.get('workdir')
        self.git_workdir = wd if wd else os.getcwd()
        self.git_remote_name = git_cfg.get('remote_name', 'origin')

    # ── Dispatch ──

    def dispatch(self, parsed: dict) -> dict:
        """根据解析结果路由到对应 handler"""
        self._request_count += 1
        lookup = f"{parsed['domain']};{parsed['action']}"
        canonical = self._alias_map.get(lookup)

        if canonical is None:
            self._error_count += 1
            return error('unknown_instruction',
                        f'未识别的指令: {lookup}。'
                        f'可用指令: {", ".join(self._handlers.keys())}')

        handler = self._handlers.get(canonical)
        if handler is None:
            self._error_count += 1
            return error('unknown_instruction',
                        f'指令 {canonical} 已注册但无 handler')

        try:
            result = handler(parsed['params'])
            if 'rst_err' in result:
                self._error_count += 1
            return result
        except Exception as e:
            self._error_count += 1
            return error('internal_error', f'{type(e).__name__}: {e}')

    def track_error(self):
        self._request_count += 1
        self._error_count += 1

    # ── 安全校验 ──

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

"""
text-cli-copilot 核心 — 配置加载、指令解析、响应辅助、dispatch 引擎
零依赖，Python stdlib only。
"""

import json
import os
import re
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
                print(f"[copilot] [WARN] env var {var_name} not set, using empty string")
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

PREFIXES = ['指令:', 'AI:']


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
    # Unicode 冒号归一化（全角 ： → 半角 :）
    # 仅当后续字符非冒号时执行，避免 AI：：xx 或 AI::xx 语义丢失
    if body.startswith('：') and not body[1:2].startswith((':', '：')):
        body = body[1:].strip()

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

def ok(text: str, type: str = 'text', url: str | None = None, **extra) -> dict:
    """text-cli 标准成功响应"""
    rst_data = {'text': text}
    if url:
        rst_data['url'] = url
    rst_data.update(extra)
    return {
        'rst_types': type,
        'rst_data': rst_data,
    }


def error(code: str, detail: str, **extra) -> dict:
    """text-cli 标准错误响应"""
    result = {
        'rst_types': 'text',
        'rst_data': {'text': f'[{code}] {detail}'},
        'rst_err': code,
    }
    if extra:
        result.update(extra)
    return result


# ═══════════════════════════════════════════════════════════════
# Copilot 核心引擎
# ═══════════════════════════════════════════════════════════════

class CopilotCore:
    """指令辅助服务器核心 — dispatch、凭据、安全校验"""

    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.config_dir = Path(config_path).parent
        (self.config_dir / 'data').mkdir(parents=True, exist_ok=True)
        (self.config_dir / 'whitelists').mkdir(parents=True, exist_ok=True)
        # token: null = 不校验（A2 绑在 127.0.0.1，安全由 OS 保证）
        self.token = self.config['server'].get('token') or None
        self.start_time = time.time()
        self._request_count = 0
        self._error_count = 0
        self._ai_status: dict = {}
        self.cache_dir = self.config_dir / '.cache'
        self._handlers: dict[str, callable] = {}
        self._alias_map: dict[str, str] = {}
        self._security_overrides: dict[str, dict] = {}
        self._register_handlers()
        self._setup_git_workdir()

    # ── Handler 注册（三层匹配） ──
    # ① @directive 装饰器注册表（内存，自动发现）→ co-install reload 后立即可用
    # ② auxiliary_config operations → 安全策略覆盖层（level/sensitive/path_check）
    # ③ skill_bridge fallback（dispatch 时动态匹配）

    def _register_handlers(self):
        # 1. 从辅助配置提取安全策略覆盖（不依赖它做 handler 注册）
        operations = self.config['security'].get('operations', {})
        for op_id, op_config in operations.items():
            self._security_overrides[op_id] = op_config
            # 别名也索引安全策略
            for alias in op_config.get('aliases', []):
                if alias not in self._security_overrides:
                    self._security_overrides[alias] = op_config

        # 2. 从 @directive 装饰器 + auxiliary_config 双源注册 handler
        # auxiliary_config 有显式 handler 字段的优先（如 skill_bridge）
        for op_id, op_config in operations.items():
            handler_name = op_config.get('handler')
            if handler_name:
                if hasattr(self, handler_name):
                    self._handlers[op_id] = getattr(self, handler_name)
                else:
                    print(f"[copilot] [WARN] handler not found: {handler_name}, skip {op_id}")
                for alias in op_config.get('aliases', []):
                    self._alias_map[alias] = op_id
                self._alias_map[op_id] = op_id

        # 3. 从 @directive 装饰器自动发现（命名约定）
        # 遍历 mixin 链上所有 _handle_ 方法，自动注册
        _registered_from_directive = 0
        for attr_name in dir(self):
            if not attr_name.startswith('_handle_'):
                continue
            # 跳过已通过显式 handler 注册的
            if attr_name in self._handlers:
                continue
            handler = getattr(self, attr_name)
            if not callable(handler):
                continue
            # 从方法名反推 op_id: _handle_tc_ubuntu_resolution → tc-ubuntu;resolution
            op_id = attr_name[8:]  # 去掉 '_handle_'
            op_id = op_id.replace('_', '-', 1) if op_id.startswith(('tc_','ai_','bd_','tx_')) else op_id
            # 第一个 _ 替换为 ; , 后续 _ 替换为 -
            parts = op_id.split('_', 1)
            if len(parts) == 2:
                domain = parts[0].replace('_', '-')
                action = parts[1].replace('_', '-')
                op_id = f"{domain};{action}"
            if '_' not in attr_name[8:]:
                continue  # 无法解析的不自动注册

            self._handlers[op_id] = handler
            self._alias_map[op_id] = op_id
            # 注册 auxiliary_config 里的 aliases（如果有）
            sec = self._security_overrides.get(op_id, {})
            for alias in sec.get('aliases', []):
                if alias not in self._alias_map:
                    self._alias_map[alias] = op_id
            _registered_from_directive += 1

        # 4. 对已注册的 handler：合并安全策略覆盖（auxiliary_config 里的 level/sensitive 等）
        # @directive 注册的 handler 默认 level: read
        # auxiliary_config 里有条目的可以覆盖

        # 5. Skill bridge 路由自动发现
        #    每个 skill 路由注册为一个 handler，统一指向 _try_skill_bridge
        #    world 上几十万个 skill 包，安装后自动出现在 schema 和 query 中
        _skill_count = 0
        try:
            routes_path = self.config_dir / "config" / "skill_bridge_routes.json"
            if routes_path.exists():
                with open(routes_path) as _f:
                    skill_routes = json.load(_f).get("routes", {})
                for op_id in skill_routes:
                    if op_id in self._handlers:
                        continue  # 本地 handler 优先
                    self._handlers[op_id] = lambda p, o=op_id: self._try_skill_bridge(o, p)
                    self._alias_map[op_id] = op_id
                    _skill_count += 1
        except Exception as e:
            print(f"[copilot] [WARN] skill bridge route load failed: {e}")

        print(f"[copilot] 已注册 {len(self._handlers)} 个 handler"
              f"（其中 {_registered_from_directive} 个来自 @directive 自动发现，"
              f"{_skill_count} 个来自 skill bridge），"
              f"{len(self._alias_map)} 个别名映射，"
              f"{len(self._security_overrides)} 条安全策略覆盖")

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

        # 默认走本地 handler
        handler = self._handlers.get(canonical)
        if handler is None:
            # Skill bridge fallback — try ClawHub skill routes
            bridge_result = self._try_skill_bridge(canonical, parsed['params'])
            if bridge_result is not None:
                if 'rst_err' in bridge_result:
                    self._error_count += 1
                return bridge_result

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
                cwd=self.git_workdir, capture_output=True, text=True, timeout=10, check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def resolve_credential(self, cred_value: str | None) -> dict:
        if cred_value is None or cred_value == '':
            return {'mode': 'ssh'}
        if cred_value.startswith(('http://', 'https://')):
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
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except (ImportError, AttributeError):
            return 0.0

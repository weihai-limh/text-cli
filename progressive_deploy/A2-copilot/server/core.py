"""
text-cli-copilot 核心 — 配置加载、指令解析、响应辅助、dispatch 引擎
零依赖，Python stdlib only。MCP 桥为可选模块（懒加载）。
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
    if body.startswith('：'):
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

def ok(text: str, type: str = 'text', url: str = None, **extra) -> dict:
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
# Copilot 核心引擎（含 MCP 路由支持）
# ═══════════════════════════════════════════════════════════════

class CopilotCore:
    """指令辅助服务器核心 — dispatch、凭据、安全校验、MCP 路由"""

    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.config_dir = Path(config_path).parent
        (self.config_dir / 'data').mkdir(parents=True, exist_ok=True)
        (self.config_dir / 'whitelists').mkdir(parents=True, exist_ok=True)
        self.token = self.config['server']['token']
        self.start_time = time.time()
        self._request_count = 0
        self._error_count = 0
        self._ai_status: dict = {}
        self.cache_dir = self.config_dir / '.cache'
        self._handlers: dict[str, callable] = {}
        self._alias_map: dict[str, str] = {}
        self._routing_prefs: dict[str, str] = {}
        self._mcp_registry: dict[str, dict] = {}
        self._register_handlers()
        self._setup_git_workdir()
        self._load_routing_preferences()
        self._build_mcp_registry()

    # ── Handler 注册（命名约定自动注册） ──

    def _register_handlers(self):
        operations = self.config['security']['operations']
        for op_id, op_config in operations.items():
            # 用首个英文 alias 派生 handler 名；无 alias 时回退 canonical ID
            aliases = op_config.get('aliases', [])
            source_id = aliases[0] if aliases else op_id
            handler_name = '_handle_' + source_id.replace(';', '_').replace(':', '_').replace('-', '_')
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

    # ── MCP 路由配置 ──

    def _load_routing_preferences(self):
        """加载 routing_preferences.json。文件不存在 = 全部默认 local。"""
        prefs_path = self.config_dir / 'data' / 'routing_preferences.json'
        try:
            with open(prefs_path, 'r', encoding='utf-8') as f:
                prefs = json.load(f)
            self._routing_prefs['_default'] = prefs.get('default', 'local')
            for op_id, pref in prefs.get('preferences', {}).items():
                self._routing_prefs[op_id] = pref
            print(f"[copilot] 路由偏好已加载: default={self._routing_prefs['_default']}, "
                  f"{len(prefs.get('preferences', {}))} 条逐项覆盖")
        except FileNotFoundError:
            print(f"[copilot] routing_preferences.json 未找到，全部默认 local")
            self._routing_prefs['_default'] = 'local'
        except Exception as e:
            print(f"[copilot] ⚠ 路由偏好加载失败: {e}，回退到全部 local")
            self._routing_prefs['_default'] = 'local'

    def _build_mcp_registry(self):
        """从 operations 配置中提取所有含 MCP 路由的条目。"""
        operations = self.config.get('security', {}).get('operations', {})
        for op_id, op_cfg in operations.items():
            mcp_cfg = op_cfg.get('mcp')
            if mcp_cfg:
                self._mcp_registry[op_id] = mcp_cfg
                # 同时注册到 alias（让英文和中文 lookup 都能命中 MCP 路由）
                for alias in op_cfg.get('aliases', []):
                    self._mcp_registry[alias] = mcp_cfg
        if self._mcp_registry:
            print(f"[copilot] MCP 路由注册表: {len(self._mcp_registry)} 条目")

    # ── Dispatch ──

    def dispatch(self, parsed: dict) -> dict:
        """根据解析结果路由到对应 handler，支持 MCP 路由"""
        self._request_count += 1
        lookup = f"{parsed['domain']};{parsed['action']}"
        canonical = self._alias_map.get(lookup)

        if canonical is None:
            self._error_count += 1
            return error('unknown_instruction',
                        f'未识别的指令: {lookup}。'
                        f'可用指令: {", ".join(self._handlers.keys())}')

        # 检查路由偏好：此指令是否配置了 MCP，且偏好走 MCP？
        # 按 lookup → canonical → _default 查找，同时检查所有 alias
        pref = self._routing_prefs.get(lookup,
                self._routing_prefs.get(canonical,
                self._routing_prefs.get('_default', 'local')))
        if pref == 'local':
            # 检查 canonical 的所有 alias 是否有被偏好为 mcp 的
            for alias, cid in self._alias_map.items():
                if cid == canonical and self._routing_prefs.get(alias) == 'mcp':
                    pref = 'mcp'
                    break
        mcp_cfg = self._mcp_registry.get(canonical) or self._mcp_registry.get(lookup)

        if pref == 'mcp' and mcp_cfg:
            return self._dispatch_mcp(parsed, canonical, mcp_cfg)

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

    def _dispatch_mcp(self, parsed: dict, canonical: str, mcp_cfg: dict) -> dict:
        """通过 MCP 桥执行指令（懒加载 mcporter）"""
        try:
            from packages.mcp_bridge.handler import call_mcp_tool, parse_mcp_result
        except ImportError:
            return error('internal_error', 'MCP bridge package not installed')

        server = mcp_cfg['server']
        tool = mcp_cfg['tool']
        timeout_ms = mcp_cfg.get('timeout_ms', 30000)

        # 参数适配：位置参数 → MCP 结构化参数
        arguments = self._adapt_params_mcp(parsed['params'], mcp_cfg)

        print(f"[copilot] MCP 路由: {canonical} → {server}.{tool}")

        success, raw_result = call_mcp_tool(server, tool, arguments, timeout_ms)

        if not success:
            self._error_count += 1
            return error('mcp_error', raw_result)

        result = parse_mcp_result(raw_result)
        if 'rst_err' in result:
            self._error_count += 1
        return result

    def _adapt_params_mcp(self, params: list, mcp_cfg: dict) -> dict:
        """将 text-cli 位置参数适配为 MCP 工具的结构化参数"""
        adapter = mcp_cfg.get('adapter', 'passthrough')

        if adapter == 'git_push':
            try:
                from handlers.github_adapter import adapt_git_push
                return adapt_git_push(params, mcp_cfg, workdir=self.git_workdir)
            except ImportError:
                return {"error": "github_adapter not installed"}

        if adapter == 'passthrough':
            param_names = mcp_cfg.get('param_names', [])
            args = {}
            for i, p in enumerate(params):
                if i < len(param_names):
                    args[param_names[i]] = p
                else:
                    args[f'arg{i}'] = p
            return args

        if adapter == 'json_parse' and params:
            try:
                return json.loads(params[0])
            except json.JSONDecodeError:
                return {'_raw': params[0]}

        # 未知 adapter → 报错，不吞
        return {'_params': params}

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
        try:
            import resource
            return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        except (ImportError, AttributeError):
            return 0.0

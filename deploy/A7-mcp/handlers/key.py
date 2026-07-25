"""
密钥管理 handler — copilot 路由层 v2

copilot 不存储密钥。key 获取路径由 key_routing.json 配置决定:
  source=env     → 从环境变量直接读取
  source=service → ⤴ delegated 到 service 处理

指令:
  密钥;获取,<service>         → 按路由返回 (env 读取 / delegated)
  密钥;注册 / 撤销 / 列表     → ⤴ delegated (全部由 service 处理)
  密钥;配额追踪               → ⤴ delegated

与 service 层的关系:
  copilot 是 thin client — key 操作全部委托 service
  仅 env 变量直读不走 service (给最小化单机部署留出口)

Author: Tide 🌊 — v2 2026-05-15
"""

import json
import os
import time
from pathlib import Path

from core import error, ok

# ═══════════════════════════════════════════════════════════
# Key routing (from key_routing.json)
# ═══════════════════════════════════════════════════════════

class KeyRouter:
    """按配置决定 key 的来源: 环境变量 或 delegated service"""

    def __init__(self, config_dir: Path):
        self.config_path = config_dir / 'key_routing.json'
        self.routes: dict = {}
        self._load()

    def _load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.routes = json.load(f)
            except (json.JSONDecodeError, FileNotFoundError):
                self.routes = {}

    def resolve(self, service: str) -> dict:
        """
        返回: {"source": "env", "value": "xxx"}
               {"source": "service"}
               {"source": "not_found"}
        """
        route = self.routes.get(service)
        if not route:
            return {"source": "not_found", "service": service}

        if route.get("source") == "env":
            var = route.get("var", "")
            if var:
                val = os.environ.get(var, "")
                if val:
                    return {"source": "env", "value": val}
            return {"source": "env", "value": None,
                    "error": f"环境变量 {var or '?'} 未设置"}

        if route.get("source") == "service":
            return {"source": "service"}

        return {"source": "not_found", "service": service}


# ═══════════════════════════════════════════════════════════
# KeyHandlers mixin
# ═══════════════════════════════════════════════════════════

class KeyHandlers:
    """密钥指令 — copilot 路由层"""

    _key_router: KeyRouter | None = None

    @property
    def key_router(self) -> KeyRouter:
        if self._key_router is None:
            data_dir = Path(self.config.get('_config_dir',
                            str(Path(__file__).resolve().parent.parent / 'config')))
            self._key_router = KeyRouter(data_dir)
        return self._key_router

    # ── key;get (新增: 路由分派) ──

    def _handle_key_get(self, params: list) -> dict:
        """密钥;获取,<service> → 按路由返回"""
        if not params:
            return error('missing_param', 'missing parameter: service name')

        service = params[0]
        result = self.key_router.resolve(service)

        if result["source"] == "env":
            if result.get("value"):
                self._log_call('KEY_GET', service=service, source='env',
                               detail='ok')
                return ok(f'key:{service}', service=service,
                         source='env', value=result["value"])
            self._log_call('KEY_GET', service=service, source='env',
                           detail='empty')
            return error('env_not_set',
                        f'env var not set: {service}')

        if result["source"] == "service":
            self._log_call('KEY_GET', service=service, source='delegated')
            return error('delegated', f'key {service} managed by service',
                        __delegated__=True)

        self._log_call('KEY_GET', service=service, source='not_found',
                       detail='not_in_routing')
        return error('not_found',
                    f'key {service} not in routing table. Edit config/key_routing.json to add.')

    # ── 注册 / 撤销 / 列表 → 全部 delegated ──

    def _handle_key_register(self, params: list) -> dict:
        """密钥;注册 → ⤴ delegated"""
        self._log_call('KEY_REGISTER', delegated=True,
                       detail=f'params={params}')
        return error('delegated',
                    'key registration handled by service',
                    __delegated__=True)

    def _handle_key_revoke(self, params: list) -> dict:
        """密钥;撤销 → ⤴ delegated"""
        self._log_call('KEY_REVOKE', delegated=True,
                       detail=f'params={params}')
        return error('delegated',
                    'key revocation handled by service',
                    __delegated__=True)

    def _handle_key_list(self, params: list) -> dict:
        """密钥;列表 → ⤴ delegated"""
        self._log_call('KEY_LIST', delegated=True)
        return error('delegated',
                    'key list managed by service',
                    __delegated__=True)

    def _handle_key_quota_track(self, params: list) -> dict:
        """密钥;配额追踪 → ⤴ delegated"""
        self._log_call('KEY_QUOTA_TRACK', delegated=True,
                       detail=f'params={params}')
        return error('delegated',
                    '配额追踪由 service 管理',
                    __delegated__=True)

    # ── 审计 ──

    def _log_call(self, action: str, **kwargs):
        """写入 call_log.jsonl (审计轨迹)"""
        data_dir = Path(self.config.get('_config_dir',
                        str(Path(__file__).resolve().parent.parent / 'data')))
        log_path = data_dir / 'call_log.jsonl'
        log_path.parent.mkdir(parents=True, exist_ok=True)
        entry = {
            'ts': time.time(),
            'ts_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'action': action,
            **kwargs,
        }
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')

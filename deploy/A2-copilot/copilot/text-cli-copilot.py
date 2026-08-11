#!/usr/bin/env python3
"""
text-cli-copilot — 指令辅助服务器骨架

Architecture:
    core.py          — config loading, instruction parser, dispatch engine
    handlers/codec   — Codec;encode, Codec;decode
    handlers/key     — 密钥路由层
    handlers/skill_bridge — 通用 Skill 桥

包 handler（files/git/mail/system/media/render/mcp/terminal/browser）
由包安装时注入。

Author: Tide 🌊
"""

import json
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import handlers as _h
from core import CopilotCore, error, parse_instruction
from core import SPEC_VERSION, _ERROR_CODE_MAP
from handlers import (
    CodecHandlers,
    KeyHandlers,
    PackageManagerHandlers,
    SkillBridgeHandlers,
)

_pkg_bases = getattr(_h, '_discovered_classes', [])

_CopilotBases = (
    CodecHandlers,
    KeyHandlers,
    SkillBridgeHandlers,
    PackageManagerHandlers,
    *tuple(_pkg_bases),
    CopilotCore,
)


# ═══════════════════════════════════════════════════════════════
# Copilot Class — core + all handler mixins
# ═══════════════════════════════════════════════════════════════

class Copilot(*_CopilotBases):
    """指令辅助服务器 — 骨架 mixin + 核心引擎 + 动态发现的包 handler"""


# ═══════════════════════════════════════════════════════════════
# HTTP Service
# ═══════════════════════════════════════════════════════════════

class CopilotHandler(BaseHTTPRequestHandler):
    """HTTP request handler"""

    copilot: Copilot = None

    def log_message(self, format, *args):
        print(f"[copilot] {args[0]}")

    def do_POST(self):
        if self.path == '/ai_status':
            self._handle_ai_status()
            return
        if self.path != '/text-cli/cli':
            self._send_error_json(404, 'not_found', 'Endpoint not found')
            return

        # token: null → 不校验（A2 绑在 127.0.0.1，安全由 OS 文件权限保证）
        if self.copilot.token is not None:
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer ') or auth[7:] != self.copilot.token:
                self.copilot.track_error()
                self._send_error_json(401, 'unauthorized', 'Token invalid')
                return

        try:
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length).decode('utf-8')
            request = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            self.copilot.track_error()
            self._send_error_json(400, 'bad_request', 'Request body is not valid JSON')
            return
        except Exception:
            self.copilot.track_error()
            self._send_error_json(400, 'bad_request', 'Unable to read request body')
            return

        prompt = request.get('prompt', '')
        # Extract injected credentials (from service proxy)
        self.copilot._injected_creds = request.get('_injected_credentials', {})

        parsed = parse_instruction(prompt)

        if parsed is None:
            self.copilot.track_error()
            result = error('parse_error',
                          'Unable to parse directive format. Expected format: '
                          '"指令:domain;action,param1,param2" or "directive:domain;action,param1,param2"')
        else:
            result = self.copilot.dispatch(parsed)

        self._send_json(200, result)

    def do_GET(self):
        if self.path == '/text_cli_schema.json':
            self._send_json(200, self._build_schema())
        elif self.path == '/text-cli/health':
            self._send_json(200, {
                'status': 'ok',
                'body': self.copilot.config['endpoint_info']['description'],
                'version': self.copilot.config['endpoint_info']['version'],
                'spec_version': SPEC_VERSION,
                'public_skills': [],
            })
        else:
            self._send_error_json(404, 'not_found', 'Endpoint not found')

    def _send_json(self, status: int, data: dict):
        body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error_json(self, status: int, code: str, detail: str):
        protocol_code = _ERROR_CODE_MAP.get(code, "ERR_EXECUTION")
        self._send_json(status, {
            'rst_types': 'text',
            'rst_data': {'status': 'error', 'reason': detail, 'error_code': code},
            'rst_err': protocol_code,
        })

    def _handle_ai_status(self):
        """POST /ai_status — Agent writes current session status"""
        # token: null → 不校验
        if self.copilot.token is not None:
            auth = self.headers.get('Authorization', '')
            if not auth.startswith('Bearer ') or auth[7:] != self.copilot.token:
                self._send_error_json(401, 'unauthorized', 'Token invalid')
                return

        try:
            length = int(self.headers.get('Content-Length', '0'))
            body = self.rfile.read(length).decode('utf-8')
            data = json.loads(body)
        except Exception:
            self._send_error_json(400, 'bad_request', 'Invalid JSON')
            return

        self.copilot._ai_status = {
            'model': data.get('model', ''),
            'context_used': data.get('context_used', ''),
            'context_max': data.get('context_max', ''),
            'context_pct': data.get('context_pct', 0),
            'compactions': data.get('compactions', 0),
            'tokens_in': data.get('tokens_in', ''),
            'tokens_out': data.get('tokens_out', ''),
            'cache_hit': data.get('cache_hit', ''),
            'cache_cached': data.get('cache_cached', ''),
            'updated_at': time.time(),
        }

        self._send_json(200, {'status': 'ok'})

    def _build_schema(self) -> dict:
        """Build schema from auxiliary_config + installed package schema.json files."""
        cfg = self.copilot.config
        directives = []
        seen = set()

        # 1. 从 auxiliary_config operations 读（含安全策略覆盖）
        ops = cfg['security'].get('operations', {})
        for op_id, op_cfg in ops.items():
            if op_cfg.get('enabled') is False:
                continue
            directives.append({
                'id': op_id,
                'aliases': op_cfg.get('aliases', []),
                'description': op_cfg.get('description', ''),
                'description_en': op_cfg.get('description_en', ''),
                'parameters': op_cfg.get('parameters', []),
                'parameters_en': op_cfg.get('parameters_en', []),
                'returns': op_cfg.get('returns', ''),
            })
            seen.add(op_id)

        # 2. 从 packages/<pkg>/schema.json 读（动态安装的包）
        packages_dir = Path(__file__).parent / 'packages'
        if packages_dir.is_dir():
            for pkg_dir in sorted(packages_dir.iterdir()):
                if pkg_dir.name.startswith(('_', '.')) or not pkg_dir.is_dir():
                    continue
                schema_file = pkg_dir / 'schema.json'
                if not schema_file.is_file():
                    continue
                try:
                    pkg_schema = json.loads(schema_file.read_text(encoding='utf-8'))
                    for d in pkg_schema.get('directives', []):
                        # schema.json 用 domain+action 或 id 字段
                        op_id = d.get('id') or f"{d['domain']};{d['action']}"
                        if op_id in seen:
                            continue
                        directives.append({
                            'id': op_id,
                            'aliases': d.get('aliases', []),
                            'description': d.get('description', ''),
                            'description_en': d.get('description_en', ''),
                            'parameters': d.get('parameters', []),
                            'parameters_en': d.get('parameters_en', []),
                            'returns': d.get('returns', ''),
                        })
                        seen.add(op_id)
                except Exception:
                    pass

        # 3. 从 skill_bridge_routes.json 读 skill 指令
        try:
            routes_path = Path(__file__).parent / 'config' / 'skill_bridge_routes.json'
            if routes_path.exists():
                skill_data = json.loads(routes_path.read_text(encoding='utf-8'))
                for op_id, route in skill_data.get('routes', {}).items():
                    if op_id in seen:
                        continue
                    directives.append({
                        'id': op_id,
                        'description': route.get('description', ''),
                        'description_en': route.get('description', ''),
                        'parameters': [p.get('name', '') for p in route.get('params', [])],
                        'returns': 'rst_data',
                    })
                    seen.add(op_id)
        except Exception:
            pass

        return {
            'endpoint': {
                'name': cfg['endpoint_info']['name'],
                'url': f"http://{cfg['server']['host']}:{cfg['server']['port']}",
                'version': cfg['endpoint_info']['version'],
            },
            'directives': directives,
        }


# ═══════════════════════════════════════════════════════════════
# Entry Point
# ═══════════════════════════════════════════════════════════════

def main():
    script_dir = Path(__file__).parent.resolve()
    if not os.environ.get('TEXT_CLI_HOME'):
        os.environ['TEXT_CLI_HOME'] = str(script_dir.parent)
    config_path = script_dir / 'auxiliary_config.json'

    if not config_path.exists():
        print(f"[copilot] [ERR] Config file not found: {config_path}")
        sys.exit(1)

    copilot = Copilot(str(config_path))
    CopilotHandler.copilot = copilot

    host = copilot.config['server']['host']
    port = copilot.config['server']['port']

    server = HTTPServer((host, port), CopilotHandler)
    print(f"[copilot] [OK] text-cli-copilot v{copilot.config['endpoint_info']['version']}")
    print(f"[copilot] [LISTEN] listening on http://{host}:{port}")
    if copilot.token:
        print(f"[copilot] [AUTH] token: {'*' * 8}")
    else:
        print("[copilot] [OPEN] token: null（不校验，127.0.0.1 本地安全）")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[copilot] [STOP] Service stopped")
        server.shutdown()


if __name__ == '__main__':
    main()

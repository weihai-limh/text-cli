#!/usr/bin/env python3
"""
text-cli-copilot — directive copilot server
Encapsulates local file I/O, Git operations, mail sending, and skill terminal proxy as text-cli directives.
Zero dependencies, Python stdlib only. localhost:20260.

Architecture:
    core.py          — config loading, instruction parser, dispatch engine
    handlers/files   — File;read, File;write
    handlers/git     — Git;status, Git;push
    handlers/mail    — Mail;send
    handlers/system  — System;health, System;status
    handlers/ai      — AI;status, AI;message
    handlers/oc_terminal — Terminal;weather (depends on OpenClaw Skill)

Adding a new domain = adding handlers/xxx.py + one line in config. Zero routing changes.
"""

import json
import os
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

from core import CopilotCore, parse_instruction, error
from handlers import (
    FileHandlers, GitHandlers, MailHandlers,
    SystemHandlers, AIHandlers, TerminalHandlers,
    CodecHandlers, KeyHandlers, MediaHandlers,
    JsonProcHandlers,
)
# TerminalHandlers comes from handlers.oc_terminal (depends on OpenClaw Skill)


# ═══════════════════════════════════════════════════════════════
# Copilot Class — core + all handler mixins
# ═══════════════════════════════════════════════════════════════

class Copilot(
    FileHandlers,
    GitHandlers,
    MailHandlers,
    SystemHandlers,
    AIHandlers,
    TerminalHandlers,
    CodecHandlers,
    KeyHandlers,
    MediaHandlers,
    JsonProcHandlers,
    CopilotCore,
):
    """Directive copilot server — inherits all handler mixins + core engine"""
    pass


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
        if self.path != '/cli/text_cli':
            self._send_error_json(404, 'not_found', 'Endpoint not found')
            return

        auth = self.headers.get('Authorization', '')
        if not auth.startswith('Bearer '):
            self.copilot.track_error()
            self._send_error_json(401, 'unauthorized', 'Bearer Token required')
            return

        token = auth[7:]
        if token != self.copilot.token:
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
        elif self.path == '/health':
            self._send_json(200, {'status': 'ok'})
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
        self._send_json(status, {
            'rst_types': 'text',
            'rst_data': {'text': f'[{code}] {detail}'},
            'rst_err': code,
        })

    def _handle_ai_status(self):
        """POST /ai_status — Agent writes current session status"""
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
        cfg = self.copilot.config
        ops = cfg['security']['operations']
        directives = []
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
    config_path = script_dir / 'auxiliary_config.json'

    if not config_path.exists():
        print(f"[copilot] ❌ Config file not found: {config_path}")
        sys.exit(1)

    copilot = Copilot(str(config_path))
    CopilotHandler.copilot = copilot

    host = copilot.config['server']['host']
    port = copilot.config['server']['port']

    server = HTTPServer((host, port), CopilotHandler)
    print(f"[copilot] ✅ text-cli-copilot v{copilot.config['endpoint_info']['version']}")
    print(f"[copilot] 📡 listening on http://{host}:{port}")
    print(f"[copilot] 🔑 token: {'*' * 8} (TEXT_CLI_TOKEN_LOCAL)")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[copilot] 🛑 Service stopped")
        server.shutdown()


if __name__ == '__main__':
    main()

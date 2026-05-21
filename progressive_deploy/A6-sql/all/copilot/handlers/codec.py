"""
Codec handler mixin — base64, hex
"""

import base64
from core import ok, error


class CodecHandlers:
    """encode;base64 (alias: 编码;base64) / encode;hex (alias: 编码;hex)"""

    def _handle_encode_base64(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: mode (encode/decode)')
        mode = params[0].lower()
        if mode == 'encode':
            if len(params) < 2:
                return error('missing_param', 'Missing parameter: content')
            content = params[1]
            try:
                encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
                return ok(encoded)
            except Exception as e:
                return error('encode_error', f'Encode failed: {e}')
        elif mode == 'decode':
            if len(params) < 2:
                return error('missing_param', 'Missing parameter: base64_string')
            b64_str = params[1].strip()
            try:
                decoded = base64.b64decode(b64_str).decode('utf-8')
                return ok(decoded)
            except Exception:
                return error('decode_error', 'base64 decode failed, check input')
        else:
            return error('bad_request', f'Unknown mode: {mode}, use encode/decode')

    def _handle_encode_hex(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: mode (encode/decode)')
        mode = params[0].lower()
        if mode == 'encode':
            if len(params) < 2:
                return error('missing_param', 'Missing parameter: content')
            content = params[1]
            try:
                encoded = content.encode('utf-8').hex()
                return ok(encoded)
            except Exception as e:
                return error('encode_error', f'Encode failed: {e}')
        elif mode == 'decode':
            if len(params) < 2:
                return error('missing_param', 'Missing parameter: hex_string')
            hex_str = params[1].strip()
            try:
                decoded = bytes.fromhex(hex_str).decode('utf-8')
                return ok(decoded)
            except Exception:
                return error('decode_error', 'hex decode failed, check input')
        else:
            return error('bad_request', f'Unknown mode: {mode}, use encode/decode')

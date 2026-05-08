"""
编解码 handler mixin — base64, hex
"""

import base64
from core import ok, error


class CodecHandlers:
    """编码;base64 / 编码;hex"""

    def _handle_encode_base64(self, params: list) -> dict:
        if not params:
            return error('missing_param', '缺少参数: 模式(encode/decode)')
        mode = params[0].lower()
        if mode == 'encode':
            if len(params) < 2:
                return error('missing_param', '缺少参数: 内容')
            content = params[1]
            try:
                encoded = base64.b64encode(content.encode('utf-8')).decode('ascii')
                return ok(encoded)
            except Exception as e:
                return error('encode_error', f'编码失败: {e}')
        elif mode == 'decode':
            if len(params) < 2:
                return error('missing_param', '缺少参数: base64 字符串')
            b64_str = params[1].strip()
            try:
                decoded = base64.b64decode(b64_str).decode('utf-8')
                return ok(decoded)
            except Exception:
                return error('decode_error', 'base64 解码失败，请检查输入')
        else:
            return error('bad_request', f'未知模式: {mode}，请使用 encode/decode')

    def _handle_encode_hex(self, params: list) -> dict:
        if not params:
            return error('missing_param', '缺少参数: 模式(encode/decode)')
        mode = params[0].lower()
        if mode == 'encode':
            if len(params) < 2:
                return error('missing_param', '缺少参数: 内容')
            content = params[1]
            try:
                encoded = content.encode('utf-8').hex()
                return ok(encoded)
            except Exception as e:
                return error('encode_error', f'编码失败: {e}')
        elif mode == 'decode':
            if len(params) < 2:
                return error('missing_param', '缺少参数: hex 字符串')
            hex_str = params[1].strip()
            try:
                decoded = bytes.fromhex(hex_str).decode('utf-8')
                return ok(decoded)
            except Exception:
                return error('decode_error', 'hex 解码失败，请检查输入')
        else:
            return error('bad_request', f'未知模式: {mode}，请使用 encode/decode')

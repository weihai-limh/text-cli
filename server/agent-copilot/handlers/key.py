"""
密钥管理 handler mixin。

指令:
  密钥;注册,<service>,<cipher_hex>,<key_type>
  密钥;撤销,<service>
  密钥;列表

安全模型:
  - XOR 传输加密：调用方用 XOR_KEY_<service> 加密明文 → cipher_hex
  - 本地加密：key_registry.json 用 KEY_REGISTRY_SECRET 再加密一层
  - 列表不返回密钥值
  - 已存在 → 拒绝覆盖（需先撤销）
"""

import hashlib
import json
import os
import time
from pathlib import Path
from core import ok, error


# ═══════════════════════════════════════════════════════════
# XOR 工具函数
# ═══════════════════════════════════════════════════════════

def xor_encrypt_decrypt(data: bytes, key: str) -> bytes:
    """XOR 加密/解密（对称操作，encrypt == decrypt）"""
    key_bytes = key.encode('utf-8')
    return bytes(data[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(data)))

def xor_decrypt_hex(cipher_hex: str, key: str) -> str:
    """hex → XOR 解密 → 明文"""
    cipher_bytes = bytes.fromhex(cipher_hex)
    plain = xor_encrypt_decrypt(cipher_bytes, key)
    return plain.decode('utf-8', errors='replace')

def xor_encrypt_hex(plain: str, key: str) -> str:
    """明文 → XOR 加密 → hex"""
    plain_bytes = plain.encode('utf-8')
    cipher = xor_encrypt_decrypt(plain_bytes, key)
    return cipher.hex()


# ═══════════════════════════════════════════════════════════
# 本地加密（key_registry.json 二次加密）
# ═══════════════════════════════════════════════════════════

def _local_key() -> str:
    """本地存储加密密钥"""
    return os.environ.get('KEY_REGISTRY_SECRET', '')

def _local_encrypt(plain: str) -> str:
    """用 KEY_REGISTRY_SECRET 加密"""
    key = _local_key()
    if not key:
        return plain  # 无 KEY_REGISTRY_SECRET 时明文存储（不安全！）
    return xor_encrypt_hex(plain, key)

def _local_decrypt(cipher_hex: str) -> str:
    """用 KEY_REGISTRY_SECRET 解密"""
    key = _local_key()
    if not key:
        return cipher_hex
    return xor_decrypt_hex(cipher_hex, key)


# ═══════════════════════════════════════════════════════════
# KeyRegistry — 密钥注册表 CRUD
# ═══════════════════════════════════════════════════════════

class KeyRegistry:
    """本地密钥注册表（JSON 文件 + 二次加密）"""

    def __init__(self, data_dir: Path):
        self.registry_path = data_dir / 'key_registry.json'
        self._ensure_registry()

    def _ensure_registry(self):
        if not self.registry_path.exists():
            self._write({})

    def _read(self) -> dict:
        try:
            with open(self.registry_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            raw = {}

        # 解密所有 stored_value
        registry = {}
        for service_name, entry in raw.items():
            entry_copy = dict(entry)
            if 'encrypted_value' in entry_copy:
                entry_copy['plain_value'] = _local_decrypt(entry_copy['encrypted_value'])
            registry[service_name] = entry_copy
        return registry

    def _write(self, registry: dict):
        # 加密所有 plain_value → encrypted_value
        out = {}
        for service_name, entry in registry.items():
            entry_copy = dict(entry)
            if 'plain_value' in entry_copy:
                entry_copy['encrypted_value'] = _local_encrypt(entry_copy.pop('plain_value'))
            # 不存 plain_value
            entry_copy.pop('plain_value', None)
            out[service_name] = entry_copy

        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.registry_path, 'r' if self.registry_path.exists() else 'w', encoding='utf-8') as f:
            pass  # just ensure file exists
        with open(self.registry_path, 'w', encoding='utf-8') as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

    def register(self, service_name: str, plain_value: str, key_type: str) -> dict:
        registry = self._read()
        if service_name in registry:
            return error('key_exists',
                        f'密钥 {service_name} 已存在，请先撤销')
        registry[service_name] = {
            'service': service_name,
            'plain_value': plain_value,
            'key_type': key_type,
            'registered_at': time.time(),
            'registered_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        self._write(registry)
        return ok(f'密钥已注册: {service_name}',
                 service=service_name, key_type=key_type)

    def revoke(self, service_name: str) -> dict:
        registry = self._read()
        if service_name not in registry:
            return error('key_not_found',
                        f'密钥 {service_name} 不存在')
        del registry[service_name]
        self._write(registry)
        return ok(f'密钥已撤销: {service_name}',
                 service=service_name)

    def list_keys(self) -> dict:
        registry = self._read()
        entries = []
        for svc, entry in registry.items():
            entries.append({
                'service': svc,
                'key_type': entry.get('key_type', 'unknown'),
                'registered_at': entry.get('registered_at_iso', 'unknown'),
            })
        return entries

    def get(self, service_name: str) -> str | None:
        """获取明文密钥值"""
        registry = self._read()
        entry = registry.get(service_name)
        if not entry:
            return None
        return entry.get('plain_value')

    def get_xor_key(self, service_name: str) -> str:
        """获取对应服务的 XOR 传输密钥"""
        # 环境变量名不支持连字符，统一替换为下划线
        env_var = f'XOR_KEY_{service_name.replace("-", "_")}'
        return os.environ.get(env_var, '')


# ═══════════════════════════════════════════════════════════
# KeyHandlers mixin
# ═══════════════════════════════════════════════════════════

class KeyHandlers:
    """密钥;注册 / 密钥;撤销 / 密钥;列表"""

    _key_registry: KeyRegistry | None = None

    @property
    def key_registry(self) -> KeyRegistry:
        if self._key_registry is None:
            data_dir = Path(self.config.get('_config_dir',
                            str(Path(__file__).resolve().parent.parent / 'data')))
            self._key_registry = KeyRegistry(data_dir)
        return self._key_registry

    def _handle_key_register(self, params: list) -> dict:
        """密钥;注册,<service>,<cipher_hex>,<key_type>

        service: 服务标识（如 smtp-tide, bigmodel-embedding-3）
        cipher_hex: XOR 加密后的密钥十六进制串
        key_type: 密钥类型（如 smtp_password, api_key, github_token）
        """
        if len(params) < 3:
            return error('missing_param',
                        '缺少参数: 服务名, 密文(hex), 密钥类型')

        service_name = params[0]
        cipher_hex = params[1]
        key_type = params[2]

        # 获取 XOR 传输密钥
        xor_key = self.key_registry.get_xor_key(service_name)
        if not xor_key:
            return error('missing_xor_key',
                        f'环境变量 XOR_KEY_{service_name} 未设置，'
                        f'无法解密传输密文')

        # XOR 解密
        try:
            plain_value = xor_decrypt_hex(cipher_hex, xor_key)
        except (ValueError, UnicodeDecodeError) as e:
            return error('decrypt_failed',
                        f'解密失败: {e}')

        if not plain_value:
            return error('empty_value', '解密后密钥为空')

        # 写入本地加密注册表
        result = self.key_registry.register(service_name, plain_value, key_type)

        # 审计日志
        self._log_call('KEY_REGISTER', service=service_name, key_type=key_type)

        return result

    def _handle_key_revoke(self, params: list) -> dict:
        """密钥;撤销,<service>"""
        if not params:
            return error('missing_param', '缺少参数: 服务名')

        service_name = params[0]
        result = self.key_registry.revoke(service_name)
        self._log_call('KEY_REVOKE', service=service_name)
        return result

    def _handle_key_list(self, params: list) -> dict:
        """密钥;列表 — 返回服务名+类型+时间，不返回密钥值"""
        entries = self.key_registry.list_keys()
        if not entries:
            return ok('已注册密钥: (空)', count=0, keys=[])
        return ok(f'已注册密钥: {len(entries)} 个',
                 count=len(entries), keys=entries)

    def _log_call(self, action: str, **kwargs):
        """写入 call_log.jsonl（审计轨迹）"""
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

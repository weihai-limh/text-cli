"""
Key management handler mixin.

Directives:
  密钥;注册,<service>,<cipher_hex>,<key_type>
  密钥;撤销,<service>
  密钥;列表

Security model:
  - XOR transport encryption: caller encrypts plaintext with XOR_KEY_<service> → cipher_hex
  - Local encryption: key_registry.json is further encrypted with KEY_REGISTRY_SECRET
  - List does not return key values
  - Existing keys → reject overwrite (must revoke first)
"""

import hashlib
import json
import os
import time
from pathlib import Path
from core import ok, error


# ═══════════════════════════════════════════════════════════════
# XOR utilities
# ═══════════════════════════════════════════════════════════════

def xor_encrypt_decrypt(data: bytes, key: str) -> bytes:
    """XOR encrypt/decrypt (symmetric, encrypt == decrypt)"""
    key_bytes = key.encode('utf-8')
    return bytes(data[i] ^ key_bytes[i % len(key_bytes)] for i in range(len(data)))

def xor_decrypt_hex(cipher_hex: str, key: str) -> str:
    """hex → XOR decrypt → plaintext"""
    cipher_bytes = bytes.fromhex(cipher_hex)
    plain = xor_encrypt_decrypt(cipher_bytes, key)
    return plain.decode('utf-8', errors='replace')

def xor_encrypt_hex(plain: str, key: str) -> str:
    """plaintext → XOR encrypt → hex"""
    plain_bytes = plain.encode('utf-8')
    cipher = xor_encrypt_decrypt(plain_bytes, key)
    return cipher.hex()


# ═══════════════════════════════════════════════════════════════
# Local encryption (key_registry.json double encryption)
# ═══════════════════════════════════════════════════════════════

def _local_key() -> str:
    """Local storage encryption key"""
    return os.environ.get('KEY_REGISTRY_SECRET', '')

def _local_encrypt(plain: str) -> str:
    """Encrypt with KEY_REGISTRY_SECRET"""
    key = _local_key()
    if not key:
        return plain  # plaintext storage without KEY_REGISTRY_SECRET (insecure!)
    return xor_encrypt_hex(plain, key)

def _local_decrypt(cipher_hex: str) -> str:
    """Decrypt with KEY_REGISTRY_SECRET"""
    key = _local_key()
    if not key:
        return cipher_hex
    return xor_decrypt_hex(cipher_hex, key)


# ═══════════════════════════════════════════════════════════════
# KeyRegistry — key registry CRUD
# ═══════════════════════════════════════════════════════════════

class KeyRegistry:
    """Local key registry (JSON file + double encryption)"""

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

        # Decrypt all stored_value
        registry = {}
        for service_name, entry in raw.items():
            entry_copy = dict(entry)
            if 'encrypted_value' in entry_copy:
                entry_copy['plain_value'] = _local_decrypt(entry_copy['encrypted_value'])
            registry[service_name] = entry_copy
        return registry

    def _write(self, registry: dict):
        # Encrypt all plain_value → encrypted_value
        out = {}
        for service_name, entry in registry.items():
            entry_copy = dict(entry)
            if 'plain_value' in entry_copy:
                entry_copy['encrypted_value'] = _local_encrypt(entry_copy.pop('plain_value'))
            # Don't store plain_value
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
                        f'Key {service_name} already exists, revoke first')
        registry[service_name] = {
            'service': service_name,
            'plain_value': plain_value,
            'key_type': key_type,
            'registered_at': time.time(),
            'registered_at_iso': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        }
        self._write(registry)
        return ok(f'Key registered: {service_name}',
                 service=service_name, key_type=key_type)

    def revoke(self, service_name: str) -> dict:
        registry = self._read()
        if service_name not in registry:
            return error('key_not_found',
                        f'Key {service_name} not found')
        del registry[service_name]
        self._write(registry)
        return ok(f'Key revoked: {service_name}',
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
        """Get plaintext key value"""
        registry = self._read()
        entry = registry.get(service_name)
        if not entry:
            return None
        return entry.get('plain_value')

    def get_xor_key(self, service_name: str) -> str:
        """Get XOR transport key for the given service"""
        env_var = f'XOR_KEY_{service_name.replace("-", "_")}'
        return os.environ.get(env_var, '')


# ═══════════════════════════════════════════════════════════════
# KeyHandlers mixin
# ═══════════════════════════════════════════════════════════════

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

        service: service identifier (e.g. smtp-tide, bigmodel-embedding-3)
        cipher_hex: XOR-encrypted key as hex string
        key_type: key type (e.g. smtp_password, api_key, github_token)
        """
        if len(params) < 3:
            return error('missing_param',
                        'Missing parameter: service_name, cipher_hex, key_type')

        service_name = params[0]
        cipher_hex = params[1]
        key_type = params[2]

        # Get XOR transport key
        xor_key = self.key_registry.get_xor_key(service_name)
        if not xor_key:
            return error('missing_xor_key',
                        f'Env var XOR_KEY_{service_name} not set, '
                        f'cannot decrypt transport ciphertext')

        # XOR decrypt
        try:
            plain_value = xor_decrypt_hex(cipher_hex, xor_key)
        except (ValueError, UnicodeDecodeError) as e:
            return error('decrypt_failed',
                        f'Decrypt failed: {e}')

        if not plain_value:
            return error('empty_value', 'Decrypted key is empty')

        # Write to local encrypted registry
        result = self.key_registry.register(service_name, plain_value, key_type)

        # Audit log
        self._log_call('KEY_REGISTER', service=service_name, key_type=key_type)

        return result

    def _handle_key_revoke(self, params: list) -> dict:
        """密钥;撤销,<service>"""
        if not params:
            return error('missing_param', 'Missing parameter: service_name')

        service_name = params[0]
        result = self.key_registry.revoke(service_name)
        self._log_call('KEY_REVOKE', service=service_name)
        return result

    def _handle_key_list(self, params: list) -> dict:
        """密钥;列表 — return service+type+time, no key values"""
        entries = self.key_registry.list_keys()
        if not entries:
            return ok('Registered keys: (empty)', count=0, keys=[])
        return ok(f'Registered keys: {len(entries)}',
                 count=len(entries), keys=entries)

    def _log_call(self, action: str, **kwargs):
        """Write to call_log.jsonl (audit trail)"""
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

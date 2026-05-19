# key

Register, revoke, and list API keys with encrypted local storage.

## Install

```
AI:text-cli;install,key
```

## Dependencies

**Runtime modules** (must be deployed to the service):
- `text_cli_modules/key/` — key registry (register, revoke, list, quota tracking)
- `text_cli_modules/sqlite/` — SQLite database layer

## Security Model

- **Transport**: plaintext XOR-encrypted with `XOR_KEY_<service>` before transmission
- **Storage**: encrypted locally with `KEY_REGISTRY_SECRET`
- **List safety**: `key;list` returns service names and types only — never exposes key values

## Directives

| Directive | Description |
|-----------|-------------|
| `key;register,<service>,<value>[,<value2>],<key_type>` | Register a key. Single: `key;register,svc,val,api_key`. Dual: `key;register,svc,id,secret,cloud` |
| `key;revoke,<service>` | Remove a key |
| `key;list` | List all keys (no values exposed) |
| `key;quota-track,<service>[,<target>,...]` | Set or clear quota tracking |
| `key;export-xor,<service>` | Export XOR-encrypted key for external injection |

## Example

```
AI:key;register,my-api,sk-abc123,api_key
→ Key registered: my-api (type=api_key, cred_count=1)

AI:key;list
→ Registered keys: 2
    my-api (api_key, cred_count=1)
    my-cloud (cloud_credentials, cred_count=2)

AI:key;revoke,my-api
→ Key revoked: my-api
```

## Architecture

```
A6 SQL module
  ├── handler.py          — @directive registration + business logic
  ├── schema.json         — directive declarations
  ├── text_cli_modules/key/ — key_registry (runtime dependency)
  └── text_cli_modules/sqlite/ — database layer (runtime dependency)
```

SQLite table: `keys(service, key_type, value_encrypted, value2_encrypted?, cred_count, quota_track, registered_at)`

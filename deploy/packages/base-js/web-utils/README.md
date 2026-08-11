# web-utils

Web utility package: fetch the caller's public IP and XOR encrypt/decrypt. Deployed as a Tencent CloudBase cloud function (Node.js runtime, `wx-server-sdk`).

## Invocation

This package is **not** installed via `text-cli;install` — it runs as a cloud function.

### Direct HTTP call (when the endpoint is known)

```bash
curl -s -X POST <endpoint-url>/cli/text_cli \
  --header 'Content-Type: application/json' \
  --data-raw '{"prompt":"AI:web-utils;get_public_ip"}'
```

### Via A3 routing (after configuring aggregate routing)

```bash
tc "AI:web-utils;get_public_ip"
tc "AI:web-utils;xor_encrypt,hello world,mykey"
tc "AI:web-utils;xor_decrypt,68656c6c6f20776f726c64,mykey"
```

## Directives

| Directive | Description |
|-----------|-------------|
| `web-utils;get_public_ip` | Return the caller's public IP |
| `web-utils;xor_encrypt,<plaintext>,<key>` | XOR-encrypt plaintext with a key (key reused cyclically) |
| `web-utils;xor_decrypt,<ciphertext>,<key>` | XOR-decrypt hex ciphertext with a key |

## Example

```
AI:web-utils;get_public_ip
→ {"status":"ok","result":"203.0.113.1"}

AI:web-utils;xor_encrypt,hello world,mykey
→ {"status":"ok","result":"68656c6c6f20776f726c64"}

AI:web-utils;xor_decrypt,68656c6c6f20776f726c64,mykey
→ {"status":"ok","result":"hello world"}
```

## Notes

- Deployed as a Tencent CloudBase cloud function — not installed via `text-cli;install`.
- Responses are wrapped in the full HTTP envelope (`{rst_types, rst_data}`) because the function responds to HTTP requests directly.

## Architecture

```
web-utils/                  (Node.js, wx-server-sdk)
├── schema.json             — 3 directive declarations
├── index.js                — cloud function entry + directive dispatcher
├── package.json
└── instructions/
    ├── get_public_ip.js
    ├── xor_encrypt.js
    └── xor_decrypt.js
```

# Instruction Package Publishing Guide

> For package authors. What a SPEC-compliant instruction package should look like — a unified structure across languages and runtimes.
> Bypass-runtime compatibility: a `native-python` package conforming to this guide can be loaded directly by `textcli-loader` (PyPI), and a `native-js` package by `textcli-core` (npm) — write once, usable across multiple runtimes.

---

## 0. Distribution and Licensing

- The **distribution license of an instruction package is decided by the package author** (MIT / Apache-2.0 / GPL / proprietary / …); the SPEC imposes no restriction.
- The official repository provides multiple **SPEC-compatible runtimes**, mainly maintaining two parts: protocol evolution + runtime iteration. It does not participate in package curation or distribution review.

---

## 1. File Structure

### 1.1 Python Package

```
<package-id>/
├── schema.json              ← required
├── handler.py               ← required (@directive decorator registration)
├── README.md                ← recommended
├── requirements.txt         ← as needed
├── text_cli_modules/        ← as needed
└── config/                  ← as needed
```

### 1.2 JavaScript Package

```
<package-id>/
├── schema.json              ← required
├── handler.js               ← required (declarative module.exports registration)
├── README.md                ← recommended
├── package.json             ← as needed
└── config/                  ← as needed
```

The JS handler uses a **declarative export structure**:

```javascript
module.exports = {
  domainAlias: "example-alias",
  directives: {
    "action-name": {
      handler: (params, context) => { /* params: string[] → object */ },
      actionAliases: ["example-action-alias"]
    }
  }
};
```

### 1.3 MCP Bridge Package

```
<package-id>/
├── schema.json              ← required (type: "native", runtime: "mcp")
├── service-descriptor.json  ← required (mcporter mapping table)
└── README.md                ← recommended
```

An MCP bridge package has zero handler code — each instruction points to the MCP server's tool name via the `mcp_tool` field in `schema.json`, and `service-descriptor.json` defines the MCP connection parameters.

### 1.4 Other Forms

| Form | Handler-substitute file | Description |
|------|------------------------|-------------|
| cmd | `whitelist.json` | Command-line tool whitelist |
| path | `path/` directory | Path orchestration (pure declaration, no handler) |
| nocode | `knowledge/` directory | No-code knowledge base (see nocode guide) |

---

## 2. schema.json Specification

> The following fields are authoritative per SPEC §4.2. This guide provides a Checklist + counter-examples.

### 2.1 Top-Level Fields

| Field | Required | Legal Values |
|-------|----------|--------------|
| `id` | ✅ | Hyphenated format, e.g. `my-package` |
| `type` | ✅ | `native` / `nocode` / `aggregate` / `pipeline` |
| `name` | ✅ | English name |
| `name_zh` | optional | Chinese name (foreign prefix lowercase) |
| `runtime` | ✅ | `python` / `js` / `mcp` / `cmd` / `path` / `aggregate` |
| `version` | ✅ | Semver |
| `category` | ✅ | e.g. `utility` / `weather` / `ai` / `dev-tools` |
| `locales` | ✅ | `["zh", "en"]` |
| `trust` | ✅ | `internal` / `community` / `public` |
| `description` | ✅ | One English sentence |
| `description_zh` | optional | One Chinese sentence |
| `entry` | optional | e.g. `"handler.py"` |
| `mcp_server` | optional | MCP server name |
| `entry_runtimes` | optional | `["python", "js"]` |
| `requires` | optional | see §2.2 |
| `credentials` | optional | see §2.3 |
| `tables` | optional | Self-built-table CREATE TABLE declarations |
| `directives` | ✅ | see §2.4, at least one |

### 2.2 requires

```json
"requires": {
  "pip": ["requests>=2.28"],
  "modules": ["text_cli_modules/my_module/"],
  "tc_packages": ["other-package"],
  "npm": ["@scope/name@^1.0"],
  "binaries": {
    "some-tool": {"source": "system", "min_version": "1.0"}
  },
  "service_db": ["token_registry"]
}
```

| Sub-field | Description |
|-----------|-------------|
| `pip` | Python packages, auto `pip install` at install time |
| `modules` | Runtime module paths |
| `tc_packages` | Inter-package dependencies |
| `npm` | Node packages, auto `npm install` at install time |
| `binaries` | System binary dependencies |
| `service_db` | Server-side database tables depended on |

Zero dependencies: write `"requires": {}`.

### 2.3 credentials

> `description_zh` is an optional multilingual override — the Chinese value below is an example localized string; `description_en` is the canonical field.

```json
"credentials": [
  {
    "name": "my_api_key",
    "description_en": "API key",
    "description_zh": "API 密钥",
    "storage": "key_registry",
    "register_cmd": "key;register,my_api_key,<key>,api_key"
  }
]
```

Omit the entire block when no credentials are needed.

### 2.4 directives

Each directive must fill in at least the following fields:

> The `_zh` fields (`domain_zh`, `action_zh`, `usage_zh`, `description_zh`, `params_desc`) are optional multilingual overrides — the Chinese values below are example localized strings; canonical fields stay English/neutral.

| Field | Required | Example |
|-------|----------|---------|
| `domain` | ✅ | `"my-pkg"` |
| `domain_zh` | optional | `"我的包"` |
| `action` | ✅ | `"do-something"` |
| `action_zh` | optional | `"做某事"` |
| `usage` | ✅ | `"my-pkg;do-something,<param>"` |
| `usage_zh` | optional | `"我的包;做某事,<参数>"` |
| `description` | ✅ | One English sentence |
| `description_zh` | optional | One Chinese sentence |
| `params` | recommended | `["param"]` |
| `params_desc` | recommended | `{"param": "说明"}` |
| `outputs` | recommended | `["field1"]` |
| `estimated_time` | optional | `"30s"` |
| `estimated_time_note` | optional | Estimated-time note |

### 2.5 Counter-Examples

| ❌ Wrong | ✅ Right |
|---------|---------|
| `"type": "api"` | `"type": "native"` |
| handler returns a JSON string | handler returns a dict/object |
| handler.py hardcodes secrets | secrets go through credentials + key registry |
| docstring writes deploy paths | docstring only writes what instructions the package provides |

### 2.6 Multi-Language Vector Consistency

The foreign prefix in `name_zh`, `domain_zh` is **lowercase** — to keep the Chinese vector embedding space consistent. `domain` and `domain_zh` should be semantically aligned.

---

## 3. README

```markdown
# <name>

One-sentence description.

## Install
text-cli;install,<id>

## Directives
| Instruction | Description |

## Example
At least one complete call example.

## Dependencies
- Runtime modules / credentials / pip dependencies
```

---

## 4. Return Envelope

The handler returns a **dict/object** (not a JSON string); the runtime places it directly into the `rst_data` of the response envelope. The protocol does not constrain the internal structure of `rst_data` — the package author decides the return format:

```json
// Example 1: simple result
{"result": "2026-01-31"}

// Example 2: with status marker (for packages that don't want to be handled by path)
{"status": "ok", "result": "...", "detail": "..."}
{"status": "error", "reason": "..."}
```

**Constraints**:
- Return a dict/object, not a JSON string
- Do not nest a `data` layer
- Error messages readable, do not leak secrets or stack traces

> `rst_err` is a transport-layer field (gateway/runtime layer); the handler is unaware of it and should not set it.
> `{"status": "ok/error", ...}` is a **self-maintained convention** of the package — some packages don't want to be handled by path orchestration, and express their boundary via a self-maintained `status` field. This is not protocol-mandated; it is the package's freedom.

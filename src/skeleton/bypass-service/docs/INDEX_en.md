# bypass-service group

## Positioning

The skeleton layer under the bypass-service group is bound to the **bypass runtime** — non-Python runtimes that do not go through the standard `text-cli;install` pipeline and do not participate in the A2→A9 skeleton accumulation chain. They are hosted by independent cloud-platform gateways and synced to `deploy/bypass-service/` via the pass-through mode of `build-all.py`.

Relationship to the service group: **parallel, non-accumulating, non-inheriting**. The bypass runtime and the standard runtime interoperate through the unified `AI:domain;action,params` protocol — the caller does not perceive whether the executor is a standard service or a cloud function.

## Current runtimes

The bypass runtime covers three deployment forms: a local package loader (Python / JavaScript), a cloud-function gateway (CloudBase), and an edge-computing gateway (Cloudflare Workers).

| Runtime | Platform | Language | Files | Notes |
|------|------|------|------|------|
| pypi | PyPI | Python | `src/textcli_loader/` + `pyproject.toml` | Zero-dependency pip-installable package loader — any Python environment can directly load and execute instruction packages |
| npm | npm | JavaScript | `textcli-core/` + `package.json` | Zero-dependency npm-installable runtime — Node.js environments directly load and execute instruction packages, isomorphic to the Python loader |
| cloudbase | CloudBase SCF | Node.js | `config.js` + `index.js` + `package.json` | Tencent Cloud serverless function — gateway routing + instruction dispatch |
| cloudflare | Cloudflare Workers | JavaScript | `workers/gateway.js` | Edge-computing gateway — loads packages from KV Store, protocol parsing + route dispatch + envelope wrapping |

## Differences from service

| Dimension | service (standard runtime) | pypi (pip package) | npm (npm package) | cloudbase (cloud function) | cloudflare (edge gateway) |
|------|------|------|------|------|------|
| Deployment | `text-cli;install` / `co-install` | `pip install textcli-loader` | `npm install textcli-core` | Cloud-function console / CLI deploy | Workers CLI / Dashboard deploy |
| handler registration | `handler_inits` + `@directive` | `@directive` decorator (dynamic import) | `register()` function | Gateway route table (`domain → cloud-function name`) | Metadata schema (handler is null, delegated to backend execution) |
| Dependency management | `requires.pip` / `requires.npm` auto-installed | handler.py's own imports (installed by user) | handler.js's own require (installed by user) | Cloud-function `package.json` / platform-layer managed | KV Store / platform-layer managed |
| Discovery | `text-cli;query` aggregation | `get_registered()` API | `get_registered()` API | Gateway `get_schema` protocol endpoint | Same as textcli-core `get_registered()` |
| Port | `0.0.0.0:28050` | None — pure function call | None — pure function call | None — auto-assigned by cloud platform | None — auto-assigned by edge node |
| Protocol | HTTP POST `/text-cli/cli` | Python function call | JavaScript function call | SDK call + HTTP dual mode | HTTP POST + Workers fetch |
| Skeleton build | A2→A9 accumulation chain | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) |

## pypi (pypi/)

A pure local pip package that does not depend on any text-cli service. Any AI Agent in a Python environment can `pip install textcli-loader` and then directly load instruction packages.

```python
from textcli_loader import load_package, execute

load_package("./my-date-calc/")
result = execute("AI:date-calc;add-days,2026-01-01,30")
```

### Files

| File | Notes |
|------|------|
| `src/textcli_loader/parser.py` | Instruction parser (isomorphic to service core/parser.py) |
| `src/textcli_loader/registry.py` | `@directive` decorator registry |
| `src/textcli_loader/loader.py` | schema.json + handler.py dynamic loading (compatible with both `from core.registry` and `from textcli_loader.registry`) |
| `src/textcli_loader/envelope.py` | Unified envelope format (compatible with text-cli service) |
| `pyproject.toml` | pip package config (src-layout) |
| `tests/test_smoke.py` | Smoke test |
| `README.md` | Usage docs |

## npm (npm/)

A pure local npm package with zero external dependencies. Any AI Agent in a Node.js environment can `npm install textcli-core` and then directly load and execute instruction packages. It is **isomorphic** to the Python textcli-loader — the API and behavior of parser, registry, and envelope are exactly the same, only the language differs.

```javascript
const { parse } = require("textcli-core/parser");
const { register, dispatch } = require("textcli-core/registry");
const { ok, err } = require("textcli-core/envelope");

// Register handler
register("date-calc", "add-days", (params) => {
  const date = new Date(params[0]);
  date.setDate(date.getDate() + parseInt(params[1]));
  return { result: date.toISOString().split("T")[0] };
});

// Load instruction package from file
const { loadPackage } = require("textcli-core/loader.node");
loadPackage("./my-package/");
```

### Files

| File | Notes |
|------|------|
| `parser.js` | Instruction parser — supports `AI:`/`指令:` dual prefixes, bracket-depth tracking, escape sequences, commas inside quoted strings not split |
| `registry.js` | `register()` + `dispatch()` + `unregister()` + `getRegistered()` — supports alias resolution, sync/async handler |
| `envelope.js` | `ok()` + `err()` — `pray_rst_types` promotion, error-code whitelist validation (six closed-set codes) |
| `alias.js` | Alias mapping — `addAlias()` + `resolve()`, case-insensitive |
| `loader.js` | Core loading interface — does not depend on IO; the platform adapter is responsible for reading files, loader only does registration |
| `loader.node.js` | Node.js platform adapter — `fs` + `require` load `schema.json` + `handler.js` from disk |
| `index.js` | Unified entry point |
| `package.json` | npm package config — zero external dependencies |

## Cloudflare (cloudflare/)

Cloudflare Workers edge-computing gateway. It only uses the pure-logic modules of textcli-core (parser, envelope, alias, registry), replacing file IO with the Workers KV Store.

### Architecture

```
Cloudflare Workers (edge node)
  │
  ├── POST /text-cli/cli → gateway.js
  │     ├── Parse prompt → domain;action,params
  │     ├── Load package from KV Store (schema.json)
  │     ├── Register handler (metadata schema — handler is null)
  │     ├── dispatch → delegate to backend Node.js runtime for execution on match
  │     └── Wrap envelope (ok / err)
  │
  └── GET /health → {status: "ok", service: "text-cli-cloudflare-gateway"}
```

The gateway is a pure gateway — it does not execute, only does protocol parsing + routing + envelope wrapping. This is consistent with the pure-pipe principle of an endpoint, but an endpoint is HTTP-layer forwarding while a gateway is protocol-layer dispatch.

### Files

| File | Notes |
|------|------|
| `workers/gateway.js` | Workers entry — protocol parsing + KV package loading + route dispatch + envelope wrapping |

## CloudBase (cloudbase/)

### Architecture

```
Gateway (CloudBase HTTP trigger)
  │
  ├── POST /cli → index.js exports.main
  │     ├── Parse prompt → domain;action,params
  │     ├── Look up route table → routeTable[domain] → cloud-function name
  │     └── cloud.callFunction(name, {prompt, _routerEvent})
  │           └── Instruction cloud function → handler(params) → return envelope
  │
  ├── GET /health → {status: "ok", service: "text-cli-router"}
  ├── GET /skills → {}
  └── SDK call → action=get_schema → return schema.json
```

### Files

| File | Notes |
|------|------|
| `config.js` | Route table (`routeTable`) and package registry (`packages`) |
| `index.js` | Cloud-function entry — dual-mode (SDK + HTTP) routing + `text-cli;query` aggregation |
| `package.json` | Dependency declaration (`wx-server-sdk`) |

### Adding new instructions

1. Deploy the instruction cloud function (one independent cloud function per `domain`)
2. Register the `domain → function name` mapping in `routeTable` of `config.js`
3. Register the package id in the `packages` array of `config.js` (used for `text-cli;query` aggregation)

No skeleton changes are needed when adding a new package — only the gateway-side config changes.

## Extension plan

The following cloud-function runtimes have reserved extension entries and can be appended on demand:

| Platform | Status | Notes |
|------|:--:|------|
| PyPI (textcli-loader) | ✅ Published | pip package runtime — `pip install textcli-loader` |
| npm (textcli-core) | ✅ Implemented | npm package runtime — `npm install textcli-core`, isomorphic to Python loader |
| CloudBase SCF | ✅ Implemented | Tencent Cloud cloud-function runtime |
| Cloudflare Workers | ✅ Implemented | Edge-computing gateway — loads packages from KV Store, protocol parsing + route dispatch |
| AWS Lambda | ⏳ Reserved | Structure follows the CloudBase pattern |
| Alibaba Cloud Function Compute | ⏳ Reserved | Structure follows the CloudBase pattern |

When a new platform is added, create an independent subdirectory under `bypass-service/` (named in lowercase English) containing that platform's specific entry files and config. All bypass runtimes interoperate through the unified `AI:domain;action,params` protocol.

---

## Build

bypass-service is synced via the pass-through mode of `build-all.py`: `src/skeleton/bypass-service/` → `deploy/bypass-service/`. It does not participate in the A2→A9 accumulation chain and does not share the `SKELETON_SUBDIRS` whitelist. All files are copied as-is.

```bash
# Build the bypass service alone
python scripts/build-all.py BYPASS
```

# bypass-service group

## Positioning

The skeleton layer under the bypass-service group is bound to the **bypass runtime** — non-Python runtimes that do not participate in the A2→A9 skeleton accumulation chain. They are hosted by independent cloud-platform gateways / a generic JS logic layer / dsh, and synced to `deploy/bypass-service/` via the pass-through mode of `build-all.py`.

Relationship to the service group: **parallel, non-accumulating, non-inheriting**. The bypass runtime and the standard runtime interoperate through the unified `AI:domain;action,params` protocol.

## Directory structure

```
bypass-service/
├── pypi/                # Local pip package loader (textcli-loader, Python)
├── npm/                 # Local npm thin core (textcli-core, JavaScript)
├── tc-js-skeleton/      # Generic JS logic-layer source of truth (12 textcli-core-* component family, onion layering)
├── cloudbase/           # Tencent Cloud SCF cloud-function gateway
├── cloudflare/          # Cloudflare Workers edge gateway (D1 multi-function edition)
├── dsh/
│   ├── dsh-tc-runtime/  # dsh as a tc runtime (Cordis plugin set, 15 runtime-* packages)
│   └── dsh-tc-bridge/   # Capability-seam plugin for dsh consuming the tc directive ecosystem (five closed-set tools)
└── docs/                # This INDEX
```

## Current runtimes

The bypass runtime covers five forms: local package loader (Python / JavaScript), cloud-function gateway (CloudBase), edge-computing gateway (Cloudflare Workers D1), generic JS logic layer (tc-js-skeleton), and dsh hosting (dsh-tc-runtime / dsh-tc-bridge).

| Runtime | Platform | Language | Files | Notes |
|------|------|------|------|------|
| pypi | PyPI | Python | `src/textcli_loader/` + `pyproject.toml` | Zero-dependency pip-installable package loader — any Python environment can directly load and execute instruction packages |
| npm | npm | JavaScript | `textcli-core/` + `package.json` | Zero-dependency npm-installable thin core — Node.js environments directly load and execute instruction packages, isomorphic to the Python loader |
| tc-js-skeleton | Generic JS | JavaScript | `packages/` 12 components | Bypass generic JS logic-layer source of truth (thin core + compose/guard/contract and other onion-layered components) |
| cloudbase | CloudBase SCF | Node.js | `config.js` + `index.js` + `package.json` | Tencent Cloud serverless function — gateway routing + instruction dispatch |
| cloudflare | Cloudflare Workers | JavaScript | `workers/src/` 11 modules + `schema.sql` | Edge-computing gateway (D1 multi-function edition) — executable packages in D1 + restricted execution + single Service-token closed loop |
| dsh-tc-runtime | dsh (Cordis) | TypeScript | `dsh/dsh-tc-runtime/` 15 runtime-* packages | dsh as a tc runtime — full 9-mechanism capability set, a Cordis plugin set external to dsh |

## Differences from service

| Dimension | service (standard runtime) | pypi (pip package) | npm (npm package) | cloudbase (cloud function) | cloudflare (D1 multi-function gateway) | dsh-tc-runtime (dsh Cordis) |
|------|------|------|------|------|------|------|
| Deployment | `text-cli;install` / `co-install` | `pip install textcli-loader` | `npm install textcli-core` | Cloud-function console / CLI deploy | Workers CLI / Dashboard deploy + `schema.sql` D1 init | Cordis plugin assembly (external to dsh, 15 runtime-* packages) |
| handler registration | `handler_inits` + `@directive` | `@directive` decorator (dynamic import) | `register()` function | Gateway route table (`domain → cloud-function name`) | Executable packages in D1, restricted execution by executor + metadata registration | runtime-mapper directive mapping (tc directive ↔ ctx.tools) |
| Dependency management | `requires.pip` / `requires.npm` auto-installed | handler.py's own imports (installed by user) | handler.js's own require (installed by user) | Cloud-function `package.json` / platform-layer managed | D1 / platform-layer managed | pnpm workspace (each runtime-* package manages its own deps) |
| Discovery | `text-cli;query` aggregation | `get_registered()` API | `get_registered()` API | Gateway `get_schema` protocol endpoint | Same as textcli-core `get_registered()` | runtime-meta `text-cli;query` meta directive |
| Port | `0.0.0.0:28050` | None — pure function call | None — pure function call | None — auto-assigned by cloud platform | None — auto-assigned by edge node | Inbound HTTP (runtime-inbound, `POST /text-cli/cli`) |
| Protocol | HTTP POST `/text-cli/cli` | Python function call | JavaScript function call | SDK call + HTTP dual mode | HTTP POST + Workers fetch | HTTP POST + dsh ecosystem (three-field closed-set envelope) |
| Skeleton build | A2→A9 accumulation chain | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) | `build-all.py` pass-through mode (BYPASS) |

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

Cloudflare Workers **D1 multi-function edition** edge gateway. **It is not a port of tc-js-skeleton, nor a second implementation** — it is the Cloudflare installation of "sharing one set of logic components (textcli-core + contract) + three platform adapters". Executable packages are stored in **D1** (not KV), with restricted execution + a single Service-token closed loop.

### Architecture

```
Cloudflare Workers (D1 multi-function edition)
  │
  ├── POST /text-cli/cli → src/index.js
  │     ├── Auth (src/token.js single Service-token closed loop)
  │     ├── Parse prompt → domain;action,params (src/endpoints.js + src/runtime.js)
  │     ├── D1 load executable package + metadata (src/d1-storage.js + src/meta.js)
  │     ├── Restricted execution (src/executor.js graded sandbox) or mesh forward (src/mesh.js)
  │     ├── Key-as-directive credentials (src/key.js, AES-GCM)
  │     ├── Async task 5-state + restart reconciliation (src/tasks.js)
  │     └── Per-caller counting / quota degradation (src/usage.js)
  │
  ├── GET /text-cli/health | /schema | /tasks/{id} | /packets/... (endpoint surface)
  └── Init: schema.sql (create D1 tables)
```

The protocol is identical to text-cli / dsh-tc-runtime: reuses the `textcli-core` envelope + the `contract` 6-code closed set, async task 5-state, quota `status:"stop"` degradation, mesh loop-guard routing.

### Files

| File | Notes |
|------|------|
| `workers/src/index.js` | Worker entry (`export default { fetch }`) |
| `workers/src/endpoints.js` | Endpoint surface — HTTP status codes + three-field envelope error construction |
| `workers/src/runtime.js` | Runtime assembly — directive registration + run |
| `workers/src/d1-storage.js` | D1 → StorageKV adapter |
| `workers/src/executor.js` | Restricted execution (graded sandbox) |
| `workers/src/meta.js` | Package lifecycle (install/uninstall/query) |
| `workers/src/token.js` | Service-token closed loop |
| `workers/src/key.js` | Key-as-directive credentials (AES-GCM) |
| `workers/src/usage.js` | Per-caller counting (quota degradation) |
| `workers/src/tasks.js` | Async task 5-state + restart reconciliation |
| `workers/src/mesh.js` | Mesh proxy (peer/route, loop guard) |
| `workers/schema.sql` | D1 table creation script |
| `workers/package.json` | Worker dependency declaration |
| `workers/docs/` | design_en.md + README.md + user-manual_en.md |

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

## tc-js-skeleton (tc-js-skeleton/)

The bypass **generic JS logic-layer source of truth** — an onion-layered component family around the `textcli-core` thin core (12 packages), platform-agnostic, reused by cloudflare / dsh / other JS hosts.

```
Skeleton/facade: compose                       ← assembly + package lifecycle (install/uninstall + JSON index) + multi-package consumption
Interaction (outermost): mesh / approval / credentials  ← binds external capability, deps injected
Guardrail layer: quota / audit                 ← intercept/record before dispatch
Orchestration layer: path / aggregate / contract ← declaration-layer logic, built-in path:/agg: loop check
Core guard (innermost): guard                  ← native loop detection
Core (thin, invariant): textcli-core           ← parser/envelope/alias/registry/loader
```

| Component | Source | Notes |
|------|------|------|
| `textcli-core` | Thin core | parser/envelope/alias/registry/loader, moved in as-is |
| `textcli-core-compose` | Built-in | Assembly + package lifecycle + multi-package consumption (lazy loading) |
| `textcli-core-contract` | runtime-contract | Canonical envelope + 6-code closed set, pure functions with zero deps |
| `textcli-core-guard` | runtime-sandbox | Loop detection (shared ancestorChain) |
| `textcli-core-path` | runtime-path | Declaration-layer path engine (instruction template form) |
| `textcli-core-aggregate` | runtime-aggregate | Aggregation + try-in-order degradation |
| `textcli-core-quota` / `audit` | runtime-* | Quota guardrail / audit channel |
| `textcli-core-storage` | Built-in | Storage substrate (memory / file / D1) |
| `textcli-core-auth` / `approval` / `credentials` / `mesh` | runtime-* | Auth / human gate / credentials / mesh forwarding |

> Explicitly not abstracted (kept as master copies): runtime-mapper / the runtime-meta assembly surface / runtime-host / runtime-bridge.
> Tests 91/91 — serves as the bypass generic JS logic-layer source of truth.

## dsh (dsh/)

The bypass runtime hosted by the dsh ecosystem, in two plugins:

### dsh-tc-runtime (dsh/dsh-tc-runtime/)

**dsh as a tc runtime (JS edition)** — a Cordis plugin set external to dsh (15 `runtime-*` packages) that bridges text-cli / tc directive capability into dsh, providing a bypass runtime form (full 9-mechanism capability set; does not claim standard-runtime identity).

```
runtime-inbound      Inbound HTTP (six-segment pipeline + reserved-domain interception)
runtime-mapper       Directive mapping (tc directive ↔ ctx.tools)
runtime-sandbox      Sandbox execution host (restricted subprocess + layered policy guardrails)
runtime-credentials  Per-package credential isolation
runtime-audit        Audit channel (append-only JSONL)
runtime-meta         text-cli;* meta directives (install/query/path/...)
runtime-quota        dsh-quota (period window + atomic check+consume)
runtime-approval     Approval answerer (HMAC + fail-closed)
runtime-host         Host directives
runtime-path         path engine (declaration-layer interpreter + workflow compilation)
runtime-aggregate    Async task bridging (5-state) + aggregate degradation
runtime-mesh         mesh forwarding (route table / loop guard / backoff)
runtime-bridge       Protocol bridge (mcp-client → mcp__<server>__<tool>)
runtime-pro          Facade registry (short name → path/aggregate)
runtime-contract     Global acceptance (canonical envelope + 16-line mapping contract)
```

Red lines (7): no intrusion into the dsh core; credential plaintext never enters the JS execution environment; sandbox denies by default; protocol closed set; reserved-domain meta directive interception; approval ownership filtering; tc audit kept as independent JSONL.

### dsh-tc-bridge (dsh/dsh-tc-bridge/)

**The capability-seam plugin through which dsh consumes the tc directive ecosystem** — unifies the tc directive ecosystem (remote tc endpoints + the local textcli-core JS engine) with dsh's own / mcp tools onto a single scheduling plane, exposing five closed-set tools to the dsh agent so the LLM consumes tc capability through the `AI:<domain>;<action>,<params>` primitive.

| Tool | Purpose |
|------|------|
| `call_tc` | Call a tc directive (bridge mode goes remote / hybrid mode short-circuits tc__ tools) |
| `wait_tc` | Async long-task polling (exponential backoff) |
| `run_tc_js` | In-process zero-network execution of local textcli-core JS packages |
| `tool_avatar` | Same-process proxy for dsh's own tools (including mcp tools), saves tokens |
| `find_tc` | Unified capability discovery surface inside the bridge (whitelist + prefix mapping) |

Three operating forms: bridge mode (dsh has no tc runtime) / service mode (dsh acts only as a tc runtime) / hybrid mode (dsh is both agent and runtime).

## Extension plan

The following runtimes are either landed or have reserved extension entries:

| Platform | Status | Notes |
|------|:--:|------|
| PyPI (textcli-loader) | ✅ Published | pip package runtime — `pip install textcli-loader` |
| npm (textcli-core) | ✅ Implemented | npm thin-core runtime — isomorphic to the Python loader |
| tc-js-skeleton | ✅ Implemented | Generic JS logic-layer source of truth (12 components, onion layering) |
| CloudBase SCF | ✅ Implemented | Tencent Cloud cloud-function runtime |
| Cloudflare Workers (D1) | ✅ Implemented | Edge gateway D1 multi-function edition — executable packages in D1 + restricted execution + single Service-token closed loop |
| dsh-tc-runtime | ✅ Implemented | dsh as a tc runtime (Cordis plugin set, 15 runtime-* packages) |
| dsh-tc-bridge | ✅ Implemented | Capability-seam plugin for dsh consuming the tc directive ecosystem (five closed-set tools) |
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

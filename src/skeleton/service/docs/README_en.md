# service Group

## Positioning

The skeleton layers under the service group bind to the **service runtime (:28050)** — it is the platform management core of text-cli. From A3's basic install/uninstall up to A9's full aggregation degradation, service is the backbone of the skeleton accumulation chain.

> A5 (integration endpoint, :29050) is an **independent horizontal layer**, not part of this group's accumulation chain. It is hosted under `src/skeleton/endpoint/`; see its group document for details. This group covers A3→A9.

## Accumulation Chain

```
A3-service (base platform)
  → A4-paths (path orchestration)
    → A6-sql (SQLite persistence — the "from toy to tool" line)
      → A7-mcp (MCP bidirectional bridge)
        → A8-discovery (instruction discovery & aggregation entry)
          → A9-advanced (advanced instructions — accumulation terminus)
```

Each layer adds new capabilities on top of the previous one. Later layers override same-named files from earlier layers, and `build-all.py` guarantees the accumulation is correct. The A5 endpoint and the bypass runtimes (CloudBase/PyPI/npm/Cloudflare) do not participate in the accumulation chain — they are distributed horizontally and independently.

---

## A3 — Service Platform Management Core

A standard instruction service callable by the agent-copilot proxy. **9 categories** of skeleton handlers (path under the A4 subdir, pro under the A9 subdir, the rest under A3) + a package-install mechanism + multi-runtime support (python / node / mcp / cmd / path / aggregate).

### Skeleton Handlers

| File | Layer | Directive | Description |
|------|-------|-----------|-------------|
| `text_cli_path.py` | A4 | `text-cli;path` | Full path engine (upgraded to the full engine version in A4) |
| `text_cli_pro.py` | **A9** | `text-cli;pro` | Facade abstraction (entry point for the two target types: path / aggregate) |
| `text_cli_install.py` | A3 | `text-cli;install` `文本指令;安装` | Package install (pip/npm deps + file deployment + manifest registration) |
| `text_cli_export.py` | A3 | `text-cli;export` `文本指令;导出` | Package export |
| `text_cli_uninstall.py` | A3 | `text-cli;uninstall` `文本指令;卸载` | Package uninstall (incl. DROP TABLE) |
| `text_cli_nocode.py` | A3 | `text-cli;nocode` | Automatic conversion of Markdown experience documents |
| `package_manifest.py` | A3 | — | Manifest persistence |
| `schema_query.py` | A3 | `text-cli;query` | Schema query |
| `proxy.py` | A3 | — | Proxy routing (incl. `sensitive` desensitization; federated mesh forwarding logic lives in A9) |
| `js_bridge.py` | A3 | — | Node.js runtime bridge |

### Package Categories

The following capabilities are provided by instruction packages, installed into the `packages/` directory:

| Category | Packages (examples) |
|----------|---------------------|
| AI | ai-generate, ai-inference, ai-im |
| Map | bd-map, gd-map, tx-map, tdt-map |
| Coordinate | geo-coords, geo-grid, geo-panoramic |
| Media | image, ms-tts, tc-browser |
| Tools | tc-json, tc-markdown, path-str, sample, template |
| Platform | key, quota-manage, task-manager |
| Cloud services | bd-cloud, tx-cloud |
| Bridge | mcp, skill-endpoint, stream-im |

Install: `AI:text-cli;install,<package-name>`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TEXT_CLI_HOME` | `~/text-cli` | Project root directory |
| `TEXT_CLI_MODULES_DIR` | `$TEXT_CLI_HOME/text_cli_modules` | Infrastructure module path |
| `PORT` | `28050` | Service port |

---

## A4 — Paths Instruction Paths

### What is a Path

| Question | Answer |
|----------|--------|
| What is a path | Orchestrating atomic instructions into a declarative, fault-tolerant execution pipeline |
| What does a path solve | "Doing one thing takes multiple steps — which first, which after, and what if it fails" |
| What does an instruction answer | "How to perform this one specific operation" |
| Boundary | The path orchestrates *what* to do; the instruction implements *how* |
| Complexity ceiling | The depth of instantaneous reasoning — two degradation steps is the depth limit |

A path is not a Turing-complete programming language. It is an ordered, readable, debuggable recipe — both humans and AI can read, generate, and execute it.

### Pre-A4 → Post-A4

```
Pre-A4                          Post-A4
──────────────────────────────────────────
path = JSON declaration         path = engine-executed
AI reads JSON to understand     engine parses if/degradation/timeout
orchestration burden on AI      orchestration burden shifted to engine
"I geocode then offset"         "geocode fails → degrade → timeout → circuit break"
```

The two eras coexist. A path without `if` can still be executed by AI through its native comprehension. A path with `if` lets the engine take over fault-tolerant orchestration. Post-A4 is a superset of Pre-A4.

### Capability Overview

| Layer | Capability | Syntax |
|:--:|-----------|--------|
| L0 | Circuit-break protection | Built into the engine |
| — | timeout guard | `"timeout": <ms>` |
| L1 | Conditional branch | `"if": {...}` + equals/contains/matches/exists |
| — | Degradation fallback | `"degradation": [...]` |
| L2 | Parallel execution | `"mode": "parallel"` + first_ok/all |
| L2 | Function expression | count/size/exists + eq/gt/lt/gte/lte/ne |
| L2 | Loop iteration | `"map": {...}`, `MAP_HARD_CAP=1000`, nesting depth ≤ 2 to prevent runaway |
| L2 | Cross-node dispatch | HTTP `http_dispatch` calling a remote runtime |
| — | Unified step dispatcher | All steps routed uniformly via `_dispatch_step` (local / aggregate / http) |

### Quick Start

```
AI:text-cli;path,examples/paths/geo_panoramic_query.json,威海
```

Conditional branch example:

```json
{
  "id": "visual",
  "directive": "geo-panoramic;china,{coord.0},{coord.1}",
  "output_as": "panorama",
  "if": {"step": "road", "field": "status", "equals": "ok"},
  "degradation": [
    {"id": "fallback", "directive": "bd-map;static-map,{lon},{lat},16"}
  ]
}
```

---

## A6 — SQL Data Persistence Layer

The line between a personal toy and a small-business tool. SQLite provides persistence for key management, quota tracking, and async tasks.

### quota-manage: amount extension

`quota;check,<target>[,<amount>]` — amount defaults to 1 (per call); a specific value enables usage-dimension quotas:

```
quota;check,tx-cloud-translation,128  # consume 128 characters (translation quota 5M chars/month)
quota;check,tx-cloud-asr              # consume 1 call
```

`cycle_limit` carries the unit — limit=5000000 means characters for translation, limit=1000 means calls for ASR. The SQLite layer does not change schema; the semantics of `usage_count` are assigned by the caller.

### task-manager: tracked mode

| Mode | Execution ownership | Query behavior | Fits |
|------|---------------------|----------------|------|
| managed | owned by task-manager | query local state | bim-ifc local process |
| tracked | owned by external service | real-time dispatch instruction to query upstream | tx-cloud ASR, MCP async |

User calls `task;status,<id>` → task-manager sees mode=tracked → dispatches the corresponding instruction in real time to query upstream. No background polling — the external service is only queried when the user explicitly asks.

### Token Identity Management

A6 skeleton adds two tables. The request-entry middleware extracts the **last 6 characters** of the Service-token (when token length ≥ 15) → looks up `token_registry` for admission → injects `identity_code`.

> Caliber note: the service monolith uses the **last 6 characters** as the identity code; the integration endpoint (A5, :29050) uses the **first 8 characters** as the control-plane recognition prefix. The two have different scopes and do not conflict.

**`token_registry`** — token admission control:

| Field | Type | Description |
|-------|------|-------------|
| token | TEXT PK | Identity code (last 6 chars of token) |
| enabled | INTEGER | 0=revoked |
| quota_limit | INTEGER | -1=unlimited |
| used_count | INTEGER | Used count |
| expires_at | DATETIME | NULL=never expires |

**`token_call_logs`** — call audit log (token + domain + action + status + duration_ms).

**App self-built tables**: each package declares `tables` in `schema.json`; CREATE TABLE runs automatically on install, DROP TABLE on uninstall. Supports `requires.service_db` to declare skeleton-table dependencies.

### Instance-level Config

| Config | Default | Controls |
|--------|---------|----------|
| `A3_ALLOW_ANONYMOUS` | `true` | Whether token-less requests are allowed |
| `A3_COUNT_CALLS` | `false` | `true`=write log + deduct quota |

---

## A7 — MCP Bidirectional Bridge

Configuration-driven exposure, thousands of tools. One mapping, and all tools of an MCP server are automatically compiled into text-cli instructions:

```
MCP server  ←→  text-cli instruction
    tool        =      instruction
  server      →    handler
```

The caller uses the same `AI:domain;action,params` protocol, unaware of the underlying transport difference (MCP, native handler, and Skill Bridge are peers).

`MCPservice/` is an independent reverse-proxy MCP sub-service, running on par with copilot/service, listening on `:9020` (SSE) by default. It is launched by the `lifespan` daemon hook in main.py; when A3 is deployed standalone without MCP enabled, it is skipped automatically.

---

## A8 — Instruction Discovery & Aggregation Entry

Not just "what instructions can be found", but "converge multiple sources through one entry".

### Aggregation Dispatch Pipeline

```
request → aggregation dispatch → MCP-priority routing → local dispatch → MCP fallback → proxy
```

On aggregation hit → traverse the default degradation chain → call dispatch() on each provider → return the first successful result.

### aggregate Routing Table

Pure routing table, no execution logic. JSON declares the aggregate domain and degradation chain:

```json
{
  "id": "map", "type": "aggregate", "domain": "map",
  "default": ["tx-map", "tencent-maps", "gd-map", "bd-map"],
  "providers": {
    "tx-map": {"geocode": "tx-map;geocode"},
    "tencent-maps": {"geocode": "tencent-maps;geocode"}
  }
}
```

### Service Manifest Whitelist

`config/service_manifest.json` controls external exposure. The `/skill` endpoint only exposes instructions on the whitelist. When populated, only the listed entries are exposed — external callers see only the aggregation entry, not the atomic providers.

---

## A9 — Advanced Instructions & Skill-as-a-Service

The final layer of progressive deployment. Facade abstraction — the caller need not know how many providers sit behind it or whether MCP or a native handler is used — one entry converges all.

### Degradation Chain

The `default` list defines the degradation order. Each provider is tried in sequence; on success it returns immediately, on failure it automatically switches to the next:

```
map;geocode,威海
  → tx-map;geocode     → quota exhausted → skip
  → tencent-maps;geocode → MCP unavailable → skip
  → gd-map;geocode     → ok → return result
```

**Failure is only returned after all three conditions are exhausted** — guaranteeing maximum availability:

1. dispatch returns `{"status":"stop"}` (quota exhausted)
2. dispatch throws an exception or returns an error
3. instruction not registered (that provider does not support this action)

### Multi-source Unification

Aggregation does not distinguish source type. `tx-map` is a native handler, `tencent-maps` is an MCP bridge, `skill-bdmap` is a Skill Bridge — all three are peers in the degradation chain. Adding a new provider only requires one line in the aggregate JSON, without affecting any existing caller.

### Cognitive Burden Reduction

```
Before: Agent needs to know the three domains and parameter formats of tx-map/gd-map/bd-map
After:  Agent only needs to remember the single entry map;geocode
```

---

## Build

The skeleton layers under the service group participate in the standard accumulation chain of `build-all.py`. Later layers' true sources override same-named files from earlier layers.

---

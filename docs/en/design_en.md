# text-cli Design Document

> **Document type**: Technical design | **Related**: [SPEC_en.md](SPEC_en.md) | **Revision**: 2026-08-29
> **Language note:** This English text is a translation of the normative Chinese design document (`docs/design_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.
> **Scope**: text-cli full project
>
> This document describes the engineering mechanisms of text-cli. §One–§Three describe the general design of the protocol and runtime system; §Four expands implementation details using the Python standard runtime as the main line.
> The protocol's normative definitions (directive format, response envelope, error codes, etc.) are specified in SPEC_zh.md.

---

## One. Protocol Mechanisms

text-cli dispatches all backend capabilities with a single line of text. Unified protocol format:

```
AI:domain;action,param1,param2,...
```

**Parameter splitting**: Parameters are separated by commas, in fixed order. The trailing parameter may be free text (including commas). JSON arrays/objects within parameters may contain commas — when parsing, track bracket depth `{}` `[]` and string quotes, splitting only at commas where depth is 0.

**Routing rule**: The `domain;action` combination is matched exactly against a handler. On a miss, go through the alias map (e.g. Chinese→English canonical), then retry the match. Still missing → return `ERR_NOT_FOUND`.

**Dispatch pipeline**: Directive dispatch follows a fixed priority — the aggregate entry is matched first; on a miss, local native/MCP explicit preference; on a local miss, MCP fallback; finally proxy forwarding as the last resort. All misses → `ERR_NOT_FOUND`.

### 1.1 Response Envelope

```json
{
  "rst_types": "text",
  "rst_data": {"status": "ok", "result": 14},
  "rst_err": ""
}
```

| Field | Description |
|------|------|
| `rst_types` | Reflects the response type. Default `"text"`. When a handler's returned dict contains the `pray_rst_types` key, the skeleton promotes its value to this field. Values: `text` / `picture` / `video` / `audio` / `file` |
| `rst_data` | The JSON object returned by the handler, carried directly by the skeleton — no longer nested as `{"text": "..."}`. The caller reads `rst_data` directly |
| `rst_err` | Empty string = success; otherwise an error code |

### 1.2 Error Codes

| Error code | Meaning |
|--------|------|
| `ERR_NOT_FOUND` | domain;action does not exist |
| `ERR_EXECUTION` | handler execution exception |
| `ERR_ROUTING` | routing failure (proxy destination unreachable, etc.) |
| `INVALID_PARAMS` | invalid parameters |
| `ACCESS_DENIED` | Access Token invalid |
| `SERVICE_DENIED` | Service Token invalid or quota exhausted |

Long-running tasks (video conversion, ASR, etc.) do not return results immediately — the handler is registered as async mode and returns a `task_id`. The caller polls progress via `GET /text-cli/tasks/{task_id}`.

---

## Two. Runtime System

### 2.1 Runtime Classification

text-cli positions runtimes on **the same gradient** by capability coverage (SPEC §6.1) — the three (minimal-compliant / bypass / standard) are positions, not ranks:

- **Standard runtime**: Fully implements all mechanisms required by the protocol. The standard runtime is a capability definition, not tied to any specific language — any implementation that fully carries the protocol mechanism set is a standard runtime. The current standard runtime is based on Python (see §Four).
- **Bypass runtime**: Implements **any mechanism subset** above the mandatory baseline — **including the full set**; the full set is not required. By form: multi-language SDKs (textcli-loader / textcli-core), zero-code single file (base_nocode), cloud platforms (CloudBase SCF / Cloudflare Workers), and plugin host (dsh-tc-runtime). Constraint examples: textcli-loader (PyPI) and textcli-core (npm) do not support federation Mesh and path orchestration.

> **Identity is self-declared by the implementer; the project does not adjudicate**: `dsh-tc-runtime` covers the full 9-mechanism set but self-describes as a bypass form — coverage does not imply identity. Callers are unaffected: the one-dimensional contract guarantees runtime identity is invisible to the caller.

### 2.2 Standard Runtime Required Mechanisms

The standard runtime must fully implement the following 9 protocol mechanisms (closed set):

| Mechanism | Description |
|------|------|
| Directive execution | Parse, route, execute, and encapsulate the response for directives conforming to the protocol |
| Install/uninstall directive packages | Package lifecycle management: register directives and dependencies on install, fully reclaim on uninstall |
| Directive auth & discovery | Auth (dual-layer token / quota protection) and discovery (schema-based directive query) |
| Path orchestration | Orchestration and interpolated execution of directive sequences |
| Async task scheduling (state persistence) | Task-based scheduling and query of async directives |
| Aggregation & degradation chain | Domain-level aggregate entry and provider degradation |
| Federation Mesh | Per-peer credential injection and forwarding under multi-node federation topology |
| Protocol bridge | Bidirectional bridging with other protocol ecosystems (MCP is one implementation) |
| Facade abstraction | Mapping from short name to execution target; facade directives are equal-weight with atomic directives |

The protocol only specifies the mechanism set itself, not the implementation approach of each mechanism.

### 2.3 Current Runtime Forms

| Form | Type | Deployment | Description |
|------|------|------|------|
| Python standard runtime | Standard | Self-hosted | Full 9 mechanisms (see §Four) |
| textcli-loader | Bypass | In-process (`pip install`) | PyPI SDK, lightweight consumer (see §Five) |
| textcli-core | Bypass | In-process (`npm install`) | npm SDK, JavaScript isomorphic implementation (see §Five) |
| base_nocode | Bypass | Local single-file service | Pure-stdlib script, zero-code form (see §Five) |
| CloudBase SCF | Bypass | Self-deployed cloud function | Tencent Cloud cloud function, Node.js (see §Five) |
| Cloudflare Workers | Bypass | Self-deployed edge node | D1 multi-function edge runtime — restricted execution (see §Five) |
| dsh-tc-runtime | Bypass | Cordis plugin assembly | 15 `runtime-*` packages, covers full 9-mechanism set (see §Five) |
| tc-js-skeleton | — | Not a runtime form | Generic JS logic-layer source of truth, reused by cloudflare / dsh (see §Five) |

---

## Three. Consumer Side — From Bare Protocol to Intelligent Scheduling

The consumer side has four layers: bare curl (lowest barrier), protocol consumer SDK (wraps calls), AI skill scheduling layer (multi-endpoint degradation), Agent integration panorama (self-evolving loop).

### 3.1 Bare curl Call

Lowest barrier — just know one endpoint address:

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:tc-math;eval,2+3*4"}'
```

Response:

```json
{"rst_types": "text", "rst_data": {"status":"ok","result":14}, "rst_err": ""}
```

`rst_types` reflects the response type. `rst_data` directly carries the JSON object returned by the handler — the caller reads `rst_data` directly: a `"text"` field = plain text, a `"url"` field = renderable media, neither = metadata.

### 3.2 Protocol Consumer SDK

curl is direct enough, but every call requires assembling the HTTP request, parsing the envelope, and handling errors. The protocol consumer SDK wraps these into a unified API — four language implementations, zero dependencies, usable with a single script.

#### API Abstraction

Core return type `DirectiveResult` (`src/skeleton/base/A0-protocol/python/call.py:73`), encapsulating success/failure/async three states:

```python
from call import call, discover, poll, wait

# Synchronous call — returns immediately
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"result": 14})

# Directive discovery — one HTTP, cached result, zero-cost filter
directives = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]

# Async task — poll or exponential backoff wait
status = poll("abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"50%"})

final = wait("abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})
```

The JavaScript API is equivalent to Python: `call()` / `discover()` / `poll()` / `wait()`, returning `DirectiveResult`.

#### Two-layer Positioning

Source locations:

| Layer | Language | Entry | For |
|:---:|------|------|------|
| SDK | Python | `src/skeleton/base/A0-protocol/python/call.py` (urllib) | AI Agent |
| SDK | JavaScript | `src/skeleton/base/A0-protocol/js/call.js` (fetch) | AI Agent |
| CLI | Shell | `src/skeleton/base/A0-protocol/shell/call.sh` | Human — command-line pipe |
| CLI | PowerShell | `src/skeleton/base/A0-protocol/shell/call.ps1` | Human — command-line pipe |

Shell CLI example:

```bash
echo "AI:tc-math;eval,2+3*4" | ./call.sh
./call.sh --task abc123
```

#### Configuration & Token

Default endpoint `http://127.0.0.1:28050/text-cli/cli`. Configuration priority (see each language's `conf.json`, e.g. `src/skeleton/base/A0-protocol/python/conf.json`):

```
environment variable (TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN)
  > conf.json
  > default value
```

Each call may carry an independent Token:

```python
call("AI:...", endpoint="...", access_token="...", service_token="...")
```

#### Response Parsing

All four implementations uniformly parse the protocol envelope: `rst_data` is used directly (no longer nested via `.text`), read `rst_err` to judge success/failure, detect `status=="pending"` + `task_id` to mark an async task.

---

### 3.3 AI Skill Scheduling Layer

The protocol consumer SDK solves "how to call one endpoint". The AI skill scheduling layer solves "how to call multiple endpoints + how to fabricate directives" — it is the multi-endpoint scheduling layer above the SDK, oriented to an Agent's daily operation.

#### Architecture

```
Agent Skill.run()
  → query capability aggregate list (agent-text-cli-schema.json, sorted by rank)
  → look up endpoint registry (agent-endpoints.json, take token)
  → SDK call(endpoint, access_token, service_token)
  → success → format_result()
  → failure → consumer-side degradation: auto try next rank endpoint
  → all exhausted → on_error()
```

The Skill does not directly hold HTTP calls — all network operations go through the SDK. The Skill layer only does endpoint selection, degradation decisions, and result formatting.

#### Dual-file Source of Truth

(`src/skeleton/base/A1-skill/skill/config/`)

| File | Role | Has Token | Maintenance |
|------|------|:---:|------|
| `agent-endpoints.json` | Endpoint registry: URL + token + rank + trust | ✅ | Manually maintained |
| `agent-text-cli-schema.json` | Capability aggregate list: directive → source (by rank), no token | ❌ | Generated by `aggregation.py` sync |

Token is stored in only one place (endpoint registry); the capability list does not duplicate token — the two files each serve their own role, not coupled.

Endpoint registry example:

```json
{
  "endpoints": {
    "home-service": {
      "url": "http://192.168.1.2:28050/text-cli/cli",
      "service_token": "${HOME_SERVICE_TOKEN}",
      "auth": "single",
      "rank": 1,
      "trust": "internal"
    },
    "cloud-endpoint": {
      "url": "https://tide.agentbot.space/text-cli/cli",
      "access_token": "${TIDE_ACCESS_TOKEN}",
      "service_token": "sk-abc123",
      "auth": "dual",
      "rank": 2,
      "trust": "community"
    }
  }
}
```

Token supports `${ENV_VAR}` (environment variable reference) or bare string. `auth: "single"` connects directly to Service (Service Token only); `auth: "dual"` goes via Endpoint (Access + Service Token).

#### Consumer-side Degradation

Different from the §Four server-side aggregate degradation, consumer-side degradation tries endpoints in rank order — not provider switching inside the service, but endpoint-level fault tolerance:

- Return on success
- `ERR_NOT_FOUND` / `ERR_ROUTING` / HTTP unreachable → auto switch to next rank
- Parameter errors and auth failures do not degrade (switching endpoint is meaningless)
- All exhausted → `on_error()` callback

#### Compile Path: Fabricating Directives

(`src/skeleton/base/A1-skill/skill/python/cli.py` — `register()` at :36, `generate_schema()` at :155)

```python
from cli import register, generate_schema

@register(domain="weather", action="query", category="tool", trust="community")
def weather_query(params):
    return {"status": "ok", "result": f"{params[0]}: Sunny, 20C"}

schema = generate_schema("my-weather")
# → {"id":"my-weather","type":"native","runtime":"python","directives":[...]}
```

The compile path is only responsible for directive registration and Schema generation — it does not provide an HTTP runtime.

#### Consume Path: Calling Directives

(`src/skeleton/base/A1-skill/skill/python/skill.py` — `Skill` class at :105, `Skill.run()` at :203, `@skill` decorator at :213)

```python
from skill import Skill, skill

@skill("weather", domain="weather", action="query")
class WeatherSkill(Skill):
    def format_result(self, data):
        return f"[OK] {data['result']}"

    def on_error(self, params, err_code):
        return f"Cannot query {params[0]} weather ({err_code})"

result = WeatherSkill.run("Beijing", "tomorrow")
```

Skill.run() walks the full scheduling chain internally: query capability list → take token → SDK call → degrade → format. The Agent only calls `Skill.run()`, unaware of endpoint topology.

#### Cold-path Sync

Endpoint capability aggregation is not inside the Agent reasoning loop — `aggregation.py` (`src/skeleton/base/A1-skill/skill/python/aggregation.py`) acts as a cold-path tool, executed periodically or on demand:

```python
from aggregation import sync_endpoints

sync_endpoints()  # poll all endpoints → aggregate → write agent-text-cli-schema.json
```

---

### 3.4 AI Agent Integration Panorama

Agents have three complementary paths to integrate with text-cli, covering the full spectrum of users from zero-code to full-code:

| Path | Entry | For | Output |
|------|------|------|------|
| **Compile path** | `@register` → `generate_schema()` | Developer | schema.json + handler.py |
| **Consume path** | `@skill` → `Skill.run()` | Agent runtime | reusable skill |
| **NoCode path** | Structured Markdown → auto parse | Non-developer | nocode directive package |

On top of the three paths, Agents can form a self-evolving loop — extending through text-cli's meta-directive self-management capability:

```
Agent wakes → /health → text-cli;query → lacks translation capability
  → use scaffolding/guide to quickly convert into a directive package
  → text-cli;install,xx-cloud → install directive package, new capability online
  → "check weather → clothing advice" recurs → text-cli;pro → publish as a path
```

Agent's accompanying System Prompt templates (`src/skeleton/base/A1-skill/skill/prompts/` directory): core scheduling protocol (`SKILL.md`, `text-cli-core_zh.md`), sync Skill concept design (`text-cli-sync-skill.md`), aggregate schema example (`agent-text-cli-schema.example.json`) — guiding Agents to correctly use the SDK and Skill layer.

In addition, the skill scheduling layer can be installed as an OpenClaw Skill (entry: `src/skeleton/base/A1-skill/skill/SKILL.md`) — after loading, the Agent automatically learns to use `call()` / `discover()` / `Skill.run()`, no manual route configuration needed.

---

## Four. Python Standard Runtime

> The following describes the concrete implementation of the Python standard runtime. Other runtime forms see §Five.
> All source code is under `src/skeleton/`. `deploy/` is auto-generated by build scripts and should not be manually modified.

### 4.1 Component Topology

The three components have strict responsibility boundaries and security isolation:

```
┌─────────────────────────────────────────────────────┐
│               Python Standard Runtime                 │
│                                                     │
│  ┌──────────┐   ┌──────────┐   ┌──────────────┐    │
│  │ copilot  │   │ service  │   │  endpoint     │    │
│  │ :20260   │   │:28050/9020│   │  :29050       │    │
│  │          │   │          │   │               │    │
│  │ Local terminal │   │ Package mount │   │ Public auth forward │    │
│  │ file/Git  │   │ API/container  │   │ Dual Token     │    │
│  │ shell    │   │ orchestrate/aggregate │   │ transparent proxy │    │
│  └──────────┘   └──────────┘   └──────────────┘    │
│  127.0.0.1       0.0.0.0             public          │
└─────────────────────────────────────────────────────┘
```

| Component | Listen | Capability | Security boundary |
|------|------|------|---------|
| copilot | 127.0.0.1:20260 | Package mount / filesystem / shell / operations | Local-reachable only |
| service | 0.0.0.0:28050 | Package mount / orchestrate / aggregate / MCP / SQL | Intranet-reachable, public controlled access |
| endpoint | 0.0.0.0:29050 | Access Token auth / route forward / accounting | Holds no directives, executes no logic |
| service-mcp | 0.0.0.0:9020 | Outbound MCP bridge — reverse-expose registered directives as MCP tools | Exposure surface controlled by the `public_directives` whitelist in `service_manifest.json` (same source as `/skills`) |

### 4.2 Progressive Layering System

Built cumulatively layer by layer from A0–A9, each layer a complete endpoint:

| Layer | Module | Mechanism |
|:---:|------|------|
| A0 | protocol | Protocol spec — four-language zero-dependency call examples |
| A1 | skill | Directive compile/consume/NoCode — three paths to fabricate and call directives |
| A2 | copilot | Local terminal agent — whitelist + Skill Bridge + independent package management |
| A3 | service | Scheduling hub — install/uninstall/query/dispatch/nocode/export/proxy |
| A4 | paths | Path orchestration — conditional branch / degradation fallback / parallel / loop iteration (map) / cross-node dispatch |
| A5 | endpoint | Auth gateway — dual Token / multi-backend discovery / forward accounting |
| A6 | sql | SQLite persistence — key/task management + quota + auth |
| A7 | mcp | MCP bidirectional bridge — mcporter inbound + FastMCP outbound |
| A8 | discovery | Aggregate entry — multi-provider degradation chain / dispatch pipeline first seat |
| A9 | advanced | Facade abstraction + full endpoint |

> Note: A8/A9 definitions are unified with other docs — A8 aggregate entry, A9 facade abstraction + full endpoint.

**Accumulation rule**: A3 automatically includes all of A2 + service body. A9 includes all of A2–A8. Later-layer same-name files override earlier layers. A5 endpoint and bypass runtimes (CloudBase/PyPI/npm/Cloudflare/base_nocode/dsh-tc-runtime) do not participate in the accumulation chain — horizontally independently distributed.

**Build chain**: `src/skeleton/` (sole edit entry) → `build-all.py` (accumulate/passthrough) → `deploy/` (intermediate artifacts) → distribution scripts → `.zip/.tar.gz/Docker`. `deploy/` is auto-generated by build and should not be edited manually.

### 4.3 Source Structure

#### copilot

```
src/skeleton/copilot/A2-copilot/copilot/
├── text-cli-copilot.py     # python text-cli-copilot.py → :20260
├── core.py                 # directive engine + routing + dispatch
├── handlers/               # key / skill_bridge / package_manager / codec / adapters
├── whitelist_loader.py     # whitelist index
└── auxiliary_config.json   # security policy + handler registration
```

copilot runs independently, not depending on service.

#### service

Accumulation chain backbone, A3→A9 layered. Each layer only places files introduced or overridden by that layer; same-name files overridden by later layers:

```
src/skeleton/service/
├── A3-service/service/     # base platform (foundation of all layers)
│   ├── main.py              # HTTP service entry + dispatch pipeline
│   ├── core/                # parser, registry, response, auth, config, identity_context
│   ├── handlers/            # install/uninstall/query/export/nocode/proxy/sync + schema/
│   ├── installer/           # validate, filesystem, dependencies, audit
│   └── config/              # handler_inits, YAML, manifests, webhook
├── A4-paths/service/       # + path engine (text_cli_path/path_schema/path_loader/path_executor)
├── A6-sql/service/         # + SQLite persistence (key/task management/task + quota + auth)
├── A7-mcp/service/         # + MCP bidirectional bridge (mcp_dispatch, mcp_handler)
├── A8-discovery/service/   # + aggregate entry (aggregate/)
└── A9-advanced/service/    # + facade abstraction (handler_inits, pro_registry)
```

#### endpoint

```
src/skeleton/endpoint/A5-endpoint/
├── python/                 # FastAPI variant (uvicorn → :29050)
│   ├── api/                # cli / health / skills / tasks
│   └── core/               # parser / backend_registry / forwarder / database
└── js/                     # Cloudflare Workers variant
```

endpoint is a horizontal bypass — does not participate in the skeleton accumulation chain, independently distributed. The two implementations are functionally equivalent.

### 4.4 Deployment

#### Layer Integration

Build chain: `src/skeleton/` → `build-all.py` (accumulate/passthrough) → `deploy/` → distribution scripts → `.zip/.tar.gz/Docker`.

- Accumulation layers (A2–A9): later layers override earlier same-name files
- Passthrough layers (A0/A1/A5/BYPASS): mirrored as-is
- A5 endpoint does not participate in accumulation chain

#### Container

```bash
python scripts/build-all.py       # build deploy/ artifacts
cd deploy/skeleton-container
python build.py                   # generate .build/ context
python build.py --build           # generate + docker build
```

Four targets: `copilot`(:20260) / `service`(:28050) / `advanced`(:28050+20260+9020) / `a5-endpoint`(:29050).

#### Distribution Packages

```bash
# Windows
python scripts/release/win/build.py --layer A9
# Linux
python scripts/release/ubuntu/build.py --layer A9
# Endpoint
python scripts/release/win/build-endpoint.py --variant python
```

Artifacts are self-contained — extract and use, no need to clone the repo.

### 4.5 Implementation Details

#### Protocol Parsing

**Parse chain** (`src/skeleton/service/A3-service/service/core/parser.py`):

```
"AI:天气;查询,明天,威海"
  → prompt parse → directive = "天气;查询"
  → split by `;` → domain="天气", action="查询"
  → split by `,` → params=["明天", "威海"]
```

The `domain;action` combination is exactly matched against a handler function in `_registry` (in-memory dict). On a miss, go through `_alias_map` for Chinese alias → English canonical mapping (e.g. "天气;查询" → "weather;query"), then retry the match. Still missing → return `ERR_NOT_FOUND`.

**@directive decorator** (`core/registry.py`):

```python
@directive("hello", "world", domain_alias="你好", action_aliases={"world": "世界"})
def hello_world(params: list[str]) -> str:
    ...

# Auto-register: _registry["hello"]["world"] = hello_world
# Auto-register alias: _alias_map["你好;世界"] = "hello;world"
```

On service startup, `import handlers` (`handlers/__init__.py` auto-discovers and traverses the `packages/` directory) triggers registration of all `@directive`. External directive packages are hot-loaded at install time via `handler_inits.py` through `importlib.reload` — handlers are instantly usable, no service restart needed.

**Dispatch pipeline** (`service/main.py`):

```
0. Aggregate directive priority (multi-provider scheduling of degradation chain)
1. Local native/MCP explicit preference
2. Local dispatch
3. Local unmatched → MCP fallback routing
4. Local and MCP both unmatched → proxy forward
```

Pipeline order is fixed — aggregate executes first, proxy forward as last resort (supports single hop and configurable multi-hop follow). On a miss, continue to subsequent routes; all misses → `ERR_NOT_FOUND`.

**Directive re-entry detection (call loop guard)**: `registry.dispatch()` internally uses `ContextVar("_ANCESTOR_CHAIN")` call stack — before each handler executes, push the resolved target key (`path:<id>` / `agg:<domain>` / `native:<domain>;<action>`), pop after return. Key already on stack → `ERR_EXECUTION`. Legitimate repeated calls in order (diamond/sequential repeat) are released by pop, only true loops (`A→…→A`) intercepted. `pro` facade delayed check (only query not push), ensuring `pro→native/first` is not falsely killed. Cross-node forward loop is independently covered by `proxy.py`'s `MeshLoopError`/`MAX_HOP_DEPTH`, orthogonal to the dispatch ancestor chain.

#### Directive Query

`AI:text-cli;query` does not depend on the in-memory registry — every query scans all `*_schema.json` under `handlers/schema/` in real time. Data flow: `_load_schemas()` scans directory → `_flatten_directives()` extracts `directives[]` → `_apply_no_schema()` filters hidden items → render output.

Eight query modes:

| Param | Effect |
|------|------|
| none | Full plain text, grouped by package, Chinese first |
| `,json` | JSON format |
| `,compact` | One `domain;action` per line |
| `,python\|js\|mcp` | Filter by runtime |
| `,category[,<category>]` | Filter by category or list all categories |
| `,<keyword>` | Fuzzy search domain/action/description |
| `,collection` | Read user's curated set from `config/collection_text_cli.json` |
| `,delta` | Compare with last query for changes (add/remove) |

Directive query (schema directory) and directive execution (`_registry` in-memory dict) are two independent systems. On package install, schema.json takes effect immediately (query visible at once), handler is instantly usable after hot-load via `importlib.reload` (no restart). A2 proxy discovery: on render, additionally `GET http://127.0.0.1:20260/text_cli_schema.json` to get copilot-reachable directives.

#### Directive Package Install & Uninstall

**Install flow**: `validate_package()` validates schema/runtime/system-domain protection → `install_files()` schema→handlers/schema (immediate) / handler.py→packages → `install_deps()` pip/npm → `_append_handler_init()` AST-parses handler.py to append init declaration → `_load_and_wire()` directly `import_module` new module + init injection + dispatch injection (handler instantly usable, no restart. New package first install needs no reload; update/--force scenario first `_invalidate_package` cleans old registration and module refs then re-import) → `manifest_register()` writes installed_packages.json. Source: `handlers/text_cli_install.py`.

**Uninstall flow**: System-domain protection rejects uninstalling text-cli → `_registry_unregister()` removes from memory → `remove_files()` deletes packages + schema → `_drop_tables()` executes DROP TABLE → `_remove_handler_init()` + `manifest_remove()` cleans registration records → `_invalidate_package()` detaches all module refs of the corresponding package in `sys.modules` (thorough cleanup). Source: `handlers/text_cli_install.py` (`_invalidate_package`), `handlers/text_cli_uninstall.py`.

pip dependencies are not auto-removed (may be shared by other packages).

#### copilot

copilot uses `co-install/co-uninstall`, independent from service's `install/uninstall`. Installed package handlers take effect instantly via `import_module` (new package) or `_invalidate_package` + `import_module` (update) with dynamic method binding (no longer uses `importlib.reload`). Source: `handlers/package_manager.py`.

```bash
python text-cli-copilot.py    # 127.0.0.1:20260
```

**co-install flow**: `_resolve_package()` search → schema validate → full copy to `packages/` (incl. whitelists/adapters/config) → `_write_package_ops()` writes `auxiliary_config.json` → `_load_and_wire()` directly `import_module` new module (new package) or first `_invalidate_package` cleanup then `import_module` (update/--force) → `_wire_package_handlers()` dynamic binding → `_register_handlers()` re-scan registry → `WhitelistIndex.refresh()` refresh whitelist index → `_write_skill_routes()` auto-infer skill routes and write `skill_bridge_routes.json`. Source: `handlers/package_manager.py`.

**co-uninstall**: delete ops → delete skill routes → clean adapters → rmtree → `_invalidate_package()` clean dynamic binding + detach `sys.modules` → `WhitelistIndex.refresh()` refresh whitelist index → `_register_handlers()` re-register routes. Source: `handlers/package_manager.py`.

**Whitelist terminal agent**: All shell/file/Git operations pass `WhitelistIndex` validation. `CopilotCore.__init__` instantiates `WhitelistIndex` (`whitelist_loader.py`), `dispatch()` calls `whitelist.lookup()` before routing handler — unregistered or param not matching regex returns `ACCESS_DENIED`. `WhitelistIndex.refresh()` rebuilds index after co-install/co-uninstall, ensuring newly installed/uninstalled packages take effect instantly. Whitelist is deployed at co-install — no package installed means no executable terminal operations. Source: `core.py`, `whitelist_loader.py`.

**Skill Bridge**: Skill Bridge maps external skills to text-cli directives — does not modify skill code, only declares command templates via `skill_bridge_routes.json`. Execution chain: directive → `_alias_map` resolve canonical → handler miss → `_try_skill_bridge()` → whitelist validation (`WhitelistIndex.lookup`) → lookup route table → template assemble command → `subprocess.run()` → generic adapter standardize → output_adapter field mapping → return.

**Response envelope spec**: copilot's `ok()` / `error()` functions (`core.py`) follow the text-cli protocol envelope. `error()` maps internal fine-grained error codes (e.g. `skill_timeout`, `install_failed`) to the protocol's closed set of 6 error codes (`ERR_NOT_FOUND`/`ERR_EXECUTION`/`ERR_ROUTING`/`INVALID_PARAMS`/`ACCESS_DENIED`/`SERVICE_DENIED`) via `_ERROR_CODE_MAP`, original code retained in `rst_data.error_code`. `ok()`'s `rst_type` is limited to the protocol's whitelist (text/picture/video/audio/file).

#### Path Orchestration

The path engine chains multiple atomic directives into a declarative pipeline. Path only does orchestration and interpolation — file IO, API calls, and inference all go through downstream directives.

**Variable system**: `{input}` references user input, `{step_id}` references the previous step's `output_as` output, supports deep path `{geo.poi.0.name}`.

**Conditional branch**: `if` field supports `equals/contains/matches/exists` and compound conditions `all([...])`/`any([...])`.

**Degradation fallback**: `degradation` chain defines alternatives when a main step fails — try in order, resume execution on success.

**Execution modes**: `mode: "toolchain"` (default) is a serial chain; under `mode: "parallel"`, `strategy: first_ok` takes the first successful result / `strategy: all` executes all.

**Cross-node dispatch**: `steps[].source` specifies a remote URL per step — different steps can be sent to different nodes.

**Timeout circuit break**: Each step has independent `timeout` (ms); when not set, inherits `default_source` or goes to local dispatch.

**Loop iteration (map)**: `mode:"map"` executes the same sub-steps for each element of a collection. Each iteration deep-copies variables, element bound to `{as}` (default `{item}`), last-step output accumulated via `collect_as` into a list for downstream consumption. Supports `concurrency: serial|parallel`, `on_error: break|continue`, nested depth guard ≤2.
- **Safety gate**: map is an inbound capability, off by default — deployer must set `paths.map_enabled: true` in `text_cli.yaml` or set `MAP_ENABLED=true` env. Single fan-out upper limit `paths.map_max_iter` (default 100, hard cap `MAP_HARD_CAP=1000` clamped). Excess returns `INVALID_PARAMS` + `LOOP_LIMIT`.
- **Config lazy load**: `_get_map_config()` caches after first yaml read, valid for process lifetime (consistent with `config.py` behavior). When config unavailable, safely degrades to `(False, 100)` — follows A3 daemon hook pattern.
- **Injection prevention**: loop binding `{as}` is still in param position, data flows one-way into body's `steps`, cannot escape from data position to directive position — same-origin guarantee as §4.5 "declaration is sandbox".

**Unified step dispatcher**: `execute_path`'s top loop routes uniformly via `_dispatch_step(step, variables, index, messages, ..., lines, step_results, ...)` — `toolchain` goes `execute_step`, `parallel` calls `execute_parallel_*`, `map` calls `_execute_map`. Replaces the old inline `mode` judgment in the top loop.

**Pipeline closure**: `steps` are fixed in JSON, data flows one-way through named pipes — previous step's output passes to subsequent step's directive params via `{step_id.field}` syntax, no intermediate storage.

**Declaration is sandbox**: The path protocol's `steps` are fixed in JSON, data flows one-way. User input is always a handler param, accepting whitelist / regex / timeout three-layer validation. Injection payloads cannot escape from data position to directive position — this is a protocol-level built-in security feature, not extra hardening.

**Complete example** — a pipeline using cross-node dispatch, timeout, conditional branch, and degradation fallback together:

```json
{
  "id": "geo-panoramic-query",
  "name": "Geo Panoramic Query",
  "type": "pipeline",
  "version": "1.0.0",
  "mode": "toolchain",
  "lang": "en",
  "default_source": "http://192.168.1.2:28050/text-cli/cli",
  "input_schema": {"type": "object", "properties": {
    "address": {"type": "string"},
    "end_lat": {"type": "number"}, "end_lon": {"type": "number"}
  }},
  "requires": ["map;geocode", "map;route", "geo-panoramic;china", "bd-map;static-map"],
  "steps": [
    {"id": "geocode", "instruction": "map;geocode,{input.address}",
     "output_as": "geo", "timeout": 5000},
    {"id": "road",
     "instruction": "map;route,{geo.lat},{geo.lon},{input.end_lat},{input.end_lon}",
     "output_as": "road", "timeout": 8000,
     "if": {"step": "geo", "field": "status", "equals": "ok"}},
    {"id": "visual",
     "instruction": "geo-panoramic;china,{road.points.0.lat},{road.points.0.lon}",
     "output_as": "panorama", "timeout": 15000,
     "source": "http://192.168.1.100:28050/text-cli/cli",
     "degradation": [
       {"id": "fallback", "instruction": "bd-map;static-map,{geo.lon},{geo.lat},16,600x400",
        "timeout": 10000}
     ]}
  ]
}
```

**Example pipeline mechanism**: The path engine executes `steps[]` in order. Each step first does variable interpolation (`{input.key}`, `{step_id.field}`), then dispatches the directive via `dispatch()`. Step results are parsed as JSON and registered to the variable pool for downstream steps to reference. `if` condition not met → skip the step; `degradation` chain tries alternatives in order on main-step failure; `timeout` triggers circuit break. Steps with `source` go through HTTP cross-node dispatch; when omitted, inherit `default_source` or go local.

**Example note**: IP addresses are placeholders, corresponding to different nodes' text-cli runtimes. The directives in the example (`map;geocode`, `geo-panoramic;china`, etc.) are not in the project's base tool packages — to achieve equivalent functionality, you need to find or develop the corresponding directive packages yourself.

#### Key Management

A6 layer SQLite skeleton service. Keys are stored via `key;register` into `key_registry`, handlers obtain key injection into API requests via `_get_dispatch()` callback — Agent never sees key plaintext.

| Directive | Behavior |
|------|------|
| `key;register` | Register dual credentials (secret_id+secret_key) |
| `key;revoke` | Revoke and clean |
| `key;list` | List (with quota tracking status) |
| `key;quota-track` | Associate quota tracking target |

At startup `init_key_handler(db_path, dispatch_fn)` injects connection. Degrades to proxy forward when no SQLite module.

#### Task Management

Long tasks trigger async mode via `--async` — after detecting trailing `--async` param, pop it, register `task_id`, `asyncio.create_task` runs in background, immediately return `{"status":"pending","task_id":"..."}`.

Background serially executes the full dispatch chain: aggregate → local → proxy, each step completed calls `task_manager_update`/`task_manager_complete` to update SQLite status. Caller polls progress and result via `GET /text-cli/tasks/{task_id}`.

**managed mode**: service owns execution (triggered by `--async` param), runs in background and auto-writes `done`/`error`. Task states include 5 terminal states: `pending`/`running`/`done`/`error`/`cancelled` (`task;cancel` sets `pending`/`running` to `cancelled`). On instance restart, residual `running` tasks are marked `error`, reason `service_restarted`. When upstream returns `stop` during async execution (quota exhausted), `task_status` recognizes the signal and marks `error` + `quota_exhausted`.

**tracked mode**: external service owns execution, `task;track` registers writing `{"mode":"tracked","poll":{...}}` metadata. `task;status` detects tracked mode and polls upstream in real time — status only refreshes when user queries, no background timed polling. Upstream returning `stop` is also recognized as quota exhausted. Source: `handlers/task_manager.py`.

| Directive | Behavior |
|------|------|
| `task;status` | Query status (tracked mode polls upstream in real time) |
| `task;result` | Get completed task result |
| `task;track` | Register as tracked task |
| `task;cancel` | Cancel pending/running task |

#### Quota Management

Atomic quota check and consumption — key dependency of the aggregate degradation chain: when `quota;check` returns `stop`, the aggregate layer auto-switches to the next provider.

Period types: day/week/month/year/forever. Auto-zero on period flip. `amount` param supports usage-based quota.

| Directive | Behavior |
|------|------|
| `quota;check` | Atomic check + consume (optimistic lock) |
| `quota;register` | Register quota rule |
| `quota;list` | List all and usage/remaining |
| `quota;reset` | Manual reset count |
| `quota;unregister` | Remove rule |

#### MCP Bridge

**Inbound** — maps external MCP server tools to text-cli directives. Three-layer mcporter parse: `config/mcporter.json` (user explicit) → `text_cli_modules/bin/mcporter` (auto-discover) → `PATH` (system fallback).

Route decision: build alias→canonical mapping and MCP route table at startup. `decide_backend()` decides mcp or local per `routing_preferences.json`.

MCP is queried twice in the dispatch pipeline — explicit preference first, then as fallback after local miss. Quota check executes before call. Param adaptation: `adapt_params()` maps text-cli positional params to MCP named params. MCP package install triggers `refresh_routes()` to dynamically rebuild route table — no restart.

**Outbound** — exposes text-cli registered directives as MCP tools. FastMCP sub-service (:9020) reads the exposure whitelist from `public_directives` in `service_manifest.json`, then reads directive definitions from `handlers/schema/*.json`, dynamically generates MCP tool functions. Each tool internally POSTs `AI:domain;action,params` to service via HTTP — not rewriting logic, but bridging. Exposure surface shares the same source as the `/skills` endpoint (single source of truth). Pulled up by main.py's lifespan daemon hook (background thread), auto-skipped on A3 standalone deploy.

#### Aggregate Degradation

`aggregate/map.json` defines each domain's degradation chain. `_aggregate_dispatch()` tries in order per `default[]` — first successful return.

**Degradation trigger**: `status: "stop"` (quota exhausted) / `status: "error"` / rst_err non-empty / throws exception / action not supported.

**User explicit selection**: when trailing param matches a name in `providers`, skip the degradation chain and use only that provider. Providers are source-agnostic — native handler / MCP bridge / Skill Bridge are equal-weight in the degradation chain. Aggregate has the highest priority in the dispatch pipeline.

#### Facade Entry

`text-cli;pro` provides short-name→target mapping. Two target types:

| Type | Behavior |
|------|------|
| path | Transfer to `text-cli;path` to execute path declaration |
| aggregate | Transfer to `domain;action` to walk aggregate degradation chain |

Config in `config/pro_registry.json`. Caller only needs to remember one short name `text-cli;pro,<name>`.

#### Federation Mesh Credentials

**Delegation model**: mesh's essence is delegation, not routing. The source node only declares "I delegate this directive to peer A" — peer A's `proxy_routes.json` decides whether to forward to peer B. The hop chain is not pre-planned by the source node, but decided by each hop node's own route table. What the source node controls is not "which nodes to pass through", but "max follow hops".

**Unified entry & multi-hop follow**: `proxy_dispatch` uniformly handles single and multi-hop. Default single hop — match `proxy_routes.json` `domain;action` → forward to target URL. Multi-hop follow only activates when `mesh.multi_hop_enabled: true`: downstream node returns `_mesh_redirect` in response (with `domain;action` and `url`), proxy parses and delegates `proxy_dispatch_multi_hop` to follow to next hop, until target node no longer returns `_mesh_redirect` or reaches depth limit.

**Trust radius**: `mesh.multi_hop_enabled: false` (default off — mesh is an outbound capability, but multi-hop follow takes the request path beyond the deployer's direct control range, requires explicit enable). `mesh.multi_hop_max_depth: 3` (yaml configurable, effective value `min(multi_hop_max_depth, MAX_HOP_DEPTH)`, `MAX_HOP_DEPTH=5` is code hard ceiling). Same pattern as path map's `map_max_iter` — yaml tunes trust radius, code constant is ceiling.

In multi-node federation topology, proxy forward injects credentials per peer. `proxy_routes.json` entries with `peer` field → `MeshCredentialInjector.inject(body, peer)` injects credentials → forward to target URL.

**Injection layering**: proxy layer (`handlers/proxy.py`) is a pure forward pipeline, holds no credential logic. Credential injection is independently provided by `MeshCredentialInjector` (`handlers/mesh_credentials.py`) — injected into proxy's `credential_injector` param via `handler_inits`. Proxy only calls `injector.inject(body, peer)` interface, unaware of internal implementation.

`MeshCredentialInjector` internally handles two paths: (A) `peer` not None → per-peer credentials (query `peer_credentials` table); (B) `peer` is None → legacy all_keys injection. When credentials missing, per `mesh.require_credentials` config decide reject (`mesh_credential_unavailable`) or degrade forward (marked `_mesh_credential_degraded`).

**Security guard**: `visited` anti-loop / `MAX_HOP_DEPTH=5` hard ceiling (`multi_hop_max_depth` tunable below it) / exponential backoff retry (max 2). proxy's injector exception caught and converted to `ERR_ROUTING` response. Source: `handlers/proxy.py` (incl. `_get_mesh_config` lazy config load + daemon hook safe degrade), `handlers/mesh_credentials.py`, `config/text_cli.yaml`.

#### endpoint

endpoint executes no directives — only routes. At startup it traverses the `A3_BACKENDS` list, `GET /text-cli/skills` from each backend service to pull reachable directives, aggregates into a unified capability table. `build_external_schema()` replaces each directive's URL in the aggregate table with the endpoint's own address — caller only sees the endpoint.

On request arrival `forward_request()`: `find_backend_source()` locates target backend → `httpx.AsyncClient.post()` passthrough → 5xx auto-retry → write `call_logs` (request_id/domain/action/token prefix/status code/latency) → update `daily_stats`.

endpoint does not distinguish backend runtime form — standard Python service, Docker deploy, CloudBase cloud function are equal-weight in `A3_BACKENDS`.

**Security line**: three-layer progressively tightening middleware chain —

1. **IP blacklist**: load CIDR list from `IP_BLACKLIST`, hit → 403.
2. **Rate limit**: sliding window algorithm. POST 1000/h, GET 10000/h. Excess → 429.
3. **Token validation**: Access Token validates identity → Service Token prefix strategy controls.

**Dual Token auth**:

```
Caller ──Access Token──> Endpoint ──passthrough Service Token──> Service
```

- **Access Token**: issued by endpoint, validates caller identity.
- **Service Token**: privately agreed between caller and runtime owner, endpoint only passthroughs first 8 chars for policy control-plane identification. Follows prefix immutability principle — identity code bit count extensible, endpoint unaware.

> The protocol does not require a directive length limit; the project implementation sets 512 for 'endpoint' and 2048 for 'runtime'.

---

## Five. Bypass Runtimes

Do not participate in the A2→A9 accumulation chain, but interoperate with the standard runtime through the unified protocol.

Per SPEC §6.1, bypass implements **any mechanism subset** above the mandatory baseline — **including the full set**; the full set is not required. Coverage spans widely across the sequence: from the two loaders (2–3 mechanisms) to `dsh-tc-runtime` (full 9-mechanism set).

> **Identity is self-declared by the implementer; the project does not adjudicate**: `dsh-tc-runtime` covers the full set but self-describes as a bypass form — this is its own positioning, not an inference from coverage. Callers are unaffected — the one-dimensional contract guarantees runtime identity is invisible to the caller.

Five forms by deployment, plus one shared logic layer reused across them.

### In-process SDK (Lightweight Loaders)

In-process loaders deploy no service — they install the "execute directive package" capability into your existing environment.

#### textcli-loader (PyPI)

`pip install textcli-loader` lets you directly load and execute Python directive packages that need no extra keys in any Python environment — no dependency on any text-cli service, zero extra dependencies. Core files: `loader.py` + `registry.py` + `envelope.py`.

```python
from textcli_loader import load_package, execute

load_package("./my-date-calc/")
result = execute("AI:date-calc;add-days,2026-01-01,30")
# → {"rst_types": "text", "rst_data": {"status":"ok","result":"2026-01-31"}, "rst_err": ""}
```

**Working principle**: `load_package()` reads the directive package's `schema.json`, dynamically `importlib` imports `handler.py` — `@directive` decorator registers the directive into the in-memory registry. `execute()` parses prompt → `dispatch()` → handler → returns text-cli standard envelope format.

**Compatibility bridge**: loader injects a `sys.modules` shim, mapping both `from core.registry` and `from textcli_loader.registry` — existing text-cli directive packages run in loader without any modification.

#### textcli-core (npm)

`npm install textcli-core` lets you directly load and execute directive packages in any Node.js environment. Zero external dependencies. Isomorphic with Python textcli-loader — parser, registry, envelope APIs and behavior are fully identical, only language differs.

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

// Load directive package from file
const { loadPackage } = require("textcli-core/loader.node");
loadPackage("./my-package/");
```

**Core modules**: `parser.js` (supports `AI:`/`指令:` dual prefix, bracket depth tracking), `registry.js` (`register`/`dispatch`/`unregister`/`getRegistered`, supports sync/async handler), `envelope.js` (`ok`/`err`, error code whitelist validation), `alias.js` (alias mapping, case-insensitive), `loader.js` (core load interface independent of IO), `loader.node.js` (Node.js platform adapter — `fs` + `require` load from disk).

**Key difference from Python loader**: loader and platform adapter separated — `loader.js` is pure logic, does not depend on `fs`/`require`; `loader.node.js` is the Node.js adapter. This separation lets non-Node.js environments like Cloudflare Workers directly reuse the pure logic modules, only needing to provide their own platform adapter — an idea later solidified as `tc-js-skeleton` (see "Shared Logic Layer" below).

### Zero-code Single File

#### base_nocode

A pure-stdlib single script: `markdown_converter_zh.py` plus one structured Markdown experience document starts a complete HTTP directive service — no framework, no third-party dependency.

- Endpoints: `POST /text-cli/cli` (directive execution; `AI:text-cli;query` returns the capability list via the same endpoint), `GET /text-cli/schema` (package schema), `GET /text-cli/health` (health check)
- Document format: `## Directive` (declares domain / action / triggers / params; optional `Source` / `Verified` / `Stale After` / `Status`) + `## Knowledge` (experience content, supports `鉴别` / `教训` convention fields)
- Source: `src/text_cli/base_text-cli/template/base_nocode/zh/`

This is the smallest realization of "if you can speak, you can propagate" — no code, no runtime deployment; experience text becomes a service callable via `AI:domain;action`.

### Cloud Platform
#### CloudBase SCF

Tencent Cloud cloud function runtime (Node.js), deploys directive packages as independent cloud functions, routed via gateway. Core files: `config.js` + `index.js`.

**Architecture**:
```
HTTP trigger → index.js exports.main
  → parse prompt → query config.js routeTable[domain] → cloud function name
    → cloud.callFunction(name, {prompt}) → handler(params) → return envelope
```

Supports HTTP POST `/cli` and SDK call (`action=get_schema`) dual mode. `GET /health` returns health status.

**Extend new directive**: deploy directive cloud function → register `domain → function name` in `config.js` `routeTable` → register package id in `packages` array (for `text-cli;query` aggregation). Adding a package needs no skeleton code change, only gateway-side config change.

#### Cloudflare Workers (D1 Edge Runtime)

Cloudflare Workers **D1 multi-function edition** — **not a pure gateway; it has restricted execution capability** (the earlier version was a pure gateway + KV Store that only registered metadata and delegated execution to the backend). It shares `tc-js-skeleton` logic components (`textcli-core` + `contract`) with three platform adapters; executable packages are stored in **D1** (not KV) and executed under restriction in a graded sandbox inside Workers.

```
Cloudflare Workers (D1 multi-function edition)
  │
  ├── POST /text-cli/cli → src/index.js
  │     ├── auth (src/token.js single Service-token closed loop)
  │     ├── parse prompt → domain;action,params (src/endpoints.js + src/runtime.js)
  │     ├── D1 load executable package + metadata (src/d1-storage.js + src/meta.js)
  │     ├── restricted execution (src/executor.js graded sandbox) or mesh forward (src/mesh.js)
  │     ├── key-as-directive credentials (src/key.js, AES-GCM)
  │     ├── async task 5-state + restart reconciliation (src/tasks.js)
  │     └── per-caller counting / quota degradation (src/usage.js)
  │
  ├── GET /text-cli/health | /schema | /tasks/{id} | /packets/... (endpoint surface)
  └── init: schema.sql (create D1 tables)
```

Protocol-wise identical to text-cli / dsh-tc-runtime: reuses the `textcli-core` envelope + the `contract` 6-code closed set, async task 5-state, quota `status:"stop"` degradation, mesh loop-guard routing.

### Plugin Host

#### dsh-tc-runtime

A bypass runtime hosted by the dsh (Cordis) ecosystem — a plugin set external to dsh (15 `runtime-*` packages) that bridges tc directive capability into dsh. It **covers the full 9-mechanism capability set, but self-describes as a bypass form and does not claim standard-runtime identity** (identity is self-declared, not inferred from coverage — see §2.1).

```
runtime-inbound      Inbound HTTP (six-segment pipeline + reserved-domain interception)
runtime-mapper       Directive mapping (tc directive ↔ ctx.tools)
runtime-sandbox      Sandbox execution host (restricted subprocess + layered policy guardrails)
runtime-credentials  Per-package credential isolation
runtime-audit        Audit channel (append-only JSONL)
runtime-meta         text-cli;* meta directives (install/query/path/...)
runtime-quota        Period window + atomic check+consume
runtime-approval     Approval answerer (HMAC + fail-closed)
runtime-host         Host directives
runtime-path         path engine (declaration-layer interpreter + workflow compilation)
runtime-aggregate    Async task bridging (5-state) + aggregate degradation
runtime-mesh         mesh forwarding (route table / loop guard / backoff)
runtime-bridge       Protocol bridge (mcp-client → mcp__<server>__<tool>)
runtime-pro          Facade registry (short name → path/aggregate)
runtime-contract     Global acceptance (canonical envelope + 16-line mapping contract)
```

**Red lines (7)**: no intrusion into the dsh core; credential plaintext never enters the JS execution environment; sandbox denies by default; protocol closed set; reserved-domain meta directive interception; approval ownership filtering; tc audit kept as independent JSONL.

### Shared Logic Layer (Not a Runtime Form)

#### tc-js-skeleton

The bypass **generic JS logic-layer source of truth** — an onion-layered component family around the `textcli-core` thin core (12 packages), platform-agnostic, reused by cloudflare / dsh / other JS hosts. **It is not a runtime and occupies no runtime slot.**

```
Skeleton/facade: compose                       ← assembly + package lifecycle + multi-package consumption
Interaction (outermost): mesh / approval / credentials  ← binds external capability, deps injected
Guardrail layer: quota / audit                 ← intercept/record before dispatch
Orchestration layer: path / aggregate / contract ← declaration-layer logic, built-in path:/agg: loop check
Core guard (innermost): guard                  ← native loop detection
Core (thin, invariant): textcli-core           ← parser/envelope/alias/registry/loader
```

Components: `textcli-core` (thin core), `-compose` (assembly + package lifecycle), `-contract` (canonical envelope + 6-code closed set), `-guard` (loop detection), `-path` (declaration-layer path engine), `-aggregate` (try-in-order degradation), `-quota` / `-audit` (quota guardrail / audit), `-storage` (storage substrate: memory / file / D1), `-auth` / `-approval` / `-credentials` / `-mesh`. Tests 91/91.

See `src/skeleton/bypass-service/docs/INDEX_en.md` for details.

---

## Six. Directive Package Design

### 6.1 Relationship Between Directive and Directive Package

text-cli's basic scheduling unit is the **directive**: one line `AI:domain;action,params` corresponds to one capability call. One handler can register multiple directives (e.g. `bd-map;geocode` and `bd-map;route` belong to the same package), multiple related directives form a **directive package**. The directive package is text-cli's capability distribution unit — install one package, all its directives are instantly usable.

### 6.2 Directive Package Classification System

Directive packages declare their own positioning via two key fields in `schema.json`:

| Field | Meaning | Decided by |
|------|------|------|
| `type` | Package's declared form | How capability is organized — code / Markdown / route / step chain |
| `runtime` | Package's execution method | Who executes — Python / js / MCP / command-line / path engine |

**type × runtime matrix**:

| type | python | js | cmd | mcp | path | aggregate |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| native | ✅ tool/API/container | ✅ | ✅ | ✅ MCP bridge | — | — |
| nocode | — | — | — | — | ✅ | — |
| aggregate | — | — | — | — | — | ✅ pure declaration |
| pipeline | — | — | — | — | ✅ pure declaration | — |

> nocode has no independent handler execution; its carrier is the path engine (`runtime: path`), consumed by `tc-markdown`+`ai_inference` knowledge base.
> The project provides initial versions of `tc-markdown`+`ai_inference` in open-source directive packages.

**Design intent of four types**:

| type | Design intent | Typical scenario |
|------|---------|------|
| `native` | Capability with code implementation | Python handler, Node.js cloud function needing programming language support |
| `nocode` | Zero code — experience as service | Flower shop owner's bonsai diagnosis notes |
| `aggregate` | Multi-provider unified entry | Map service aggregating tx-map/gd-map/bd-map etc. |
| `pipeline` | Multiple directives orchestrated into chain | "Check weather → clothing advice" auto-orchestrated |

### 6.3 Package-Runtime Contract

**schema.json** is the package's declaration surface to the runtime — `id`, `type`, `runtime`, `directives[]` and other fields form the protocol contract. The runtime completes directive registration, discovery, and routing based on it. Field definitions see [package-publish-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-publish-guide_zh.md).

**Implementation substitutes per runtime**:

| runtime | Implementation file | Registration mechanism |
|------|------|------|
| `python` | `handler.py` + `@directive` decorator | handler_inits + importlib.reload hot-load |
| `js` | `index.js` + `INSTRUCTIONS` map | exports.main entry |
| `cmd` | `whitelist.json` + `handler.py` (whitelist validation) | whitelist_loader + subprocess.run |
| `mcp` | `service-descriptor.json` (no handler.py) | mcp_dispatch route table |
| `path` | Pure JSON declaration (`type: "pipeline"`) | path_loader registration |
| `aggregate` | Pure JSON declaration (`type: "aggregate"`) | aggregate loader |

**Package lifecycle**: on install, schema.json is written to handlers/schema/ immediately (query visible at once), handler.py is hot-loaded via importlib.reload (no restart) → caller discovers via `AI:text-cli;query` → dispatch execution → on uninstall, fully reclaim files, registration entries, and self-built tables.

### 6.4 Scaffolding Converter

The project provides converter scripts to transform existing software engineering artifacts into directive package starter skeletons:

| Scaffold converter | Script | Input → Output |
|-----------|------|------------|
| webapi directive package | `postman_to_pkg_python.py` | Postman Collection → schema.json + handler.py |
| MCP bridge package | `mcp_to_pkg.py` | MCP server → schema.json + service-descriptor.json |

Converter-produced scaffolding needs business logic and error handling supplemented before use. Full guide see [package-scaffolding-converter-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-scaffolding-converter-guide_zh.md).

### 6.5 Directive Package Dev Guide Entries per Runtime

| Category | Runtime | Dev guide |
|------|------|------|
| Standard | Python runtime | [package-python-dev-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-python-dev-guide_zh.md) |
| Standard | JS runtime | [package-js-dev-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-js-dev-guide_zh.md) |
| Other | nocode (cross-runtime) | [package-nocode-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md) |
| Other | Existing service converter scaffold | [package-scaffolding-converter-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-scaffolding-converter-guide_zh.md) |
| Other | Directive package distribution spec | [package-publish-guide_zh.md](../../src/text_cli/base_text-cli/docs/package-publish-guide_zh.md) |

### 6.6 AI Agent Advanced Assistance

Agents self-extend through text-cli's self-management capability:

```
Agent wakes → /health → text-cli;query → lacks translation capability
  → use 'scaffold/guide' to quickly convert need into 'directive package'
  → text-cli;install,xx-cloud → install directive package, new capability online
  → "check weather → clothing advice" recurs → text-cli;pro → publish as path
```

Agents gradually shift from caller to manager — no need for humans to configure routes or write deployment docs.

---

## Standard Runtime Mechanism Cross-Reference

The Python standard runtime implements the protocol's 9 required mechanisms (the table below is labeled by **real implementation location** — each mechanism's owning layer and implementation file have been verified against source code, consistent with "where the mechanism was first introduced"; the aggregate degradation declaration file is in A8, but execution logic is in the A3 dispatch pipeline; facade abstraction implementation and its config/registry are both in A9):

| Required mechanism | Implementation layer | Implementation location |
|------|:---:|------|
| Directive execution | A3 | service/core/parser.py + core/registry.py |
| Install/uninstall directive package | A3 | handlers/installer/ + handlers/text_cli_install.py / text_cli_uninstall.py |
| Directive auth & discovery | A3/A5 | core/auth.py + handlers/schema_query.py |
| Path orchestration | A4 | handlers/path_executor.py |
| Async task scheduling | A6 | handlers/task_manager.py |
| Aggregation & degradation chain | A3 execution / A8 declaration | A3 service/main.py dispatch pipeline + A8 aggregate/*.json |
| Federation Mesh | A3 (forward) / A6 (credential injection) | handlers/proxy.py (forward) + handlers/mesh_credentials.py (credential injector) |
| Protocol bridge | A7 | handlers/mcp_handler.py + MCPservice/ |
| Facade abstraction | A9 | handlers/text_cli_pro.py + config/pro_registry.json |

---

## Appendix: Key File Index (Python-based)

### Protocol Consumer SDK
- `src/skeleton/base/A0-protocol/python/call.py` — Python SDK: DirectiveResult + call/discover/poll/wait
- `src/skeleton/base/A0-protocol/js/call.js` — JavaScript SDK
- `src/skeleton/base/A0-protocol/shell/call.sh` — Bash CLI
- `src/skeleton/base/A0-protocol/shell/call.ps1` — PowerShell CLI

### AI Skill Scheduling
- `src/skeleton/base/A1-skill/skill/python/cli.py` — Compile path: register() + generate_schema()
- `src/skeleton/base/A1-skill/skill/python/skill.py` — Consume path: Skill class + Skill.run() + degradation chain
- `src/skeleton/base/A1-skill/skill/python/aggregation.py` — sync_endpoints endpoint capability aggregation
- `src/skeleton/base/A1-skill/skill/config/agent-endpoints.json` — Endpoint registry (has token, manually maintained)
- `src/skeleton/base/A1-skill/skill/config/agent-text-cli-schema.json` — Capability aggregate list (sync generated)
- `src/skeleton/base/A1-skill/skill/prompts/SKILL.md` — Agent scheduling System Prompt
- `src/skeleton/base/A1-skill/skill/prompts/text-cli-core_zh.md` — Core scheduling v2.0
- `src/skeleton/base/A1-skill/skill/prompts/text-cli-sync-skill.md` — Sync Skill concept design
- `src/skeleton/base/A1-skill/skill/prompts/agent-text-cli-schema.example.json` — Aggregate Schema example

### copilot
- `src/skeleton/copilot/A2-copilot/copilot/core.py` — Directive engine
- `src/skeleton/copilot/A2-copilot/copilot/handlers/package_manager.py` — co-install/uninstall/list
- `src/skeleton/copilot/A2-copilot/copilot/whitelist_loader.py` — Whitelist index
- `src/skeleton/copilot/A2-copilot/copilot/handlers/skill_bridge.py` — Skill bridge
- `src/skeleton/copilot/A2-copilot/copilot/handlers/adapters.py` — Adapter
- `src/skeleton/copilot/A2-copilot/copilot/config/skill_bridge_routes.json` — Skill routes
- `src/skeleton/copilot/A2-copilot/copilot/auxiliary_config.json` — Security policy

### service
- `src/skeleton/service/A3-service/service/core/parser.py` — prompt parse
- `src/skeleton/service/A3-service/service/core/registry.py` — @directive decorator + dispatch + `_ANCESTOR_CHAIN` (ContextVar call stack anti-loop) + `_make_ancestor_key` + `register_aggregate_domain`
- `src/skeleton/service/A3-service/service/main.py` — dispatch pipeline + aggregate degradation
- `src/skeleton/service/A3-service/service/handlers/schema_query.py` — Directive query
- `src/skeleton/service/A3-service/service/handlers/text_cli_install.py` — Install
- `src/skeleton/service/A3-service/service/handlers/text_cli_uninstall.py` — Uninstall
- `src/skeleton/service/A3-service/service/handlers/installer/validate.py` — Package validate
- `src/skeleton/service/A3-service/service/handlers/installer/filesystem.py` — File deploy
- `src/skeleton/service/A9-advanced/service/config/handler_inits.py` — Startup registry
- `src/skeleton/service/A4-paths/service/handlers/text_cli_path.py` — Path engine entry
- `src/skeleton/service/A4-paths/service/handlers/path_schema.py` — Path declaration validate
- `src/skeleton/service/A4-paths/service/handlers/path_loader.py` — File load
- `src/skeleton/service/A4-paths/service/handlers/path_executor.py` — Execution engine + `_dispatch_step` (unified step dispatcher) + `_execute_map` (map loop execution) + `_get_map_config` (lazy config load) + `MAP_HARD_CAP=1000`
- `src/skeleton/service/A6-sql/service/handlers/key.py` — Key management
- `src/skeleton/service/A6-sql/service/handlers/task_manager.py` — Task management
- `src/skeleton/service/A6-sql/service/handlers/quota_handler.py` — Quota management
- `src/skeleton/service/A7-mcp/service/handlers/mcp_handler.py` — MCP inbound
- `src/skeleton/service/A7-mcp/service/core/mcp_dispatch.py` — MCP route
- `src/skeleton/service/A7-mcp/MCPservice/server.py` — FastMCP outbound
- `src/skeleton/service/A8-discovery/aggregate/map.json` — Aggregate route table
- `src/skeleton/service/A9-advanced/service/handlers/text_cli_pro.py` — Facade entry (incl. call-loop early check: query not push, coordinated with dispatch ancestor chain)
- `src/skeleton/service/A3-service/service/handlers/proxy.py` — Proxy forward (unified entry: single hop default, multi-hop follow via mesh.multi_hop_enabled config; pure pipeline, holds no credential logic)
- `src/skeleton/service/A6-sql/service/handlers/mesh_credentials.py` — Mesh credential injector (per-peer + legacy all_keys)

### endpoint
- `src/skeleton/endpoint/A5-endpoint/python/main.py` — FastAPI entry + security middleware
- `src/skeleton/endpoint/A5-endpoint/python/core/backend_registry.py` — Multi-backend aggregation
- `src/skeleton/endpoint/A5-endpoint/python/core/forwarder.py` — Forward + audit
- `src/skeleton/endpoint/A5-endpoint/python/core/ip_guard.py` — IP blacklist
- `src/skeleton/endpoint/A5-endpoint/python/core/rate_limiter.py` — Rate limit
- `src/skeleton/endpoint/A5-endpoint/python/core/auth.py` — Token validate

### Bypass Runtime
- `src/skeleton/bypass-service/pypi/src/textcli_loader/loader.py` — Dynamic package load
- `src/skeleton/bypass-service/pypi/src/textcli_loader/registry.py` — @directive registry
- `src/skeleton/bypass-service/pypi/src/textcli_loader/envelope.py` — Envelope format
- `src/skeleton/bypass-service/npm/textcli-core/parser.js` — JavaScript protocol parser (isomorphic with Python)
- `src/skeleton/bypass-service/npm/textcli-core/registry.js` — register/dispatch registry
- `src/skeleton/bypass-service/npm/textcli-core/loader.node.js` — Node.js platform adapter
- `src/skeleton/bypass-service/npm/textcli-core/package.json` — npm package config (zero external dependency)
- `src/text_cli/base_text-cli/template/base_nocode/zh/markdown_converter_zh.py` — Zero-code single-file service (pure stdlib)
- `src/skeleton/bypass-service/cloudbase/config.js` — CloudBase gateway route
- `src/skeleton/bypass-service/cloudbase/index.js` — CloudBase entry
- `src/skeleton/bypass-service/cloudflare/workers/src/index.js` — Cloudflare Workers entry (D1 multi-function edition; the old `gateway.js` has been removed)
- `src/skeleton/bypass-service/cloudflare/workers/src/executor.js` — Restricted execution (graded sandbox)
- `src/skeleton/bypass-service/cloudflare/workers/src/d1-storage.js` — D1 → StorageKV adapter
- `src/skeleton/bypass-service/cloudflare/workers/src/tasks.js` — Async task 5-state + restart reconciliation
- `src/skeleton/bypass-service/cloudflare/workers/schema.sql` — D1 table creation script
- `src/skeleton/bypass-service/tc-js-skeleton/packages/` — Generic JS logic-layer source of truth (12 components, onion layering)
- `src/skeleton/bypass-service/dsh/dsh-tc-runtime/` — dsh bypass runtime (15 `runtime-*` Cordis packages)
- `src/skeleton/bypass-service/dsh/dsh-tc-bridge/` — Capability-seam plugin for dsh-agent consuming the tc ecosystem (not a runtime)
- `src/skeleton/bypass-service/docs/INDEX_en.md` — Bypass runtime index (per-form build modes, differences vs service)

### Build & Deploy
- `scripts/build-all.py` — Full build
- `scripts/release/win/build.py` — Windows artifact distribution
- `scripts/release/win/build-endpoint.py` — Windows endpoint artifact distribution
- `scripts/release/ubuntu/build.py` — Linux artifact distribution

### Base Tools
- `src/text_cli/base_text-cli/template/base_nocode/zh/markdown_converter_zh.py` — NoCode path (plus the `template/base_nocode/` no-code template, with an `en/` edition)
- `src/text_cli/base_text-cli/converter/postman_to_pkg_python.py` — Postman converter
- `src/text_cli/base_text-cli/converter/mcp_to_pkg.py` — MCP converter

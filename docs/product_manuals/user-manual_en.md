# text-cli User Manual

> **Language note:** This English text is a translation of the normative Chinese manual (`../product_manuals/user-manual_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.

> This manual is distributed with all packages (Windows / Linux / Docker). The four products can be deployed and used independently — when the artifact you receive contains only some of them, skip to the relevant sections. This artifact works on the text-cli (MIT) protocol specification. Manual revision: 2026-07-31

---

## 0. Concept Overview

text-cli consists of four independent products. Each can be deployed alone — combine only when needed.

```
Copilot (:20260, 127.0.0.1)    Service (:28050/9020, 0.0.0.0)    Endpoint (:29050, 0.0.0.0)
  ┌─ Local capability agent          ┌─ Core orchestration platform     ┌─ Auth gateway
  │   Terminal · Files · Skill       │   Install · Orchestrate · SQL · MCP  │  IP blocklist · Rate limit · Token
  │                                  │                                  │
  │     sync-copilot ───────────────→│                                  │
  │          optional linkage        │    A3_BACKENDS ─────────────────→│
  │                                  │         optional linkage         │
  └──────────────────────────────────┴──────────────────────────────────┘
                     Unified protocol: AI:domain;action,params
                     Consume the above services conveniently via Protocol
```

| Product | Artifact name | Listens | What it can do standalone |
|---------|---------------|:-------:|---------------------------|
| Copilot | `text-cli-A2-v*` | :20260, 127.0.0.1 | Install cmd/skill directive packages; operate the local machine |
| Service | `text-cli-A3-v*` ~ `A9-v*` | :28050, 0.0.0.0 | Install directive packages, orchestrate pipelines, persist state, connect MCP |
| Endpoint | `text-cli-endpoint-python-v*` | :29050, 0.0.0.0 | Auth, rate limiting, audit; pass through to Service |
| Protocol | `protocol/` (distributed with all artifacts) | - | Zero-dependency consumer SDK, four languages (Python/JS/Shell/PS), one-call without curl |

Three common combinations:

| Mode | Includes | Suitable for |
|------|----------|--------------|
| Local | Copilot + protocol only | Personal development; AI operates the local machine |
| Intranet | Copilot + Service + protocol | Shared directive packages for home/team |
| Public | Copilot + Service + Endpoint | Expose services externally with a security defense |

---

## 1. Deployment

Deployment of the four products is independent — deploy whichever you need. **The protocol is unified** (§1.4), so no matter how many products you run, the way you talk to them is the same.

### 1.1 Copilot

The Copilot artifact is `text-cli-A2-v*` (Win `.zip` / Linux `.tar.gz` / Docker).

#### Windows

`start.bat` is the unified entry point — it sets environment variables automatically and launches Copilot. **Choose one of two run methods:**

```powershell
# PowerShell
Expand-Archive text-cli-A2-v*.zip -DestinationPath .
Start-Process -FilePath "start.bat" -WorkingDirectory "text-cli-A2-v*"
```

```cmd
:: cmd
cd text-cli-A2-v*
start.bat
```

Stop: `.\end.bat`

#### Linux

```bash
tar -xzf text-cli-A2-v*.tar.gz
cd text-cli-A2-v*
chmod +x start.sh
./start.sh
```

Stop: `./end.sh`

#### Docker

```bash
docker run -d -p 20260:20260 text-cli-copilot:latest
```

**Verify** (identical on all three platforms):

```bash
curl http://localhost:20260/text-cli/health
# → {"status":"ok"}
```

> Other configuration items (auth, log level, query language, etc.) are in [§1.5 Configuration](#15-configuration).

### 1.2 Service

The Service artifact is `text-cli-A3-v*` to `A9-v*` (higher tier number = more capabilities; each tier can be deployed independently). All tiers include Copilot — if you deploy only the Service artifact, Copilot also starts. **You do not need to deploy the two artifacts separately.**

#### Windows

`start.bat` is the unified entry point — it auto-sets `TEXT_CLI_HOME` + `TEXT_CLI_PACKAGE_SOURCE_DIRS`, and launches Copilot (:20260) + Service (:28050). The terminal output shows the `TEXT_CLI_PACKAGE_SOURCE_DIRS` status (`[OK]` or `[WARN]` with an English prompt). **Choose one of two run methods:**

```powershell
# PowerShell
Expand-Archive text-cli-A9-v*.zip -DestinationPath .
Start-Process -FilePath "start.bat" -WorkingDirectory "text-cli-A9-v*"
```

```cmd
:: cmd
cd text-cli-A9-v*
start.bat
```

Stop: `.\end.bat` (stops the three services by ports 20260/28050/9020)

#### Linux

```bash
tar -xzf text-cli-A9-v*.tar.gz
cd text-cli-A9-v*
chmod +x start.sh
./start.sh
```

Stop: `./end.sh` (`fuser -k` stops by port)

#### Docker

```bash
docker run -d -p 28050:28050 -p 20260:20260 \
  -v ./packages:/packages \
  text-cli-service:latest
```

**Verify**:

```bash
curl http://localhost:28050/text-cli/health
# → {"status":"ok","domains":["key","quota","task","text-cli"],"sqlite":"enabled"}
```

#### Package source path

The install directive needs to know where directive packages are placed. The environment variable `TEXT_CLI_PACKAGE_SOURCE_DIRS` defaults to the `packages/` directory alongside the artifact. `start.bat` / `start.sh` detect it at startup — outputs `[OK]` if the directory exists, `[WARN]` and a prompt to create it otherwise.

> Other configuration items (auth, log level, query language, etc.) are in [§1.5 Configuration](#15-configuration).

### 1.3 Endpoint

Endpoint is a standalone artifact `text-cli-endpoint-python-v*` (Win `.zip` / Linux `.tar.gz` / Docker).

#### Windows

```powershell
Expand-Archive text-cli-endpoint-python-v*.zip -DestinationPath .
cd text-cli-endpoint-python-v*
# PowerShell
Start-Process -FilePath "start-endpoint.bat"
# Stop: .\end-endpoint.bat
```

#### Linux

```bash
tar -xzf text-cli-endpoint-python-v*.tar.gz
cd text-cli-endpoint-python-v*
./start.sh   # Stop: ./end.sh
```

#### Docker

```bash
docker run -d -p 29050:29050 text-cli-endpoint:latest
```

`start-endpoint.bat` / `start.sh` automatically creates the `.venv` and installs dependencies. Detailed configuration parameters are in Chapter 4.

**Verify**:

```bash
curl http://localhost:29050/text-cli/health
# → {"liveness":true,"schema":true,"backends":[...]}
```

> Endpoint configuration (`backends.yaml`, Token, rate-limit parameters) is in [§1.5 Configuration](#15-configuration).

### 1.4 Protocol

All three products use exactly the same protocol — learn it once.

**Directive syntax**:

```
AI:<domain>;<action>,<param1>,<param2>,...
```

**Request format** (the field name is `prompt`, not `directive`):

```bash
curl -X POST http://localhost:<port>/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:domain;action,params"}'
```

**Response envelope**:

```json
{"rst_types": "text", "rst_data": {"status":"ok","result":14}, "rst_err": ""}
```

- `rst_types`: reflects the response type. Defaults to `"text"`. When the handler includes a `pray_rst_types` key in the returned dict, the skeleton promotes its value to this field. Values: `text` / `picture` / `video` / `audio` / `file`.
- `rst_data`: the JSON object returned by the handler, carried directly by the skeleton — no longer nested as `{"text": "..."}`. The caller reads `rst_data` directly.
- `rst_err`: structured error field. Empty string `""` means success; non-empty means failure. Error codes (see the error-code quick reference below).

**Content-type mapping** (by `rst_types` value):

| `rst_types` | Caller behavior |
|-------------|-----------------|
| `"text"` | Display `rst_data` directly |
| `"picture"` | Render `rst_data.url` |
| `"video"` | Render `rst_data.url` |
| `"audio"` | Render `rst_data.url` |
| `"file"` | Render `rst_data.url` |

**Error-code quick reference**:

| Error code | Meaning | Common scenario |
|------------|---------|-----------------|
| `ERR_NOT_FOUND` | Directive does not exist | Corresponding directive package not installed |
| `ERR_EXECUTION` | Execution failed | Exception inside handler |
| `ERR_ROUTING` | Routing failed | proxy destination unreachable |
| `INVALID_PARAMS` | Invalid parameters | Required parameter missing or malformed |
| `ACCESS_DENIED` | Access Token invalid | Endpoint auth failed |
| `SERVICE_DENIED` | Service Token invalid or **explicitly denied** (not quota exhaustion) | Provider denial (quota exhaustion follows the `status:stop` degradation chain, see §3.11, and does not return this error code) |

> **Example convention**: For reading brevity, all `→ {...}` directive-call examples in this manual show **only the contents of the `rst_data` field** (the JSON object returned by the handler, carried directly in `rst_data`); the real HTTP response is always the envelope format above (this section, L211). Caller rule: **read `rst_data` directly**; only when `rst_types="text"` and the data happens to be of the `{"text": ...}` shape (some handlers' business returns include a `text` field) should you take `.text`; in all other cases, use `rst_data` directly per the content-type mapping (e.g. `.url` for `picture`/`video`/`audio`/`file`). For example, the `→ {"status":"ok","result":7}` at L251 is `rst_data` itself.

**End-to-end verification** (Service port):

```bash
# List installed directives
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;query,compact"}'

# Install tc-math (zero-dependency arithmetic evaluator)
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;install,tc-math"}'

# Call — effective immediately after install
curl -s -X POST http://localhost:28050/text-cli/cli \
  -d '{"prompt":"AI:tc-math;eval,1+2*3"}'
# → {"status":"ok","result":7}
```

### 1.5 Configuration

The text-cli runtime reads configuration from `$TEXT_CLI_HOME/service/config/text_cli.yaml`. On first startup, `start.bat` / `start.sh` automatically copies from the same-directory `text_cli.example.yaml` (if the file does not yet exist).

**Configuration priority**: environment variable > YAML value > built-in default.

```yaml
# $TEXT_CLI_HOME/service/config/text_cli.yaml
server:
  port: 28050               # Service HTTP port
  log_level: info            # Log level: debug | info | warning | error
  instructions_language: auto  # Default language for directive queries: zh | en | auto

auth:
  allow_anonymous: true      # Intranet mode: allow anonymous access (product default)
  service_token: ""          # Service Token shared secret (empty = no verification)
  count_calls: false          # Whether to record call audit logs

paths:
  # TEXT_CLI_HOME is injected by the startup script and cannot be configured here
  packages: ../packages      # Directive package source directory
  # map loop primitive (mode:"map") — path engine iterates the collection element by element
  map_enabled: false         # Whether to enable map capability (default off. map is an inbound capability; deployer must enable explicitly)
  map_max_iter: 100          # Single map fan-out upper bound (1–1000; exceeding the code hard cap is auto-clamped)

mcp:
  service_url: ""            # MCP outbound Service address
  port: 9020                 # MCP outbound FastMCP port

mesh:
  require_credentials: false  # Federated Mesh security: true = reject cross-hop when credentials missing, false (default) = degraded forwarding + mark _mesh_credential_degraded
  multi_hop_enabled: false    # Multi-hop following (default off; deployer enables explicitly)
  multi_hop_max_depth: 3      # Multi-hop depth upper bound (1–5; exceeding the code hard ceiling is auto-clamped)
```

**Key configuration items**:

| Config | Default | Description |
|--------|---------|-------------|
| `server.instructions_language` | `auto` | Query output language. `auto` = spec fields (English); `zh` / `en` = prefer the corresponding localized field. Caller can override with a trailing param: `AI:text-cli;query,zh` |
| `auth.allow_anonymous` | `true` | Intranet mode allows anonymous access by default. `allow_anonymous: true` applies only to a **fully trusted intranet/local machine**; whenever Service listens on `0.0.0.0` and is routable from an untrusted network, you must set `allow_anonymous: false` and fill `service_token`. For public exposure, always front it with an Endpoint (§1.3 + Chapter 4). After setting `false`, all requests must carry a Service Token |
| `auth.service_token` | `""` | Once set, requests with a Service-token header must match this secret. Combined with `allow_anonymous=false` for intranet auth |
| `paths.packages` | `../packages` | Directory scanned by `text-cli;install` for directive packages |
| `paths.map_enabled` | `false` | Controls whether `mode:"map"` takes effect. map is inbound; default off. Deployer sets `true` to enable. env: `MAP_ENABLED=true/false` |
| `paths.map_max_iter` | `100` | Upper bound on elements per map iteration. Adjust as needed by the deployer (≤1000 code hard cap). LLM need not be aware of this config. env: `MAP_MAX_ITER=<n>` |
| `mesh.require_credentials` | `false` | Federated Mesh security: `true` = reject cross-hop forwarding when credentials missing, `false` (default) = degraded forwarding + mark `_mesh_credential_degraded`. env: `REQUIRE_CREDENTIALS=true/false` |
| `mesh.multi_hop_enabled` | `false` | Controls whether proxy follows downstream `_mesh_redirect` for multi-hop forwarding. Default off — multi-hop takes the request path beyond the deployer's direct control and must be enabled explicitly. env: `MULTI_HOP_ENABLED=true/false` |
| `mesh.multi_hop_max_depth` | `3` | Maximum number of multi-hop follows. Adjust in yaml by the deployer (≤5 code hard ceiling). env: `MULTI_HOP_MAX_DEPTH=<n>` |

> Full configuration details are in the comments of the `service/config/text_cli.yaml` file inside the artifact.

### 1.6 Protocol (SDK)

All extracted artifacts ship with a zero-dependency Protocol SDK under the `protocol/` directory. No hand-written curl or envelope parsing — the SDK returns structured results directly. Full API reference is in [§4](#4-protocol).

**One-call CLI** (human):

```bash
# Shell (Linux/macOS)
echo "AI:tc-math;eval,2+3*4" | ./protocol/shell/call.sh

# PowerShell (Windows)
./protocol/shell/call.ps1 "AI:tc-math;eval,2+3*4"

# Query an async task
./protocol/shell/call.sh --task <task_id>
```

**SDK call** (AI Agent / script):

```python
# Python (zero-dependency, urllib standard library)
import sys; sys.path.insert(0, "protocol/python")
from call import call, discover, poll

result = call("AI:tc-math;eval,2+3*4")
print(result.data)  # → {"status":"ok","result":14}

directives = discover(search="weather")  # discover available directives
status = poll("task-123")                 # query an async task
```

```javascript
// Node.js (zero-dependency, built-in fetch)
const { call, discover } = require('./protocol/js/call');
const result = await call('AI:tc-math;eval,2+3*4');
console.log(result.data);
```

**Default endpoint**: `http://127.0.0.1:28050/text-cli/cli`. Overridable via `protocol/*/conf.json` or the environment variable `TEXT_CLI_ENDPOINT`.

---

## 2. Copilot

Copilot listens on `127.0.0.1:20260`, unreachable from external networks. Design intent: only people and programs on your local machine can drive it to operate your files, terminal, and credentials.

### 2.1 Self Package Management

```bash
curl -s -X POST http://localhost:20260/text-cli/cli \
  -d '{"prompt":"AI:text-cli;co-install,<package-name>"}'

curl -s -X POST http://localhost:20260/text-cli/cli \
  -d '{"prompt":"AI:text-cli;co-list"}'

curl -s -X POST http://localhost:20260/text-cli/cli \
  -d '{"prompt":"AI:text-cli;co-uninstall,<package-name>"}'
```

Copilot uses `import_module` to load directly (new package) or `_invalidate_package` + `import_module` (update) with dynamic method binding — effective immediately after install, no restart needed. The package model is a `*Handlers` mixin class + `_handle_*` methods (different from the Service's `@directive` decorator; the two are not interchangeable). (Deliberate design: Copilot holds local privileges, Service holds network reachability, so their trust tiers differ and their handler contracts are not shared; per SPEC §6.2.1/§6.2.2, privileged host packages must be installed to Copilot only via `co-install`.)

### 2.2 Whitelist Terminal Proxy

`copilot/config/auxiliary_config.json` controls the operations that may execute:

```json
{
  "operations": {
    "domain;action": {
      "level": "read | write",
      "handler": "_handle_xxx",
      "parameters": ["param1", "param2"]
    }
  }
}
```

Undeclared = execution refused. Auto-initialized from `auxiliary_config.example.json` on first startup. See Appendix A for details.

### 2.3 Skill Bridging

External skills can be bridged as text-cli directives. On package install, routes are inferred from handler.py and written to `skill_bridge_routes.json`. When called, Copilot executes the external skill via a subprocess, and the result is adapted into the text-cli standard envelope.

---

## 3. Service

Service is the core orchestration platform for all directive packages. The capabilities below are organized by cumulative tiers — your Service may be A3 (basic) or A9 (full). **All capabilities work independently without Copilot.**

### Part A: Package Management & Directive Discovery (≥A3)

#### 3.1 Installing Directive Packages

```
AI:text-cli;install,<package-name>
```

Install chain: validate schema → copy files → `import_module` loads the new module directly → handler is immediately available. **No Service restart needed after install.** (update/--force scenarios clear old registrations and module references first, then re-import, also effective immediately.)

```bash
# Force overwrite
curl ... -d '{"prompt":"AI:text-cli;install,tc-math,--force"}'

# Uninstall (schema + packages + handler_inits entries + SQL tables all cleaned)
curl ... -d '{"prompt":"AI:text-cli;uninstall,tc-math"}'
```

#### 3.2 Directive Discovery

`AI:text-cli;query` reads from `handlers/schema/` in real time (a full-directory scan per call, O(n)): for high-frequency calls, cache the result, or use the `/text-cli/skills` endpoint (§Part E Supplement) to pull a static list:

| Param | Effect |
|-------|--------|
| none | Grouped by package |
| `,json` | Structured JSON |
| `,compact` | One `domain;action` per line |
| `,python\|js\|mcp` | Filter by runtime |
| `,category,<name>` | By category |
| `,<keyword>` | Fuzzy search |
| `,collection` | Curated directive set |
| `,delta` | Change diff |

#### 3.3 Built-in Domains

| Domain | Capability |
|--------|-----------|
| `text-cli` | install / uninstall / export / export-all / packages / query / path / pro / sync-copilot |
| `key` | Key CRUD |
| `quota` | Quota management |
| `task` | Async task lifecycle |

> Superficially consistent with SPEC §6.2.1 meta-directives (8): install / uninstall / export / export-all / packages / query / path / pro; `sync-copilot` is an additional meta-directive for Service→Copilot linkage (see §3.18).

---

### Part B: Path Orchestration (≥A4)

Paths chain multiple directives into a pipeline. Data flows in one direction — the previous step's output is injected into subsequent steps via interpolation.

#### 3.4 Your First Path

Write to `$TEXT_CLI_HOME/paths/pythagorean.json`:

```json
{
  "id": "pythagorean", "type": "pipeline", "mode": "toolchain",
  "input_schema": {"type": "object", "properties": {"a": {"type":"number"}, "b": {"type":"number"}}},
  "steps": [
    {"id": "square", "instruction": "tc-math;eval,{input.a}**2+{input.b}**2", "output_as": "squared"},
    {"id": "root",   "instruction": "tc-math;eval,sqrt({squared.result})", "output_as": "hypotenuse"}
  ]
}
```

```bash
curl ... -d '{"prompt":"AI:text-cli;path,pythagorean,{\"a\":3,\"b\":4}"}'
# → {"status":"ok","result":5.0}
```

**Interpolation syntax**: `{input.xxx}` (call params) / `{varname.field}` (previous step output). Deep paths supported: `{geo.poi.0.name}`.

#### 3.5 Conditional Branching & Parallelism

```json
{"if": {"step": "calc", "field": "result", "equals": "5"}}
```

```json
{"id": "group", "mode": "parallel", "strategy": "all", "steps": [...]}
```

#### 3.6 Degradation Fallback

On step failure, automatically degrade per `degradation[]`. If all fail, returns `DEGRADE_EXHAUSTED`.

#### 3.7 Inline JSON & Registration

Send path JSON directly in the request body (auto-detected when starting with `{`). `--register` registers the path as a discoverable directive with `runtime=pipeline`.

#### 3.8 Cross-Node

`steps[].source` specifies a remote Service per step — different steps of one pipeline go to different machines.

#### 3.9 Iterative Loops (map)

`mode:"map"` executes the same sub-steps over each element of a collection. Data flows in one direction — the element is bound to `{item}`, and each round's last-step output is accumulated via `collect_as` into a list for downstream consumption.

> **Prerequisite**: map is off by default. Set `paths.map_enabled: true` in `service/config/text_cli.yaml` and restart first.

Write to `$TEXT_CLI_HOME/paths/summarize.json`:

```json
{
  "id": "summarize", "type": "pipeline",
  "steps": [
    {"instruction": "tc-json;query,select * from files", "output_as": "urls"},
    {
      "mode": "map", "items": "urls", "output_as": "summaries",
      "steps": [
        {"instruction": "tc-markdown;read,{item}", "output_as": "doc"},
        {"instruction": "ai;infer,摘要：{doc}", "output_as": "summary"}
      ]
    },
    {"instruction": "ai;infer,汇总：{summaries}", "output_as": "report"}
  ]
}
```

```bash
curl ... -d '{"prompt":"AI:text-cli;path,summarize"}'
# → reads each URL's document → AI summarizes → aggregates all summaries into a report
```

| Field | Required | Default | Description |
|-------|:---:|---------|-------------|
| `mode` | ✓ | — | Fixed `"map"` |
| `items` | ✓ | — | Collection variable name; value must be a list |
| `as` | ✗ | `"item"` | Element binding name; body uses `{item}` |
| `steps` | ✓ | — | Sub-step array |
| `collect_as` | ✗ | = `output_as` | Accumulation variable name |
| `on_error` | ✗ | `"break"` | `break` (circuit break) / `continue` (skip) |
| `concurrency` | ✗ | `"serial"` | `serial` / `parallel` |

> **Security note**: a single map fan-out is limited by `paths.map_max_iter` (default 100, cap 1000). Exceeding it returns `INVALID_PARAMS`; raise the yaml config. Nested map is forbidden (no map inside a map).

---

### Part C: State Persistence (≥A6)

#### 3.9 Key Management

```
AI:key;register,<svc>,<v1>,<v2>,<type>
AI:key;list
AI:key;get,<svc>
AI:key;revoke,<svc>
```

> The security boundary of `key;get` is in §3.19.

#### 3.10 Task Management

| Mode | Trigger | Executor | Poll |
|------|---------|----------|------|
| managed | `--async` | Service `asyncio.create_task` | `GET /text-cli/tasks/{id}` |
| tracked | `task;track` | External service | `task;status` poll on demand |

Task states: 5 terminal states total: `pending` → `running` → `done` / `error` / `cancelled`. `task;cancel` sets `pending`/`running` tasks to the `cancelled` terminal state (unrecoverable). On Service restart, residual `running` tasks are marked `error`.

```bash
# managed
curl ... -d '{"prompt":"AI:tc-math;eval,1+2*3,--async"}'
# → {"status":"pending","task_id":"..."}
curl http://localhost:28050/text-cli/tasks/<task_id>

# tracked
curl ... -d '{"prompt":"AI:task;track,id-001,hello,world,user"}'
curl ... -d '{"prompt":"AI:task;status,id-001"}'
curl ... -d '{"prompt":"AI:task;cancel,id-001"}'
```

#### 3.11 Quota Management

```bash
curl ... -d '{"prompt":"AI:quota;register,my-svc,day,10"}'
curl ... -d '{"prompt":"AI:quota;check,my-svc"}'       # atomic consume
# → {"status":"ok","remaining":9}
# exhausted → {"status":"stop"}  # degradation chain auto-switches
curl ... -d '{"prompt":"AI:quota;reset,my-svc"}'
curl ... -d '{"prompt":"AI:quota;unregister,my-svc"}'
```

`amount` defaults to 1 (by count); pass a numeric value for char/byte-based. cycle: `day`/`week`/`month`/`year`/`forever`.

#### 3.12 Cross-Layer Composition: Task + Path

The task-manager (Part C) and path-engine (Part B) are loosely coupled via the `domain;action` protocol — the task layer only manages the SQLite lifecycle, the path layer only manages step orchestration. A tracked task does not distinguish whether the target is an atomic directive or a path; registration is identical.

**Example**: register the Pythagorean path as an async tracked task.

1. Prepare the path file `$TEXT_CLI_HOME/paths/pythagorean-async.json` (same as 3.4, add `timeout: 5000` to each step)

2. Register the tracked task:

```bash
curl ... -d '{"prompt":"AI:task;track,path-001,text-cli,path,pythagorean-async,{\"a\":6,\"b\":8}"}'
# → {"status":"ok","task_id":"path-001","mode":"tracked"}
```

3. Poll at multiple time points — in tracked mode the task does not execute automatically; `state` stays `pending`:

```bash
curl ... -d '{"prompt":"AI:task;list"}'
# → [{"task_id":"path-001","domain":"text-cli","action":"path","state":"pending"}]

curl ... -d '{"prompt":"AI:task;status,path-001"}'
# → {"state":"pending","params":{"mode":"tracked","poll":{"domain":"text-cli","action":"path","params":["pythagorean-async",{"a":6,"b":8}]}}}

curl ... -d '{"prompt":"AI:task;cancel,path-001"}'
# → {"cancelled":true}
```

**Design point**: the task-manager does not care about the path-engine's internal structure — it only needs `domain=text-cli`, `action=path`. The path's `timeout` field is passed across layers as scheduling metadata, reserving execution-budget info for managed mode. This is text-cli's core philosophy: **each layer does one thing, and layers interface through protocol, not interfaces**.

---

### Part D: MCP Bridging (≥A7)

MCP (Model Context Protocol) bridging is an **optional capability** of tier A7 — A8 aggregation and A9 facade work completely without MCP. MCP being unavailable does not affect path orchestration, quota management, aggregate degradation, or any other function.

> text-cli's MCP bridge is not bound to a specific CLI — currently only [mcporter](https://github.com/weihai-limh/mcporter) is supported; other MCP clients can be added on demand in the future.

#### 3.13 Inbound Capability Dependencies

MCP directive packages (`runtime:"mcp"`) are **always installable and queryable** — no external dependency required. But actually calling MCP tools needs mcporter as the protocol execution layer.

| Dependency satisfaction | mcporter | install / query | dispatch (call MCP tool) | A8/A9 other capabilities |
|------|:--:|:--:|------|:--:|
| No mcporter | — | ✅ installable, visible | ❌ fallback proxy, returns `ERR_NOT_FOUND` | ✅ completely unaffected |
| mcporter installed | ✅ | ✅ | ✅ full chain | ✅ |

#### 3.14 Obtaining & Installing mcporter

**Step 1: Get the source.**

Clone or download the tgz package from the [mcporter repo](https://github.com/weihai-limh/mcporter):

```bash
git clone https://github.com/weihai-limh/mcporter.git
# or download tgz: https://github.com/weihai-limh/mcporter/releases
```

**Step 2: Choose the mcporter version per your Node.js version.**

| Node.js version | mcporter version | Description |
|------|:--:|------|
| ≥20, <24 | **0.9.0** | Stable, transport uses `http` |
| ≥24 | **0.12.3** | Supports `streamable-http` transport |

> Version syntax differences:
> - 0.9.0: `mcporter config add <name> --transport http --url <url>`
> - 0.12.3: `mcporter add <name> --transport streamable-http --url <url>`

**Step 3: Extract and run (no `npm install -g` needed).**

The tgz package contains a prebuilt `dist/cli.js` that runs directly:

```bash
tar -xzf mcporter-0.9.0.tgz
node package/dist/cli.js --version
# → 0.9.0
```

It is recommended to create a wrapper script (`.bat` on Win, shell on Linux/macOS) pointing to `node <dist/cli.js>`, then put the wrapper in PATH.

**Step 4: Configure the MCP server.**

```bash
# 0.9.0
mcporter config add github --transport http --url https://api.github.com/mcp
# 0.12.3
mcporter add github --transport streamable-http --url https://api.github.com/mcp

# Verify
mcporter list
mcporter list github
```

#### 3.15 Service-Side Configuration

After installing mcporter, Service needs two configs declaring how to call it:

**mcporter.json** — specifies the executable path (three-level fallback: explicit config → `text_cli_modules/bin/` → PATH):

```json
{"bin": "<path-to-mcporter-wrapper>", "cwd": "<mcporter-package-dir>"}
```

**routing_preferences.json** — declares which directives go through the MCP pipeline:

```json
{"preferences": {"comcp-github;search_repos": "mcp"}}
```

#### 3.16 End-to-End Verification

```bash
# Install the MCP package
curl ... -d '{"prompt":"AI:text-cli;install,tc-mcp-github"}'

# Call — full chain:
# decide_backend → routing_preferences → "mcp"
# → call_mcp_tool → subprocess.run(mcporter call server.tool --args '{...}')
curl ... -d '{"prompt":"AI:comcp-github;search_repos,text-cli"}'
```

#### 3.17 Outbound Exposure

`mcp_exposure.json` declares the directives exposed outward. FastMCP (:9020) reads this list to dynamically generate MCP tools — any MCP client can discover and call text-cli directives. The bridge is bidirectional.

---

### Part E: Linkage (Optional)

The capabilities below are not needed when Service runs standalone — they take effect only when you also deploy Copilot or Endpoint.

#### 3.18 Service → Copilot Transparent Proxy

```bash
curl ... -d '{"prompt":"AI:text-cli;sync-copilot"}'
```

`sync-copilot` discovers Copilot directives → generates `proxy_routes.json`. After that, requests to Service that miss locally are automatically forwarded to Copilot — the caller is unaware of who is behind it.

#### 3.19 Key Security Boundary

`key;get` is handled by Copilot's `KeyRouter` (not directly exposed by Service). It requires `copilot/config/key_routing.json` to declare how to fetch:

```json
{"service-a": {"source": "env", "var": "KEY"}, "service-b": {"source": "service"}}
```

`source: "env"` reads from an environment variable; `source: "service"` delegates to Service SQLite. Undeclared keys return `not_found` — a security boundary that prevents Copilot from exposing keys without limit. See Appendix F for details.

#### 3.20 Deploying Behind an Endpoint

Endpoint is deployed at the public edge; Service is on the intranet. After `A3_BACKENDS` points to the Service address, Endpoint passes requests through and attaches a three-layer security defense (see Chapter 4).

### Part E Supplement: External Exposure (Skills)

Service exposes the registered directive list to Endpoint via the `/text-cli/skills` endpoint. This is the sole data source for Endpoint's aggregated backend directive table.

- Paths registered via `path,<name>,--register` are automatically included in skills
- After a directive package is installed, its directives become automatically visible (effective immediately with hot-reload)
- Format: `{skill_id: {visibility, type, domain, action, ...}}`

Before deploying Endpoint, ensure Service is started and the target paths/directive packages are registered — Endpoint pulls the directive table from this endpoint at startup.

```bash
# Verify the skills endpoint
curl http://localhost:28050/text-cli/skills
# → {"branch-demo": {"visibility":"public","type":"pipeline",...}}
```

---

### Part F: Facade & Aggregation (≥A8/A9)

#### 3.21 Short-Name Mapping (`text-cli;pro`)

```bash
curl ... -d '{"prompt":"AI:text-cli;pro,calc,1+2+3"}'
# → {"status":"ok","result":6}
```

`service/config/pro_registry.json` (Appendix E) defines the short-name → target mapping. Two target types: `aggregate` (atomic directive) and `path` (path engine).

#### 3.22 Aggregate Degradation Chain

`aggregate/map.json` (Appendix D) defines the multi-provider degradation order. Quota exhaustion auto-switches, transparent to the caller. Explicitly specify provider: `AI:map;geocode,北京,gd-map`.

---

## 4. Protocol

Protocol is text-cli's zero-dependency consumer SDK, distributed with all packages — after extracting an artifact, the `protocol/` directory is the complete SDK. No install, no dependency configuration; a single script calls the text-cli service.

### 4.1 Directory Structure & Acquisition

All artifacts (Copilot / Service / Endpoint) zip/tar.gz contain a root-level `protocol/` directory:

```
text-cli-A9-v0_1_1.zip
├── text-cli-A9-v0_1_1/    ← runtime
├── packages/               ← directive package source
└── protocol/               ← Protocol SDK
    ├── python/
    │   ├── call.py          ← Python SDK entry
    │   └── conf.json        ← endpoint config
    ├── js/
    │   ├── call.js          ← JavaScript SDK entry
    │   └── conf.json
    └── shell/
        ├── call.sh          ← Bash CLI
        ├── call.ps1         ← PowerShell CLI
        └── conf.json
```

### 4.2 Configuration & Endpoints

**Default endpoint**: `http://127.0.0.1:28050/text-cli/cli`.

The four-language implementations declare defaults via `conf.json`:

```json
{
  "endpoint": "http://127.0.0.1:28050/text-cli/cli",
  "service_token": "",
  "access_token": ""
}
```

**Configuration priority (high to low)**:

```
1. Parameters passed at call time (call()'s endpoint/token parameters)
2. Environment variables (TEXT_CLI_ENDPOINT / TEXT_CLI_SERVICE_TOKEN / TEXT_CLI_ACCESS_TOKEN)
3. conf.json (same directory as the script)
4. Built-in default (127.0.0.1:28050)
```

**Direct / via Endpoint modes**:
- Direct to Service: only set `service_token`, leave `access_token` empty
- Via Endpoint: `endpoint` points to :29050, and set both `access_token` and `service_token`

### 4.3 Command-Line CLI

**Shell** (`protocol/shell/call.sh`) — curl + python3, good for pipelines:

```bash
echo "AI:tc-math;eval,2+3*4" | ./protocol/shell/call.sh
# → {"status":"ok","result":14}

echo "AI:weather;query,Beijing" | ./protocol/shell/call.sh
# → {"city":"Beijing","temp":22}

# Query an async task
./protocol/shell/call.sh --task <task_id>
# → {"state":"running","progress":"50%"}
```

**PowerShell** (`protocol/shell/call.ps1`):

```powershell
./protocol/shell/call.ps1 "AI:tc-math;eval,2+3*4"
./protocol/shell/call.ps1 -Task "task-abc123"
```

### 4.4 Python SDK

(`protocol/python/call.py`, zero-dependency, urllib implementation)

```python
import sys; sys.path.insert(0, "protocol/python")
from call import call, discover, poll, wait
```

#### call() — Synchronous call

```python
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"status":"ok","result":14})

# Override endpoint and Token per call
result = call(
    "AI:weather;query,Beijing",
    endpoint="http://192.168.1.2:28050/text-cli/cli",
    service_token="sk-abc123",
)
```

#### discover() — Directive discovery

```python
# Full discovery (cached after first HTTP call)
all_directives = discover()

# Filtered search
weather = discover(search="weather")
python_pkgs = discover(runtime="python")

# Force refresh cache
fresh = discover(force_refresh=True)
```

Result format is `[{domain, action, usage, runtime, description, ...}]`.

#### poll() / wait() — Async tasks

See [§4.7](#47-asynchronous-tasks).

### 4.5 JavaScript SDK

(`protocol/js/call.js`, zero-dependency, built-in fetch)

```javascript
const { call, discover, poll, wait } = require('./protocol/js/call');

const result = await call('AI:tc-math;eval,2+3*4');
console.log(result.data);  // → {"status":"ok","result":14}

const directives = await discover({ search: 'weather' });

// Pass Token when connecting to Endpoint
const r = await call('AI:text-cli;query', null, null, {
  endpoint: 'http://localhost:29050/text-cli/cli',
  accessToken: 'at-xxx',
  serviceToken: 'sk-abc123',
});
```

API equivalent to Python: `call()` / `discover()` / `poll()` / `wait()`, returning `DirectiveResult`.

### 4.6 DirectiveResult Reference

All SDKs uniformly return a `DirectiveResult` object. The caller judges status via fields, no manual HTTP-envelope parsing.

| Field | Type | Description |
|-------|------|-------------|
| `ok` | `bool` | Whether the call succeeded (`rst_err` empty and not async) |
| `data` | `Any` | Response data — `rst_data` carried directly, no longer nested via `.text` |
| `rtype` | `str` | Response type: `"text"` / `"picture"` / `"video"` / `"audio"` / `"file"` |
| `err_code` | `str` | Error code. Empty string on success |
| `directive` | `str` | The original directive of this call (for logging and debugging) |
| `is_async` | `bool` | Whether it is an async task. When `True`, use `poll()` / `wait()` to get the final result |

```python
result = call("AI:weather;query,Beijing")
if not result.ok:
    print(f"Error [{result.err_code}]: {result.data}")
    return
print(f"OK: {result.data}")
```

### 4.7 Asynchronous Tasks

Long tasks (video conversion, ASR, etc.) are triggered with `--async`. The caller has two ways to wait:

**poll() — single query**:

```python
status = poll("task-abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"step 3/8"})
```

**wait() — exponential backoff wait**:

```python
# Auto-poll until done, with on_status callback each round
final = wait("task-abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})

# Custom backoff params (initial 2s, max 30s)
final = wait("task-abc123", initial=2.0, maximum=30.0)
```

JavaScript equivalent: `poll("task-abc123")` / `await wait("task-abc123")`.

### 4.8 Usage Examples

```python
from call import call, discover, poll, wait

# 1. Discover directives
dirs = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>"}]

# 2. Synchronous call
r = call("AI:tc-math;eval,2+3*4")
assert r.ok and r.data["result"] == 14

# 3. Async call + wait for completion
r = call("AI:ffmpeg;convert,video.mp4,--async")
if r.is_async:
    final = wait(r.task_id)    # exponential backoff auto-poll
    print(final.data)

# 4. Error handling
r = call("AI:nonexistent;action")
if not r.ok:
    print(f"[{r.err_code}] {r.data}")  # → [ERR_NOT_FOUND] ...
```

---

## 5. Endpoint

Endpoint is an independent bypass gateway, deployed at the public edge, with Service on the intranet. The caller requests Endpoint (:29050); after auth it passes through to Service (:28050).

### 5.1 Deployment

Artifact `text-cli-endpoint-python-v*`:

```powershell
# Win (PowerShell)
Expand-Archive text-cli-endpoint-python-v*.zip -DestinationPath .
cd text-cli-endpoint-python-v*
pip install fastapi uvicorn httpx pydantic
.\start-endpoint.bat
# Stop: .\end-endpoint.bat
```

```bash
# Linux
tar -xzf text-cli-endpoint-python-v*.tar.gz
cd text-cli-endpoint-python-v*
pip install fastapi uvicorn httpx pydantic
./start.sh
```

```bash
# Docker
docker run -d -p 29050:29050 text-cli-endpoint:latest
```

### 5.2 Configuration

| Variable/File | Default | Description |
|------|--------|-------------|
| **`backends.yaml`** (recommended) | — | Multi-backend definition file; each backend is self-contained with url/token/st_prefix |
| `A3_BACKENDS` | — (required) | Service address, comma-separated for multiple backends (fallback when no yaml) |
| `ACCESS_TOKEN_REQUIRED` | `true` | Whether to enforce Bearer Token auth |
| `ENDPOINT_BASE_URL` | `http://localhost:29050` | Own address, used to rewrite external Schema URL |
| `FORWARD_TIMEOUT` | `30` | Pass-through timeout (seconds) |

`backends.yaml` format — each backend self-contained; adding/removing does not affect adjacent lines:

```yaml
backends:
  - url: http://service1:28050
    token: ""        # optional, passed through as this backend's Service Token
    st_prefix: ""    # optional, this backend's ST prefix
  - url: http://service2:28050
```

When `backends.yaml` does not exist, it auto-falls back to the `A3_BACKENDS` environment variable. `start-endpoint.bat` shows the configuration status at startup.

Endpoint's directive table is aggregated from Service's `/text-cli/skills` — ensure Service is started and paths/directive packages are registered before deploying Endpoint (see Service §Part E Supplement).

### 5.3 Three-Layer Security Defense

| Layer | Mechanism | On exceed |
|:--:|------|:--:|
| 1 | IP blocklist (CIDR) | 403 |
| 2 | Sliding-window rate limit (default POST 1000/h, GET 10000/h, overridable via `RATE_LIMIT_PER_HOUR`) | 429 |
| 3 | Token auth (Access Token + Service Token) | 401 |

### 5.4 Observability

SQLite `data/textcli.db`:

| Table | Content |
|------|---------|
| `call_logs` | Per-request log (request_id / domain / action / status / response_time_ms) |
| `daily_stats` | Daily aggregation (domain + action + date / call_count / success_count) |
| `access_tokens` | Token management (token_prefix / scopes / quota) |

### 5.5 Pass-Through

Endpoint does not execute directives — after auth it forwards directly to `A3_BACKENDS`. The caller uses the same protocol format as Service, only the port changes from 28050 to 29050:

```bash
curl -X POST http://localhost:29050/text-cli/cli \
  -d '{"prompt":"AI:text-cli;path,branch-demo"}'
```

---

## Appendices

### A. Whitelist Configuration (`auxiliary_config.json`)

```json
{
  "server": {"host": "127.0.0.1", "port": 20260, "token": null},
  "security": {
    "path_whitelist": ["${TEXT_CLI_HOME}/", "${HOME}/"],
    "operations": {
      "domain;action": {
        "level": "read | write",
        "handler": "_handle_xxx",
        "parameters": ["param1", "param2"],
        "returns": "expected format"
      }
    }
  }
}
```

### B. Path Declaration Spec

```json
{
  "id": "unique-id", "type": "pipeline", "mode": "toolchain",
  // mode: "toolchain"(serial, default) | "parallel"(parallel) | "map"(iterative loop, A4+, needs yaml enabled)
  "default_source": "http://192.168.1.2:28050/text-cli/cli",
  "input_schema": {"type": "object", "properties": {"p": {"type": "number"}}},
  "steps": [{
    "id": "s1", "instruction": "domain;action,{input.p}",
    "output_as": "v", "timeout": 5000,
    "if": {"step": "prev", "field": "status", "equals": "ok"},
    "degradation": [{"id": "fb", "instruction": "domain;fallback", "timeout": 10000}],
    "source": "http://192.168.1.3:28050/text-cli/cli"
  }]
}
```

Supports inline JSON (send `{...}` directly in the request body, no file needed).

### C. MCP Configuration

**routing_preferences.json**:
```json
{"preferences": {"comcp-github;search_repos": "mcp"}}
```

**mcporter.json**:
```json
{"bin": "<path>", "cwd": "<dir>"}
```

**mcp_exposure.json** (outbound):
```json
["tc-math;eval", "web-utils;fetch"]
```

**service-descriptor.json** (required for MCP packages):
```json
{"mcp_server": "http://localhost:8080/mcp", "name": "my-svc"}
```

### D. Aggregate Routing Table (`aggregate/map.json`)

```json
{
  "id": "map", "domain": "map",
  "default": ["provider-a", "provider-b"],
  "providers": {
    "provider-a": {"geocode": "provider-a;geocode"},
    "provider-b": {"geocode": "provider-b;geocode"}
  }
}
```

### E. Facade Registry (`pro_registry.json`)

```json
{
  "calc": {"type": "aggregate", "domain": "tc-math", "action": "eval"},
  "pythag": {"type": "path", "path": "pythagorean"}
}
```

### F. Key Routing (`key_routing.json`)

```json
{
  "svc-a": {"source": "env", "var": "KEY"},
  "svc-b": {"source": "service"},
  "local": {"source": "env", "value": "sk-xxx"}
}
```

Copilot's `KeyRouter` reads this config to decide the key source. Located in `copilot/config/`.

### G. Environment Variable Reference

| Variable | Product | Description |
|------|:--:|------|
| `TEXT_CLI_HOME` | Service | Data root directory |
| `TEXT_CLI_PACKAGE_SOURCE_DIRS` | Service | Package source directory |
| `A3_BACKENDS` | Endpoint | Backend Service address |
| `ACCESS_TOKEN_REQUIRED` | Endpoint | Token auth switch |
| `RATE_LIMIT_PER_HOUR` | Endpoint | Rate limit |
| `IP_BLACKLIST` | Endpoint | IP blocklist (CIDR) |
| `TEXTCLI_SERVICE_URL` | MCP outbound | Service address |
| `MCP_PORT` | MCP outbound | FastMCP port |

### H. Configuration File Index (Source-of-Truth Responsibilities)

text-cli's runtime state is spread across several JSON/YAML files. The table below annotates "who writes, who reads, whether authoritative" for each, to help troubleshoot multi-config drift:

| File | Writer | Reader | Responsibility |
|------|--------|--------|----------------|
| `handlers/schema/` | `text-cli;install` | `text-cli;query` real-time scan | Directive package Schema (full-directory scan per query, see §3.2) |
| `proxy_routes.json` | `sync-copilot` | Service proxy forward | Copilot directive routing |
| `/text-cli/skills` endpoint | Service runtime | Endpoint aggregation | Exposed directive list (static pull, §Part E Supplement) |
| `skill_bridge_routes.json` | Auto-inferred on package install | Copilot | External skill bridge routing |
| `routing_preferences.json` | User config | dispatch | Specify directives going through MCP pipeline |
| `pro_registry.json` | User config | `text-cli;pro` | Short-name → target mapping |
| `aggregate/map.json` | User config | Aggregate degradation | Multi-provider degradation order |
| `key_routing.json` | Copilot config | `KeyRouter` | Key source declaration (deny by default, §3.19) |

> This is a known implementation-layer characteristic (multiple JSON files each a source of truth); the document presents it faithfully; cross-file consistency is maintained by the deployer.

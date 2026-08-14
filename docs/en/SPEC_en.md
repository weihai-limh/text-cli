# text-cli Protocol Specification v1.3.2

> **Language note:** This English text is a translation of the normative Chinese specification (`docs/SPEC_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.

The protocol turns 'natural language' into a stable semantic space through 'network' and 'syntax'. Within a stable semantic space:

- A capability provider can expose capabilities such as 'software service / experience service / time service' to the outside world through a 'runtime' that supports the 'protocol'.
- A capability caller uses 'natural language' through the protocol to drive the 'runtime' to invoke the capability stored by the 'capability provider'; both parties complete the enabling based on the protocol.
- As long as one can output 'natural language' over the network and has permission to use the corresponding 'semantic space', whether human or AI, one can obtain services through the 'semantic space'.
- The protocol ecosystem is independent of any project ecosystem. The protocol primitive is natural language, and the protocol ecosystem is the natural-language ecosystem.

### Reading Conventions

This specification uses the following formats to distinguish information at different levels:

- **Prose**: protocol requirements — all protocol-compliant implementations must satisfy them.
- **> Blockquote**: implementation reference — non-normative; provides examples or suggestions for context, and does not constitute a compliance constraint.
- **"optional" annotations in tables**: that field/behavior is not mandatory at the minimum baseline compliance.
- **"is an implementation" / "the protocol does not prescribe"**: marks the boundary of the protocol — at that point the mechanism is decided by the runtime; the protocol only defines the principle.

### Chapter Overview

| Chapter | Audience | Description |
|---------|----------|-------------|
| §1 Directive Format Specification | Caller / Capability Provider | Protocol communication primitive: directive format, request/response envelope, error codes, capability discovery |
| §2 Auth & Quota | Capability Provider / Endpoint Developer | Identity verification, quota protection, federated credentials |
| §3 Schema Metadata Specification | Capability Provider | How to declare directive packages: package-level and directive-level field definitions |
| §4 Path Protocol | Capability Provider | How to orchestrate multi-step directive sequences (pipeline) |
| §5 Aggregate Directives | Capability Provider | Multi-provider degradation and domain-level entry |
| §6 Runtime | Runtime Developer | Mechanism requirements for standard runtime vs bypass runtime |
| §7 Multilingual | Capability Provider | Localization declaration and response of directives |
| §8 Integration Endpoint | Endpoint Developer | Pure pipe: auth, routing, pass-through |

---

## 1. Directive Format Specification

### 1.1 Basic Structure

```
AI:<domain>;<action>,<param1>,<param2>,...
指令:<domain>;<action>,<param1>,<param2>,...
```

- **Current two prefixes**: `指令:` (Chinese entry, retained during transition until 1.5.0) and `AI:` (long-term spec). The two are equivalent.
- **domain**: namespace; canonical name is ASCII; aliases are unrestricted in character set, supporting multilingual via aliases.
- **action**: verb; canonical name is ASCII; aliases are unrestricted, supporting multilingual via aliases.
- **params**: comma-separated, fixed order. The trailing param may be free text (including commas). Params may contain JSON arrays/objects with commas — the implementation layer tracks bracket depth `{}` `[]` and string quotes `""`, splitting only at commas whose depth is 0.

> The canonical name (`domain`/`action`) is the sole routing primary key and is always ASCII; all non-ASCII forms (including Chinese/other-language aliases) must be normalized back to the canonical name by the runtime via alias mapping before they may participate in routing and cross-runtime deduplication. Aliases are equal, bidirectional, and case-insensitive, but are merely access entries to the canonical name and do not change the routing primary key.

### 1.2 HTTP-based Request and Response

> All HTTP endpoints are uniformly under the `/text-cli/` prefix. Nodes conforming to this protocol all use this path convention.

#### 1.2.1 Request Structure

```
POST /text-cli/cli
Content-Type: application/json
Service-token: <token>

{"prompt": "AI:domain;action,param1,param2"}
```

#### 1.2.2 Response Structure

```json
{
  "rst_types": "text",
  "rst_data": {"status": "ok", "result": 14},
  "rst_err": ""
}
```

- `rst_types`: reflects the response type. Default is `"text"`. When the handler returns a dict containing the `pray_rst_types` key, the skeleton promotes its value to this field. Values: `text` / `picture` / `video` / `audio` / `file`.
- `rst_data`: the JSON object returned by the handler, carried directly by the skeleton — no longer nested as `{"text": "..."}`. The caller reads `rst_data` directly.
- `rst_err`: structured error field. Empty string `""` means success; non-empty means failure. Values see §1.2.8.

> Promotion keys (such as `pray_rst_types`) are consumed by the skeleton when sealing the envelope and stripped from `rst_data`; the `rst_data` received by the caller contains no skeleton-internal convention keys.

**Content-type mapping** (by `rst_types` value):

| `rst_types` | Caller behavior |
|------------|-----------------|
| `"text"` | Display `rst_data` directly |
| `"picture"` | Render `rst_data.url` |
| `"video"` | Render `rst_data.url` |
| `"audio"` | Render `rst_data.url` |
| `"file"` | Render `rst_data.url` |

Examples:

```json
// plain text
{"rst_types":"text","rst_data":{"status":"ok","result":14},"rst_err":""}
// renderable media
{"rst_types":"picture","rst_data":{"status":"ok","url":"https://example.com/photo.jpg","alt":"example"},"rst_err":""}
// structured metadata
{"rst_types":"text","rst_data":{"status":"ok","lon":122.1,"lat":37.5},"rst_err":""}
```

Async directives return a task_id:

```json
{"rst_types": "text", "rst_data": {"status": "pending", "task_id": "asr-12345"}, "rst_err": ""}
```

The caller queries task status via `GET /text-cli/tasks/{task_id}` (see §1.2.6).

#### 1.2.3 GET Emergency Channel

```
GET /text-cli/cli?prompt=<URL-encoded directive>
```

Disabled by default. The capability provider explicitly enables it. No authentication; use at your own risk.

#### 1.2.4 Skills Endpoint

```
GET  /text-cli/skills          → public skill list (controlled by service_manifest whitelist)
```

**Skill exposure control**: the service declares the externally exposed directive whitelist via `service_manifest.json`:

```json
{"public_directives": ["map;geocode", "web;search", "weather;query"]}
```

Empty whitelist = expose all; when content exists, only the listed entries are exposed. The `/skills` endpoint filters output accordingly.

#### 1.2.5 Health Check

```
GET /text-cli/health
```

The public layer returns `{status, body, version, spec_version, public_skills}`. The auth layer returns the full `capabilities`.

> **Runtimes that serve across terminals SHOULD declare the subset of mechanisms they carry in `mechanism`** (e.g. `{"mechanism": ["directive_execution", "discovery", "async"]}`) so callers can programmatically perceive the runtime's capability boundary. Runtimes that do not serve across terminals have no such obligation — the caller is the user themselves, and there is no information asymmetry.
>
> Mechanism identifier vocabulary (stable identifiers, referenced by `mechanism`): `directive_execution` (directive execution), `package_lifecycle` (package install/uninstall), `discovery` (directive discovery), `path` (path orchestration), `async` (async task scheduling), `aggregate` (aggregate degradation), `mesh` (federated Mesh), `bridge` (protocol bridge), `facade` (facade abstraction).

#### 1.2.6 Async Task Query

```
GET /text-cli/tasks/{task_id}
```

**Success response**:

```json
{
  "status": "ok",
  "task": {
    "task_id": "task-0001",
    "domain": "domain",
    "action": "action",
    "state": "pending|running|done|error|cancelled",
    "result": {"..."},
    "progress": "step 3/8"
  }
}
```

**Task not found**: `404` + `{"rst_err": "not_found"}`

> Current task status only supports polling. For long-running tasks, the caller polls with exponential backoff. **(optional extension)** The runtime MAY accept a `callback_url` at task creation and notify via **webhook (one-way HTTP POST)** upon completion; whether to implement webhook is decided by the runtime, not mandated by the standard runtime.
>
> In synchronous calls, quota exhaustion is expressed as `status:"stop"`, triggering the aggregate degradation chain. For async tasks (polled via `tasks/{id}`), when quota exhaustion is encountered during execution, its `state` SHOULD be recorded as the terminal state `error` with reason `quota_exhausted`; the consumer decides whether to switch providers and resend based on that reason, rather than relying on the synchronous degradation chain (the async context has left the original caller's synchronous degradation path).
>
> **`cancelled` terminal state** (the fifth state): `task;cancel,<task_id>` marks `pending`/`running` tasks as `cancelled`. cancelled is a terminal state and cannot be restored to other states.
>
> **Restart residual handling**: on restart, the runtime SHOULD mark all residual `running` tasks as `error` with reason `service_restarted`.

#### 1.2.7 Directive Discovery

When a 'runtime' supports 'directive discovery', it should follow these requirements:

##### Trigger Forms

| Directive | Meaning |
|----------|---------|
| `AI:text-cli;query` | Full plain text (human-readable) |
| `AI:text-cli;query,json` | **Machine-readable JSON** (core of this contract) |
| `AI:text-cli;query,compact` | Minimal (one `domain;action` per line) |
| `AI:text-cli;query,python\|js\|mcp\|cloudbase` | Filter by runtime |
| `AI:text-cli;query,category[,<name>]` | Filter by category / list categories |
| `AI:text-cli;query,<keyword>` | Keyword search |
| `AI:文本指令;查询` | Chinese alias (equivalent to `AI:text-cli;query`) |

A language override may be appended to the trailing param: `,zh` / `,en` (affects text/minimal mode only; JSON mode returns all locale variants, see §7.2).

> Implementation reference: runtime filtering (`,python|js|mcp|cloudbase`), category filtering, and keyword search are all **optional capabilities** — a single-language runtime may not support filtering or may return only its own directives, which does not affect minimum baseline compliance.

##### Response Envelope

The query response **reuses the §1.2.2 envelope** and introduces no new fields:

```
{ "rst_types": "text", "rst_data": <discovery data>, "rst_err": "" }
```

- Success: `rst_err` is the empty string.
- Failure: see §1.2.8; errors travel the `rst_err` main signal and must not be stuffed into `rst_data`.

##### Machine-readable response canonical (`,json` mode)

`rst_data` structure:

```json
{
  "directives": [
    {
      "domain": "web-utils",
      "domain_zh": "网络工具",
      "action": "get_public_ip",
      "action_zh": "获取公网IP",
      "usage": "web-utils;get_public_ip",
      "usage_zh": "网络工具;获取公网IP",
      "params": ["target"],
      "description": "Return caller public IP",
      "description_zh": "返回调用方公网IP",
      "package": "web-utils",
      "runtime": "js"
    }
  ]
}
```

> Implementation reference: the example above is the **full form**, containing all optional enhancement fields. The minimum baseline compliant response only needs each directive to contain `domain`+`action`; other fields may be absent (the consumer falls back to canonical or ignores them).

> **usage prefix convention**: the `usage` / `usage_zh` fields do **not** contain the `AI:` / `指令:` prefix — they are the **trunk part** of a callable directive (`domain;action,params`), and the caller must prefix them before issuing (e.g. `AI:` + `usage`). All section examples in this document (§1.2.7 / §3.1 / §7.2) uniformly follow this convention.

##### Field-level Definitions

| Field | Type | Level | Source | Description |
|-------|------|-------|--------|-------------|
| `directives` | `array` | **Mandatory** | Fixed top-level key | Directive list container; key name is fixed as `directives` |
| `domain` | `string` | **Mandatory** | Package schema `directives[].domain` | Canonical (English) domain, one of the call primitives |
| `action` | `string` | **Mandatory** | Package schema `directives[].action` | Canonical action, one of the call primitives |
| `usage` | `string?` | Optional | Package schema `directives[].usage` | Callable directive source text (derivable from `domain`/`action`) |
| `package` | `string?` | Optional | Package schema `id` (flattened promotion) | Package identifier promotion, for grouping/dedup; a single-language runtime may omit |
| `runtime` | `string?` | Optional | Package schema `runtime` (flattened promotion) | Runtime identifier promotion; **not protocol-mandatory** (protocol does not specify runtime) |
| `domain_zh` | `string?` | Optional | Package schema `domain_zh` | Chinese domain alias (present if exists) |
| `action_zh` | `string?` | Optional | Package schema `action_zh` | Chinese action alias |
| `usage_zh` | `string?` | Optional | Package schema `usage_zh` | Chinese directive source text |
| `description` | `string?` | Optional | Package schema `description` | Canonical description |
| `description_zh` | `string?` | Optional | Package schema `description_zh` | Chinese description |
| `params` | `array?` | Optional | Package schema `directives[].params` | **Pass through as-is** |

**Layering rules:**

- **Mandatory baseline (any runtime must pass):**
  - Each directive **must** contain `domain` and `action` — these two are the call primitive `AI:domain;action`; having them makes it callable.
  - The `directives` container key name is fixed; the consumer reads via `rst_data["directives"]` and must not assume a bare array.
  - The internal `_package` nested object **must be stripped** and must not appear in the response.
  - Errors travel the `rst_err` main signal.
- **Optional enhancement:**
  - `usage`: canonical callable directive source text (derivable from `domain`/`action`, recommended but not required).
  - `package` / `runtime`: top-level promotion labels for cross-runtime grouping/dedup — **not mandatory**; a single-language runtime may omit.
  - `domain_zh` / `action_zh` / `usage_zh` / `description` / `description_zh`: locale overlay; when absent the consumer falls back to canonical.
  - `params`: pass through as-is.

> Implementation reference: the protocol does not specify a runtime, so the contract **must not mandate any runtime to support multilingual or to tag its runtime**. Multilingual / runtime tags are an enhancement layer of "add it if you want", not an entry barrier.

##### Localization Strategy

- **JSON mode**: returns all locale variants present in the schema (canonical fields + `_zh` + `_en` if declared). The consumer selects fields per its own needs; **the server does not make a single-language choice**.
- **Text / minimal mode**: the server selects a single language by the trailing param `,zh` / `,en` (fall back to canonical).
- **Prohibited**: carrying a `lang` field inside a response item and depending on the client to filter by `lang` — i.e., the response structure contains no `lang` key, and the consumer should not depend on any undefined field.

##### `params` Field Handling

`params` is **passed through as-is** from the package declaration; this contract does not constrain its shape:
- Standard Python package: string array `["text","target"]` (SPEC §3.3).
- Platform subset (e.g. CloudBase requires object array `[{name,required,description}]`): a platform constraint, not protocol canonical.

> Implementation reference: the query contract only specifies "the transport shape of the discovery response"; the concrete shape of `params` is governed by the package declaration contract (SPEC §3.3); cross-runtime differences are platform subsets and should not be forcibly unified in the discovery contract.

##### Error Handling

When the query itself fails (e.g. the runtime has no registered directives, or an internal query exception), it also uses the §1.2.8 error response:

```json
{ "rst_types": "text", "rst_data": {"status":"error","reason":"..."}, "rst_err": "ERR_EXECUTION" }
```

- The error code goes into `rst_err` (e.g. `ERR_EXECUTION` / `ERR_NOT_FOUND`); **must not** stuff errors into `rst_data`'s business fields (such as the old `rst_data.text.status` paradigm).
- Empty result (no directives) is considered success: `rst_err=""`, `directives: []`.

#### 1.2.8 Error Response

Error codes:

| Error code | Meaning |
|------------|---------|
| `ERR_NOT_FOUND` | Capability does not exist — upper layer may reroute |
| `ERR_EXECUTION` | Execution failed — retryable |
| `ERR_ROUTING` | Routing/network failure — stop + alert |
| `INVALID_PARAMS` | Invalid params |
| `ACCESS_DENIED` | Access Token invalid |
| `SERVICE_DENIED` | Service Token invalid or provider explicitly denies (***excluding quota exhaustion*** — quota exhaustion is a degradation signal, returns `{"status":"stop"}` and walks the degradation chain, see §2.2, and does not produce this error code) |

The `rst_err` field carries the error code. Empty string `""` means success.
Inner business errors uniformly use the `reason` field name.
Errors are returned as a single-line structured string and must not bloat the caller context.

Error codes (e.g. `ERR_NOT_FOUND`) and status values (e.g. `pending|running|done`) are closed sets — implementations must not introduce values not defined by the protocol.

### 1.3 Related Parties

- **Caller**: the protocol does not care whether the caller is a human, an AI, or a machine; as long as it can output 'natural language' over the network to the 'corresponding semantic space' and can present the corresponding credentials, the caller is a protocol-compliant caller.
- **Capability provider**: the capability provider wraps 'software service / experience service / time service' into a service that the 'runtime' can proxy, so that it can continue to provide the corresponding service after it leaves.
- **Runtime**: the 'capability provider' 'registers' the capability to the 'runtime' by installing it as a 'directive package'; the runtime serves the caller based on 'auth'.
- **Integration endpoint**: the 'runtime' can serve the 'caller' directly, or serve the 'caller' through an 'integration endpoint'.

> Runtime: a 'runtime' can be deployed on various platforms or terminals. The protocol supports runtimes constructed in various development languages.

---

## 2. Auth & Quota

> Implementation reference: this chapter establishes principles and does not prescribe specific mechanisms. The token encoding scheme, the credential storage medium, and the declaration file shape are decided by the runtime.

### 2.1 Two-layer Tokens

```
Caller ──Access Token──> Integration Endpoint ──Service Token──> Skill Service
```

Principle: **identity and commerce are separated**.

- **Access Token**: verifies "who you are" — issued and verified by the endpoint, carrying the caller's identity.
- **Service Token**: carries "your agreement with the capability provider" — privately agreed between caller and provider; the endpoint **passes through**, does not parse its semantics, does not store its content.

**Token segmentation principle**: structurally the Service Token is divided into three segments — **service instance identifier / policy control plane / user identity**. The policy control plane is embedded in the token itself: flipping the control plane enables batch interception and centralized rotation without touching the user identity segment.

**Prefix invariance principle**: routing and interception depend only on the token's **fixed-length prefix** (instance identifier + policy control plane). The postfix structure may be extended and variable-length; the part beyond the prefix is **permanently invisible** to the endpoint. This is the contract that decouples the endpoint from token evolution: upgrading the token scheme does not require upgrading the endpoint.

> Implementation reference: one implementation may adopt a three-segment encoding (instance identifier / policy control plane / user identity), with the first two segments merged into a fixed-length prefix for routing and interception. Specific bit counts and encoding are decided by the runtime, not protocol constraints.

### 2.2 Quota Protection

Principle: **quota exhaustion is not an error, it is a degradation signal**.

- A directive may check quota before execution via `quota;check,<target>[,<amount>]`.
- Quota exhaustion returns `{"status":"stop"}` — the aggregation layer treats it as a degradation signal and automatically switches to the next provider (§5.4).
- Semantic division of labor: `status: "stop"` walks the **degradation chain** (there are other providers to try); a non-empty `rst_err` walks the **failure return** (this call terminates). The two are not mixed.

Scope boundary: the prerequisite for `status:"stop"` to trigger the automatic degradation chain is that the request hits an aggregate domain (i.e. the domain is registered in the aggregate routing table with a `default` multi-provider chain, see §5.4). The aggregation layer recognizes stop when dispatching and automatically switches to the next provider.

For ordinary directives in non-aggregate domains (including directly invoking `quota;check` itself), returning `status:"stop"` is only passed through to the caller as a signal, without triggering any automatic degradation — because a non-aggregate domain has no "next provider to switch to". After receiving stop, if failover is needed, the consumer should decide per §5.4 (aggregate degradation chain) or at the business layer.

The stop in a synchronous call is consumed by the aggregation layer; the stop handling inside the async task (§1.2.6) kernel is described in the "async degradation" note below.

### 2.3 Federated Mesh Credentials

**Delegation model**: the essence of mesh is delegation — the source node delegates the directive to peer A, and peer A's own routing table decides whether to continue delegating to peer B. The hop chain is not pre-planned by the source node, but decided by each hop node's own routing declaration. Each runtime MAY limit the follow depth via configuration — this is a runtime security behavior, not protocol-mandated.

In a multi-node federated topology, forwarding between nodes follows three principles:

1. **Credentials isolated per peer**: when forwarding, only inject the credential corresponding to the target node, not carry it in full — no peer should see credentials addressed to another peer.
2. **Mapping chain semantics**: directive (`domain;action`) → target node (peer) → that node's credential → inject into forwarding. Each step in the chain is an explicitly declared mapping; no implicit inference.
3. **Graceful degradation**: when credential mapping or storage is missing, **degrade and forward** (explicitly degrade, log an alert), do not silently block — mesh reachability takes priority over credential completeness. This degradation is an **availability** trade-off, not a security recommendation (essentially delegation-outbound, a runtime security behavior); a production mesh should ensure `peer_credentials` is persisted in place, otherwise unauthorized nodes may receive requests that should have been credential-limited.

> Enabling a mechanism does not equal automatically discovering/accepting peers. A peer must be explicitly written into the routing table to exist; an empty routing table → no forwarding target → no request goes out of bounds → no "degraded forwarding", and no "unauthorized node receives requests".

> **Runtime layering of credential injection**: the persistence and injection of peer credentials is an optional enhancement of the standard runtime — the standard runtime MAY provide it, but it is not a minimum baseline requirement. When the standard runtime provides this capability, credential absence should be explicitly marked with `_mesh_credential_degraded` in the response `rst_data` for the caller to perceive programmatically. The security fallback strategy (reject cross-hop vs degrade-forward) is decided by the runtime via configuration; the protocol does not mandate it.

> Implementation reference: the specific mechanisms of credential storage medium, routing declaration file shape, and injection field names are decided by the runtime.

---

## 3. Schema Metadata Specification

The protocol recognizes four types of directive carriers:

| Type | Implementation | Declaration |
|------|----------------|------------|
| **native** | Version based on the 'runtime's' implementation language | schema.json + handler (e.g. python: handler.py) |
| **nocode** | Markdown knowledge file + path JSON | schema.json + knowledge/ + paths/ |
| **aggregate** | Pure declaration, no handler | aggregate/*.json |
| **pipeline** | Step-chain JSON | path JSON + schema.json |

### 3.1 Directive Package Schema (package-level)

Each directive package must have a `schema.json` declaring package metadata and the directive list.

```json
{
  "id": "xx-cloud",
  "name": "XX Cloud",
  "name_zh": "XX云",
  "type": "native",
  "runtime": "python",
  "entry_runtimes": ["python"],
  "category": "云服务",
  "version": "1.0.0",
  "locales": ["zh", "en"],
  "trust": "internal",
  "description": "...",
  "description_zh": "...",
  "requires": {
    "pip": ["requests>=2.28"],
    "tc_packages": ["task-manager", "quota-manage"]
  },
  "credentials": [
    {
      "name": "xx_cloud_key",
      "description_en": "API key for XX Cloud",
      "description_zh": "XX云 API 密钥",
      "storage": "key_registry",
      "register_cmd": "AI:key;register,xx_cloud_key,<key>,api_key"
    }
  ],
  "directives": [
    {
      "domain": "xx-cloud",
      "domain_zh": "XX云",
      "action": "translation",
      "action_zh": "翻译",
      "usage": "xx-cloud;translation,<text>[,<target>]",
      "usage_zh": "XX云;翻译,<文本>[,<目标>]",
      "description": "Translate text via API.",
      "description_zh": "通过 API 翻译文本。",
      "params": ["text", "target"],
      "params_desc": {
        "text": "Text to translate",
        "target": "Target language ISO code (default: en)"
      },
      "outputs": ["text"],
      "estimated_time": "3s",
      "estimated_time_note": "Single translation usually 1-3 seconds, depending on text length and API response speed"
    }
  ]
}
```

### 3.2 Top-level Fields

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Package unique identifier |
| `name` | ✅ | Package name (canonical, English / neutral) |
| `name_zh` | Recommended | Chinese package name overlay |
| `description` | ✅ | English description |
| `description_zh` | Recommended | Chinese description overlay |
| `type` | ✅ | `"native"` / `"nocode"` / `"aggregate"` / `"pipeline"`. Describes **how to build** the directive package (carrier type) |
| `runtime` | ✅ | `"python"` / `"js"` / `"mcp"` / `"cmd"` / `"path"` / `"aggregate"`. Describes **in what language/form it runs**; when `type` is `pipeline` / `aggregate`, `runtime` takes the same-named value (`"path"` / `"aggregate"`) or is omitted as the runtime infers it from `type`. The two are orthogonal: `type` describes the build method, `runtime` describes the run language |
| `category` | ✅ | Category tag |
| `locales` | ✅ | Multilingual coverage. Format `["<ISO 639-1 language code>", ...]` (e.g. `["zh", "en"]`). Chinese uses `"zh"` not `"cn"` |
| `trust` | ✅ | `"internal"` / `"community"` / `"public"` |
| `requires.<ecosystem>` | No | Generic convention for external ecosystem dependencies: key is the ecosystem identifier, value is the dependency list in that ecosystem's syntax. Ecosystem names are open, not a closed set. Examples: `requires.pip` (Python package deps, e.g. `["requests>=2.28"]`), `requires.npm` (Node.js package deps, project-level install, e.g. `["@scope/name@^1.0"]`) |
| `requires.tc_packages` | No | Inter-package dependencies |
| `requires.modules` | No | `text_cli_modules/` runtime dependencies |
| `requires.binaries` | No | System binary / global CLI dependencies. Format: `{"<name>": {"source": "system"\|"package"\|"npm-global", "min_version": "..."}}`. `source: "system"` = OS package manager install; `source: "package"` = distributed with the package; `source: "npm-global"` = npm global install |
| `entry_runtimes` | No | Package runtime environment list (used when a single `runtime` cannot fully describe). Format: `["python", "js"]`. Does not affect framework registration; only declares the environment to prepare before running |
| `requires.service_db` | No | Declares the server-side persistent surface the package depends on (table name list, e.g. `["token_registry", "token_call_logs"]`). Created on install, reclaimed on uninstall. Storage medium and table-creation mechanism are implementation |
| `tables` | No | Declares the persistent surface the package builds itself. Created on install, reclaimed on uninstall. Declaration syntax and table-creation mechanism are implementation |
| `credentials` | No | Required credentials (key name → source) |
| `entry` | No | Public endpoint URL |
| `mcp_server` | No | MCP server name |
| `version` | Recommended | Semver |

### 3.3 Directive-level Fields (directives[])

| Field | Required | Description |
|-------|----------|-------------|
| `domain` | ✅ | Directive domain |
| `domain_zh` | Recommended | Chinese domain alias |
| `action` | ✅ | Action name |
| `action_zh` | Recommended | Chinese action alias |
| `usage` | ✅ | Usage example (canonical name) |
| `usage_zh` | Recommended | Chinese usage example |
| `description` | ✅ | English description |
| `description_zh` | No | Chinese description |
| `params` | No | Param name list |
| `params_desc` | No | Param description object |
| `mcp_tool` | No | Original MCP tool name |
| `outputs` | No | List of status-level field names the directive returns (declarative, not runtime-mandated). Used by the path engine for `{step.field}` reference validation; later consider auto-building `:OUTPUTS` relationships via a graph. Declared but unreturned fields do not cause an error |
| `estimated_time` | No | Maximum expected execution time of the directive. Format `"<number><ms\|s\|h>"` (e.g. `"500ms"`, `"30s"`, `"2h"`). For async scheduler timeout estimation and priority decisions. Not filled for sync directives |
| `estimated_time_note` | No | Explanation of the estimated time. E.g. `"0.5h video conversion ~120s, time grows approximately linearly with video duration"`. Used with `estimated_time` to help the caller estimate expected time at different input scales |

### 3.4 Aggregate Directive Schema

The aggregate directive has only routing declarations.

```json
{
  "id": "map",
  "type": "aggregate",
  "domain": "map",
  "name_zh": "地图服务",
  "description_zh": "地图服务：多提供方自动降级",
  "default": ["x1-map", "x2-map", "x3-map"],
  "providers": {
    "x1-map": {"geocode": "x1-map;geocode", "route": "x1-map;route"},
    "x2-map": {"geocode": "x2-map;geocode"},
    "x3-map": {"geocode": "x3-map;geocode"}
  }
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Aggregate unique identifier |
| `type` | ✅ | Fixed as `"aggregate"` |
| `domain` | ✅ | Externally exposed aggregate domain name |
| `default` | ✅ | Degradation chain order |
| `providers` | ✅ | Provider→action mapping. Value format `"<domain>;<action>"` |

### 3.5 Path Declaration Entry

```json
{
  "id": "route-map",
  "name_zh": "地图连线",
  "type": "pipeline",
  "version": "1.0.0",
  "input_schema": {"type": "string"},
  "output_schema": {"type": "picture"},
  "requires": ["map;geocode", "map;route", "xx-map;static-map"],
  "steps": [
    {"id": "start", "instruction": "map;geocode,{input.address}", "output_as": "start"},
    {"id": "route", "instruction": "map;route,{start.lat},{start.lon},{end.lat},{end.lon}", "output_as": "route"},
    {"id": "map", "instruction": "xx-map;static-map,{end.lat},{end.lon},14,600x400,...", "output_as": "map"}
  ]
}
```

| Field | Required | Description |
|-------|----------|-------------|
| `id` | ✅ | Path unique identifier |
| `type` | ✅ | Fixed as `"pipeline"` |
| `version` | Recommended | Semver |
| `input_schema` | Recommended | JSON Schema fragment of input params |
| `output_schema` | Recommended | JSON Schema fragment of output result |
| `requires` | ✅ | List of dependent directives |
| `default_source` | No | Path-level default endpoint URL. When omitted all steps execute at the local service |
| `steps` | ✅ | Step array |

---

## 4. Path Protocol

### 4.1 Pipeline Closure Principle

**The path only does orchestration and interpolation. File IO, API calls, inference — all done via directives.**

```
Path engine: orchestrate directive sequence (step1 → step2 → step3)
Directive:   execute specific operation (tc-markdown;read, ai;infer, map;geocode)
```

The path does not read files — it calls `tc-markdown;read`. It does not infer — it calls `ai;infer`. It does not call API — it calls `map;geocode`. This is the protocol's design red line.

### 4.2 Step Syntax

```json
{
  "id": "step_id",
  "instruction": "domain;action,{input.key},{prev.field}",
  "if": "{step.field} == 'NOMATCH'"
}
```
```json
{
  "id": "step_id",
  "instruction": "domain;action,{input.key},{prev.field}",
  "if": {"step": "prev", "field": "field", "equals": "NOMATCH"}
}
```
> The two writings are equal in status: the string form suits manual authoring and simple `==`/`!=`; the object form suits program generation and complex conditions.
> The path engine's handling of references to undeclared fields must be globally consistent: validation only produces warnings; at execution, undefined variables are always substituted with an empty string, and behavior must not change across runtimes. No implementation may treat an undeclared reference as a blocking error.

| Syntax | Meaning |
|--------|---------|
| `{input.key}` | The key field in the user's input JSON |
| `{step_id.field}` | The JSON field output by a previous step (supports deep paths such as `{geo.poi.0.name}`) |
| `"if"` | Optional condition — when false, skip this step. Supports two **equal-status** writings, each with its use case: (a) string shorthand `"{step.field} == 'VALUE'"` (only `==`/`!=` text comparison), suited for manual authoring and simple conditions; (b) object form `{step, field, equals\|contains\|matches\|exists}` or comparison with `op`/`value`, supporting top-level `all`/`any` composition, suited for program generation and complex conditions. The protocol **does not specify a single primary form** |
| `"instruction"` | The text-cli directive template to dispatch |
| `"source"` | Optional — step-level endpoint URL. When omitted inherits `default_source` or the local service. Value must be a complete URL, e.g. `"http://10.168.1.122/text-cli/cli"` |
| `"mode"` | Optional — pipeline execution mode. Currently defined: `"toolchain"` (serial chain), `"parallel"` (parallel, minimal shape `{"mode":"parallel","strategy":"all\|first_ok"}`, `strategy` value `all` (execute all) / `first_ok` (return on any success)), `"map"` (loop iteration, execute sub-step array per element of a collection, minimal shape `{"mode":"map","items":"<var name>","steps":[...]}`; `as` (element binding name, default `"item"`), `collect_as` (collect variable name, default = `output_as`), `max_iter` (fan-out cap, optional; deploy-side yaml config `paths.map_max_iter`, not the LLM authoring surface, not protocol-mandated), `on_error` (`"break"` circuit / `"continue"` skip, default `"break"`), `concurrency` (`"serial"` serial / `"parallel"` parallel, default `"serial"`) are all optional enhancement fields). The protocol reserves the right to extend other modes and strategies |

> `{step_id.field}` referenced fields should be within the target directive's `outputs` declaration range in schema.json. The path engine may use this for field reference validation.
> **Undefined variable behavior**: when a referenced variable does not exist, substitute an empty string `""` and log `WARNING: undefined variable {name}`. Do not throw — in async scenarios a variable may not yet be ready due to step execution timing; throwing would block path execution.
> Implementation reference: `mode` defaults to `"toolchain"` — steps execute serially in array order, the previous step's output injected into later steps via `{step_id.field}`. `"toolchain"`, `"parallel"` (parallel, with `strategy: all|first_ok`) and `"map"` (loop iteration, executing sub-steps per element of a collection) are the currently defined modes; each runtime may implement and register other modes as needed; the protocol does not enumerate all possible mode values.

Cross-node path execution example:

```json
{
  "id": "cross-node-demo",
  "default_source": "http://10.168.1.122/text-cli/cli",
  "steps": [
    {"id": "local", "instruction": "tc-datetime;now", "output_as": "time"},
    {"id": "remote", "instruction": "tc-ffmpeg;info,{video.path}", "source": "http://10.168.1.122/text-cli/cli", "output_as": "info"}
  ]
}
```

When `source` is omitted it inherits `default_source`; when `default_source` is also omitted it defaults to the local service.

### 4.3 Conditional Execution

```json
{"id": "fallback", "instruction": "...", "if": "{step.field} == 'NOMATCH'"}
{"id": "fallback", "instruction": "...", "if": {"step": "prev", "field": "field", "equals": "NOMATCH"}}
```

**Condition operators** (available in object-form `if`):

| Operator | Writing | Description |
|----------|---------|-------------|
| Equal | `{"step","field","equals":"V"}` | Text/value equality |
| Contains | `{"step","field","contains":"V"}` | Substring/element contains |
| Matches | `{"step","field","matches":"regex"}` | Regex match |
| Exists | `{"step","field","exists":true}` | Field non-empty/exists |
| Compare | `{"step","field","op":"gt\|lt\|gte\|lte\|ne","value":N}` | Numeric comparison; when `op` appears together with equals/contains/matches/exists, `op` takes effect and the other fields are ignored |
| Composite | `{"all":[...]}` / `{"any":[...]}` | Multi-condition AND/OR; elements are any of the above operator objects |

The string form only supports `==`/`!=` text comparison and is the equivalent shorthand of the object form.

### 4.4 Context Injection Protection

The path declaration is inherently injection-resistant — `steps` are fixed in JSON, and data flows one-way through named pipes. An injection payload can never escape from the data position to the instruction position. The loop binding `{as}` (e.g. `{item}`) also belongs to the param position, and data still cannot escape from the data position to the instruction position — `map`'s iteration strengthens rather than weakens this guarantee.

### 4.5 Facade Entry

```
text-cli;pro,<name>[,<input_json>]
```

Principle: the facade layer maintains a **facade registry**, mapping a short name (name) to an execution target (target) — the target can be a path or an aggregate directive.

> Implementation reference: the registry file shape and parsing mechanism are decided by the runtime.

Facade directives are co-equal with atomic directives — the caller is unaware whether the implementation behind it is single-step or multi-step. This is the core value of the advanced directive facade layer: **growth by service domain count, not by tool count.**

---

## 5. Aggregate Directives

### 5.1 Overview

Aggregate directives provide a domain-level entry, converging multiple providers into a single directive. The caller is unaware of provider differences and sees only one entry.

### 5.2 Declaration

Aggregate directives are defined in a purely declarative way (no handler); the declaration shape and fields are in §3.4.

> Implementation reference: the storage location and loading timing of declaration files are decided by the runtime.

### 5.3 Providers Not Distinguished by Source

native handler, MCP bridge, Skill Bridge — are equal in status in the aggregate degradation chain. The value in `providers` only needs to be a `domain;action` resolvable by `dispatch()`.

### 5.4 Degradation Chain

```
Request → aggregate hit
  → look up default degradation chain
  → dispatch each provider in order
  → return the first successful result
```

Degradation triggers: returns `status: "stop"` (quota exhausted), returns `status: "error"`, dispatch exception, or directive not registered.

> When the user explicitly specifies a provider, that provider's returned `status:"stop"` is treated as a hard failure (terminates this call, does not walk the degradation chain), because the user's explicit choice expresses deterministic intent; the degradation chain only applies to default routing.

### 5.5 Explicit User Selection

When the trailing param matches a provider name, that provider takes priority:

```
map;geocode,威海,x2-map     →  only use x2-map, no degradation
```

### 5.6 Position of Aggregation in the Request Pipeline

Principle: **aggregation is hit first** — when a request enters the dispatch pipeline, it first matches the aggregate entry; if no hit, it continues through the subsequent dispatch pipeline.

> Implementation reference: the specific segment order of the pipeline is decided by the runtime.

### 5.7 Protocol Bridge

Principle: a runtime MAY map capabilities from other protocol ecosystems (such as MCP tools, third-party skills) into this protocol's directives via a protocol bridge.

- Bridged directives are **co-equal** with native directives — they can be resolved, can be providers in the aggregate degradation chain, and can be referenced by path orchestration.
- Bridging should be equal and reciprocal; build a two-way bridge whenever capable.
- The caller is unaware whether the directive behind it is a native implementation or a protocol bridge.

> Implementation reference: the specific bridging mechanism (declaration file, adapter, compilation method) is decided by the runtime.

---

## 6. Runtime

### 6.1 Runtime Classification

A runtime is located on **two mutually independent dimensions**:

**Dimension one: mechanism coverage** — decides "which packages can run".

- **Minimum-compliant runtime (mandatory baseline)**: implements and only implements mechanism 1 "directive execution". Receives `AI:domain;action[,params]`, routes to implementation, returns the `{rst_types, rst_data, rst_err}` three-field envelope. **This is the runtime's entry barrier, and the only barrier.**
- **Bypass runtime**: implements any subset of mechanisms above the mandatory baseline. By deployment form it can be a cloud platform (e.g. CloudBase, Cloudflare, where the platform decides which mechanism subsets to support) and a multilingual SDK (cross-language access in SDK form such as pypi, npm).
- **Standard runtime**: implements the full set of mechanisms in §6.2.1. The standard runtime is a capability definition, not specific to a certain language — any implementation that fully carries the protocol mechanism set is a standard runtime.

The three are **positions on the same gradient, not three grades**. Not implementing any optional mechanism does not affect compliance.

**Dimension two: whether it serves across terminals** — decides "whether there is an auth and declaration obligation".

Criterion: **whether the caller is outside the trust domain already guaranteed by the OS/process boundary.**

- **Not across terminals**: the caller and runtime are in the same OS/process trust domain (in-process library, loopback bound to 127.0.0.1). **No auth obligation, no capability declaration obligation** — the caller is the user themselves, and there is no information asymmetry.
- **Across terminals**: the served object exceeds the OS-guaranteed scope (network-reachable). **Incurs an auth obligation (§2) and a capability declaration obligation (§1.2.5 `capabilities`)**.

The two dimensions do not imply each other: a minimum-compliant runtime can serve across terminals (e.g. a no-code template), and a full standard runtime can bind only loopback (e.g. copilot).

> Constraint example: `textcli-loader` (PyPI bypass runtime) is an in-process library — not across terminals, mechanism coverage 2–3, does not support `mesh` and `path` mechanisms.

### 6.2 Standard Runtime

#### 6.2.1 Mandatory Mechanisms of the Standard Runtime

The standard runtime must fully implement the following protocol mechanism set (closed set). Implementing the full set makes it a standard runtime; forms implementing only a subset fall into bypass runtime (§6.1). The protocol only specifies the mechanism set itself, not the implementation method of each mechanism.

| Mechanism | Description | Spec chapter | Level |
|----------|-------------|--------------|-------|
| Directive execution | Parse, route, execute, and encapsulate the response for protocol-compliant directives | §1 | **Mandatory baseline** |
| Install/uninstall directive packages | Package lifecycle management: register directives and dependencies on install, fully reclaim on uninstall | §3 | Optional enhancement |
| Directive discovery | Schema-based directive query (§1.2.7) | §1.2.7 / §3 | Optional enhancement |
| Path orchestration | Orchestration and interpolation execution of directive sequences | §4 | Optional enhancement |
| Async task scheduling (state persistence) | Task-based scheduling and query of async directives, with state persistence as its support | §1.2.6 | Optional enhancement |
| Aggregate & degradation chain | Domain-level aggregate entry and provider degradation | §5 | Optional enhancement |
| Federated Mesh | Per-peer credential injection and forwarding under multi-node federated topology | §2.3 | Optional enhancement |
| Protocol bridge | Two-way bridging with other protocol ecosystems (e.g. MCP is one implementation) | §5.7 | Optional enhancement |
| Facade abstraction | Mapping from short name to execution target; facade directives co-equal with atomic directives | §4.5 | Optional enhancement |

**Auth & quota** do not belong to the runtime capability set; they belong to the **property of the cross-terminal relationship** (see §2 / §8):
- A runtime serving across terminals **must** implement auth — a second party that does not know you has appeared, and credentials are the only trust anchor.
- A runtime not serving across terminals has **no auth obligation** — the caller is the user themselves, out of scope.
- Quota protection (§2.2) likewise: only incurs an obligation in the cross-terminal scenario.

**Reserved-domain extension**: this table is the mandatory minimum surface. A runtime MAY extend self-management directives within the `text-cli` reserved domain, without polluting third-party namespaces. Precedent: copilot's `co-install` / `co-uninstall` (see §6.2.2).

**Package capability classification (terminology)**: by whether they depend on host resources, directive packages are divided into two types — **non-host-privileged package**: the capability does not access the host machine's terminal/file/Git/shell/local-service resources (e.g. pure functions, external API calls); **host-privileged package**: the capability depends on the host machine's execution surface (e.g. screenshot, camera, microphone, screen lock, local service control, shell bridge). This classification is a protocol-layer terminology definition, used only to clarify the package's capability nature, and does not introduce a new schema field.
> Based on the package capability classification, the distinction of **non-host-privileged packages** allows the runtime internally to divide copilot and service as different components of the same standard runtime. **Non-host-privileged packages** can be loaded under both copilot and service; **host-privileged packages**, depending on host resources, can only be loaded under copilot (the `127.0.0.1` local proxy). The component's deployment form and combination are an implementation choice; the protocol does not prescribe them.
> Implementation reference: the package's install boundary, validation, and isolation mechanism are defined by the runtime (see §6.2.2).
**Cross-trust-domain capability provision**: copilot and service are both independent and cooperative. **When the capability provider explicitly agrees**, service MAY consume directives stored by copilot. This is the only authorized path for a host-privileged package to leap from "not across terminals" to "across terminals" — at the moment of the leap, the auth obligation goes from none to present. The form of "agreement" is defined by the runtime; the protocol only requires it to be **explicit** and **revocable**.

**Platform self-management meta-directive surface**: the standard runtime exposes self-management capability via meta-directives in the `text-cli` domain:

| Meta-directive | Semantics |
|---------------|-----------|
| `text-cli;install,<package-name>` | Install directive package |
| `text-cli;uninstall,<package-name>` | Uninstall directive package (fully reclaim files, registry entries, and self-built tables) |
| `text-cli;export,<package-name>` | Single-package export — export structure consistent with install format, directly consumable by `install` |
| `text-cli;export-all` | Full export |
| `text-cli;packages` | List installed packages |
| `text-cli;query,<keyword>` | Directive discovery/search |
| `text-cli;path,<json_or_file>[,<input_json>]` | Execute path step sequence |
| `text-cli;pro,<name>[,<input_json>]` | Facade entry |

> Implementation reference: the installer behavior of meta-directives (which files to deploy by runtime type, how to build tables, etc.) is decided by the runtime; the protocol only specifies the directive surface and semantics.

#### 6.2.2 Standard Runtime — Python

The Python standard runtime is a concrete instance of the standard runtime (the standard runtime is a capability definition, not specific to a certain language, see §6.1).

Composed of three components:

- **copilot**: runtime component for the local terminal.
- **service**: runtime component for network service.
- **MCP**: the carrying component of the protocol bridge mechanism, implementing two-way bridging with the MCP ecosystem.

```
AI:text-cli;co-install,<package-name>
AI:text-cli;co-uninstall,<package-name>
```

---

## 7. Multilingual

The protocol directive format itself is language-independent (see §1.1: `domain;action` canonical name is ASCII, aliases are unrestricted in character set, the runtime normalizes aliases before routing). This chapter specifies the three **protocol principles** of multilingual, in three layers: query response (L1), registration (L2), execution (L3). The translation responsibility is inside the package; the endpoint does not translate (the endpoint is a pure forwarding pipe, see §8 / ecosystem spec).

> Implementation reference: this chapter establishes principles and does not prescribe specific mechanisms. How the runtime extracts language, and how the package carries translations with data tables, vary by language / runtime.

### 7.1 Multilingual Response at Query (L1)

Principle: when a user initiates a query (e.g. `text-cli;query`), the runtime should return the **corresponding language** content from `schema.json`.

- The protocol only establishes the principle: **the query response extracts the corresponding fields by the caller's expected language**; it does not specify which languages to extract or how.
- Canonical fields (e.g. `domain` / `action` / `usage` / `name`) are default / language-neutral (English); localization overlay takes `_zh` as an example — `domain_zh` / `action_zh` / `usage_zh` provide Chinese overlay, falling back to canonical when absent.
- How the caller expresses the expected language is an **implementation mechanism** (e.g. meta-directive trailing param, server config); the protocol does not specify its form; which languages a runtime supports is an **implementation choice**, not a protocol constraint.

> Implementation reference: one runtime extracts via `field_zh` overlays, falling back to canonical when absent, with caller language prioritized over config default. This is an implementation example, not a protocol requirement.

### 7.2 Multilingual Schema for Package Registration (L2)

Principle: the directive package registers its multilingual content into `schema.json` — this is the declaration-surface contract.

- `schema.json` is the contract surface shared across implementation languages (whether python / node / mcp / cmd / path / aggregate / nocode); the multilingual declaration shape is the same.
- `locales`: declares the package's supported **output languages** (ISO 639-1, Chinese `zh`). For AI / runtime discovery.
- Canonical fields are default (English / neutral); with `_zh` as the localization overlay example:
  ```json
  {
    "locales": ["zh"],
    "directives": [{
      "domain": "weather",
      "domain_zh": "天气",
      "action": "query",
      "action_zh": "查询",
      "usage": "weather;query,<city>[,<date>[,<lang>]]",
      "usage_zh": "天气;查询,<城市>[,<日期>[,<语言>]]"
    }]
  }
  ```
- The protocol specifies the **field shape** (`locales` + `<field>_zh` overlay convention), and **does not specify which languages the runtime must support** — that is the implementation layer's concern.

> Note: `name` itself is English / neutral, so `_en` is not explicitly defined; canonical assumes the English form. Other languages extend by the same `<field>_<lang>` convention; the protocol does not list them separately.

### 7.3 Directive Execution Response to Call-time Language (L3)

Principle: the directive execution function should respond to the **language passed at call time** — this is an **abstraction inside the package**; the protocol does not specify its mechanism.

- The package is responsible for the call-time language: the caller may explicitly carry a language in the directive call (e.g. trailing optional positional param `lang`, default `zh`).
- When language is out of bounds, **gracefully degrade to the default language**, and should not return `ERR_NOT_FOUND` (the `ERR_NOT_FOUND` in §1.2.8 is only for routing-layer alias miss, not for output language).
- The specific mechanism (data-driven i18n table, template-as-resource, localized error text, input/output separation, etc.) is **implementation**, varying by language; the protocol only requires the principle "execution is responsible for the call-time language".

> Implementation reference: Python packages may use an I18N data table inside the handler + `lang` positional param; Node / MCP / nocode carry it in different positions. These are all legal implementation examples, not the protocol's sole prescription.

---

## 8. Integration Endpoint

### 8.1 Architectural Role

The integration endpoint is the public entry component in the text-cli architecture located between the caller and the runtime. It does not execute directives and does not hold capabilities — it only does **auth, routing, and transparent forwarding**.

```
Caller ──→ Integration Endpoint ──→ Runtime A (:28050)
                  ├──→ Runtime B (:28050)
                  └──→ Runtime C (:28050)
```

The caller's request reaches the endpoint; the endpoint verifies the caller's identity, then forwards the request to the backend runtime, and returns the result as-is to the caller.

### 8.2 Pure Pipe Principle

Like the runtime itself, the integration endpoint is a pure pipe:

- **Does not parse** the content of `rst_data` — `pray_rst_types` is a protocol convention key name and does not belong to content parsing
- **Does not execute** any handler — directive execution always completes at the backend runtime
- **Does not store** the caller's Service Token — the endpoint only passes through, does not own its semantics

The endpoint's sole duty is: verify Access Token → match backend → pass through request → return result.

### 8.3 Multi-backend Aggregation

One endpoint can aggregate the directive tables of multiple backend runtimes. At startup the endpoint pulls `/text-cli/skills` from each backend and merges them into a unified external capability catalog. When the caller invokes a directive through the endpoint, the endpoint routes the request to the corresponding backend by the directive's `domain;action`.

The caller is unaware of the number, address, or form of backend runtimes behind it (standard Python service, Docker deployment, bypass runtime — all equal in the endpoint's backend list).

In the directive table exposed by the endpoint, each directive's call address is rewritten to the endpoint's own URL — the caller always sends requests to the endpoint and is unaware of the backend runtime's real address.

### 8.4 Pass-through Service Token

The Service Token is privately agreed between caller and capability provider (§2.1). The endpoint **only passes through** — does not verify its validity, does not parse its structure, does not store its content. When the endpoint injects credentials per peer in the federated Mesh scenario (§2.3), it only uses the Service Token's fixed-length prefix for policy control plane identification — the Token content beyond the prefix is permanently invisible to the endpoint.

### 8.5 Optional Security Layer

The endpoint MAY provide three layers of optional defense independent of the protocol:

1. **IP filtering**: CIDR blacklist
2. **Rate limiting**: sliding window limiter
3. **Token auth**: Access Token verifies caller identity (§2.1)

These are endpoint-level optional mechanisms, not protocol-mandated requirements.

### 8.6 What the Endpoint Does Not Do

- Does not execute directives — execution always at the backend runtime
- Does not host settlement — billing is privately agreed between caller and provider
- Does not own the semantics of the Service Token — the endpoint only passes through
- Does not guarantee backend availability — when backend is unreachable returns `ERR_ROUTING`

> - Does not guarantee backend availability — when backend is unreachable returns `ERR_ROUTING` (the endpoint-side `ERR_ROUTING` is **only** for this scenario; governance denial must not share it, see §8.7)

**8.7 Endpoint's Own Response**

The endpoint's response is divided into two categories:

| Category | Trigger | Disposition |
|----------|---------|-------------|
| **Forwarded response** | Request has reached the backend runtime | Backend envelope returned as-is; endpoint must not rewrite |
| **Own response** | Request terminated by endpoint, did not reach backend | Endpoint constructs the full envelope itself |

When producing its own response, the endpoint **must** output the full three-field envelope (`rst_types` / `rst_data` / `rst_err`), and must not omit `rst_err`.

- The `rst_err` value must fall within the §1.2.8 closed set;
- The endpoint's governance reason (e.g. `IP_BLOCKED`, `RATE_LIMIT_EXCEEDED`) goes in `rst_data.reason`, not constrained by the closed set.

The endpoint's own response `rst_err` **can only** take the following four values:

| Scenario | `rst_err` |
|----------|-----------|
| Endpoint security layer denies (§8.5: IP filtering / rate limiting / Token auth / ST prefix interception) | `ACCESS_DENIED` |
| Request params or directive format invalid | `INVALID_PARAMS` |
| Directive not registered in aggregate table; endpoint channel not enabled | `ERR_NOT_FOUND` |
| Backend unreachable (connection failed / timeout, see §8.6) | `ERR_ROUTING` |

The endpoint **must not** use `SERVICE_DENIED` in its own response — the endpoint does not parse the Service Token (§8.4), nor is it a capability provider, and is not qualified to produce that code.

The endpoint also must not use `ERR_EXECUTION` — the endpoint does not execute directives (§8.1, §8.6).

> Implementation reference:
> ```json
> HTTP 403
> {"rst_types":"text","rst_data":{"status":"error","reason":"IP_BLOCKED"},"rst_err":"ACCESS_DENIED"}
> ```
> The governance vocabulary in `reason` is defined by the endpoint; the protocol does not constrain its value.
>
> This motion does not involve the correspondence between HTTP status code and `rst_err`; the endpoint reuses the existing status code.

---

## Appendix A Protocol Primitives and Ecosystem

### Protocol Primitives

The root contract of the protocol is 'natural language' compressed into an 'imperative sentence'. The protocol uses natural language as its primitive and natively supports multilingual.

```
AI:math;eval,2+3*4+pi  -> English
AI:数学;计算,2+3*4+pi  -> Simplified Chinese
AI:数学;計算,2+3*4+pi  -> Japanese
AI:數學;計算,2+3*4+pi  -> Traditional Chinese
AI:수학;계산,2+3*4+pi  -> Korean
```
The 'protocol' defines the response that should be received when requesting with the 'protocol primitive'. The project `text-cli` is support for the 'protocol primitive'; the 'protocol primitive' itself does not depend on any project. The 'protocol' originates from the exploration of 'natural language'; no person or group owns 'natural language', and no person or group owns the 'protocol primitive'. The 'protocol' is derived by the project `text-cli` from reasoning about 'natural language'. The 'protocol' is currently maintained by the project `text-cli`; when the project's corruption attempts to infect the 'protocol', the protocol itself, rooted in natural language, can be corrected by any project based on the 'protocol primitive'.

The project `text-cli`'s main revisions to the protocol are as follows:
- **Call equality**: anyone who can generate 'natural language', human or AI, can use 'text directive' to initiate a request to the 'runtime' that receives the directive.
- **Response envelope**: how the 'runtime' responds to 'text directive' with artifacts of different modalities.
- **Directive query**: obtain via the 'query' directive which 'directive services' the 'target runtime' can provide.
- **One-dimensional contract**: for the user, the entry is always only one sentence `AI:domain;action,params`, and the exit is always only one result. Internal aggregate degradation, path orchestration, federated multi-hop, multi-provider selection — all happen behind the seam, **invisible to the caller**.
- **Runtime**: the runtime is the entity that processes 'text directive' requests. The 'runtime' is not bound to a programming language; the 'runtime' concept body only defines the capability scope (when the protocol adds new capability scope, there must be a corresponding 'landing implementation' to ensure the protocol's integrity). The runtime should carry several 'directive packages' capable of processing 'text directives'.
- **Directive package**: when proposing 'directive package' content in the protocol, the definition of 'directive package' must be accompanied by a 'directive package creation guide, transformation framework, template, example package'. And the 'minimum implementation' of the 'directive package' should let an LLM with ≤9B parameters and a person without coding ability complete the corresponding implementation.

### Protocol Ecosystem

From every human utterance, to every LLM generation of 'natural language' response, is using 'natural language'. The natural language ecosystem is the 'protocol' ecosystem; the project never owns the 'protocol', it only wipes the dust.

| Traditional code ecosystem | Protocol's natural-language ecosystem |
|---|---|
| Reproduction unit = code repository | Reproduction unit = one imperative sentence + one package |
| Producer = developer | Producer = anyone who can express (florist boss...) |
| Threshold = programming ability | Threshold = expression ability |
| AI is consumer | AI is consumer + producer (helps turn experience into packages) |

**Florist boss orally describes ten years of experience → AI wraps it into a directive / or no-code wraps it into a directive → other florist bosses or their AIs call it directly** — in this loop not a single line of code is written by a human, yet it completes the full reproduction of "experience → service → consumed". **This is the natural-language ecosystem: with natural language as the medium, anyone can reproduce capability.**

The protocol is not "waiting to be validated by the ecosystem" — it is "waiting for reproduction with the lowest threshold". And the lowest threshold is being able to speak.

---

## Appendix B

### 1.0
- **Directive Format Specification**: protocol communication primitive: directive format (`AI:<domain>;<action>,<param1>,<param2>,.../指令:<domain>;<action>,<param1>,<param2>,...`), request/response envelope, error codes, capability discovery, how to declare directive packages: package-level and directive-level field definitions
- **Runtime**: identity verification, quota protection, path protocol, aggregate directives
- **Integration Endpoint**: auth, routing, pass-through (pure pipe)
### 1.1
- **One-dimensional contract**: for the user, the entry is always only one sentence `AI:domain;action,params`, and the exit is always only one result. Internal aggregate degradation, path orchestration, federated multi-hop, multi-provider selection — all happen behind the seam, invisible to the caller.
- **Directive package**: introduce the directive package concept (schema.json declaration), define package-level metadata (id/name/type/runtime/category/trust/version) and directive-level fields (domain/action/usage/description/params), as well as package install/uninstall lifecycle.
- **'指令:' exit**: runtimes conforming to protocol version '1.2' and above may no longer support the '指令:' prefix, and will completely remove '指令:' in protocol version '1.5'.
- **Directive discovery enhancement**: `text-cli;query,json` machine-readable response introduces the `directives` container and field-level definitions (domain/action mandatory baseline + usage/package/runtime/domain_zh/action_zh/usage_zh/description/description_zh/params optional enhancement). Layering rules: mandatory baseline / optional enhancement / prohibited behavior. Localization strategy (JSON mode returns all locale variants, text/minimal selects language by trailing param).
- **Path mode extension**: pipeline steps add the `mode` field, supporting `"toolchain"` (serial, default) and `"parallel"` (parallel, strategy: all/first_ok).
- **Skills endpoint exposure control**: add `service_manifest.json`'s `public_directives` whitelist to control the directive scope exposed by the `/text-cli/skills` endpoint. Empty whitelist = expose all; when content exists, only expose listed entries.
### 1.2
- **Multi-runtime directive package**: directive package schema adds the `entry_runtimes` field, declaring the package's runtime environment list. Introduces `requires.modules` (runtime module dependency), `requires.binaries` (system binary dependency), `requires.service_db` (server-side persistent surface dependency), `tables` (package self-built persistent surface).
### 1.3.0
- **GET emergency channel**: add `GET /text-cli/cli?prompt=` as an emergency entry, disabled by default, explicitly enabled by the capability provider.
- **Async task scheduling**: add the `task_id` async model (pending/running/done/error/cancelled five states), `GET /text-cli/tasks/{task_id}` polling endpoint. Restart residual handling rule (running→error, service_restarted). Optional webhook callback notification.
- **Protocol bridge**: introduce the protocol bridge principle — bridged directives are co-equal with native directives, can be resolved, serve as aggregate degradation chain providers, and be referenced by path orchestration.
### 1.3.1
- **Multilingual**: the protocol directive format itself is language-independent (canonical name ASCII, aliases unrestricted in character set). Define three-layer multilingual principles: L1 query response extracts by caller language; L2 directive package registers multilingual schema (`locales` + `<field>_zh` overlay convention); L3 directive execution is responsible for call-time language (package-internal abstraction, graceful degradation on language out-of-bounds).
- **Federated credentials**: three principles of multi-node federated topology: credentials isolated per peer (not carried in full); mapping chain semantics (domain;action→peer→credential→inject, each step explicitly declared); graceful degradation (degrade-forward when credential missing, do not silently block). Service Token three-segment segmentation principle (instance identifier / policy control plane / user identity) and fixed-length prefix invariance principle.
- **Health check enhancement**: `/text-cli/health` public layer response adds the `spec_version` field, declaring the protocol spec version this runtime follows, orthogonal to the runtime's own `version`.
### 1.3.2
- **Directive new fields**: `estimated_time` (async directive maximum expected execution time), `estimated_time_note` (explanation of the estimated time).

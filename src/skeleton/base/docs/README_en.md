# base Group

## Positioning

The skeleton layer under the base group **is not bound to any runtime** — they are the foundation for all upper layers. A0 provides zero-dependency protocol-level invocation; A1 is the **capability integration wrapper layer** above A0, composed of three peer submodules: skill/ (Agent-consumable Skill capability wrapping and directive compilation), phase-kernel (the ecosystem-upstream orchestration kernel built on text-cli), and tc-web-chat (a single-file complete modern agent front end).

## Layers

| Layer | Name | Content | Notes |
|:---:|------|------|------|
| A0 | protocol | Protocol spec + zero-dependency invocation examples (shell/python/js/ps1) | Not part of the skeleton accumulation chain; pass-through mode |
| A1 | skill | A1's Skill capability wrapper submodule — compilation (cli.py) + consumption (skill.py) + multi-endpoint degradation | A1 peer submodule; A0 is injected into its `skill/` subdirectory at build time |
| A1 | phase-kernel | Ecosystem-upstream orchestration component built on text-cli (phase-reasoning scheduling kernel) | A1 peer submodule |
| A1 | tc-web-chat | Single-file modern agent (chat + external inference + directive tool calling + human gate) | A1 peer submodule |

## Relationship Between A0 and A1

A0 is "how to call" (single-endpoint SDK, zero dependency); A1 does capability integration wrapping on top of A0 — skill/ handles "how to call multiple endpoints + how to build" (multi-endpoint scheduling + directive compilation, issuing HTTP via the A0 SDK), phase-kernel handles "how to orchestrate multi-step reasoning" (connecting to the tc runtime via the `adapters/` adapters), and tc-web-chat handles "how to let humans and agents interact" (single-file agent front end, connecting an external LLM + calling text-cli directives).

---

## A0 — Protocol Consumption SDK / CLI

Zero dependencies — a single script can call a text-cli service. The four-language implementations are split into two tiers: Python/JS target AI Agents (SDK tier), Shell/PowerShell target humans (CLI tier).

### API Quick Reference (Python)

```python
from call import call, discover, poll, wait

# Call directive — always returns immediately
result = call("AI:tc-math;eval,2+3*4")
# → DirectiveResult(ok=True, data={"result":14})

# Discover capabilities — one HTTP call, cached, zero-cost filtering
directives = discover(search="weather")
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]

# Async poll — single query
status = poll("abc123")
# → DirectiveResult(is_async=True, data={"state":"running","progress":"50%"})

# Async wait — exponential backoff + progress callback
final = wait("abc123", on_status=lambda s: print(s.get("state")))
# → DirectiveResult(ok=True, data={"path":"/media/out.mp4"})
```

JavaScript API is identical: `call()` / `discover()` / `poll()` / `wait()`, returning `DirectiveResult`.

Per-call token overrides supported: `call("AI:...", endpoint="...", access_token="...", service_token="...")`.

### CLI Quick Start (Shell)

```bash
echo "AI:tc-math;eval,2+3*4" | ./call.sh
./call.sh --task abc123
```

PowerShell: `./call.ps1 "AI:..."` / `./call.ps1 -Task abc123`.

### Four Implementations

| Tier | Language | File | Zero-deps | API |
|:---:|------|------|:---:|------|
| SDK | Python | `A0-protocol/python/call.py` | urllib | call, discover, poll, wait, call_batch |
| SDK | JavaScript | `A0-protocol/js/call.js` | fetch | call, discover, poll, wait, callBatch |
| CLI | Shell | `A0-protocol/shell/call.sh` | curl+python3 | call, --task |
| CLI | PowerShell | `A0-protocol/shell/call.ps1` | Invoke-WebRequest | call, -Task |

### Configuration

Default endpoint `http://127.0.0.1:28050/text-cli/cli`:

```json
{
  "endpoint": "http://127.0.0.1:28050/text-cli/cli",
  "service_token": "",
  "access_token": ""
}
```

Priority: env vars (`TEXT_CLI_ENDPOINT` / `TEXT_CLI_SERVICE_TOKEN` / `TEXT_CLI_ACCESS_TOKEN`) > `conf.json` > defaults.

### Response Parsing

All four implementations uniformly parse the protocol envelope: `rst_data` is used directly (no longer nested via `.text`), read `rst_err` to judge success/failure, and detect `status=="pending"` + `task_id` to mark async tasks.

### Directory Structure

```
A0-protocol/
├── python/
│   ├── call.py                    ← Python SDK: DirectiveResult + discover + poll + wait
│   └── conf.json                  ← default endpoint config
├── js/
│   ├── call.js                    ← JavaScript SDK
│   └── conf.json
└── shell/
    ├── call.sh                    ← Bash CLI
    ├── call.ps1                   ← PowerShell CLI
    └── conf.json
```

---

## A1 — Capability Integration Wrapper Layer

A1 is the **capability integration wrapper layer** above A0: on top of A0's protocol capability, it wraps, schedules, and presents "consumable capability" to Agents and humans. It consists of three peer submodules:

```
A1 = skill/ (Skill capability wrapping + endpoint scheduling) + phase-kernel (scheduling kernel) + tc-web-chat (single-file modern agent)
```

- **`skill/`**: Skill capability wrapping — endpoint registry + aggregation manifest + consumer-side degradation + multi-token routing, Agent-consumable (detailed in the §skill section of this chapter).
- **`phase-kernel/`**: Phase-reasoning scheduling kernel (see its dedicated section below).
- **`tc-web-chat/`**: A single-file complete modern agent (dialog + external inference + directive tool calling; see its dedicated section below).

A1 provides no runtime — all HTTP calls go through the A0 SDK.

### A1 Panorama Directory

```
A1-skill/
├── skill/                         ← OpenClaw Skill entry container (SKILL.md lives here)
│   ├── SKILL.md                   ← OpenClaw Skill entry — quick start
│   ├── README_zh.md
│   ├── python/
│   │   ├── skill.py               ← Skill base class + @skill + degradation chain
│   │   ├── aggregation.py         ← endpoint management + sync_endpoints
│   │   ├── cli.py                 ← @register + generate_schema
│   │   ├── handlers/sample.py     ← compilation-path example
│   │   └── call.py                ← A0 SDK (injected at build time, see "A0 SDK Injection" below)
│   ├── prompts/                   ← Agent System Prompt templates
│   │   ├── SKILL.md
│   │   ├── text-cli-core_zh.md
│   │   ├── text-cli-sync-skill.md
│   │   └── agent-text-cli-schema.example.json
│   └── config/
│       ├── agent-endpoints.json       ← endpoint registry (manually maintained)
│       └── agent-text-cli-schema.json ← aggregation manifest (sync-generated)
├── phase-kernel/                  ← Phase-reasoning scheduling kernel (core/ports zero dependency)
│   ├── docs/                      ← design_zh.md + user-manual_zh.md
│   └── phase_kernel/              ← core / ports / adapters / serve hexagon
└── tc-web-chat/                   ← Single-file modern agent
    ├── docs/                      ← README_zh.md + user-manual_zh.md
    ├── tc-web-chat-src/           ← source files (build.js + tc-*.js modules)
    └── tc-web-chat.html           ← both/zh/en three-piece artifact
```

**A0 SDK injection (build time)**: the source `A1-skill/` does **not** contain `call.py` — `build-all.py`'s dependency build injects `base/A0-protocol` into the `deploy/A1-skill/skill/` subdirectory, so that `call.py` sits in the **same directory** as `skill.py` (`skill/python/`), and `skill.py` locates and imports A0 relative to `__file__`.

### skill/ — Skill Capability Wrapping (Agent-consumable)

`skill/` is A1's core capability container: a multi-endpoint scheduling layer facing multiple Services and Endpoints. Each A1 consumer defines its own trusted endpoint set. **`skill/`'s internal structure and A0 SDK injection are shown in "A1 Panorama Directory" above.**

```
skill = Skill + endpoint registry + aggregation manifest + consumer-side degradation + multi-token routing
```

Two paths:
- **Consumption**: Skill.run() → look up aggregation manifest → pick highest-rank endpoint (including token resolution) → A0.call() → on failure degrade to next rank
- **Production**: @register → generate_schema() → install as instruction package

#### Endpoints and Degradation

A1 maintains two endpoint files — the token is stored in only one place; the aggregation manifest does not duplicate tokens:

| File | Role | Maintainer |
|------|------|------------|
| `agent-endpoints.json` | **Single source of truth**: URL + token + rank + trust | human |
| `agent-text-cli-schema.json` | Aggregation capability manifest: directive → [source by rank], no token | `aggregation.py` sync |

**agent-endpoints.json**:
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

Tokens support `${ENV_VAR}` (environment variable reference) or bare strings. `auth: "single"` connects directly to Service (Service Token only); `auth: "dual"` goes through Endpoint (Access + Service Token).

**Degradation logic**: Inside Skill.run(), endpoints are tried in descending rank order — return on success; on failure (ERR_NOT_FOUND / ERR_ROUTING / HTTP unreachable) automatically switch to the next source. Parameter errors and auth failures do not degrade.

#### Compilation Path (cli.py)

Agent developers use the `@register` decorator to wrap an existing function as a directive, auto-generating a SPEC-compatible `schema.json`:

```python
from cli import register, generate_schema

@register(domain="weather", action="query", category="tool", trust="community")
def weather_query(params):
    return {"status": "ok", "result": f"{params[0]}: Sunny, 20C"}

schema = generate_schema("my-weather")
# → {"id":"my-weather","type":"native","runtime":"python","directives":[...]}
```

cli.py is only responsible for directive registration and Schema generation — it provides no HTTP runtime.

#### Consumption Path (skill.py)

Agents use the `@skill` decorator to wrap directives as reusable skills. Skill completes all calls through the A0 SDK:

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

Skill.run() internal flow:
1. Look up `agent-text-cli-schema.json` for all available sources (sorted by rank)
2. Back-lookup `agent-endpoints.json` for the token
3. Send the directive via A0 `call(endpoint, access_token, service_token)`
4. Success → `DirectiveResult.data` → `format_result()`
5. Failure → consumer-side degradation: automatically try the next rank endpoint
6. All exhausted → `on_error()` callback

#### sync Tool (aggregation.py)

```python
from aggregation import sync_endpoints, register_endpoint

register_endpoint("add endpoint https://my-api.example.com/text-cli/cli, token MY_TOKEN")
sync_endpoints()  # poll all endpoints → aggregate → write to agent-text-cli-schema.json
```

sync is a cold path — not inside the Agent inference loop. Runs periodically or on demand.

#### Agent Skill Definitions (prompts/)

| File | Content |
|------|---------|
| `SKILL.md` | Agent scheduling System Prompt — A0 SDK + A1 degradation |
| `text-cli-core_zh.md` | Core scheduling v2.0 — A0 call() + DirectiveResult |
| `text-cli-sync-skill.md` | Sync Skill concept design |
| `agent-text-cli-schema.example.json` | Aggregation Schema example |

#### Install as an OpenClaw Skill

**`skill/` can be installed as an OpenClaw Skill** (it is A1's Skill body; `SKILL.md` lives here). phase-kernel and tc-web-chat are A1 peer submodules, not the Skill body, and do not participate in installation:

```bash
# Git install
git clone https://github.com/weihai-limh/text-cli.git
cp -r text-cli/deploy/A1-skill/skill ~/.openclaw/skills/text-cli

# ClawHub (after publish)
clawhub install text-cli
```

OpenClaw loads `skill/SKILL.md` → the Agent learns to use `call()` / `discover()` / `Skill.run()`.

### phase-kernel — Ecosystem Upstream Orchestration Component Built on text-cli

An A1 submodule: the ecosystem-upstream multi-step intervenable scheduling kernel (entry directive `tc-phase;run`, connecting to the text-cli runtime via the TCExecutor in `adapters/`).

- **Mechanism**: phase reasoning = the projection of "multiple inferences + multiple context reorganizations" onto the planning layer. **The core mechanism (`core/` + `ports/`) has zero external dependencies** (standard library + itself only); all tc/strata/LLM differences are absorbed in `adapters/` — i.e. "the phase mechanism is generic; tc integration lives in the adapter layer".
- **Correspondence with tc**: the one-dimensional contract's recursive convergence → phase recursive layering (`Planner` → `PhasePlan` phase tree → `Executor`); the unified envelope's knowable state → phase gates and rollback (`PhaseResult{status}` closed set); query/install introspection → phase tool directory.
- **Docs**: `phase-kernel/docs/design_zh.md` (design + implementation source of truth), `user-manual_zh.md` (usage manual).
- **Verification**: 15 Python tests all green; node core isomorphism passed; dsh internalization not yet scheduled.

### tc-web-chat — A Single-file Complete Modern Agent

An A1 submodule: a **single-file self-contained modern agent** — following the modern paradigm of "orchestration + consuming external capability": it ships no model and no tool implementation; inference connects to an external LLM, and directive execution is delegated to the text-cli runtime.

- **Form**: single-file self-contained. A three-piece artifact — `tc-web-chat.html` (both edition, with Chinese/English embedded) + `tc-web-chat_zh.html` / `tc-web-chat_en.html` (single-language editions); all source modules (config/chat/parser/approval/quiet/cache/integrate) are inlined into a single html by `build.js`, ready to open, zero external JS dependencies.
- **Agent capability**: dialog and context; connects to an external LLM backend for inference (Base URL); consumes directives through the text-cli runtime (`discover` for capability discovery + `runTool` issuing `AI:` primitives); human-gate approval (Tool Gate + human-gate card + circuit breaker); multimodal upload; graceful degradation to plain chat when tc is offline; Chinese/English bilingual.
- **Usage**: open the html → fill in the chat backend Base URL + request headers → optionally check `tc_enabled` to start consuming tc directives (pointing at a text-cli runtime).
- **Docs**: `tc-web-chat/docs/README_zh.md` + `user-manual_zh.md`.

---

_2026-08-28_

# text-cli-based DeepSeek Harness Integration Example

> Source locations:
> - Bridge: `src/skeleton/bypass-service/dsh/dsh-tc-bridge/` (five tools: call_tc / wait_tc / run_tc_js / tool_avatar / find_tc)
> - Runtime: `src/skeleton/bypass-service/dsh/dsh-tc-runtime/` (15 runtime-* packages)

---

## Chapter 1 dsh: A Self-Consistent Agent Where Everything Is a Plugin

dsh (DeepSeek Harness) is the first protagonist of this document. This chapter explains it clearly — what it is, by what worldview it runs, what capabilities it has, and why it deserves the word "deep". Only after understanding it does the "integration" of the next three chapters have a place to land.

### 1.1 Positioning in One Sentence

dsh is an **open-source Agent runtime**. The official formula:

> **Model + Harness = Agent**

The model is the brain; the Harness is responsible for stringing together "model, tools, workspace, permissions, session memory, task loop" into a subject that can do work. It shares the track with Claude Code / Codex, but its positioning is one level lower: **a configurable, reconfigurable agent runtime environment** — not "a programming tool", but "a skeleton from which any agent can grow".

Its most striking worldview is only one sentence:

> **Everything is a plugin.**

There is no privileged kernel — bash is an ordinary plugin, the model adapter is a plugin, and even the agent loop itself is a replaceable plugin. Extensions always happen by "hanging a plugin alongside", never by "changing the kernel"; uninstalling recycles everything, leaving no residue.

### 1.2 Worldview: Three Iron Laws

"Everything is a plugin" is not a slogan; it is supported by three engineering iron laws:

**① Registrations are effects**

Every contribution is registered via `ctx.effect()` / `ctx.on()`, and `register()` returns a disposer. When a plugin is uninstalled, everything it registered is recycled — there is no residual state left over from "installed but not cleanly removed".

**② Model-visible ⟺ logged**

Anything that reaches the model's request must be rebuildable from the session log; any new model-visible input must have a corresponding session event. This iron law is the foundation of all of dsh's reliability: **every byte the model sees corresponds to a replayable event**.

**③ The capability-seam triangle is complete**

A qualified capability = Service Definition (machine contract) / Service Provider (implementation) / Consumer (caller), all three roles complete and closed within the package. It forces a separation between "what the interface looks like" and "how the work is done", so implementation details never leak to callers.

### 1.3 The Skeleton: How an Agent Runs

dsh's "spine" lives in the `core` group; a turn flow threads it together:

**agent loop**: one turn = zero or more steps; one step = one model request + the tools it calls. The event flow is fixed:

```
turn/start → step/start → llm/stream → assistant/message → tool/call
→ tools/pre-execute → tools/execute → tools/post-execute → tool/result
→ step/end → (need another request?) → turn/end
```

**Event-sourced session**: the entire interaction history is an append-only `SessionEvent` log (raw log, never deleted); what the model actually sees is its derived projection (surface). When the context grows too long, compaction does "replacement compression" — replacing old ranges with a summary checkpoint rather than truncating by appending. **Tokens truly decrease, the raw log is never lost, it is replayable and auditable**, and the KV prefix cache is preserved.

**Tool registry**: a scope-isolated registry + a guarded execution pipeline. Tools are defined via `defineTool` (strongly typed contract), registered into `ctx.tools`, and pass through guards (timeout, approval, scope filtering) when executed.

### 1.4 The Capability Map

All capabilities hang on the central axis as plugins, grouped by responsibility into five categories:

| Group | Capability packages |
|---|---|
| Execution environment | llm / shell / subprocess / terminal / fs / lsp / code-runtime / sandbox / e2b |
| Orchestration intelligence | subagent / workflow / plan / todo / goal / compaction / context |
| Knowledge & external | skill / web / mcp / storage / attachment |
| Governance guardrails (upper) | guard / hooks / interaction (approval) / credentials / settings / identity / session / session-query |
| Governance guardrails (lower) | self-modification / acp / schedule / jobs / feedback / spill |
| Assembly & distribution | bundle / preset / boot / api / typert / sdk / client / extensions |

The human interaction surface has six layers: CLI (headless one-shot tasks), browser GUI (`dsh --profile web`), approval / command / ask protocols (the `interaction` group), ACP (automation-only, no human in the loop), SDK / JSON-RPC (embedding dsh into other products), and cordis.yml (assembling the entire agent tree at the platform layer).

### 1.5 Where the Depth Shows

"Depth" is not piling up features; it is making a few key mechanisms thorough:

**fail-safe approval**: before a tool executes, `PreToolDecision` has three states `allow / deny / ask`. `ask` is handled by a human when an approval channel is attached; **when there is no channel it degrades to deny** — dangerous operations must pass through a human, otherwise they are rejected by default. This is the "brake" between human and agent.

**Long-horizon tasks**: not by "one extremely long turn", but by split + continue + control — split (subagent / workflow / ralph cut long tasks into bounded units), continue (compaction + durable checkpoint, resumable after crash), control (round cap / barrier / turn-stopping give a hard boundary for "when to stop").

**Four-layer memory**: no vector DB / RAG. Session memory (raw log, replayable) / cross-session memory (session-reference read-only snapshots, max 3, treated as untrusted) / long-term knowledge (the AGENTS.md file chain, "the file is the memory") / user identity (settings / identity / credentials). Stance: memory = rebuildable state; automatic fuzzy recall is refused — automatic recall = uncontrolled context injection = a poisoning surface.

### 1.6 Depth = Constraint-Type Victories

What dsh shows are all "constraint-type" victories, not a single "feature stunt":

| Design it prides itself on | Content |
|---|---|
| No privileged kernel | Even the kernel bash is an ordinary plugin, seamlessly replaceable by a sandbox |
| Rebuildable context | Model-visible ⟺ logged; still replayable and auditable after compaction |
| Crash-safe compaction | durable lock (event pair), not an in-memory mutex; a crash mid-compaction leaves a detectable orphan lock |
| KV cache awareness | every package must declare its KV Cache effect; compaction uses replace to preserve prefix reuse |
| Human commands do not disturb the model | `/compact` etc. go through the command plane, never entering the model message, no token cost |
| Scope restraint | two-level flat + shadowing, refusing scope explosion |
| Goal as state | goal folds into the session state machine instead of building a separate "goal engine" |

On engineering discipline: explicit package boundaries, misconfiguration fails loud on the spot, branded opaque ids across boundaries, a per-file 100% coverage gate. **All mechanisms trace back to the same discipline: rebuildable, auditable, replaceable, unpolluting, non-crashing, non-leaking.**

### 1.7 Preview: Depth and Breadth Are Orthogonal

At this point we can characterize dsh: **it answers "how a capability is reliably executed"** — sandbox, credentials, audit, compaction are all there to make every operation reliable.

The text-cli (tc) this document is based on answers another question: **"how capabilities are broadly supplied and consumed"**. Depth and breadth are two orthogonal dimensions — dsh is deep, tc is broad.

dsh is first self-consistent as itself, not depending on external completion. The next three chapters present its three integration forms with tc: bridge (consumption), runtime (hosting), hybrid (merger).

---

## Chapter 2 The Bridge: Depth Borrowing Breadth — dsh Agent Taps into the tc Directive Ecosystem

tc (text-cli) uses one line `AI:domain;action,params` as its primitive and presses the "capability breeding threshold" down to "people who can speak" — its directive-package ecosystem (arithmetic, weather, maps, even a florist's experience) is a natural "directive marketplace". This chapter presents the first integration form: **the bridge** — a dsh agent actively goes shopping at this marketplace.

### 2.1 Positioning

The bridge is a **consumption-layer** integration:

| Dimension | Bridge |
|---|---|
| Direction | dsh reaches out for capabilities (outbound) |
| dsh role | Consumer |
| Faces | dsh agent (trusted subject) |
| Guardrail need | thin (agent is trusted; no sandbox / approval needed) |

In one sentence: **"the tool-eater" meets "the directive marketplace"**. dsh's agent is the tool-eater — it decides what to call inside its own loop; tc is the vast directive marketplace — it provides the things that can be called. The bridge is the seam between the two: it stitches the tc marketplace into dsh, and keeps the LLM remembering only one prefix (`AI:`).

Chapter 1's "depth and breadth" first converge here: dsh's depth guarantees "eaten capabilities are reliably orchestrated into its own loop", and tc's breadth provides "capabilities that can never be eaten up".

### 2.2 Core Decision: One Plugin = One Capability Seam

The bridge's first design decision directly determines its shape: **do not register every tc directive as a dsh tool; instead let one plugin play the capability seam, hang three capability sources inside it, and expose a fixed, closed-set, stable set of five tools to dsh.**

Why not "one tool per directive"?

- **tc directive packages are dynamic**: installed means declared, uninstalled means gone, and endpoints change too. If every directive were statically registered as a dsh tool, dsh's plugin tree would drift as the tc endpoint changes — dsh would have to keep reinstalling plugins.
- **tc's package schema, `AI:` syntax, envelope, dual tokens** — these are tc's internal language. If they leaked into dsh's contract, dsh's kernel would "see" things it should not see.

The bridge seals all of this inside its own implementation layer. It satisfies Chapter 1's capability-seam triangle:

| Role | The bridge's instantiation |
|---|---|
| Service Definition | the strongly typed interface of the five tools |
| Service Provider | the three capability-source implementations (remote HTTP / local JS engine / dsh tool proxy) |
| Consumer | dsh agent |

The bridge is an **adapter, not a passthrough**: it absorbs the philosophical difference between tc's thin protocol and dsh's capability plane, letting neither side change its kernel. dsh does not reinstall plugins when the tc endpoint changes — tc's dynamism is fully preserved by the bridge.

### 2.3 Three Capability Sources → Five Tools

The bridge hangs three capability sources inside itself:

1. **tc remote endpoint** (HTTP, wrapping the A0 SDK) — calls directives registered on the remote side
2. **tc local JS engine** (`textcli-core`, in-process, zero network) — executes local JS packages like `tc-math`
3. **dsh's own tools** (including mcp tools, in-process proxy) — reuses dsh's registered tools

The three sources are exposed to the LLM through five tools:

| Tool | Capability source | Purpose |
|---|---|---|
| `call_tc` | remote (or short-circuited local) | call one tc directive, `prompt` carries `AI:domain;action,params` |
| `run_tc_js` | local JS engine | execute a local JS directive package in-process with zero network, returning an envelope isomorphic to `call_tc` |
| `tool_avatar` | dsh's own tools | in-process proxy for dsh native / mcp tools, saving tokens |
| `find_tc` | three-source aggregation | unified discovery surface: returns a flat dictionary, each entry carrying its own `call_tool` |
| `wait_tc` | remote | poll asynchronous long tasks (tc's tracked semantics: a human who replies once every three days can still be caught) |

`find_tc`'s return shape is the "consumption closed loop" — not a bare list grouped by source, but each capability carrying its own way to be consumed:

```json
{
  "tc-math_eval": { "cli": "AI:tc-math;eval,<expr>", "call_tool": "call_tc", "rank": 90 },
  "github.create_issue": { "cli": "github.create_issue", "call_tool": "tool_avatar", "rank": 50 }
}
```

The LLM gets "capability → cli template → which tool to use" in one shot, without guessing. `rank` only decides return order, not "whether it should be called" — the semantic responsibility for choosing a directive always rests with the caller.

### 2.4 The One-Dimensional Experience

The bridge's only promise to the LLM is: **you always write `AI:domain;action,params`**. The `tc__` prefix, endpoint switching, envelope conversion — all internal to the bridge; the LLM neither perceives them nor should it.

The five tools' `description` fields are the model-visible strongly typed contract; but the model does not automatically know "how to call correctly", so a companion SKILL compresses it into a few disciplines:

- **Discover first, then call**: when unsure of a directive, `find_tc` first; do not guess the `AI:` syntax
- **The allowlist is the boundary**: only call directives seen in `find_tc`
- **One-dimensional experience**: every tc directive expressed in one sentence, never split into JSON fields
- **Handle async**: when `call_tc` returns an async task → immediately poll with `wait_tc`
- **One direction**: `tool_avatar` only calls dsh's own / mcp tools, never exposing backward
- **Look at the envelope first on failure**: when `{ok:false, err}` comes back, look at `err` (closed-set 6 codes) before degrading or switching directives
- **Save tokens**: take everything at once with `find_tc`; do not circle back to dsh's native channel

One counter-example best shows what "one-dimensional" means: `call_tc({domain:'weather', action:'query', params:[...]})` breaks the `AI:` one-dimensional contract — the correct way is `call_tc({prompt:'AI:weather;query,Beijing'})`.

### 2.5 The Two-Branch Envelope and the One-Direction Discipline

The bridge's conversion layer has **two envelope branches**:

| Branch | Conversion | Input → output |
|---|---|---|
| tc family | `tcToDsh` | tc closed-set envelope `{rst_types, rst_data, rst_err}` → dsh strongly typed result (`ok = (rst_err === '' && status is not not_found-like)`) |
| dsh tool family | `toolToDsh` | dsh native / mcp tool result → `{ok, data, err?}` |

The two return semantics are non-isomorphic, but both are absorbed in the bridge's own conversion layer — **dsh's kernel only sees clean strongly typed tool results**. tc's envelope ambiguities (e.g. `status:"ok"` but the `error` field says "not found") are digested inside `tcToDsh` and never leak into the loop.

Two disciplines run through everything:

- **One direction**: the bridge is a "dsh → outside" adapter. `tool_avatar` is only called by the dsh agent and only calls dsh's registered tools; there is no path that exposes dsh capabilities back to tc — the bridge does not overstep into a two-way bridge.
- **Model-visible ⟺ logged**: every `call_tc` prompt and return is written into a session event — the tc envelope becomes an ordinary tool result in dsh's session log; Chapter 1's iron law continues to hold on the bridge side.

### 2.6 The Bridge's Internal Structure

The bridge's source organization corresponds one-to-one with its design (source location: `src/skeleton/bypass-service/dsh/dsh-tc-bridge/`):

```
dsh-tc-bridge/
├── src/
│   ├── index.ts          # apply(ctx) assembly + makeBridgeDeps
│   ├── tools.ts          # the five tools (createBridgeTools)
│   ├── config.ts         # config (three-state endpoint / dual tokens / allowlist / jsPkgDirs)
│   ├── envelope.ts       # two-branch conversion: tc envelope ↔ dsh tool result
│   ├── tc_client.ts      # remote tc endpoint (call / discover / poll / wait, A0 SDK)
│   ├── js_engine.ts      # local textcli-core engine (load / execute / discover)
│   ├── tool_proxy.ts     # tool_avatar in-process proxy (including mcp tools)
│   ├── runtime_detect.ts # mode detection (bridging / hybrid)
│   ├── mapper.ts         # prefix bijection tc__ ↔ AI:
│   ├── allowlist.ts      # tc directive allowlist
│   ├── session.ts        # session passthrough (Model-visible ⟺ logged)
│   └── types.ts          # bridge-internal types + ToolRegistry dependency-injection interface
```

Modules and their correspondence to the five tools:

| Module | Corresponding tool / responsibility |
|---|---|
| `tools.ts` | registration entry for the five tools |
| `tc_client.ts` | `call_tc` / `wait_tc` / `find_tc` (remote source) |
| `js_engine.ts` | `run_tc_js` (local source) |
| `tool_proxy.ts` | `tool_avatar` (dsh tool source) |
| `envelope.ts` | the two envelope branches (`tcToDsh` / `toolToDsh`) |
| `runtime_detect.ts` + `mapper.ts` + `allowlist.ts` | the hybrid-mode trio (short-circuit / prefix bijection / allowlist) |
| `session.ts` | writes a session event on every call |

At this point the consumption layer is fully clear: **the bridge uses one plugin, five tools, two envelope branches to stitch tc's "breadth" into dsh's "depth", while the LLM always sees only one prefix.** The next chapter presents the second integration form — the runtime: dsh is no longer the buyer, but the seller.

---

## Chapter 3 The Runtime: Depth Carrying Breadth — dsh Becomes a tc Runtime Node

In Chapter 2 dsh was the buyer. In this chapter it changes role: **dsh becomes a tc runtime node** — exposing tc protocol endpoints and executing tc's JS directive packages. The buyer becomes the seller.

### 3.1 Positioning

The runtime is a **hosting-layer** integration:

| Dimension | Bridge (Chapter 2) | Runtime (this chapter) |
|---|---|---|
| Direction | dsh reaches out for capabilities (outbound) | directives come in from outside (inbound) |
| dsh role | Consumer | Host |
| Execution target | dsh agent calls tc directives | dsh executes tc's JS directive packages |
| Faces | dsh agent (trusted) | tc callers (untrusted) |
| Guardrails | thin | thick (sandbox / credentials / approval / audit, the full set) |

In one sentence: **`dsh-tc-runtime` is one JS implementation variant of tc — as a host, it chooses to carry the full 9-mechanism set, using dsh's "depth" to provide reliable execution for under-constrained JS packages.**

tc's protocol deliberately leaves things blank — it does not grab credentials, directories, or sandboxes; it only keeps the one-dimensional contract. The blank is the protocol's design, not a gap; the runtime, as a host, chooses to fill in these engineering guardrails at the implementation layer. The runtime lets dsh expose `POST /text-cli/cli`, routing tc directives into dsh's capabilities: sandboxed execution host, per-package credential isolation, approval, audit. Callers speak the tc protocol and enjoy dsh's engineering guardrails — guardrails they neither need nor notice.

### 3.2 Why "Thick" Cures "Few Constraints"

tc's JS directive packages are **easy to create but lightly constrained**: bare `require` loads arbitrary code, arbitrary file side effects, globally shared credentials, execution with no trace. The breeding threshold is extremely low (anyone who can speak can create one), but execution guardrails are nearly zero:

| JS package's "few constraints" | dsh runtime's "thick" |
|---|---|
| Bare `require` loading arbitrary code | sandboxed execution host, intercepting file / network / process side effects |
| Globally shared credentials, grab anything | per-package credential isolation; a package can only take the references it is authorized for |
| Execution leaves no trace, cannot be followed | full session audit, replayable and rebuildable |

The key realization: **dsh chooses to become a tc runtime implementation — and hosting "under-constrained" JS packages requires "thick", and dsh happens to be that thick thing.**

What is dsh running after the transformation? A `AI:domain;action,params` comes in from outside; dsh parses, authenticates, runs the corresponding package in the sandboxed execution host, wraps it in a tc envelope, and returns it. dsh does not rewrite the protocol, does not modify tc — it simply connects tc's directive-package ecosystem into its own reliable execution chain.

### 3.3 The 15-Package Structure and 7 Red Lines

The runtime is in **bypass form**: it only mounts plugins, does not invade dsh's kernel, and does not claim "standard runtime" status. Mounting is done as a profile combination (`dsh-tc` = base + host-webserver + runtime-bundle), while disabling three lines of dsh's native `agent` / `agent-default-model` / `llm` — **tc only provides directive execution capability; it does not take over dsh's conversation / model kernel**.

The implementation is a 15-package monorepo (source location: `src/skeleton/bypass-service/dsh/dsh-tc-runtime/`), whose physical structure is:

```
dsh-tc-runtime/
├── runtime-inbound/      # inbound HTTP: POST /text-cli/cli → envelope; six-stage pipeline; reserved-domain interception
├── runtime-mapper/       # directive mapping: tc directives ↔ ctx.tools; tcToDsh / dshToTc
├── runtime-sandbox/      # sandboxed execution host (restricted subprocess + policy 7-class layered guardrails)
├── runtime-credentials/  # per-package credential isolation (CredentialRef + env allowlist injection)
├── runtime-audit/        # audit channel: independent append-only JSONL (traceId + seq)
├── runtime-approval/     # approval answerer (ownership filtering / HMAC / fail-closed)
├── runtime-meta/         # text-cli;* meta-directives (install / query / path / pro / ...)
├── runtime-quota/        # dsh-quota: period window + atomic check+consume
├── runtime-host/         # host directives: dsh-sandbox / credential / approval / ...
├── runtime-path/         # path engine: declarative interpreter + workflow compilation
├── runtime-aggregate/    # aggregate try-in-order degradation + async-task bridge
├── runtime-mesh/         # mesh forwarding: route table / cycle prevention / backoff
├── runtime-bridge/       # protocol bridge: mcp-client → mcp__<server>__<tool>
├── runtime-pro/          # facade registry: short name → path / aggregate
└── runtime-contract/     # global acceptance: canonical envelope + 16-row mapping contract
```

Grouped by responsibility into five layers:

| Layer | Packages |
|---|---|
| Access | runtime-inbound (inbound six-stage pipeline: parse→route→execute→envelope→audit), runtime-mapper (tc↔dsh translation + discovery) |
| Security guardrails | runtime-sandbox (cycle detection + sandbox policy + execution host), runtime-credentials (credential isolation), runtime-audit (independent JSONL), runtime-approval (approval) |
| Scheduling & orchestration | runtime-path (declarative interpreter), runtime-aggregate (aggregate degradation + async tasks), runtime-mesh (cross-node), runtime-pro (facade), runtime-host (host directives), runtime-quota (quota) |
| Protocol bridge | runtime-bridge (mcp-client protocol bridge) |
| Contract & acceptance | runtime-contract (envelope + 16-row mapping contract), runtime-meta (meta-directives + lifecycle) |

The 7 red lines (against regression):

① no invasion of dsh's kernel; ② no plaintext credentials in the JS execution environment; ③ sandbox rejects by default; ④ closed-set protocol; ⑤ reserved domain does not pollute `ctx.tools`; ⑥ approval ownership filtering (dsh agent approvals are never hijacked by a tc webhook); ⑦ tc audit is an independent JSONL, never written into `ctx.sessions`.

**Bottom-line principle**: any unforeseen failure goes to `ERR_EXECUTION` rather than silent success; approval / sandbox / missing credentials all fail closed when the capability is absent.

### 3.4 The Closed-Set Protocol and the 16-Row Mapping

The runtime **does not reinvent the protocol** — it reuses `textcli-core`'s envelope (parser / envelope / alias / registry / loader) and asserts field-by-field identity with contract tests. This is hard evidence of "zero protocol rewrite" and a regression gate that keeps the tc side from drifting from the true source.

The envelope has three fields: `{rst_types, rst_data, rst_err}`. The error codes form a closed set of 6; any dsh-side signal must land in the closed set, otherwise it falls back to `ERR_EXECUTION` — **the protocol never silently lets things through**.

The key mechanism is the **dsh→protocol 16-row mapping**: various dsh-side signals are translated one by one into protocol language (representative rows shown):

| dsh-side signal | Protocol code | Meaning |
|---|---|---|
| tool not registered | `ERR_NOT_FOUND` | directive does not exist |
| sandbox policy rejection | `ACCESS_DENIED` | capability not authorized |
| approval deny / no channel | `ACCESS_DENIED` | human gate rejected, fail-closed |
| missing credential | `SERVICE_DENIED` | service-side credential unavailable |
| cycle detected | `ERR_EXECUTION` | `CYCLE_DETECTED`, structural rejection |
| mesh unreachable | `ERR_ROUTING` | cross-node failure |
| quota exceeded | (not an error) | `rst_data.status="stop"` degradation signal |
| aggregate degradation exhausted | (not an error) | `rst_data.status="error"` + reason |
| unknown / not listed | `ERR_EXECUTION` | fallback |

Note that quota exhaustion and degradation exhaustion are **not errors** — they go through the `rst_data.status` degradation signal, keeping the 6-code closed set unpolluted while giving callers structured semantics. This is one explicit confluence at the protocol layer between dsh's "depth" (auditable degradation semantics) and tc's "breadth" (the caller's semantics are never broken).

### 3.5 Deep-Broad Alignment and Contrast

The runtime does not "happen to host" tc packages; rather, **dsh host's deep mechanisms, via `dsh-tc-runtime` (tc's implementation variant), align and contrast item by item with tc protocol's broad mechanisms**. After the merger, every pair opens both a "depth" and a "breadth" face:

| dsh's mechanism (depth) | tc protocol's mechanism (breadth) | After the merger: how depth and breadth both appear |
|---|---|---|
| Event-sourced session (raw log→surface→compaction) | async tasks / tracked long chains | every step of a long chain has a replayable session; therefore tracked long tasks can be accepted |
| subagent / workflow (splitting chains) | aggregate degradation (merging chains) | multi-provider step-down with auditable stop/error semantics; one directive hangs on multiple capability sources, aggregation does not crash |
| fail-safe approval (default deny) | closed-set envelope stop/error degradation signals | dangerous operations must pass a human; even when rejected, it returns neatly in a tc envelope |
| Per-package credential isolation (references, not plaintext) | protocol leaves blank (does not grab credentials) | can safely host any third-party under-constrained JS package |
| Four-layer memory / session rebuild | the protocol's cross-call context | complex multi-turn tc directives can be reliably hosted |
| Facade abstraction (short name + cycle detection) | the protocol mechanism set | many packages and many domains are discovered under one tc protocol entry |

**Core logic**: each row's "depth" and "breadth" are not separate; they are **two faces of the same mechanism after the merger** — depth guarantees "reliable", breadth guarantees "dare to accept, can accept, accept broadly". Depth is the confidence behind breadth; breadth is where depth earns its keep.

At this point the bridge-runtime contrast is complete: **the bridge is thin, the runtime is thick; the bridge consumes, the runtime hosts; the bridge faces the trusted dsh agent, the runtime faces the untrusted tc caller.** The previous two chapters presented them separately — the next chapter, they move into the same process.

---

## Chapter 4 Hybrid: Depth and Breadth in One Body — Bridge + Runtime Coexist

In the previous two chapters, the bridge (consumption) and the runtime (hosting) were two plugins, two forms, two faces. This chapter they coexist in the same dsh process — and not merely side by side: **the bridge senses the runtime and actively changes its own behavior**. This is the merged form of the whole system.

### 4.1 Three Modes

The relationship between the bridge and the runtime is determined by "whether the current dsh also mounts `dsh-tc-runtime`", giving three forms:

| Mode | dsh role | Trigger condition | Bridge's form |
|---|---|---|---|
| Bridging | agent (consuming tc) | no runtime plugin | `call_tc` goes remote HTTP; `find_tc` fully exposes all three sources |
| Service | tc protocol host (production) | dsh is runtime only | bridge does not intervene; the runtime serves externally on its own |
| Hybrid | agent + runtime | runtime present in the same dsh | bridge does runtime awareness: short-circuit + allowlist + prefix mapping |

The previous two chapters each presented one: Chapter 2 was the bridging mode (dsh pure consumption), Chapter 3 the service mode (dsh pure hosting). This chapter is the hybrid — and it is the genuinely new increment of this integration.

### 4.2 The Bridge's Runtime Awareness

The bridge's mode detection is a **pure probe**: at startup / runtime it checks whether `ctx.tools` already has `tc__`-prefixed tools (or a marker injected by the runtime plugin), returning `bridging` / `hybrid`. The probe result decides the default behavior of `call_tc` and `find_tc` — all through Config, with the LLM side always one-dimensional.

In hybrid mode, the bridge has three specializations:

**① `call_tc` self-request direct short-circuit**. Instead of round-tripping `AI:d;a` through `POST 127.0.0.1:<port>/text-cli/cli` (which would be two pointless in-process HTTP round trips), it parses out `domain;action` → maps to the runtime-registered `tc__domain__action` tool → calls it directly in-process. This reuses all of the runtime's guardrails (sandbox / approval / audit / quota / cycle detection) without executing twice.

**② `find_tc` allowlist filtering + prefix bijection**. tc directives are hidden by a configurable allowlist (granularity down to `domain;action`, supporting domain-level wildcards), with a `tc__d__a` → `AI:d;a` prefix mapping — the LLM only discovers the allowed tc capabilities, and the dictionary always uses the `AI:` primitive form. An empty allowlist = everything exposed (backward-compatible with bridging mode).

**③ `tool_avatar` fully exposed**. The allowlist only applies to tc sources, not the `dsh_tool` source — because the tc primitive saves roughly 5× tokens per call compared to a native JSON tool call, `tool_avatar` is the core token-saving channel and must not be weakened.

### 4.3 The LLM Always Sees One Prefix

Across all three modes the LLM's experience is identical: **always write `AI:domain;action,params`**. The `tc__` prefix, short-circuit or remote, allowlist filtering — all mode differences are absorbed at the bridge's seam; the LLM neither knows nor needs to know.

Two constraints make "one-dimensional" hold:

- **Prefix bijection**: `AI:d;a` ↔ `tc__d__a` must be a bijection. `domain` / `action` names must not contain `__` (aligned with mcp-client's double-underscore naming), otherwise the mapper rejects rather than silently mis-mapping.
- **The allowlist hides names, not execution**: the allowlist only acts on `find_tc`'s discovery surface (hiding names); `call_tc` lets out-of-allowlist directives through by default — this is a soft limit, consistent with tc's one-dimensional contract: semantic responsibility rests with the caller. For a hard limit, turn on execution-layer validation.

In hybrid mode the SKILL adds two disciplines: **the LLM always writes the `AI:` primitive** (never sees the `tc__` prefix), **and only calls directives seen in `find_tc`** (the allowlist is the boundary).

### 4.4 The Merged Panorama

In one process, dsh is simultaneously an agent and tc's runtime implementation (`dsh-tc-runtime`):

- as an **agent**, it thinks and decides in its own agent loop, deciding which tools to call
- as a **runtime**, it exposes `POST /text-cli/cli`, hosting directives from tc callers
- when the agent itself decides to call a tc directive, the bridge short-circuits to the in-process runtime — **it eats the meal it cooked itself**

Chapter 1 said depth and breadth are orthogonal — orthogonality is not isolation. In the same process, depth and breadth each sit where they belong: dsh's loop is responsible for decision, tc's protocol for expression, the bridge for translation and sensing in the middle, the runtime for reliable execution underneath.

Here the whole document closes: **dsh is first self-consistent (depth), then borrows breadth (bridge), carries breadth (runtime), and finally merges depth and breadth in one body (hybrid). This is not a confrontation of two systems, but hosting based on the text-cli protocol — dsh is both consumer and host, the thin protocol and the thick implementation joined as one.**

---

## Appendix: On the Universality of the Natural Primitive, Seen from the dsh Integration

### The Proposition

> **The protocol's universality comes from the language substrate it inherits: any capability expressible in natural language is naturally inside the protocol's semantic space. The protocol does not merge anything — because it is isomorphic to language.**

The protocol's root primitive is natural language; **to speak is to realize**: the moment a person expresses an inner picture, it is the realization of a same-dimensional primitive. Natural language (including programming languages — which are also a kind of language, a stricter gear on the controlled spectrum) is the **same-dimensional expression** of this semantic space, not a hetero-dimensional encoding. The developer writing code is also a speaker: a native package (code) and a nocode package (spoken words) have no species difference — both are realizations of language, differing only in spectrum gear.

### Why dsh Is the Strongest Evidence

tc and dsh are opposed at the value level — tc bets "the machine adapts to the LLM emitting text" (no boundary validation, validation pushed to the handler), dsh bets "strongly typed capability seams" (Service Definition is the machine contract). Yet none of the three integration forms (bridge / runtime / hybrid) asks dsh to change its faith: dsh's capability seams, session logs, and agent-loop are fully preserved.

The key realization: **dsh realizes the tc protocol with TS (a programming language)** — `dsh-tc-runtime` is exactly one JS implementation variant of tc (on a par with pypi being the Python implementation, npm the JS implementation, and cloudbase the cloud-function implementation, all in the bypass-runtime family). Two philosophically opposed systems can address each other not because tc can merge dsh, but because **they are both realizing pictures in language** — the protocol merely lets them see each other within the same semantic space.

**Systems opposed in values are naturally isomorphic, so universality does not depend on the other side agreeing with you.**

### The Logical Mechanism: Language Is a Substrate, Not a Seam

The protocol needs no "entry" or "seam", because:

> Any system that ultimately serves humans or AI must use language as its medium — human use is expressed through language, and AI's input/output is language at its core. And "being in language" is itself the condition of participation; no connection is required.

The protocol merely projects the already-existing semantic space into an addressable form: `AI:domain;action,params` + envelope. It does not touch the other side's interior — it only provides a handle, letting things on the language plane address each other.

### Boundaries and Costs

- **Boundary**: everything speakable is already inside; what cannot be spoken does not belong to the semantic space. Pure physical processes and closed systems without an interface are not inside — but they can be brought in through an intermediary translation (that is precisely the bridge's job).
- **Cost**: the protocol collects no "seam tax". The minimal baseline is only "directive execution + three-field envelope", and integration can be very light — pypi pure-function calls and npm in-process execution are examples. The thickness of `dsh-tc-runtime`'s 15 packages is its self-imposed pressure, as one JS implementation variant of the tc runtime, choosing to carry the full 9-mechanism set (all optional enhancements): **thickness belongs to the runtime's choice, not the protocol's cost, and not tc's debt.**

### Closing

> **The protocol is the projection / handle of the semantic space — universality comes from the language substrate itself, not from tc's capability; light or heavy, the runtime chooses for itself, and the protocol never collects.** What the dsh integration proves is not "tc can merge everything", but: everything in language already exists in the same dimension, and the protocol merely lets them see each other.

# text-cli-based Agent Solution Example

> Source locations:
> - tc-web-chat artifacts: `src/skeleton/base/A1-skill/tc-web-chat/` (`tc-web-chat.html` / `_zh.html` / `_en.html`)
> - tc-web-chat source: `src/skeleton/base/A1-skill/tc-web-chat/tc-web-chat-src/` (modular source + `build.js`; rebuildable, capabilities addable/removable)

---

## Core Contents of a Modern AI Agent

### 1.1 Drawing the Boundary: What This Document Discusses and What It Does Not

"Modern Agent" is all too easily treated as a vague buzzword. Before expanding, we first set aside one piece of **default infrastructure** — **built-in reasoning**.

It is not that reasoning is unimportant; it is that it is not a problem Agent engineering needs to solve: reasoning is the capability of the LLM itself. For Agent engineering, reasoning being **externalized** is the norm — you obtain it by plugging in a model; there is no such thing as "implementing reasoning yourself". The real question is not "whether there is reasoning", but "how reasoning is scheduled".

After setting that aside, what remains is the capability layer that Agent engineering must build brick by brick.

### 1.2 Mental Model: Every Capability Hangs on the Agent Loop

The behavior of a modern Agent can be summarized by one loop:

```
plan → act → observe → re-plan → …
```

There are four roles on this loop:

| Role | What it does | Usually carried by |
|---|---|---|
| Decision maker | Decides what to do next | LLM (external) |
| Executor | Actually does the work | Tool / runtime |
| Observer | Turns the result into a decidable signal | Runtime returns the envelope |
| Re-decision maker | Reads the signal, decides continue / retry / switch / wrap up | LLM (external) |

**Every capability listed below can find its place on this loop.** To judge whether a system "looks like a modern Agent" is to see whether this loop is complete and whether every capability has a clear bearer.

### 1.3 The Capability Checklist

Grouped by loop role into four layers, eleven items in total:

**Perception layer — the input port of the loop**

1. **Perception and context management**: receive multimodal input (text / image / audio-video / files); manage long context (chunking, retrieval, compression).
2. **State perception**: perceive the current environment state (files, processes, running services) and update it in real time as operations proceed.
3. **Memory**: short-term working memory (intermediate state of the current task) + long-term memory (cross-session knowledge accumulation, e.g. user preferences, project conventions, past decisions); with write, retrieve, and forget mechanisms.

**Decision layer — the brain of the loop**

4. **Reasoning** (externalized): connecting to an LLM for understanding, generation, and judgment. Agent engineering cares about the **entry and exit** of reasoning — what context goes in, what action comes out.
5. **Task decomposition**: breaking a large goal into executable sub-steps with explicit order, dependencies, and outputs.

**Action layer — the hands of the loop**

6. **Tool calling**: registration and discovery of tools, parameter validation, result parsing — the only channel through which an Agent touches the real world.
7. **Temporary orchestration power**: an Agent is not merely "picking a tool" — it can **organize multi-step execution on the spot**, stringing several tools into one execution plan (with data flow, branches, degradation) and handing it to the runtime for one-shot execution. This is the watershed between an Agent and a "single function call".

**Governance layer — the brakes and instruments of the loop**

8. **Self-evaluation and correction**: turning execution results into a decidable signal of "whether the goal was reached", driving the next round — continue, retry, change parameters, change path, declare done.
9. **Human interaction and human gate**: requesting human confirmation before critical / risky operations; tiered authorization; the user can interrupt and redirect at any time.
10. **Security governance**: credential isolation, sandboxing, sensitive-operation protection, circuit breaking — unauthorized actions are intercepted before they happen.
11. **Observability**: logs, call chains, cost metering — when something goes wrong you can look it up; how well it runs can be quantified.

One sentence to close: **A modern Agent = perception that catches + decision that thinks clearly + action that gets done + governance that brakes.**

### 1.4 The Capability Coordinate System

Compress the eleven items above into eight backbone coordinates (reasoning was set aside in §1.1; task decomposition merges into temporary orchestration power; state perception merges into perception and context management), each with a **judgment criterion** (what counts as "having it"). This table is the anchor of the whole document — the lightweight example in Chapter 2 will check every cell against it.

| # | Capability | Definition (what problem it solves) | Judgment criterion (how "having it" is judged) |
|---|---|---|---|
| 1 | Perception and context management | Catching the world's information | Supports multimodal input; maintains context and continuously tracks environment state |
| 2 | Memory | Remembering "who I am, what I have done" | Has long-term memory, with write / retrieve / forget mechanisms |
| 3 | Tool calling | Touching the real world | Tools can be registered, discovered, parameters validated, results parsed |
| 4 | Temporary orchestration power | Organizing multi-step execution on the spot | Agent can generate a multi-step plan; runtime executes once and returns one envelope |
| 5 | Self-evaluation and correction | Knowing "whether the goal was reached" | Execution results carry a standardized signal; Agent self-drives the next round from it |
| 6 | Human interaction and human gate | Dangerous actions have a human checkpoint | Has tiered approval; critical operations can be interrupted |
| 7 | Security governance | Unauthorized action intercepted before it happens | Credential isolation, sandbox, sensitive-operation protection, circuit breaking |
| 8 | Observability | Can look it up when something goes wrong | Has logs, call chains, cost metering |

> The judgment criteria are deliberately written to be "comparable, checkable". The second capability ledger will mark each cell with three marks: **✅ implemented in-agent** / **⚡ carried by the LLM or the tc runtime** / **❌ temporarily absent**.

## A Lightweight Example - tc-web-chat

Now, using Chapter 1's coordinate system, look at a real minimal implementation: `tc-web-chat`. It wants to prove one thing — **the standard is heavy; the implementation can be light**.

### 2.1 What It Is

tc-web-chat is a **complete Agent**, carried by just one HTML file:

- **Zero install**: no installer, no login, no external dependency libraries — double-click `tc-web-chat.html` and it opens, start chatting immediately
- **Not bound to any platform**: fill in a backend address and it talks to that backend; resources in replies are rendered inline, no navigation away
- **Two addresses decoupled**: chat goes through `Base URL`, directive execution goes through a separate `tc_endpoint` — where you chat and where you execute are independent

As a complete Agent, its three modules each do their job:

| In-agent module | Carries |
|---|---|
| LLM (Base URL) | reasoning / decision |
| tc-web-chat | coordination / UI / human gate |
| tc runtime (tc_endpoint) | tool execution |

### 2.2 How Tool Calls Happen

With tc enabled, one question flows through the do-not-disturb round:

```
Your input
  │
  ▼
[LLM thinks] → answer directly | decide to call a tool
                    │
                    ▼
           front-end agent fires → tc runtime executes → (human gate) → result fed back to LLM
                    │
                    ▼
             the final answer you see
```

Three key conventions make "fire → execute → feed back" reliable:

- **Protocol**: unified directive syntax `AI:domain;action,params`
- **Envelope**: responses are always `rst_types / rst_data / rst_err` — the front end **judges success only by `rst_err`** (`rst_err === ''` means success), never by HTTP status code
- **Error codes**: closed set of 6 (`ERR_NOT_FOUND` / `ERR_EXECUTION` / `ERR_ROUTING` / `INVALID_PARAMS` / `ACCESS_DENIED` / `SERVICE_DENIED`), from which the front end gives actionable hints

### 2.3 Temporary Orchestration Power

The LLM does not merely "pick a tool" — it can write an **executable program** on the spot (multi-step + data flow + dependency declaration), fire it once, and the runtime executes it once and returns one envelope. This is cell 4 of Chapter 1's coordinate system:

```
AI:text-cli;path,{
  "id": "tomorrow-weather",
  "type": "pipeline",
  "version": "1.0.0",
  "input_schema": {"type": "object", "properties": {"city": {"type": "string"}}},
  "requires": ["map;geocode", "weather;query"],
  "steps": [
    {"id": "geo", "instruction": "map;geocode,{input.city}", "output_as": "geo"},
    {"id": "wx",  "instruction": "weather;query,{geo.city},tomorrow", "output_as": "wx"}
  ]
},{"city":"Beijing"}
→ text-cli executes two steps once → one envelope back → LLM assembles the final answer
```

- **Orchestration power is in the LLM**: step order, data flow (`{geo.city}` cross-step interpolation), dependency declarations — all decided by the LLM at fire time
- **Execution power is in the runtime**: text-cli executes the plan, degradation, aggregation — the LLM never touches execution details
- This is precisely the watershed between an Agent and a "single function call"

### 2.4 Self-Driven Results

The envelope is the signal for "whether the goal was reached":

| Signal | Meaning |
|---|---|
| `status: ok / stop` | whether the business layer reached it |
| `rst_err: "" / error code` | whether the protocol layer succeeded |
| `result` | to what degree it was reached |

The LLM reads the envelope and decides the next step itself: continue / retry / change parameters / change path / declare done.

At this point, all four roles of Chapter 1's agent loop have found their bearers:

```
plan (LLM generates path) → execute (tc runtime) → observe (envelope signal) → re-plan (LLM self-drives next round) → …
```

This closed loop is the behavior of tc-web-chat as a complete Agent — decision goes to its LLM module, execution goes to its tc runtime module, observation and re-decision happen between the envelope and the LLM.

### 2.5 Human Gate and Security

The governance layer is implemented by tc-web-chat itself, with three mechanisms ensuring "dangerous actions have a human checkpoint":

- **Three-tier human gate**: Read-only auto (default, read-only directives run automatically, side-effect directives pop a card) / None (every directive pops a card) / Auto all (everything auto-runs, dangerous tier)
- **Byte identity**: what is shown to the human for confirmation and what the runtime executes are the same bytes
- **Circuit breaking**: after 3 consecutive failures of the same directive, it automatically switches to mandatory human review

Credential security: dual tokens (`Authorization: Bearer <access_token>` + `Service-token: <service_token>`), credentials injected by the runtime side via `context.env` — **the front end stores no credentials**; resource rendering validates `http/https` and uses iframe `sandbox`.

### 2.6 The Capability Ledger

Check each cell against Chapter 1's coordinate system:

| # | Capability | Judgment | Bearer |
|---|---|---|---|
| 1 | Perception and context management | ✅ / ⚡ | multimodal upload, chat history (tc-web-chat); environment state carried by tc runtime |
| 2 | Memory | ❌ temporarily absent | — |
| 3 | Tool calling | ⚡ | tc runtime executes (own protocol + envelope) |
| 4 | Temporary orchestration power | ⚡ | LLM generates inline path, runtime executes once |
| 5 | Self-evaluation and correction | ⚡ | LLM reads envelope to judge completion, self-drives next round |
| 6 | Human interaction and human gate | ✅ in-agent | three-tier gate + circuit breaking |
| 7 | Security governance | ✅ in-agent | dual tokens / byte identity / sandbox |
| 8 | Observability | ⚡ minimal form | session-level JSONL export archiving (tc-web-chat) |

### 2.7 Trade-off Landing

Seven of eight cells hit; only memory remains wholly missing. **Lightweight does not mean missing capabilities** — the capabilities are carried by an in-agent division of labor: the LLM decides, the tc runtime executes, tc-web-chat handles interaction and gating. The missing cell (memory) is tc-web-chat's current choice; lightweight is the result of the same choice, not a cost — that is why all its capabilities fit in a single file of around 90 KB.

### 2.8 An Addable/Removable Skeleton: From Artifact to Source

tc-web-chat is not merely "a 90 KB artifact" — it is a **modular skeleton**:

```
tc-web-chat-src/          # source (in version control; the html can be rebuilt, losing this is the real loss)
├── shell.html            # the true source of the shell (DOM + CSS)
├── tc-*.js               # feature modules: config / cache / parser / approval / quiet / chat / integrate
├── i18n.json             # single multilingual source
└── build.js              # zero-dependency bundling script → produces single-file artifacts
```

**Adding/removing capabilities happens at the source level**: add a feature = add / modify a module, rebuild to get a new artifact — not editing one big blob of HTML. **Language preference** is just one example of customization: add one line to `i18n.json`, rebuild with `--lang`, and you get a single-file version in your language.

This **calls back to 2.7**: the missing cell is not "impossible to have" but "a choice" — the source is a skeleton, need memory, add a module; need logging, add a module. **What is light is not just the artifact; what is light is the cost of change.** Users can entirely base themselves on this usable skeleton and, according to their own feature needs, customize their own single-page agent.

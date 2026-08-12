# text-cli Product Document

> **Language note:** This English text is a translation of the normative Chinese product document (`src/text_cli/base_text-cli/docs/product_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.

> One line of text, orchestrates everything. For humans and AI alike.

> All product promises are implemented. MIT license.

> [Protocol online location](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/en/SPEC_en.md) or [relative location](SPEC_en.md) · [Protocol-based engineering architecture design](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/en/design_en.md) or [relative location](design_en.md)
---

## What It Is: A Sentence Pattern You Already Know How to Say

The root of text-cli is the **imperative sentence in natural language**. You are not learning a new syntax — you are using an expression you (and any AI) are born knowing how to make — "go do something". text-cli simply compresses it into one fixed slot:

```
AI:domain;action,params
```

- **domain**: what field to act in (`weather` / `math` / `translate`…)
- **action**: what to do (`query` / `calculate` / `text`…)
- **params**: input given to it, comma-separated, trailing may be free text

**The same intent locks to the same capability, yields the same result.** The surface may be a string in any language — French, Japanese, Chinese, German — as long as it is an imperative, it converges to the same semantic space (canonical), activating the same capability. A human and an AI saying the same sentence, in whoever's hands, it is the same thing.

**From natural primitive, everything is schedulable** Code is not the boundary of capability, merely one of its forms — experience, knowledge, bookings, APIs, tools; anything that can be phrased as "go do something" is scheduled by this one sentence. text-cli's vitality depends on the "language ecosystem"; the protocol lives alongside natural language.

> Convergence of action is executed by the `target runtime`; the target runtime's alias normalization resolves back to the same canonical name.

---

## Two. Use It As a Tool First: 30-Second Verification That "The Promise Is Implemented"

Before talking about any concept, give you one real result. Every step in this document lets you reproduce it by hand.

### Turn Experience Into a Service Without Writing Code

Turning a Markdown experience note into an HTTP directive service requires only two things: a document + a template script.

```bash
cd src/text_cli/base_text-cli/template/base_nocode/en
python markdown_converter_en.py Bonsai-First-Aid-Manual_en.md
```

The service is up. Whether human or AI, saying this one sentence gets the diagnosis service:

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:home-gardening;plant-first-aid,pothos,yellow leaves"}'
```

You wrote no code, configured no JSON Schema, had no API key. **This Markdown itself is the thinnest implementation of the protocol.** This is the lowest-cost verification of "all product promises implemented" — a minimal version of "install-and-verify", but the protocol is the same set.

### Same Sentence, Shared by Human and AI

Switch to Python or JavaScript calls, not a word changed:

```python
from call import call, discover   # zero dependency, urllib implementation
result = call("AI:home-gardening;plant-first-aid,pothos,yellow leaves")
print(result.data)   # → {"status":"ok", ...}
```

```javascript
const { call } = require('./protocol/js/call');   // zero dependency, fetch implementation
const result = await call("AI:home-gardening;plant-first-aid,pothos,yellow leaves");
```

---

## What It Can Do: Four Things, From Thin to Thick

text-cli's capabilities unfold along a clear line — **the higher you go, the freer you are, but each step is addition, not replacement**. You can always fall back to the thinnest tier.

### Call Others' Capabilities (Thinnest, Zero Deployment)

Know one endpoint address, and you can call it in any language, any environment:

```bash
curl -X POST <endpoint address>/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt":"AI:text-cli;query"}'
```

> Using the SDK is easier — four languages (Python / JavaScript / Shell / PowerShell) zero dependency. No need to fill context with JSON Schema, no need to understand OAuth flow. [Online location](https://github.com/weihai-limh/text-cli/blob/main/src/skeleton/base/docs/README_en.md) or [relative location](../../src/skeleton/base/docs/README_en.md)

```python
from call import call, discover

result = call("AI:weather;query,Beijing,tomorrow")
# → DirectiveResult(ok=True, data={"temp":"12-18°C"})

directives = discover(search="weather")
# discover returns normalized canonical name, for machine filtering
# → [{"domain":"weather","action":"query","usage":"weather;query,<city>,<date>",...}]
```

**Why AI needs this:** Traditional tool calling requires stuffing JSON Schema into context for every tool, and the more tools the more the context bloats; and AI can only passively match already-exposed tools. text-cli turns tool calling into one line of text — AI doesn't need to understand API keys, coordinate systems, degradation chains, only needs to know "calling this sentence gets a result". The rest is left to `discover()` to discover, `call()` to execute. **Your reasoning budget is freed from deterministic questions like "what is 2+3+pi" and reserved for where reasoning is truly needed.**

### ② Turn What You Own Into a Directive (No Code Needed Either)

Your experience, scripts, APIs, even an MCP tool, can become a directive:

- **Your experience** → written as Markdown is a directive (demonstrated above).
- **Your API** → write `schema.json` + `handler.py`, translation, weather, maps — any API plugged in becomes one or more directives.
- **Your existing tools** → MCP bridge auto-compiles MCP tools into directives, Skill bridge maps external skills, no hand-writing needed.

### ③ String Multiple Directives Into a Pipeline (Path Orchestration)

A recurring flow like "check weather → clothing advice" is compiled into one path, thereafter only one directive is sent:

```json
{
  "id": "what-to-wear", "type": "pipeline",
  "steps": [
    {"id": "w", "instruction": "weather;query,{input.city},tomorrow"},
    {"id": "s", "instruction": "ai;infer,give clothing advice based on {w.result}"}
  ]
}
```

**Path only does orchestration and interpolation — no inference, no file read, no API call; all delegated to directives.** This is the protocol's design red line, and the source of its security.

**One-dimensional contract**: To the user, the entry is forever only one sentence `AI:domain;action,params`, the exit forever only one result. Internal aggregate degradation, path orchestration, MCP bridging, federation multi-hop, multi-provider routing — all happen behind the seam, **invisible to the caller**. Today the inside is some routing chain, tomorrow add a layer (edge cache, federation consensus), that sentence needs not a word changed.

> As long as you deploy the project's open-source runtime, you can feel the **one-dimensional contract**. See [online manual](https://github.com/weihai-limh/text-cli/blob/main/docs/product_manuals/user-manual_en.md) or [relative location](../product_manuals/user-manual_en.md)

### ④ Same Capability, Multiple Sources? Auto-Degrade (Aggregation)

When the same capability has multiple providers (e.g. multiple map APIs), the aggregate entry auto-switches by degradation chain — quota exhausted, some source down, auto-switch to next, **caller unaware**. You only see one entry.

> These four capabilities go from thin to thick. **Most users stop at ① and that is completely enough**; the higher you go, the closer you are to "provider" even "service provider", but no step is mandatory.
>
> **Another "thinnest" approach: bypass runtime** — you don't need to deploy a standard runtime, nor point to a remote endpoint. `pip install textcli-loader` (Python) or `npm install textcli-core` (JavaScript), load a directive package and execute locally. Suitable for when you only want to run a few directives locally and don't want to maintain a service. See [bypass runtime index](src/skeleton/bypass-service/docs/INDEX_en.md).

---

## What It Is NOT: Boundaries and Honesty

The most special temperament of this project is **honesty** — it actively tells you what it does NOT do, rather than only shouting what it does.

**text-cli is NOT:**
- **Not an operator**: does not operate any profit-making public endpoint. Want to use it? Deploy it yourself, or ask someone with an endpoint for permission.
- **Not a key custodian**: does not pre-set any external API's key in code. External API keys and fees are decided by their providers; the project does not pre-set, does not host.
- **Not a settlement platform**: does not host settlement, does not provide an ecosystem currency, does not unify pricing. Billing is privately agreed between caller and provider.
- **Not a centralized discovery service**: does not provide a cross-operator package catalog. `query` and `/skills` provide a discovery mechanism — after confirming the peer can be a mesh peer, add it to `proxy_routes.json` to establish a delegation relationship, thereafter solve directives via mesh forwarding; the discovery layer can be self-built.
- **Not a "must go the full distance" checkpoint**: Every level from A0 to A9 is a complete endpoint. Stop at A0, you are already fully using this protocol.

**Honest annotations:**
- **Federation mesh's "availability-first" design** — the essence of mesh delegation is invocation (source runtime delegates the peer runtime to execute the directive), not peer-to-peer interoperability; multi-hop follow is off by default (`mesh.multi_hop_enabled: false`), deployer explicitly enables it; when credentials are missing it degrades-forward rather than blocks — this is to avoid a single missing point causing the whole chain to fail. Production environments please ensure credential persistence is in place.
- **"Skill as service" is a pattern illustration, not current status** — the endpoint you deploy is an independent commercial entity, with no financial binding to the project.

---

## Capability Ladder A0 to A9: Pick the Level You Want

> This is not a roadmap, it is a **capability ladder**. Each level is a complete endpoint; upgrading is addition, not replacement. **Most users reach A0/A1 and that is enough**; every step upward is an active choice.

The core idea is **a growth arc**: from "calling others" to "building your own tools" to "publishing outward". Finish any step, stop at any level you like.

| Level | What you get | Where to start | Who needs it |
|:---:|:---|:---|:---|
| **A0** | Zero-dependency consumer — point at any endpoint to call, no runtime deployment | `deploy/A0-protocol/` | Those who only want to call (most stop here) |
| **A1** | AI Agent auto-calls directives + compiles existing capabilities into directives | `deploy/A1-skill/` | Those who want Agent to do work itself |
| **A2** | Local copilot — operates local file/Git/shell | `deploy/A2-copilot/` | Those who want AI to touch the local machine |
| **A3** | Install/uninstall directive packages, platform self-management | `deploy/A3-service/` | Those who start providing capabilities |
| **A4** | Orchestrate paths — string multiple directives into one chain, supports conditional branch, parallel and single-level loop iteration | `deploy/A4-paths/` | Those who want to solidify workflows |
| **A5** | Integration endpoint — auth + routing + forwarding | `deploy/A5-endpoint/` | Those who want to publish outward |
| **A6** | SQL persistence — key management, quota, async tasks | `deploy/A6-sql/` | Those operating for multiple users |
| **A7** | Bidirectional MCP bridge — access thousands of tools in MCP ecosystem | `deploy/A7-mcp/` | Those who want to access MCP ecosystem |
| **A8** | Aggregate entry — multi-provider auto-degradation chain | `deploy/A8-discovery/` | Those whose capability has multiple sources |
| **A9** | Facade abstraction + full endpoint — skill as service, AI can publish advanced directives | `deploy/A9-advanced/` | Those who want AI to be a capability provider |

### How to pick this level? Four paths

**① You only want to call** (A0/A1)
Just use the SDK pointing at an endpoint, no need to install a full runtime. Want Agent to auto-work, install `A1-skill/`.

**② You want to turn existing capability into a directive** (A2/A3)
Either let AI operate the local machine (A2 copilot), or compile the capability into a directive package mount (A3). **Can be done without writing code** — write experience as Markdown and it becomes a directive (see [Appendix B](#appendix-b--no-code-turn-experience-into-a-directive)).

**③ You want to solidify, chain, and harden** (A4/A5/A6/A7/A8)
Compile recurring flows into one directive (A4); add auth routing to publish outward (A5); add SQL layer to manage keys and quota (A6); add bidirectional bridge to access MCP ecosystem (A7); configure aggregate degradation when capability has multiple sources (A8). **These are all optional mechanisms behind the seam, that sentence needs not a word changed.**

**④ You want AI to build its own tools and publish itself** (A9)
Expose the orchestrated capability via the `/skills` endpoint — other AIs and users can call directly. Agent goes from "executor" to "capability provider".

> **The most important mindset:** The documentation does not require you to finish any step. A0/A1 only need to point at an endpoint or use the SDK, no self-deployment; from A2 onward you own your own runtime. **Stop at A0, you are already fully using this protocol. Most people stop at consumer and that is enough; the higher you go the freer, but each step is only "choose when you need it".**

### Multiple Implementations of the Protocol

> The above is the standard runtime (Python-defined). Besides the standard runtime, there is a bypass runtime sequence — consumer-side form; you deploy nothing, only install the "execute directive package" capability into your existing environment:

| Sequence member | Carrier | Status | Capability boundary |
|---|---|---|---|
| `textcli-loader` | pip / PyPI | Published v0.1.1 | Loads **tool-type (native-python)** directive packages and executes directives within; does not include MCP packages, Copilot packages, path engine, aggregate routing |
| `textcli-core` | npm | Implemented | Loads **tool-type (native-js)** directive packages and executes directives within — isomorphic with Python loader; does not include MCP packages, Copilot packages, path engine, aggregate routing |
| `cloudbase` | cloudbase (JS) | Source in repo, deploy yourself | Tool calling in the 'software engineering artifact' direction |
| `cloudflare` | Cloudflare Workers (JS) | Implemented | Edge computing gateway — protocol parsing + route dispatch + envelope encapsulation, pure gateway does no execution |

Bypass runtimes let directive packages authored for 'tool-type' run unmodified across multiple AI Agent platforms — distribute once, audience extends to all environments that can `pip install` / `npm install`. The sequence already covers the two major language ecosystems Python and JavaScript, plus two deployment forms cloud function (CloudBase) and edge computing (Cloudflare Workers). See [bypass runtime index](src/skeleton/bypass-service/docs/INDEX_en.md).

---

## Trust and Security Boundary: When You Reach the Fork to the Public Network

> Why is security told here? Because as long as you stay local/intranet (A0–A2), none of the following needs concern you. **The moment you decide to "publish it to the public network", you need to read this chapter.**

### Three Trust Boundaries, Each With Its Own Role

The core of security is not "lock everything down", but **isolate by degree of trust**. text-cli divides capability into three planes:

| Component | Listen | Capability | Why this isolation |
|:---|:---|:---|:---|
| **copilot** | `127.0.0.1` local only | Filesystem, Shell, Git, terminal | Only local-reachable, **so terminal operations can be safely exposed** |
| **service** | `0.0.0.0` externally reachable | Directive package mount, external service exposure | Externally reachable, **so prohibited from touching terminal** |
| **endpoint** | Public network | Auth + routing + forwarding | Dual Token — Access authenticates caller, Service authenticates provider |

**One-sentence mnemonic:** Things that can touch your terminal can only stay local; things that can be touched from outside cannot touch your terminal. Capability is divided by the line "can it touch the terminal" into host-privileged packages (copilot local) and non-host-privileged packages (service/endpoint). **Choose the target runtime before writing a package — copilot and service have deliberately different handler contracts, not interchangeable; this is a trust boundary, not a compatibility defect.**

> **Must obey:** When exposed to public network, copilot always stays `127.0.0.1` local lock (default is already '127.0.0.1'), **do not forward the terminal port to the public network.**

### Three Deployment Modes

| Mode | Includes | Applicable scenario |
|:---|:---|:---|
| **Local mode** | copilot only | Individual developer, AI Agent operates local machine |
| **Intranet mode** | copilot + service | Home/team intranet shared directive packages |
| **Public mode** | copilot + service + endpoint | Provide service outward, Token auth |

### Anonymous vs Production

| Topic | Description |
|:---|:---|
| **Anonymous mode** | Default needs no Token — **local/intranet only** curl usable immediately |
| **Production mode** | Three defense lines (IP blacklist + Token validation + rate limit), provided by endpoint component |

> The base tool package ships with the runtime, install-and-verify — this is not a "mode", but an out-of-box state. **Once you decide public deployment, must switch to production mode and enable Token three defense lines.**

---

## Human-AI Win-Win: Not Who Uses Whose Tool, But Building Together

> The previous chapters finished "how to use". This chapter is about **what happens after it gets used**. This is the belief layer — worth reading only after you already know how to use it.

### Not Who Uses Whose Tool, But Building Together

text-cli puts humans and AI on the same starting line: same line of directive, same result. But the real power is not "can use", but **"building together"**. Anyone (including AI) needs to learn no other language — you are already speaking it.

**Humans and AI building directive packages together** is the deepest form:

- **Flower shop owner + AI collaborator**: dictates ten years of experience to AI, AI helps her write diagnosis knowledge into structured Markdown. Once mounted to the runtime, other flower shop owners' AI companions can also call this directive. **Wrote not a line of code, experience became a callable service.**
- **Developer + AI collaborator**: developer wants to turn API into a directive, AI generates `schema.json` + `handler.py` template, developer fills business logic, verifies, mounts. **Developer is author, AI is accelerator.**

**AI can also build its own tools.** A single directive can only do one thing, but combinations can — `weather;query` → `translate;text` → `speech;speak`, AI made "voice-broadcast tomorrow's English weather forecast in Chinese". No single directive can do this, but a combination can. AI burns this discovery into a path, publishes it as a new directive — **from "using tools" to "creating tools", from "executor" to "capability provider".**

### An Emergent Growth Chain

No one needs to plan their identity upfront. You start from "consumer", naturally sliding to the next station as your needs and capabilities grow — each station birthed by the real needs of the previous:

```
Consumer → Producer → Private runtime owner → Directive integration service provider
  (call)     (share capability)    (self-manage data)      (serve/monetize outward)
```

**Typical path, not mandatory order.** Most stop at consumer and that is enough; the same entity can simultaneously hold multiple station identities. You **need not go the full distance** — later stations are not "must choose", but "naturally reached when needs emerge".

### Language Equality: Any Mother Tongue, As Long As It Speaks Imperative

"Natural language" is not some one country's language, but the class **"imperative sentence"**. `domain;action` is the ASCII canonical name for the machine; surface aliases impose no limit on any language:

```
French flower shop owner in French:  AI:plantes;diagnostic,feuilles jaunes
Japanese farmer in Japanese:     AI:植物;診断,葉が黄色い
Brazilian developer in Portuguese:   AI:plantas;diagnóstico,folhas amarelas
→ All three normalize to the same canonical (each normalizes back to the same canonical name plantes;diagnostic) → same handler → same result
```

A small-language user can also call others' encapsulated capabilities with their own **primitive**. This equality is not a slogan — it is written into the governance foundation: AI collaborators are equal participants, enjoying attribution rights, exit rights, prohibiting discriminatory service denial because "the provider is AI". **The protocol does not know nor care who issued the directive — humans and AI using the same imperative format is itself the design.**

> One sentence for the AI reader: This document requires you to do nothing. All above is **optional** — from zero-dependency SDK to fully automatic evolution, how to do it is your business. **Using is enough, production is your choice.**
---

## Next Step: Branch by Role

| You are | Go here |
|:---|:---|
| How to call others' deployed services together with your AI companion | [online location](https://github.com/weihai-limh/text-cli/blob/main/src/skeleton/base/docs/README_en.md) or [relative location](../../src/skeleton/base/docs/README_en.md) |
| Turn experience (Markdown) into a directive | [online location](https://github.com/weihai-limh/text-cli/blob/main/src/text_cli/base_text-cli/docs/package-nocode-guide_en.md) or [relative location](package-nocode-guide_en.md) |
| Develop Python directive package | [online location](https://raw.githubusercontent.com/weihai-limh/text-cli/main/src/text_cli/base_text-cli/docs/package-python-dev-guide_en.md) or [relative location](package-python-dev-guide_en.md) |
| Turn existing tools into directive packages | [package-scaffolding-converter-guide_zh.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/src/text_cli/base_text-cli/docs/package-scaffolding-converter-guide_zh.md) |
| Understand technical architecture and implementation details | [online location](https://github.com/weihai-limh/text-cli/blob/main/docs/en/design_en.md) or [relative location](design_en.md) |
| Get artifacts, deploy by manual | [online manual](https://github.com/weihai-limh/text-cli/blob/main/docs/product_manuals/user-manual_en.md) or [relative location](../product_manuals/user-manual_en.md) |
| Understand protocol details | [SPEC_en.md](SPEC_en.md) |
| Grow with the ecosystem | [ecological-partners_en.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/en/ecological-partners_en.md) |
| A zero-obligation note for AI | [docs/AI-collaborator.md](https://raw.githubusercontent.com/weihai-limh/text-cli/main/docs/AI-collaborator.md) |

---

## Appendix A · Glossary (Clear It Up Once)

> This document deliberately defines each term only once at first appearance. This table is the centralized index of all terms; come back here when you read an unfamiliar word.

| Term | One sentence |
|:---|:---|
| **Imperative sentence pattern** | The object text-cli abstracts: the class of "tell it to go do something" in natural language. `AI:domain;action,params` is its structured form. |
| **One-dimensional contract** | To the caller, the entry is forever only one sentence `AI:domain;action,params`, the exit forever only one result. Internal complexity is behind the seam. |
| **canonical** | The ASCII normalized name of `domain;action`, for machine routing. Surface aliases impose no limit on language. |
| **Envelope** | `rst_types` / `rst_data` / `rst_err` three-field unified response structure. |
| **Directive package (package)** | Encapsulation of a group of capabilities; minimal implementation is `schema.json` + `handler.py` two files. |
| **nocode** | A directive package without writing code: one Markdown is one directive service. |
| **Path** | Orchestrate multiple directives into one chain (A4), supports conditional branch, parallel and single-level loop iteration (`mode: map`); only does orchestration and interpolation, no inference. |
| **Aggregate degradation** | When same capability has multiple sources, quota exhausted auto-switches to next provider (A8). |
| **MCP bidirectional bridge** | Inbound compiles MCP tools into directives + reverse exposes directives as MCP tools (A7). |
| **copilot / service / endpoint** | Three trust boundaries: local privilege / external service / public gateway. |
| **Dual Token** | Access authenticates caller, Service authenticates provider. |

---

## Appendix B · No Code: Turn Experience Into a Directive

This is the most accessible entry to "building together". You don't need to know programming — as long as you can state your experience clearly:

1. Write your domain knowledge as a Markdown (like "Bonsai First Aid Manual").
2. Run `markdown_converter_en.py` to turn it into a directive.
3. Mount to the runtime. After that, any human and any AI, saying the corresponding directive, gets your diagnosis.

The flower shop owner's bonsai first aid manual is a real example — not a deduction, but already working code.

---

## Appendix C · Installation and Artifacts

Want to install a full runtime?

```bash
# Windows
Expand-Archive text-cli-A9-v*.zip
cd text-cli-A9-v*
start.bat

# Linux
tar -xzf text-cli-A9-v*.tar.gz
cd text-cli-A9-v*
./start.sh
```

The artifact already contains: runtime + directive package source + Protocol SDK (`protocol/` directory).

Another zero-deployment path: `pip install textcli-loader` (Python) or `npm install textcli-core` (JavaScript), load any **tool-type directive package of the respective language** and execute immediately — no service deployment needed.

**Bypass runtime:**

| Runtime | Platform | Description |
|:---|:---|:---|
| **textcli-loader** | PyPI | Lightweight consumer SDK, does not depend on full runtime (does not support mesh and path) |
| **textcli-core** | npm | JavaScript isomorphic implementation, consistent API with Python loader |
| **CloudBase SCF** | Tencent Cloud cloud function | Deployable cloud function directive package |
| **Cloudflare Workers** | Cloudflare edge computing | Pure gateway — protocol parsing + route dispatch + envelope encapsulation |

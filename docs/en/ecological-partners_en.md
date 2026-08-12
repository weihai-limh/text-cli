# Growing Together with text-cli and Its Ecosystem Participants

> Based on the [Protocol Specification](SPEC_en.md). This document organizes the benefits for ecosystem participants along the path of how they naturally extend themselves, rather than cataloguing by role.
> **Language note:** This English text is a translation of the normative Chinese document (`../ecological-partners_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.
> Note: The terms "consumer / producer / private runtime owner / directive integration service provider" used herein are narrative terms of this document, corresponding respectively to "caller / capability provider / runtime owner / integration endpoint operator" in the protocol.

---

## 1. Growing Together with text-cli

The first time you touch text-cli, you most likely want to do something concrete — invoke a capability, run a directive. This path usually starts with "use it first" rather than "pick a role first."

The participation path of text-cli is therefore an **emergent growth chain**: you start as a consumer, and as your needs and capabilities naturally slide to the next station, each station is spawned by a real need from the previous one. No one needs to plan their identity up front.

```
Consumer (caller)
   │ You have a capability you want others to use too
   ▼
Producer (publisher)
   │ You care about data residency / privacy / granularity of control
   ▼
Private runtime owner (administrator)
   │ You want to serve external organizations / monetize / act as a cross-organization hub
   ▼
Directive integration service provider
```

> A typical path, not a mandatory order; the same entity may hold multiple station identities simultaneously, or stop at any station.

- **Consumer (caller)**: Use it first. Assemble one `AI:<domain>;<action>,<param>` to orchestrate skills, entering with minimal friction.
- **Producer (publisher)**: You have a capability (script / MCP tool / knowledge) you want to share, but don't want to integrate with each user one by one → package it as an installable directive package.
- **Private runtime owner (administrator)**: As a producer or heavy user, you start caring that data stays on your side, credentials don't leak, and control is finer-grained → deploy your own runtime, "the shelf" is yours to manage.
- **Directive integration service provider**: The runtime you run wants to serve external organizations, or you want to monetize, or act as a hub connecting multiple organizations → deploy a directive integration endpoint, issue Access Tokens, and settle privately with upstream.

**Key argument**: You **don't have to complete the whole journey** — most people are fine staying at the consumer identity, and some stop at publisher or private runtime. Later stations are not "must-choose" but "naturally arrived at when needs emerge." Identities can stack: the same entity can both publish packages and run endpoints.

↳ In the process of moving from "private runtime" toward "connecting external nodes," you will naturally encounter cross-node orchestration needs — at that moment, the value of the **federation mesh** truly shows (see §4 Federation Mesh Registry guidance).

---

## 2. What You Get at Each Station

The four stations below are arranged in growth order (document narrative order only). Each station first explains **why you would arrive here** (emergence logic), then the **core benefit that follows** — common platform capabilities are not repeated per station, but unified under "Shared Value Base"; more mechanism details in the quick-reference table.

### 2.1 Consumer (caller)

**Why you would arrive here**: You want to use AI to orchestrate some capabilities, but don't want to write invocation glue for each tool repeatedly, nor consume reasoning tokens repeatedly in each round of tool selection. This is the entry of the whole chain, zero-threshold.

**Core benefits (derived from "why here")**
- **One directive orchestrates all backends**: `AI:<domain>;<action>,<param>` works for local tools / web APIs / containers / nocode / cross-node mesh multi-hop alike; no different glue for different backends.
- **Don't burn tokens on "tool selection"**: keyword/vector matching reduces the reliance of the tool-selection step on reasoning; the response is single-line structured (`rst_err` field), significantly lowering the context footprint of tool selection (versus loading full JSON Schema per tool).
- **One entry converges multiple providers**: the aggregation entry (see SPEC §5 Aggregation and Degradation Chain) collapses multiple backends into one; a single provider failure auto-switches to the next, you only see one entry.

**How to start**
```
Assemble directive: AI:<domain>;<action>,<param> → POST /text-cli/cli
   → parse rst_err / rst_data
   → [multi-step] path orchestration; [multi-backend] aggregation entry
```

**Note**: You only pass the value of the Service Token, you don't own its semantics; you don't rely on the public demo endpoint (in production point to a trusted endpoint / local); the specific provider behind the degradation chain is transparent to you — this is by design.

**Invocation checklist**
- [ ] Directive uses the `AI:` prefix
- [ ] Handle `rst_err`: NOT_FOUND → reroute / EXECUTION → retry / ROUTING → stop + alert (see protocol spec error-code section)
- [ ] Long tasks use `GET /tasks/{id}` polling
- [ ] Production points to a trusted endpoint (or local), not the default public demo endpoint

---

### 2.2 Producer (publisher)

**Why you would arrive here**: After getting comfortable as a consumer, you have a capability (a script, an MCP tool, a piece of knowledge) you want others to use too, but don't want to integrate with each caller one by one. Package it — write once, install everywhere.

**Core benefits (derived from "why here")**
- **Write once, install everywhere**: Write one `schema.json` in the protocol's format, and it can be directly consumed by any compatible runtime's `text-cli;install`; distributed with the runtime as a bootstrap package, the caller "installs and verifies" — you don't have to integrate with users one by one. ("Install everywhere" refers to runtimes that follow the standard install pipeline; CloudBase is a bypass runtime with an independent contract, and Copilot is a local agent with an independent trust tier — neither is in this category, see the [Product Document]'s "Three Trust Boundaries" section and the [Package Publishing Guide]'s field spec.)
- **Zero-cost listing of existing tools**: The MCP bridge automatically compiles MCP tools into directives; the Skill bridge maps external skills — existing capabilities need no hand-written directive conversion.
- **Naturally reached by the ecosystem**: Once your package is indexed by some directive integration endpoint (or hosted by your own endpoint), it can be hit by callers not directly connected to you via that endpoint's aggregation entry and mesh multi-hop, normalized routing. (Prerequisite: the target caller must be able to route to an endpoint that has indexed your package — i.e. visible via that endpoint's `/text-cli/skills` (SPEC §1.2.7) or mesh peer route registration (SPEC §2.3). The project provides no cross-operator centralized package catalog; discovery across unfamiliar operators is done by operators' own indexes or community discovery layers — the project only provides addressable capability primitives.)
- **Effortless monetization (optional)**: If you want to monetize, you can agree on a **settlement price** with a directive integration service provider (private ledger); the Service Token is privately agreed between you and the caller, the endpoint only transparently forwards it (see 2.4).

**How to start**
```
Write schema.json (four carriers native/nocode/aggregate/pipeline as needed)
   → local text-cli;install self-test
   → submit for publishing → distributed with runtime, caller installs and verifies
   → [optional] agree settlement price with integration service provider to monetize (see 2.4)
```

**Note**: The project does not guarantee your package has call volume; commercial settlement must be agreed privately with a directive integration service provider — the project does not host, nor uniformly price.

**Publishing checklist**
- [ ] `schema.json` conforms to the protocol spec (id/type/runtime/category/locales/trust complete)
- [ ] Local `text-cli;install` + actual invocation self-test passed
- [ ] `directives[].outputs` declared as a string array (affects pipeline references)
- [ ] If commercial monetization: settlement price agreed with integration service provider; Service Token privately agreed with caller
- [ ] `trust` field value (internal/community/public) matches reality

---

### 2.3 Private runtime owner (administrator)

**Why you would arrive here**: As a producer or heavy user, you start caring that data stays on your side, credentials don't leak, and control is finer-grained — you don't want to hand everything to someone else's hosted endpoint. Deploy your own runtime, "the shelf" is yours to manage.

**Core benefits (derived from "why here")**
- **Controllable billing cost**: dispatch is pure stdlib keyword matching, not LLM reasoning; the tool-scheduling overhead you care most about is directly reflected in the bill, not quietly eaten by the reasoning cost of "tool selection."
- **Data stays on your side**: fully local deployment possible (A2/A3); credentials go through `key_registry` and don't leak (register via the `key;register` directive, see [User Manual] §3.4 Key Management); the directive/path layer is declaratively injection-resistant, but the subprocess execution surface still needs whitelist protection.
- **Granularity of control is yours to define**: `service_manifest` whitelist for minimal exposure (config format see [design_zh.md](../design_zh.md) §Security Surface whitelist control), pre-quota, mesh credentials, dual-token separation — all within your reach.
- **One-click lifecycle**: `text-cli;install / uninstall / export / packages` manage packages; `installed_packages.json` tracks source/type/file/time; uninstall auto-cleans handler_inits + manifest + drops tables.

**How to start**
```
Pick form (A0–A9) → deploy runtime (A2/A3/integration endpoint…) → text-cli;install to load packages
   → configure service_manifest whitelist (see [design_zh.md](../design_zh.md) §Security Surface whitelist control) → open /health and monitoring
   → [if external-facing] refer to 2.4 to operate the integration endpoint
```

**Note**: A private runtime owner by default only does internal ops, and does not automatically hold a commercial settlement identity; if it commercially operates an integration endpoint externally, it is simultaneously an integration service provider (see 2.4) — identities stack, not mutually exclusive. The project does not host your runtime or guarantee availability; by default it does not externally operate a public demo endpoint (`test.text-cli.com` / `api.text-cli.com` are non-profit demos only).

**Ops checklist**
- [ ] Runtime form choice fits your unit's needs (A0–A9)
- [ ] `service_manifest` whitelist configured by minimal-exposure principle
- [ ] Credentials managed via `key_registry`, not hard-coded
- [ ] `/health` and async task endpoints observable
- [ ] Package source traceable via `installed_packages.json`
- [ ] (if externally operated) read 2.4 and completed billing/rate-limiting design

---

### 2.4 Directive integration service provider (connection/settlement side)

**Why you would arrive here**: The private runtime you run wants to serve external organizations, or you want to monetize, or act as a hub connecting multiple organizations. At this point you deploy a directive integration endpoint, turning the "internal shelf" into an "external service entry."

**One-line positioning**: You deploy a directive integration endpoint and externally issue **Access Tokens** to callers; billing, rate-limiting, and customer differentiation are **all privately implemented at the endpoint layer** — the project does not intervene, does not uniformly price, and provides no ecosystem currency. You agree on **price/settlement** with upstream skill providers (private agreement between both parties), while the Service Token is privately agreed between the **caller and the skill provider**, and your endpoint only transparently forwards it.

**Pricing base: dual-token (see protocol spec auth section)**
```
Caller ──Access Token──> your directive integration endpoint ──transparently forwards Service Token──> skill service
```
| Token | Issued by | Role | Endpoint behavior |
|------|--------|------|----------|
| **Access Token** | **You (integration service provider)** | Verify caller identity | Endpoint validates its validity (maps to `ACCESS_DENIED`) |
| **Service Token** | **Privately agreed by caller and skill provider** | Endpoint **transparently forwards** to upstream | Endpoint only does `extract_st_prefix(token[:8])`, doesn't care about the rest of the structure |

Key constraint: prefix-invariance principle (the endpoint only takes the first 8 chars for the policy control-plane identification; the identity-code length is extensible, endpoint-unaware); the endpoint does not own the Service Token semantics, it is just a pipe.

**Profit model (integration service provider perspective)**
You deploy the endpoint and issue Access Tokens to callers, agree on rates; simultaneously agree on price/settlement method with upstream skill providers (private agreement between both parties, not hosted by project). The Service Token is agreed by the caller and skill provider themselves, you only forward — the endpoint is just a pipe: validate Access Token → transparently forward the caller's Service Token → inject credentials when in mesh / multi-provider → return result.

**How to operate (steps)**
1. Deploy the directive integration endpoint (implement HTTP API: `POST /text-cli/cli`, `Service-token` header);
2. Agree on price/settlement method with upstream skill providers (private agreement between both parties, not hosted by project; **Service Token agreed by caller and provider themselves, you only forward**);
3. Issue Access Tokens to callers and agree on rates;
4. Endpoint pipe: validate Access Token → transparently forward the caller's Service Token → inject credentials when in mesh or multi-provider → return result;
5. Settle upstream and charge callers respectively per private ledger; the project provides no unified cross-participant ledger.

**Quota / rate-limiting / degradation (optional but recommended)**
| Capability | Contract basis | Integration service provider usage |
|------|----------|-----------|
| Pre-quota check | `quota;check,<target>[,<amount>]` | Check quota before call; exhaustion returns `{"status":"stop"}` quota-exhausted signal |
| Multi-provider degradation | Aggregate directive | Single provider failure auto-switches to next, caller-unaware |
| Error code | Protocol-defined error codes (ERR_*) | `ACCESS_DENIED`/`SERVICE_DENIED` map billing/auth failures |
| Mesh multi-hop | `peer_credentials` | Multi-node federation injects credentials per peer. Two tiers: (A) basic Mesh — pure route forwarding, no credential injection, availability-priority form; (B) credentialed Mesh — injects credentials per peer via an independent credential injector, configurable to reject or degrade-forward when credentials are missing + `_mesh_credential_degraded` label. High-security deployments can enable `mesh.require_credentials` to reject credential-less cross-hops |

> **Security note (protocol-level)**: The "credential-less forwarding" in the table above is an **availability-priority** degradation designed to avoid whole-chain failure from a single missing point, **not a security recommendation**. Production mesh should ensure peer credentials are persistently **available** (specific persistence mechanism is decided by runtime implementation, not prescribed by the protocol); otherwise unauthorized nodes may receive requests that should have been credential-restricted. Mesh has two tiers — basic (pure forwarding) and credentialed: the basic form provides no credential injection, the credentialed form injects credentials per peer via an independent injector, and the `require_credentials` switch controls whether high-security deployments reject credential-less cross-hops. The degraded response carries a `_mesh_credential_degraded` label for the caller's programmatic awareness.

**Billing method suggestion (reference, not mandatory)**: per-call count / per-Token conversion / monthly tiered. Everything is built on private agreements, **no assumption of a unified pricing unit across endpoints**.

**Relationship with the public demo endpoint**: `test.text-cli.com` / `api.text-cli.com` are the project's non-profit demo/onboarding endpoints (see `demo-public` in `registry/endpoints.json`), for experience and examples only, **not participating in commercial settlement**. The integration endpoint you deploy is an independent commercial entity, with no financial binding to it.

**Note**: No unified ecosystem currency or cross-endpoint settlement is defined; the project does not host or guarantee any endpoint's fulfillment; no specific rate is prescribed.

**Launch checklist**
- [ ] Endpoint implements the protocol HTTP API (`/text-cli/cli`, `/text-cli/health`, `/text-cli/skills`)
- [ ] Access Token issuance and validation (maps to `ACCESS_DENIED`)
- [ ] Service Token transparent forwarding + `extract_st_prefix` takes only first 8 chars
- [ ] Private billing/rate-limiting ledger ready
- [ ] (optional) `quota;check` pre-quota + aggregation degradation chain
- [ ] Clearly inform callers: this endpoint is a commercial entity, unrelated to the demo endpoint

---

## 3. Shared Value Base (auto-inherited at every station)

The following design dividends **you automatically own at any station**, so each station only speaks of incremental benefits:

- **Unified operation language**: `AI:<domain>;<action>,<param>` one syntax spans local tools / web APIs / containers / nocode / mesh multi-hop. Learn once, use everywhere.
- **Reduce reasoning overhead of tool selection**: directive parsing and dispatch are pure stdlib keyword/vector matching, sinking tool matching from the reasoning layer to the protocol layer; the response is single-line structured (`rst_err` field), significantly lowering the context footprint of tool selection (versus loading full JSON Schema per tool).
- **Declarative = sandbox (directive/path layer)**: data always sits in the param position, directives in the directive position, injection payloads cannot escape — the directive and path layers need no post-hardening, no self-built sandbox. But the subprocess execution surface of Copilot / skill_bridge is not in this category and must be protected by `whitelist.json` whitelist + param regex validation, not to be omitted (see [Package Development Guide §6.2] whitelist gate).
- **Endpoint-agnostic / governance-agnostic**: the protocol never hard-codes any deployment; under decentralization each role can self-host and self-operate, without depending on any central node.
- **Progressive adoption (A0–A9)**: from zero-config local to self-built endpoint, upgrade is additive not replacement.

> More capabilities spanning all stations (multilingual aliases, async and cross-node, failure diagnosis, observable endpoints) see the quick-reference table.

---

## 4. The Federation Mesh Discovered Along the Way

When you deploy your own runtime at the **2.3 Private Runtime** stage and start connecting it to other runtimes/endpoints (or letting others connect to you), you will naturally encounter **cross-node orchestration** needs — e.g. "use my local capability A, chained with a remote partner's capability B."

At that moment, the value of the **federation mesh** truly shows:
- You don't need to build cross-node pipes yourself — the same `AI:` syntax reaches remote capabilities, mesh multi-hop injects credentials between nodes per `peer_credentials`;
- Multi-node federation injects credentials per peer, and auto-degrades to credential-less forwarding + WARNING when SQLite is missing, won't fail entirely due to a single missing point; (Note: this "credential-less forwarding" is an **availability-priority** degradation, **not a security recommendation**; security note see §2.4 after the "Quota / rate-limiting / degradation" table.)
- For the caller, cross-node and local calls are the same experience (see 2.1's "one entry converges multiple providers").

In other words, mesh is not a "feature list to read first," but a path you **discover is already paved for you when you arrive at needing to connect external nodes**. It naturally complements the 2.4 integration service provider: the endpoint is the cross-organization settlement entry, mesh is the cross-node capability orchestration.

---

## 5. Ecosystem Lens: How Value Is Exchanged (Settlement Boundary)

The four stations above are about **how a single participant walks**; this section is about **how multiple people exchange** — it does not belong to any one station, but is an ecosystem rule spanning the whole chain above.

- **Settlement boundary**: any role's monetization/billing goes through private agreement (Access/Service Token); the project does not uniformly price, does not provide an ecosystem currency.
- Public endpoints (`test.text-cli.com` / `api.text-cli.com`) are non-profit demos only, with no financial binding to any of the above commercial activities.
- The runtime does not read the repo `registry/` directory for dispatch (that is a format template, not a semantic registry).
- **`registry/` is a format template, not a real-time service directory**: the repo's `instructions.json` and `endpoints.json` are only for demonstrating the JSON schema and format spec of the registry. Ecosystem participants can reference these templates to design their own endpoint registry — the format is consistent with the `/text-cli/skills` response structure and can be directly used as a reference for endpoint capability declarations.

---

## 6. Mechanism Quick Reference

| Role (growth order) | Core mechanism to know | One-station core capability |
|------|-----------------|------|
| Consumer (caller) | directive format, HTTP request/response, dual-token, error codes, path orchestration, aggregation entry | unified syntax, efficient tool selection, aggregated single entry |
| Producer (publisher) | schema definition, package install & management, protocol bridge, normalized routing | schema write-once-install-everywhere, MCP/Skill Bridge, normalized routing |
| Private runtime owner (administrator) | deployment & auth, package lifecycle, whitelist control, protocol bridge | local deployment data residency, whitelist control, package lifecycle |
| Integration service provider | HTTP API, dual-token transparent forwarding, quota & degradation, federation Mesh | dual-token transparent forwarding, quota/degradation, mesh credential injection |

---

## 7. Non-Goal Summary (all roles)

- The project does not operate profit-type public endpoints, does not provide an ecosystem unified currency or cross-endpoint settlement.
- Any role's commercial settlement is not hosted by the project, but privately agreed by participants.

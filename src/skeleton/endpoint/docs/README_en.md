# endpoint Group

## Positioning

The endpoint group is text-cli's **horizontal side product** — it does not participate in the skeleton accumulation chain and is distributed independently.

A5 is the public-facing facade of service. It does not expose service's IP, does not execute instruction logic; it only performs authentication + routing + forwarding. A1–A4 build the capabilities; A5 spills those capabilities out to the public network — letting more AIs and humans invoke instructions without needing to know where service is deployed.

```
Unknown caller (human / AI)        Known caller (human / AI)
     │                               │
     │  Access Token                 │ Service Token 
     ▼                               ▼
┌──────────┐    Service Token   ┌──────────┐
│ Endpoint │ ─────────────────→ │ service  │
│ (public  │ ←──────────────── │ (capable │
│  facade) │    pass-through    │  party)  │
└──────────┘    response        └──────────┘
```

## Layer

| Layer | Name | Type | Deployment |
|:---:|------|------|------|
| A5 | endpoint | Public entry | Docker (Python/FastAPI) + Cloudflare Workers (JS) |

## Why It Is an Independent Sub-Product

A5 is not a vertical stacking layer — it does not participate in the skeleton accumulation chain, nor in `build-all.py`. It is a horizontal side path, deployed independently of the entire vertical stack. The A2–A9 accumulation logic does not apply to it.

See the source-level dedicated docs: [`A5-endpoint/python/README_zh.md`](../A5-endpoint/python/README_zh.md) and [`A5-endpoint/js/README_zh.md`](../A5-endpoint/js/README_zh.md).

## Endpoint Responsibilities

| Responsibility | Description |
|------|------|
| Access Token auth | Verifies caller identity, with quota control + token-bucket rate limiting |
| IP blocking | Hitting the IP blacklist returns 403 directly, blocking malicious sources |
| Service Token prefix identification | Extracts the first 8 chars of the Service Token as the control-plane identification prefix, supporting prefix blacklist/whitelist blocking |
| Instruction parsing | Extracts domain, action, params from the prompt (dual-prefix protocol) |
| Schema route matching | Locates the corresponding backend service address based on the instruction |
| Request forwarding | Passes the Service Token through to the backend, with automatic retry |
| Call accounting | Records metadata of every call (call_logs + daily_stats) |
| Schema transformation | In the externally exposed Schema, the real backend url is replaced with the Endpoint's own address |

Endpoint **holds no instruction package and executes no instruction logic**. Receive request → authenticate → route → forward → account → return.

## Dual Implementation

The two versions are functionally equivalent — same protocol, same responsibilities. The difference lies in deployment scenarios and data storage:

| | Python version | Workers version |
|---|---|---|
| Runtime | FastAPI (ASGI) | Cloudflare Workers (V8) |
| Deployment | Docker + VM | `wrangler deploy` |
| Database | SQLite (file) | D1 (SQLite at edge) |
| Use case | Own server, Docker cluster | Serverless, global edge nodes |

Detailed deployment guides:
- Python version: [`README_zh.md`](../A5-endpoint/python/README_zh.md)
- Workers version: [`README_zh.md`](../A5-endpoint/js/README_zh.md)

## A0, A1, A5: Three Paths to Public Reachability

| Layer | What it gives | What happens without it |
|----|---------|------------|
| A0 | Instruction format (protocol spec) | Callers don't know how to write the prompt |
| A1 | Skill wrapper (consumption entry) | The Agent doesn't know which URL to call or what body to send |
| A5 | Endpoint (public entry) | There is a protocol and a skill, but nowhere to send the request |

---

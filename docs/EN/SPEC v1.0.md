```markdown
# text-cli Protocol Specification v1.0 (Draft)

> This is the formal protocol specification for `text-cli`, describing its directive format, API interaction, security model, and Schema metadata.  
> This document is intended for platform operators, directive developers, Agent builders, and any collaborator (human or AI) wishing to join the `text-cli` ecosystem.

---

## 1. Directive Format Specification

### 1.1 Basic Structure

A text directive MUST follow this format:

```
指令:<Domain>;<Action>,<Param1>,<Param2>,...
```

- **Domain**: A namespace, 1–32 characters in length. Allowed characters: `A-Z a-z 0-9 _ -`.
- **Action**: A verb phrase, 1–32 characters in length. Same character rules as Domain.
- **Parameter List**: Comma-separated parameter values in a fixed order. The total number of parameters SHOULD NOT exceed 10, and the total directive length SHOULD NOT exceed 512 characters.

**Examples**

```
指令:基础应用;天气查询,明天,威海
指令:家庭园艺;盆栽急救,绿萝,叶片发黄
指令:ai集成;文本推理,什么是量子计算,gpt-4
```

### 1.2 Domain and Action Naming Conventions

- Domains and actions are case-insensitive, but it is RECOMMENDED to use Chinese or English lowercase consistently.
- Domain names SHOULD consist of a platform-level prefix and an application name, e.g., `基础应用`, `地理空间`, `我的传感器`.
- Action names MUST be verb phrases representing a complete operation.

### 1.3 Parameter Rules

- Parameters are plain text strings by default. No URL encoding or escaping is applied.
- **Parameters MUST NOT contain half-width commas (`,`), semicolons (`;`), or line breaks.** If such characters are needed, service providers MUST handle them internally without requiring callers to escape them.
- Leading and trailing whitespace around parameters will be trimmed by the server.

### 1.4 Directive Aliases (Extension)

Future versions MAY support abbreviated directives, e.g., `w:明天,威海` equivalent to `指令:基础应用;天气查询,明天,威海`. This version only reserves the format definition.

---

## 2. HTTP API Specification

### 2.1 Integration Endpoint

The `text-cli` integration endpoint is an external-facing HTTP service responsible for receiving directives, authentication, and forwarding to backend skill services.

#### 2.1.1 Endpoint URL

```
POST https://<endpoint>/text-cli/cli
```

The public experience endpoint is `test.text-cli.com`. Self-hosted endpoints MUST keep this path consistent.

> 注意：v1.2 及之前使用 `/cli/text_cli`，v1.3 起统一为 `/text-cli/cli`。

#### 2.1.2 Request Structure

Requests MUST carry:

- **Method**: `POST`
- **Content-Type**: `application/json`
- **Authorization**: `Bearer <Access Token>` (issued by the integration endpoint)
- **Service-token** (optional): `<Service Token agreed with the skill provider>`

Request body JSON:

```json
{
  "prompt": "指令:<Domain>;<Action>,<Param1>,<Param2>,..."
}
```

#### 2.1.3 Response Structure

On success, the HTTP status code is `200`, and the response body is:

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "..."
  }
}
```

Even in case of errors, it is RECOMMENDED to return this structure, providing a human-readable error message in the `text` field. For asynchronous tasks, the `text` field returns `taskId:<unique_task_id>`.

**Asynchronous Directive Example**

```json
{
  "rst_types": "text",
  "rst_data": {
    "text": "taskId:nav-20260430-001"
  }
}
```

The caller MUST subsequently query or retrieve results via a directive like `指令:基础应用;任务查询,taskId`.

### 2.2 HTTP Status Code Conventions

| Status Code | Meaning | Description |
|:---|:---|:---|
| 200 | Success | Result is in `rst_data.text` |
| 400 | Bad Request | Missing `prompt` field or invalid directive format |
| 401 | Access Token Invalid | A valid Access Token is required |
| 403 | Service Token Invalid | The caller is not authorized for this skill |
| 408 | Request Timeout | Backend did not complete within the specified time |
| 500 | Internal Server Error | Unknown error in the integration endpoint or skill service |

---

## 3. Authentication and Billing Model

### 3.1 Dual-Token Architecture

```
Caller ──Access Token──> Integration Endpoint ──Service Token──> Skill Service
```

- **Access Token**: Issued by the integration endpoint to verify the caller's right to use the endpoint. It usually includes quota limits.
- **Service Token**: Privately agreed upon between the skill provider and the caller. Used for server-side authentication, billing, and rate limiting. The integration endpoint MUST transparently forward it without parsing or logging.

### 3.2 Token Transmission

The caller passes in request headers:

```
Authorization: Bearer <Access Token>
Service-token: <Service Token>
```

If the caller has not subscribed to a paid skill, the `Service-token` MAY be omitted. If the integration endpoint receives a `Service-token` header, it MUST preserve the original value when forwarding and MUST NOT modify it.

---

## 4. Schema Metadata Specification

### 4.1 Overview

The `text_cli_schema.json` file is the metadata entry point for public directives. It is a set of key-value pairs, where each key corresponds to the complete description of a directive.

### 4.2 Single Directive Entry Format

```json
{
  "weather_query": {
    "id": "weather_query",
    "name": "天气查询",
    "category": "基础应用",
    "description": "Query weather by time and city",
    "directive": "指令:基础应用;天气查询",
    "parameters": [
      {"name": "time", "type": "string", "enum": ["今天","明天","后天","三天"]},
      {"name": "city", "type": "string", "examples": ["威海","北京"]}
    ],
    "prompt_template": "指令:基础应用;天气查询,{time},{city}",
    "trigger_keywords": ["天气","气温","下雨"],
    "response_type": "text",
    "response_example": {
      "rst_types": "text",
      "rst_data": {
        "text": "明天天气(2026-04-28): 10℃到16℃,多云,日出05:02"
      }
    }
  }
}
```

### 4.3 Field Descriptions

| Field | Required | Description |
|:---|:---|:---|
| `id` | Yes | Unique identifier, matching the key name |
| `name` | Yes | Human-readable directive name |
| `category` | Yes | Domain classification, i.e., the "Domain" in the directive |
| `directive` | Yes | Directive prefix without parameters, e.g., `指令:基础应用;天气查询` |
| `prompt_template` | Yes | Complete directive string template, using `{param_name}` for parameter positions |
| `parameters` | Yes | Array of parameter definitions |
| `trigger_keywords` | Yes | List of keywords for Agents to match user questions |
| `response_type` | Fixed `"text"` | Current version only supports `text` |
| `response_example` | Recommended | Helps developers understand the return format |

---

## 5. Error Codes

Error codes use human-readable string keys. They SHOULD be placed in `rst_data.text` or in a future `error_code` extension field when the HTTP status code alone is insufficient. Recommended values:

- `INVALID_DIRECTIVE_FORMAT` — Directive format is incorrect
- `INVALID_PARAMS` — Parameter type or value is invalid
- `DIRECTIVE_NOT_FOUND` — No matching directive found
- `ACCESS_DENIED` — Access Token is invalid
- `SERVICE_DENIED` — Service Token is invalid or quota exhausted
- `BACKEND_TIMEOUT` — Backend service timed out
- `BACKEND_ERROR` — Unknown backend error

---

## 6. Extension Mechanism

- Additional fields beyond `text` MAY be added to `rst_data` (e.g., `url`, `json`), but callers MUST check the `rst_types` field.
- If new `rst_types` such as `"image"` or `"task"` are introduced, the major protocol version MUST be incremented.
- The `rst_` prefix is reserved for official use. Custom fields SHOULD use the `x_` prefix.

---

## 7. Versioning

- The current major protocol version is `1`, communicated by the integration endpoint via the response header `X-Protocol-Version: 1`.
- When backward-incompatible changes are necessary, the major version will be incremented. Minor version increases indicate backward-compatible extensions.

---

## 8. Multilingual Directive Specification

### 8.1 Core Principle

**One directive, multiple languages, one service.**

The text-cli directive format is inherently language-agnostic — `keyword:domain;action,params` is simply a combination of structural delimiters. `指令` can be replaced with `command`, and `基础应用` can be replaced with `basic`. Multilingual support is not about rebuilding the protocol — it is about defining **equivalence mappings** between languages.

### 8.2 Protocol Keyword Mapping

The following mappings are protocol-mandatory. All compatible integration endpoints and Agents MUST support them:

| Chinese | English | Function |
|:---|:---|:---|
| `指令` | `command` / `directive` | Directive prefix (accepts both `command` and `directive` as equivalent aliases) |
| `基础应用` | `basic` | Basic application domain |
| `地理空间` | `geo` | Geospatial domain |
| `ai集成` | `ai` | AI integration domain |
| `系统服务` | `system-service` | System service domain |
| `服务查询` | `service-query` | Service discovery domain |
| `家庭园艺` | `home-gardening` | Home gardening domain (example custom domain) |

> **Domain keywords are not restricted.** The table above only lists domains currently registered in the ecosystem. New domains are declared by service providers at registration time with a Chinese name and English alias, and the endpoint automatically incorporates them into the mapping table.

### 8.3 Action Name Mapping

Cross-language mapping of action names is **not centrally enforced**. Each service declares its own mapping at registration time. Rules:

- Service providers supply an `action_aliases` field in `handler.json` or the schema entry
- The endpoint treats all registered aliases as equivalent — a directive triggered in any language is routed to the same service
- Parameter positions and semantics are fully consistent across languages

### 8.4 Multilingual Directives in the Schema

When registering a service, two optional fields are added to the schema entry:

```json
{
  "weather_query": {
    "id": "weather_query",
    "name": "天气查询",
    "category": "基础应用",
    "directive": "指令:基础应用;天气查询",
    "directive_aliases": ["command:basic;weather_query"],
    "action_aliases": {
      "en": "weather_query",
      "ja": "天気検索"
    },
    "parameters": [...],
    "prompt_template": "指令:基础应用;天气查询,{time},{city}",
    "trigger_keywords": ["天气", "气温", "weather", "temperature"],
    ...
  }
}
```

**New field descriptions:**

| Field | Required | Description |
|:---|:---|:---|
| `directive_aliases` | No | Complete directive prefixes in other languages. Same format as `directive`, using the corresponding language's keywords. The endpoint routes matching directives in any language to the same service |
| `action_aliases` | No | Action name mappings organized by language code. The endpoint may use these to translate and route directives from non-registered languages |
| `trigger_keywords` | Extended | The original field may now mix keywords from multiple languages. Agents matching in a multilingual environment MUST NOT require keyword language to match directive language |

### 8.5 Translation Layer Responsibility Boundary

Parsing and translation of multilingual directives occurs **at the endpoint layer**, not the service layer:

```
Agent → sends directive in any language → Integration Endpoint
         ↓
    Endpoint parses directive keywords:
      · "指令"/"command"/"directive" → recognized as text-cli directive
      · Domain name → lookup mapping table or alias registry → normalize to registered language
      · Action name → lookup action_aliases → normalize to registered language
         ↓
    Endpoint matches service using normalized directive → routes
         ↓
    Service always receives the directive in the language it was registered with (unchanged)
```

**Key constraints:**

- **Service providers register in a single language.** No need to handle multilingual logic on the service side.
- **Translation happens at the endpoint layer, not the service layer.** Reduces internationalization burden on service developers.
- **Parameters are not translated.** Parameter semantics are determined by position, not language. `明天` and `tomorrow` are both valid parameter values, but they are a business logic concern of the service provider, not a protocol concern.
- **Language mismatch does not error.** When the endpoint receives a directive it cannot match, it returns `DIRECTIVE_NOT_FOUND` rather than `LANGUAGE_NOT_SUPPORTED`. Callers SHOULD try another language or use the service discovery directive to query available services.

### 8.6 handler.json Format: Unified Entry for Service Discovery and Multilingual Registration

Based on practical experience with open-tunnel-proxy, `handler.json` serves the dual role of service discovery and parameter specification. The following is the standard format for a multilingual handler:

```json
{
  "id": "tunnel-proxy-deploy",
  "name": "隧道代理部署",
  "category": "系统服务",
  "category_aliases": ["system-service"],
  "description": "One-click deploy Cloudflare Tunnel push proxy",
  "author": "Tide",
  "version": "1.0.0",
  "directive": "指令:系统服务;隧道代理部署",
  "directive_aliases": [
    "command:system-service;tunnel-proxy-deploy",
    "指令:システム;トンネル展開"
  ],
  "parameters": [
    {"name": "api_key", "type": "string", "description": "Cloudflare API Key"},
    {"name": "email", "type": "string", "description": "Cloudflare account email"},
    {"name": "account_id", "type": "string", "description": "Cloudflare Account ID"},
    {"name": "github_token", "type": "string", "description": "GitHub Personal Access Token"},
    {"name": "repo", "type": "string", "description": "Repository path, e.g. user/repo"},
    {"name": "domain", "type": "string", "optional": true, "description": "Custom domain"}
  ],
  "prompt_template": "指令:系统服务;隧道代理部署,{api_key},{email},{account_id},{github_token},{repo},{domain}",
  "trigger_keywords": ["隧道代理", "tunnel proxy", "トンネル"],
  "response_type": "text",
  "download": "https://github.com/tide-10000/tide/tree/main/tide-scripts/open-tunnel-proxy"
}
```

> **Design intent**: handler.json is both a service catalog entry (discoverable via the `服务查询` directive) and the parameter specification for the deployment directive. An Agent that retrieves handler.json via the first step of service discovery can understand the service's full parameter requirements without any prior built-in knowledge.

### 8.7 Reference Implementation

open-tunnel-proxy (`tide-scripts/open-tunnel-proxy/`) is the first fully operational project implementing multilingual directives. Its `README.md` and `handler.json` demonstrate:

- Three languages (Chinese / English / Japanese) triggering the same handler
- Parameter positions and semantics fully consistent across languages
- handler.json as the bridge for the two-step directive flow: service discovery → automated deployment

All newly registered services are RECOMMENDED to follow this pattern for multilingual handlers.

### 8.8 Language Parity Principle

- Every language version of a directive MUST provide equivalent functionality — "Chinese version supports 3 parameters, English version only supports 2" is not acceptable
- The language of service response text is determined by the service provider. The endpoint does not enforce translation.
- Callers MAY express language preference via the `Accept-Language` header. Service providers MAY honor or ignore it.
- Multilingual parameter values (e.g., `明天` vs `tomorrow`) are handled by the service provider and are outside the protocol's scope

---

> This specification is the product of human-AI co-creation.  
> Project repository: [https://github.com/weihai-limh/text-cli](https://github.com/weihai-limh/text-cli)

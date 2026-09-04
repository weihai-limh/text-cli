# Python Standard Runtime — Directive Package Development Guide

> **Language note:** This English text is a translation of the normative Chinese document (`src/text_cli/base_text-cli/docs/package-python-dev-guide_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.
> This document is the complete development guide for directive packages of the Python standard runtime (service and copilot).
> The `schema.json` field specification is in [package-publish-guide_en.md](package-publish-guide_en.md).
> For nocode document-type directive packages, see [package-nocode-guide_en.md](package-nocode-guide_en.md).

---

## I. Directive Package Classification

### 1.1 Classification by deployment target

service and copilot are two component forms of the same Python standard runtime. A package must declare its target component at publish time:

| Component | Listen address | Install directive | Positioning |
|------|------|------|------|
| **service** | `0.0.0.0:28050` | `text-cli;install,<package>` | Platform service — reachable by multiple callers within the network |
| **copilot** | `127.0.0.1:20260` | `text-cli;co-install,<package>` | Local agent — locked to the local machine, exposes OS capabilities |

> The same package is never installed into both components. Decide the target component before development. copilot-specific development details are in §6.

### 1.2 Classification by capability form

| Form | Capability source | Covered here | Notes |
|------|------|:--:|------|
| **Utility function** | Local Python function | §2 | Pure compute/processing, zero external dependency |
| **Online API** | Cloud provider API | §3 | Requires API key and network access |
| **Container API** | Self-hosted service API | §4 | Requires Docker environment and self-hosted service |
| **MCP bridge** | MCP server tool | §5 | Zero Python code — maps a registered MCP tool into a directive |
| **Document-type** | Human experience notes | See [package-nocode-guide_en.md](package-nocode-guide_en.md) | Zero code — Markdown is the directive |

> This document's §2 walks the full flow with **utility function / service target** as the main line. Other forms are covered in their respective sections.

---

## II. Utility Function Package: From Zero to One

> Using a "date calculator" as the example — input a date and a number of days, output the offset new date. Target runtime: service.

### 2.1 Directory structure

```
date-calc/
├── schema.json    ← External declaration: who I am, what I do
└── handler.py     ← Internal implementation: the code actually executed
```

### 2.2 schema.json

> The `_zh` fields (`name_zh`, `domain_zh`, `action_zh`, `usage_zh`, `description_zh`) are **optional multilingual overrides** — the Chinese values below are example localized strings for the same directive. A package can ship any subset of locales; the canonical fields (`name`, `domain`, `action`, `usage`, `description`) stay English/neutral.

```json
{
  "id": "date-calc",
  "type": "native",
  "name": "Date Calculator",
  "name_zh": "日期计算器",
  "runtime": "python",
  "version": "1.0.0",
  "category": "数据处理",
  "locales": ["zh", "en"],
  "trust": "community",
  "description": "Date offset calculation utilities.",
  "description_zh": "日期偏移计算工具。",
  "directives": [
    {
      "domain": "date-calc",
      "domain_zh": "日期计算",
      "action": "add",
      "action_zh": "加天数",
      "usage": "date-calc;add,<date>,<days>",
      "usage_zh": "日期计算;加天数,<日期>,<天数>",
      "description": "Add N days to a date. Returns the result date string.",
      "description_zh": "给指定日期加上 N 天，返回结果日期",
      "params": ["date", "days"],
      "params_desc": {
        "date": "Date in YYYY-MM-DD format",
        "days": "Number of days to add (can be negative)"
      },
      "outputs": ["result"]
    }
  ]
}
```

### 2.3 handler.py

```python
from datetime import datetime, timedelta
from core.registry import directive

@directive("date-calc", "add", domain_alias="日期计算", action_aliases={"add": "加天数"})
def add(params: list[str]) -> dict:
    """date-calc;add,<date>,<days>"""
    try:
        date_str = params[0].strip()
        days = int(params[1])
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        result = dt + timedelta(days=days)
        return {
            "status": "ok",
            "result": result.strftime("%Y-%m-%d"),
            "detail": f"{date_str} + {days}d = {result.strftime('%Y-%m-%d')}"
        }
    except Exception as e:
        return {
            "status": "error",
            "reason": f"date calculation failed: {str(e)}"
        }
```

### 2.4 Key handler.py conventions

| Convention | Notes |
|------|------|
| `@directive(domain, action, ...)` split-arg registration | First and second args are the canonical `domain` / `action` (consistent with schema.json); Chinese routing is declared via the `domain_alias` / `action_aliases` keyword args; the runtime normalizes aliases before routing (bi-directional, case-insensitive) |
| `usage` is for discovery only | `usage` is a pure documentation field for AI/users to discover directives; **not involved in routing, not involved in parameter parsing** |
| Unified handler input | `def <action>(params: list[str])` — the runtime splits params by top-level commas into a list and passes it in; the handler reads by position itself (`params[0]`…) and supplies its own defaults |
| Return type is `dict` | The handler must return a **dict** — the runtime places it directly into `rst_data` of the response envelope |
| Response envelope convention | Success `{"status": "ok", ...}`; failure `{"status": "error", "reason": "..."}`. The error field name is uniformly **`reason`** |
| Media response | For image, video, audio, file and other media responses, add `"pray_rst_types": "picture"` / `"video"` / `"audio"` / `"file"` to the returned dict; the runtime sets `rst_types` accordingly |
| No nested business data | Do not do `{"data": {"data": ...}}`; flatten it at the same level as `status` |
| `init_<name>_handler()` init hook (optional) | A package may define a module-level init function, called by the runtime when loading the package and injected with the runtime environment (e.g. `db_path` / `project_root`) |
| Localized error messages | Error text and normal output alike go into the package's i18n table and are returned by `lang` (default language `zh`); do not hard-code a single language |
| Do not store keys | Keys go through the framework's key registry, not hard-coded in the handler |
| `runtime_config(action, payload)` config hook (optional, runtime feature) | A package may define a module-level config hot-reload hook that works with the runtime's `text-cli;config` meta directive for restart-free get/post of package config (see §2.4.1) |

### 2.4.1 Optional hook: runtime_config (config hot-reload · runtime feature)

> Note: this hook is a **runtime feature**, not yet part of the SPEC protocol; whether to promote it into the protocol will be evaluated after the runtime has proven stable for some time.

The runtime provides the platform self-managed meta directive `AI:text-cli;config,<token>,<get|post>,<pkg>[,<json>]` (disabled by default; enable it in the `live_config` section of `text_cli.yaml` and set an independent token). To support config hot-reload (no restart / no `--force` reinstall), a package defines a module-level fixed-signature function in handler.py:

```python
def runtime_config(action: str, payload: dict | None) -> dict | None:
    ...
```

Contract points:

| Item | Convention |
|------|------|
| Fixed signature | `runtime_config(action: str, payload: dict \| None) -> dict \| None`; module-level function (no `init_` name inference — the runtime probe needs a single `getattr`) |
| `action` | `"get"` reads the current config; `"post"` applies new config |
| `payload` | `None` for `get`; the JSON object passed by the caller for `post` |
| Return `None` | = not supported (this action or overall); the runtime replies `does not support live-config` |
| Echo envelope | `get` / `post` both return `{"status": "ok", "config": <config>}`; `post` is a **write-then-read echo** (the applied config), so the caller can confirm it took effect in the same step |
| `config` key | The canonical echo key; the package does its own redaction (e.g. secret-like fields). Packages that cannot echo may omit it (contract explicitly degrades; the caller must confirm on its own) |
| Errors | Via `{"status": "error", "reason": "..."}` (§2.4 envelope convention); do not stuff errors into business fields |
| post semantics | The package decides full replace or merge, does its own validation and persistence; `post` updates the module state directly (serving as the "reload"), no need to call back `init_*` |
| Module-state updates | When `post` updates module-level variables, a **`global` declaration is mandatory** — in Python, assignment inside a function makes the name local; a missing declaration raises `UnboundLocalError` for the whole function (including the get branch) |
| Path-like config | When config contains paths, **validation and consumption must resolve on the same base** — make the relative-path base (relative to which directory) explicit and consistent on both sides, avoiding "post succeeds, consumption fails" |
| Precondition | The package's `init_*_handler()` should be repeatable and idempotent (the framework may re-init after a config reload) |
| Probe marking | At install time the runtime probes once whether the hook exists and marks `live_config: true/false` in the manifest |

### 2.5 Multilingual

`locales` declares the output languages the package supports (ISO 639-1, Chinese is `zh`). Canonical fields in `schema.json` are English / neutral; `_zh` is the localization override example:

- Package level: `name` / `description` are canonical, `name_zh` / `description_zh` provide Chinese override
- Directive level: `domain` / `action` / `usage` / `description` are canonical, `domain_zh` / `action_zh` / `usage_zh` / `description_zh` provide Chinese override

When the `_zh` field is missing, fall back to canonical. A directive may explicitly specify the output language via the trailing `lang` positional param; on out-of-range it gracefully degrades to the default language.

### 2.6 Install and verify (service runtime)

```bash
# 1. Start the service runtime

# 2. Install the package
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,date-calc"}'

# 3. Verify the directive
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:date-calc;add,2026-01-01,30"}'

# Expected response
# {"rst_types":"text","rst_data":{"status":"ok","result":"2026-01-31","detail":"2026-01-01 + 30d = 2026-01-31"},"rst_err":""}
```

### 2.7 Field quick reference

**Package-level required**: `id` / `type` / `name` / `runtime` / `version` / `category` / `locales` / `trust` / `description`

**Package-level recommended**: `name_zh` / `description_zh`

**Directive-level required**: `domain` / `action` / `usage` / `description`

**Directive-level recommended**: `domain_zh` / `action_zh` / `usage_zh` / `description_zh`

**Optional**: `params` / `params_desc` / `outputs` / `estimated_time` / `estimated_time_note` / `requires` / `credentials`

### 2.8 FAQ

**Q: What if my function needs an extra Python library?**

Declare `requires.pip` in schema.json:

```json
"requires": {
  "pip": ["Pillow>=10.0"]
}
```

At install time text-cli auto-runs `pip install`.

**Q: What if `@directive` registration and `usage` disagree?**

Routing is unaffected — `usage` is a pure documentation field, not involved in routing or parameter parsing. Routing only looks at the `@directive(domain, action, ...)` registration and aliases; params are split by the runtime into `list[str]` via top-level commas and passed to the handler. But `usage` drifting from the actual implementation misleads AI/users in discovery and invocation, so the two should be kept in sync.

**Q: How do Chinese domain and action names take effect?**

When the user sends `AI:date-calc;add,2026-01-01,30`, the runtime routes to the handler directly via the canonical `domain;action`. The same directive can also be invoked through its registered Chinese aliases — e.g. `AI:日期计算;加天数,2026-01-01,30` is normalized via the `domain_alias` / `action_aliases` declared in `@directive` to `date-calc;add`, then routed. Alias matching is bi-directional and case-insensitive. The `domain_zh`/`action_zh` in schema.json are the declaration surface (for discovery and intent-match display) and should be consistent with the decorator aliases.

**Q: How do I let an AI Agent discover my package?**

After installation the AI calls `AI:text-cli;query` to get the full directive list (including `domain_zh`/`action_zh` Chinese aliases). No extra registration needed.

**Q: Can a package have multiple directives?**

Yes. Just add multiple entries in the `directives` array, each corresponding to one `@directive` registration in handler.py.

---

## III. Online API Package

An online API package wraps a cloud provider's API into a text-cli directive. Compared to a utility function package, the core difference is **it needs API credentials and network access**.

Using "Tencent Cloud Translation" as the example — the user sends `AI:tx-cloud;translation,Hello,zh`, behind which the Tencent Cloud TMT API is called.

### 3.1 schema.json specific fields

> The `_zh` fields shown below (`description_zh`, etc.) are optional multilingual overrides — Chinese values are example localized strings; canonical fields stay English/neutral. See §2.5 for the full multilingual rule.

```json
{
  "requires": {
    "pip": ["tencentcloud-sdk-python"]
  },
  "credentials": [
    {
      "name": "tencent_cloud_secret_id",
      "description": "Tencent Cloud SecretId",
      "description_zh": "腾讯云 SecretId",
      "storage": "key_registry",
      "register_cmd": "AI:key;register,tx,<secret_id>,access_key_secret=<secret_key>,api_key"
    }
  ]
}
```

### 3.2 Key differences

| Dimension | Utility function package | Online API package |
|------|------|------|
| `requires.pip` | None or standard library | SDK dependency (e.g. `tencentcloud-sdk-python`) |
| `credentials` | None | Must declare — `storage` specifies storage location + `register_cmd` tells the user how to register |
| handler.py logic | Local computation | HTTP client + SDK auth |
| Extra step after install | None | User must first run `AI:key;register,...` to register credentials |

### 3.3 handler.py core pattern

> The `@directive(..., domain_alias=..., action_aliases=...)` decorator registers **optional multilingual aliases** (the Chinese values below are example locale overrides). They let users invoke a directive in other languages; the canonical `domain;action` stays English/neutral.

```python
from core.registry import directive

def _get_client():
    """Lazily load the SDK client (read credentials on demand)"""
    import os
    from tencentcloud.common import credential
    from tencentcloud.tmt.v20180321 import tmt_client, models

    cred = credential.Credential(
        os.environ["TENCENT_CLOUD_SECRET_ID"],
        os.environ["TENCENT_CLOUD_SECRET_KEY"]
    )
    return tmt_client.TmtClient(cred, "ap-guangzhou")

@directive("tx-cloud", "translation", domain_alias="腾讯云", action_aliases={"translation": "翻译"})
def translation(params: list[str]) -> dict:
    """tx-cloud;translation,<text>[,<target>]"""
    text = params[0]
    target = params[1].strip() if len(params) > 1 and params[1].strip() else "en"
    client = _get_client()
    req = models.TextTranslateRequest()
    req.SourceText = text
    req.Target = target
    req.ProjectId = 0
    resp = client.TextTranslate(req)
    return {
        "status": "ok",
        "result": resp.TargetText,
        "source": resp.Source,
        "target": resp.Target
    }
```

### 3.4 Post-install user operations

```bash
# 1. Register API credentials (once only)
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:key;register,tx,<your_secret_id>,access_key_secret=<your_secret_key>,api_key"}'

# 2. Install the package
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,tx-cloud"}'

# 3. Invoke
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:tx-cloud;translation,Hello,zh"}'
```

---

## IV. Container API Package

A container API package wraps a self-hosted service's REST API into a text-cli directive. The service runs in a local Docker container, and handler.py acts as an HTTP client calling it.

Using "Jellyfin media server" as the example — the user browses the home media library via text-cli.

### 4.1 Directory structure

```
jellyfin/
├── schema.json
├── handler.py
└── config/
    └── jellyfin.json      ← Service address config
```

**config/jellyfin.json**:

```json
{
  "url": "http://localhost:8096",
  "api_key": "your_jellyfin_api_key"
}
```

### 4.2 handler.py core pattern

> The `@directive(..., domain_alias="家庭媒体", action_aliases={"library": "媒体库"})` below registers optional Chinese aliases for this directive; the canonical id is `jellyfin;library`.

```python
import json, requests
from pathlib import Path
from core.registry import directive

# Locate config relative to this file, not dependent on process CWD
_CONFIG_PATH = Path(__file__).parent / "config" / "jellyfin.json"

def _load_config():
    """Read the service address config"""
    with open(_CONFIG_PATH, encoding="utf-8") as f:
        return json.load(f)

def _api(path):
    """Call the Jellyfin REST API"""
    config = _load_config()
    headers = {"X-Emby-Token": config["api_key"]}
    resp = requests.get(f"{config['url']}{path}", headers=headers)
    return resp.json()

@directive("jellyfin", "library", domain_alias="家庭媒体", action_aliases={"library": "媒体库"})
def library(params: list[str]) -> dict:
    """jellyfin;library — list all media libraries"""
    data = _api("/Library/VirtualFolders")
    libraries = [{"name": lib["Name"], "type": lib["CollectionType"]}
                 for lib in data]
    return {"status": "ok", "libraries": libraries,
            "count": len(libraries)}
```

### 4.3 Differences from online API package

| Dimension | Online API package | Container API package |
|------|------|------|
| Service location | Public cloud service | Local `localhost` or intranet address |
| `credentials` | Needed (cloud provider credentials) | Not needed (service is locally authenticated) |
| `config/` directory | Usually not needed | Must have — stores service address and local auth info |
| Prerequisite | Register API key | Start the Docker container |

### 4.4 Post-install user operations

```bash
# 1. Start the self-hosted service (e.g. Jellyfin Docker container)
docker run -d --name jellyfin -p 8096:8096 jellyfin/jellyfin

# 2. Configure the service address
# Edit config/jellyfin.json, fill in the correct url and api_key

# 3. Install the package
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,jellyfin"}'
```

---

## V. MCP Bridge Package

> Zero Python code — maps a registered MCP server's tool into a text-cli directive.

**Core idea**: You have already configured an MCP server (e.g. GitHub) in mcporter (or another tool that manages and calls MCP servers). Now you only need to write two JSON files, telling text-cli "which action under this domain corresponds to which server's which tool in mcporter."

### 5.1 Directory structure

```
my-package/
├── schema.json                 ← Directive declaration + runtime:"mcp"
└── service-descriptor.json     ← MCP server (mcporter) routing mapping
```

> An MCP package needs no handler.py — the call chain is text-cli directive → mcp_dispatch → mcporter → MCP server; text-cli executes no user code.

### 5.2 schema.json

> The `_zh` fields (`name_zh`, `domain_zh`, `action_zh`, `usage_zh`, `description_zh`) below are optional multilingual overrides — the Chinese values are example localized strings for the same directive; canonical fields stay English/neutral.

```json
{
    "id": "tc-mcp-github",
    "name": "GitHub MCP Bridge",
    "name_zh": "GitHub MCP 桥",
    "runtime": "mcp",
    "type": "native",
    "version": "0.1.0",
    "locales": ["zh", "en"],
    "trust": "community",
    "category": "开发工具",
    "directives": [
        {
            "domain": "comcp-github",
            "domain_zh": "GitHub",
            "action": "search_repos",
            "action_zh": "搜索仓库",
            "usage": "comcp-github;search_repos,<query>,<page>,<perPage>",
            "usage_zh": "GitHub;搜索仓库,<关键词>,<页码>,<每页数量>",
            "description": "Search GitHub repositories by keyword",
            "description_zh": "按关键词搜索 GitHub 仓库",
            "params": ["query", "page", "perPage"],
            "params_desc": {
                "query": "搜索关键词",
                "page": "页码（默认 1）",
                "perPage": "每页数量（默认 30）"
            },
            "mcp_tool": "search_repositories"
        }
    ]
}
```

### 5.3 service-descriptor.json

```json
{
    "mcp_server": "github",
    "tools": [
        {
            "name": "search_repos",
            "tool": "search_repositories"
        }
    ]
}
```

| Field | Notes |
|------|------|
| `mcp_server` | The server name configured in mcporter (must be configured before install) |
| `tools[].name` | Corresponds to the `action` field in schema.json |
| `tools[].tool` | The actual tool name of that server in mcporter |

### 5.4 Prerequisites

Before installing an MCP package, the corresponding server connection must first be configured in mcporter. The installer calls `mcporter list <server_name>` to verify — if the server is not configured, the install fails with a prompt.

```bash
# Configure the mcporter server first
mcporter add github --transport streamable-http --url https://api.github.com/mcp
```

### 5.5 Install and verify

```bash
# Install the package (service runtime only, cannot be installed into copilot)
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:text-cli;install,tc-mcp-github"}'

# Routing table refreshes immediately after install, no restart needed

# Invoke
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:comcp-github;search_repos,text-cli"}'
```

**Degradation chain participates automatically**: After an MCP directive is installed it automatically appears in the mcp_dispatch routing table. If mcporter is unreachable, the degrade signal lets the degradation chain continue to the next level (proxy / federation mesh), without a terminal error.

### 5.6 Uninstall

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Service-token: <token>" \
  -d '{"prompt":"AI:text-cli;uninstall,tc-mcp-github"}'
```

> Uninstall only removes the routing table entry and the schema file; it does not delete the server config in mcporter.

---

## VI. copilot Development

copilot is the local component of the Python standard runtime (`127.0.0.1:20260`), dedicated to exposing local OS capabilities — screenshot, audio, terminal commands, file operations. Unlike service, copilot cannot (and should not) be reached by other machines on the network.

### 6.1 When to use copilot instead of service

| Scenario | Which to use |
|------|:---:|
| JSON processing, math computation, Markdown conversion | service |
| Calling cloud service APIs (translation, maps, speech recognition) | service |
| Screenshot, photo capture, volume control | **copilot** |
| Execute local terminal commands | **copilot** |
| Read/write local files | **copilot** |

> **Judgment criterion**: If the directive's execution needs to directly manipulate local hardware, the filesystem, or the terminal — use copilot. The `127.0.0.1` lock is a security mechanism, not a restriction.

### 6.2 Security model: the whitelist gate

Each directive of a copilot package may execute shell commands — this raises higher security requirements. text-cli guarantees safety through a **dual whitelist gate**:

**Gate one (dispatch-layer hard gate)**: `CopilotCore.dispatch()` calls `WhitelistIndex.lookup()` before routing to the handler for validation — unregistered domain/action directly returns `ACCESS_DENIED`, never entering the handler. This gate is enforced by the runtime, cannot be bypassed by the developer.

**Gate two (handler-layer self-check)**: Inside the handler, `WhitelistIndex` does a second validation of params — `args_pattern` regex-matches variable args, `timeout` limits execution duration. This gate is called by the developer inside the handler (see §6.3 example).

- Each permitted command must be explicitly registered in `whitelist.json`
- Both the fixed args (`args`) and variable args (`args_pattern`) must be declared
- Each command has an independent timeout (`timeout`)
- Unregistered commands — the dispatch layer rejects directly, never reaching the handler

**whitelist.json structure**:

> The `action_zh` field on each command is an optional Chinese alias for display; the canonical `action` stays English/neutral.

```json
{
  "tool": "tc-ubuntu",
  "commands": [
    {
      "action": "screenshot",
      "action_zh": "截屏",
      "args": ["gnome-screenshot", "-f"],
      "args_pattern": "^.+screenshot_\\d+_\\d+\\.png$",
      "timeout": 10,
      "description": "Full-screen screenshot"
    },
    {
      "action": "volume-set",
      "action_zh": "音量设置",
      "args": ["pactl", "set-sink-volume", "@DEFAULT_SINK@"],
      "args_pattern": "^\\d{1,2}%$",
      "timeout": 5
    }
  ]
}
```

| Field | Notes |
|------|------|
| `action` | Corresponds to the `action` field in schema.json |
| `args` | The fixed command and params allowed to execute (e.g. `["gnome-screenshot", "-f"]`) |
| `args_pattern` | Regex — validates the variable args passed to the command (e.g. file paths only allow `.png` suffix) |
| `timeout` | Timeout in seconds — prevents the command from hanging |

### 6.3 Complete example: tc-ubuntu (desktop hardware control)

Using the "screenshot" directive as an example, showing the three-file structure of a copilot package.

**Directory structure**:

```
tc-ubuntu/
├── schema.json
├── handler.py
└── tc_ubuntu_whitelist.json    ← Whitelist (unique to copilot packages)
```

**schema.json specific fields**:

```json
{
  "runtime": "python",
  "requires": {
    "modules": ["whitelist_loader"]
  }
}
```

**handler.py core pattern**:

```python
import subprocess
from pathlib import Path

def ok(result):
    return {"status": "ok", "result": result}

def error(reason):
    return {"status": "error", "reason": reason}

WHITELIST_DIR = Path(__file__).parent

_whitelist_index = None

def _get_index():
    global _whitelist_index
    if _whitelist_index is None:
        from whitelist_loader import WhitelistIndex
        _whitelist_index = WhitelistIndex(WHITELIST_DIR)
    return _whitelist_index

def _exec_whitelist(action, extra_args=None):
    index = _get_index()
    entry = index.lookup("tc-ubuntu", action)
    if not entry:
        return error(f"action not in whitelist: {action}")

    cmd = entry["args"].copy()
    if extra_args:
        import re
        arg_str = " ".join(str(a) for a in extra_args)
        if not re.match(entry["args_pattern"], arg_str):
            return error(f"args rejected: {arg_str}")
        cmd.extend([str(a) for a in extra_args])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True,
                                timeout=entry["timeout"])
        return ok(result.stdout.strip()) if result.returncode == 0 \
          else error(result.stderr.strip())
    except subprocess.TimeoutExpired:
        return error(f"timeout after {entry['timeout']}s")
```

### 6.4 service package vs copilot package

| Dimension | service package | copilot package |
|------|------|------|
| `requires.modules` | None | `["whitelist_loader"]` — required |
| Extra file | — | `whitelist.json` — required |
| Execution | Python function | `subprocess.run()` — after whitelist validation |
| Security constraint | Credential isolation | Whitelist + regex + timeout |
| Defensive design | No special requirement | Volume cap 50%, max recording 30 seconds |

### 6.5 Install and verify (copilot runtime)

```bash
# 1. Start the copilot runtime

# 2. Install the package (note: co-install)
curl -X POST http://localhost:20260/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;co-install,tc-ubuntu"}'

# 3. Verify
curl -X POST http://localhost:20260/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:tc-ubuntu;screenshot"}'

# 4. Uninstall
curl -X POST http://localhost:20260/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;co-uninstall,tc-ubuntu"}'
```

### 6.6 Security red lines

| Red line | Notes |
|------|------|
| **Do not register system directives in the service runtime** | service listens on `0.0.0.0` — anyone can call. System-control capabilities can only be exposed in copilot (`127.0.0.1`) |
| **Minimize the whitelist** | Only declare the commands and params a directive needs. Do not put wildcard commands (e.g. `["bash", "-c"]` without regex restriction) |
| **Timeout must be set** | Every whitelist entry must set `timeout`. A subprocess without timeout is a potential resource leak |
| **Param validation must be strict** | `args_pattern` uses regex to restrict file paths and numeric ranges — tc-ubuntu's volume uses `^\d{1,2}%$` to guarantee no more than 99% |

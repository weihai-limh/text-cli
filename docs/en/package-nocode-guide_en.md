# No-Code (nocode) Development Guide

> **Language note:** This English text is a translation of the normative Chinese guide (`src/text_cli/base_text-cli/docs/package-nocode-guide_zh.md`). Where this translation and the Chinese original differ or are ambiguous, the Chinese version is authoritative.

> No coding required. Write your experience as Markdown and turn it into a text-cli instruction service callable by both humans and AI.

---

## 1. Two Approaches

Your Markdown experience document can become an instruction service in two ways:

| | Approach 1: Single File | Approach 2: Runtime |
|---|---|---|
| What you do | Write one Markdown (starts without touching code) | `knowledge/` multi-file + index + path JSON |
| Matching | Keyword string lookup | AI semantic inference |
| Dependencies | Zero (pure Python standard library) | `tc-markdown` + `ai-inference` |
| Start | `python converter_template.py <md-file>` | `text-cli;install` |
| Best for | Clear symptoms, keywords cover it | Vague symptoms, inference needed |

The two approaches are not either/or — **Approach 1 is a zero-threshold starting point; Approach 2 is the more complete system into which the same knowledge can be embedded once you own a text-cli runtime.** Approach 1's Markdown, when split apart, becomes the `knowledge/` input of Approach 2.

Below we first walk you through Approach 1, then introduce Approach 2.

---

## 2. Approach 1: No-Runtime Mode

> Zero dependencies. One Markdown + one template script = one HTTP instruction service.

### 2.1 Try It Now

The "potted plant first aid" guide is a florist's ten-year notebook of experience. You don't need to know code — just go in and run it:

```bash
cd src/text_cli/base_text-cli/template/base_nocode/en
python markdown_converter_en.py Bonsai-First-Aid-Manual_en.md
```

After startup:

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:home-gardening;plant-first-aid,pothos,yellow leaves"}'
```

Response:

```json
{
  "rst_types": "text",
  "rst_data": {
    "status": "ok",
    "category": "Pothos",
    "sub": "Yellow Leaves",
    "content": "- Cause: Overwatering or insufficient light...\n- First Aid: ...\n- Prevention: ..."
  },
  "rst_err": ""
}
```

It returns the cause, treatment, differential diagnosis, and prevention advice for pothos leaves yellowing. One Markdown, one working service. Humans and AI consume it through the same endpoint.

### 2.2 Turn Your Experience into a Service

Write a Markdown (refer to `src/text_cli/base_text-cli/template/base_nocode/template.md` or `src/text_cli/base_text-cli/template/base_nocode/template_zh.md`):

```markdown
## Directive
- Domain: car-repair
- Action: diagnose
- Triggers: engine, brakes, noise
- Params: part, symptom
- Source: Master Wang, 20 years of auto-repair experience   # optional — knowledge source
- Verified: Engineer Li, 2025-08-01                          # optional — verifier and date
- Stale After: 2026-12-31                                    # optional — expiration date
- Status: stable                                             # optional — draft | stable | deprecated

## Knowledge
### Engine
#### Won't Start
- Cause: Dead battery or faulty starter.
- First Aid: Jump-start or replace the battery. Check the starter relay.
- Prevention: Replace the battery every 3-5 years.
- Differential: ...   # optional — how to distinguish from similar issues
- Lessons: ...        # optional — hard-earned lessons
```

> `Source`/`Verified`/`Stale After`/`Status` are optional fields — this information belongs to the knowledge-production workflow and may be cleaned during data transmission. The code passes it through if present (it appears in the schema), and its absence does not affect service operation. `Differential`/`Lessons` are content-convention fields; just write them in the entry, the parser does not special-case them.

Start without touching code:

```bash
python src/text_cli/base_text-cli/template/base_nocode/converter_template.py car-repair-manual.md
```

The script automatically extracts the domain and action from the `## Directive` section of the Markdown. If you need to override the values in the Markdown, change the top variables:

```python
Domain = "car-repair"     # explicitly set to override the value in Markdown
Action = "diagnose"
Host = "0.0.0.0"          # bind address
Port = 8000               # listen port
```

`Host` and `Port` can also be overridden via command-line arguments:

```bash
python src/text_cli/base_text-cli/template/base_nocode/converter_template.py car-repair-manual.md --port 9000
```

The service starts. `AI:car-repair;diagnose,Engine,Won't Start` → returns your experience.

### 2.3 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/text-cli/cli` | POST | Execute instruction (`AI:domain;action,params`) |
| `/text-cli/cli` | POST | Instruction discovery (`AI:text-cli;query,json`) |
| `/text-cli/schema` | GET | Instruction schema (with credibility info) |
| `/text-cli/health` | GET | Health check |

Query examples:

```bash
# Exact match
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:car-repair;diagnose,Engine,Won'\''t Start"}'

# List all subcategories under this category
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:car-repair;diagnose,Engine"}'

# List all categories
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:car-repair;diagnose"}'

# View schema (with source/verification/expiration/status and other credibility info)
curl http://localhost:8000/text-cli/schema

# Instruction discovery (returns the same content as the schema endpoint)
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;query,json"}'
```

Exact-match response:

```json
{
  "rst_types": "text",
  "rst_data": {
    "status": "ok",
    "category": "Engine",
    "sub": "Won't Start",
    "content": "- Cause: ...\n- First Aid: ...\n- Differential: ...\n- Lessons: ..."
  },
  "rst_err": ""
}
```

Degraded match (symptom not exactly hit):

```json
{
  "rst_types": "text",
  "rst_data": {
    "status": "ok",
    "category": "Engine",
    "sub": null,
    "items": [
      {"sub": "Won't Start", "content": "..."},
      {"sub": "Noise", "content": "..."}
    ]
  },
  "rst_err": ""
}
```

### 2.4 Custom Retrieval Logic

The default `category → subcategory` two-level lookup covers most scenarios. If you need a different parameter structure, change the `handler()` function in the `[Custom 3/3]` section. The handler returns a dict (used directly as `rst_data`):

```
No params    → {"status": "ok", "entry_count": N, "categories": [...]}
One param    → {"status": "ok", "category": "...", "subs": [...]}
Two params   → {"status": "ok", "category": "...", "sub": "...", "content": "..."}
              if not found, degrade → {"status": "ok", "category": "...", "sub": null, "items": [...]}
```

Restart after changing for it to take effect. Refer to `src/text_cli/base_text-cli/template/base_nocode/en/markdown_converter_en.py` for a self-contained complete example.

### 2.5 Multi-Language Support

The template script is language-agnostic — field names are driven by the `FIELD_LABELS` configuration. Chinese and English are supported by default. To add another language, add a language subtree in `FIELD_LABELS`:

```python
FIELD_LABELS = {
    "en": { "domain": "Domain", "action": "Action", ... },
    "zh": { "domain": "领域", "action": "动作", ... },
    # "ja": { "domain": "領域", "action": "動作", ... },  ← uncomment and fill in
}
```

The complete language reference library is at `src/text_cli/base_text-cli/template/base_nocode/field_labels.json` (covering zh/en/fr/ar/es/ru/ja/ko/zh-TW). Adding a language = adding one config line; the parsing logic needs zero changes.

### 2.6 Add Token Authentication

If you need to restrict who can access, change the two top variables:

```python
AuthEnabled = True
ServiceToken = "my-secret"
```

The caller must include the `Service-token: my-secret` header. A token mismatch returns `SERVICE_DENIED`.

---

## 3. Approach 2: Runtime Mode

> Prerequisite: you have deployed the text-cli runtime, and the `tc-markdown` and `ai-inference` instruction packages are installed.

Approach 2 is not more code — your Markdown experience knowledge stays the same. What it gains is the capability granted by the runtime: AI semantic inference, instruction discovery, path orchestration, and aggregation degradation. The same knowledge from Approach 1, split into multiple files plus a path definition and a package declaration, becomes a runtime-perceivable instruction package.

### 3.1 Core Difference

Approach 1 is a standalone HTTP service. Approach 2 is a first-class runtime-schedulable capability — discoverable via `text-cli;query`, participatable in path orchestration, and aggregatable/degradable.

The same knowledge, different deployment forms:

```
Approach 1                           Approach 2
Bonsai-First-Aid-Manual_en.md  ──split──→  knowledge/
  (one big document)                   ├── 绿萝-叶片发黄.md   # pothos-yellow-leaves
                                      ├── 绿萝-烂根.md       # pothos-root-rot
                                      ├── 蚜虫.md            # aphids
                                      └── ...
                                  + knowledge-index.md  ← AI matches using this (symptom → filename)
                                  + path/diagnose.json   ← orchestration steps
                                  + schema.json          ← package declaration
```

### 3.2 Upgrade from Approach 1

Already have an Approach 1 Markdown? Five steps to upgrade:

1. **Split the document**: each `### category` → `knowledge/<category>.md`
2. **Write the index**: extract each doc's symptom keywords → `knowledge-index.md`
3. **Write the schema**: `type: "nocode"`, `runtime: "path"`
4. **Write the path**: four-step pipeline JSON (see 3.4)
5. **Install**:
```
AI:text-cli;install,tc-markdown
AI:text-cli;install,ai-inference
AI:text-cli;install,<package-id>
```

> Templates and complete examples: `src/text_cli/base_text-cli/template/runtime_nocode/nocode-template/` + `src/text_cli/base_text-cli/template/runtime_nocode/nocode-example-zh/`

### 3.3 File Structure

```
<package-id>/
├── schema.json
├── path/diagnose.json
├── knowledge/              ← experience docs split from Approach 1
│   ├── 蚜虫.md              # aphids (example from the Chinese package)
│   └── 根腐.md              # root rot (example from the Chinese package)
├── knowledge-index.md      ← symptom → filename (e.g. "yellow leaves" → 蚜虫.md)
└── README.md
```

### 3.4 Path Definition

The path engine uses `tc-markdown;read` to read files and `ai;infer` to do inference — the path itself only does orchestration and interpolation:

```json
{
  "type": "pipeline",
  "default_source": "http://localhost:28050/text-cli/cli",
  "requires": ["tc-markdown;read", "ai;infer"],
  "steps": [
    {"id": "index",    "instruction": "tc-markdown;read,knowledge-index.md"},
    {"id": "lookup",   "instruction": "ai;infer,match the symptom against the index...", "output_as": "lookup"},
    {"id": "read",     "instruction": "tc-markdown;read,knowledge/{lookup.file}"},
    {"id": "diagnose", "instruction": "ai;infer,diagnose based on the experience...",   "output_as": "diagnose"},
    {"id": "fallback", "instruction": "ai;infer,general advice...", "if": "{lookup.file} == 'NOMATCH'"}
  ]
}
```

Full definition at `src/text_cli/base_text-cli/template/runtime_nocode/nocode-example-zh/path/diagnose.json`.

### 3.5 Install and Verify

```bash
curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:text-cli;install,flower-care"}'

curl -X POST http://localhost:28050/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:flower-care;diagnose,leaves curling with sticky fluid"}'
```

---

> More details: `src/text_cli/base_text-cli/template/base_nocode/docs/README_en.md` (Approach 1 template manual).

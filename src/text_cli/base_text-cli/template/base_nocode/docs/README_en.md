# converter_template.py User Guide

## What this is

`converter_template.py` is a single-file template — turns structured Markdown experience documents into text-cli directive services.

Zero dependencies, pure Python stdlib. Humans and AI consume through the same HTTP endpoint.

## Folder structure

```
base_nocode/
├── converter_template.py          ← The template (your starting point)
├── template.md                    ← Markdown spec template (write your .md like this)
├── docs/
│   ├── README_zh.md               ← Chinese guide
│   └── README_en.md               ← This file
├── zh/                            ← Chinese instance (reference)
│   ├── markdown_converter_zh.py   ← Template after filling in
│   ├── 盆栽急救手册_zh.md         ← Chinese knowledge doc
│   └── README.md
└── en/                            ← English instance (reference)
    ├── markdown_converter_en.py   ← Template after filling in
    ├── Bonsai-First-Aid-Manual_en.md ← English knowledge doc
    └── README.md
```

## Three steps

### Step 1: Write your Markdown

Follow the format in `template.md` (bilingual section headers supported):

```markdown
## Directive
- Domain: car-repair
- Action: diagnose
- Triggers: engine, brakes, oil, noise
- Params: part, symptom

## Knowledge
### Engine
#### Won't Start
- Cause: Dead battery or faulty starter.
- Fix: Jump-start or replace battery. Check starter relay.
- Prevention: Replace battery every 3-5 years.
```

Key rules:
- `## Directive` (or `## 指令定义`) block defines domain and action
- `## Knowledge` (or `## 经验内容`) block is the knowledge content
- `###` is a category, `####` is a sub-category

### Step 2: Copy the template

```bash
cp converter_template.py my-car-repair.py
```

Open `my-car-repair.py`, change the 4 variables at the top:

```python
Domain = "car-repair"
Action = "diagnose"
AuthEnabled = False
ServiceToken = ""
```

### Step 3: Start

```bash
python my-car-repair.py car-repair-manual.md
```

Call the service:

```bash
curl -X POST http://localhost:8000/text-cli/cli \
  -H "Content-Type: application/json" \
  -d '{"prompt": "AI:car-repair;diagnose,Engine,Won'\''t Start"}'
```

## Custom handler

If the default `category → sub` two-level search doesn't fit your parameters, modify the `handler()` function in the `[Custom 3/3]` section.

Default logic:
```
no params     → list all categories
one param     → list all sub-categories under that category
two params    → exact match category+sub, fallback to category-only if not found
```

Restart after changes.

## Token auth

```python
AuthEnabled = True
ServiceToken = "my-secret"
```

Callers must include the `Service-token: my-secret` header. Wrong or missing token returns `SERVICE_DENIED`.

## Reference instances

| Instance | Domain | Action | Language |
|----------|--------|--------|:--:|
| `zh/` | 家庭园艺 | 盆栽急救 | Chinese |
| `en/` | home-gardening | plant-first-aid | English |

Each is `converter_template.py` with the variables filled in — a complete, runnable service. Use them to see what a finished handler looks like.

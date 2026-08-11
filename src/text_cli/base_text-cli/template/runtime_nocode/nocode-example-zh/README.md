# Plant First Aid Diagnosis

**NoCode instruction package example** — a florist's experience turned into callable AI diagnostics.

> Want to create your own nocode package? See `../nocode-template/`.

## Install

```
AI:text-cli;install,nocode-zh
```

## Dependencies

- text-cli packages: `tc-markdown`, `ai-inference`
- Runtime: path engine (A4+)
- No pip dependencies, no credentials

## Directives

| Instruction | Description |
|-------------|-------------|
| `nocode-zh;diagnose,<symptoms>` | Diagnose plant problems from natural language symptoms |

## How It Works

```
User: nocode-zh;diagnose,月季叶子从下往上黄，一碰就掉

Path engine:
  1. tc-markdown;read → knowledge-index.md (symptom→disease mapping)
  2. ai;infer → semantic match: "root-rot.md"
  3. tc-markdown;read → knowledge/root-rot.md (expert experience)
  4. ai;infer → diagnosis + treatment + prevention
  5. NOMATCH → fallback general plant advice
```

## Architecture

```
nocode-example-zh/
├── schema.json           ← directive declarations (type: nocode, runtime: path)
├── knowledge/            ← embedded experience documents (6 plant problems)
│   ├── 蚜虫.md (aphids)
│   ├── 根腐病.md (root rot)
│   ├── 黄叶病.md (yellow leaves)
│   ├── 白粉病.md (powdery mildew)
│   ├── 浇水烂根.md (overwatering)
│   └── 光照不足.md (light deficiency)
├── knowledge-index.md    ← symptom → document mapping (AI semantic matching)
└── path/
    └── diagnose.json     ← path definition (5-step pipeline)
```

## Creating Your Own

Use the `../nocode-template/` template — placeholders are marked, copy and replace.

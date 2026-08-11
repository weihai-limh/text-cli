# NoCode Path Template

Copy this template, replace the placeholders, add your knowledge, and you have a callable AI diagnosis package — without writing any code.

> See `../nocode-example-zh/` for a complete example (Plant First Aid Diagnosis in Chinese).

## Quick Start

1. `cp -r nocode-template my-package`
2. Replace all `{PLACEHOLDER}` in `schema.json` and `path/diagnose.json`
3. Write your knowledge files in `knowledge/`, delete `example.md`
4. Fill in `knowledge-index.md`
5. `AI:text-cli;install,{PACKAGE_ID}`

## Requirements

- text-cli packages: `tc-markdown`, `ai-inference`
- Runtime: A4+ (path engine)

## How It Works

```
User: {DOMAIN};{ACTION},{symptom-description}

Path engine:
  1. tc-markdown;read → knowledge-index.md  (symptom → document mapping)
  2. ai;infer → semantic match → best document
  3. tc-markdown;read → knowledge/{document}  (expert knowledge)
  4. ai;infer → diagnosis + treatment + prevention
  5. (if NOMATCH) → fallback general advice
```

## Architecture

```
nocode-template/
├── schema.json                ← directive declaration ({placeholders})
├── path/
│   └── diagnose.json          ← 5-step pipeline ({placeholders})
├── knowledge/
│   └── example.md             ← format reference (delete when done)
├── knowledge-index.md         ← symptom → file mapping
├── TEMPLATE_INSTRUCTIONS.md   ← detailed replacement checklist
└── README*.md
```

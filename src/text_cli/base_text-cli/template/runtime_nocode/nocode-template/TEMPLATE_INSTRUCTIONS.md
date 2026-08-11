# NoCode Template Instructions

Copy this directory and replace all `{PLACEHOLDER}` values.
Each placeholder appears once — global search-and-replace works.

## Replacement Checklist

### schema.json

| Placeholder | What to put |
|-------------|------------|
| `{PACKAGE_ID}` | Unique package ID, e.g. `car-troubleshooting` |
| `{NAME_EN}` | Package name in English |
| `{NAME_ZH}` | Package name in Chinese |
| `{CATEGORY}` | Category tag, e.g. `知识库` `生活` `工具` |
| `{LOCALE}` | Primary locale, e.g. `zh` |
| `{DESCRIPTION_EN}` | One-sentence English description |
| `{DESCRIPTION_ZH}` | One-sentence Chinese description |
| `{DOMAIN}` | Canonical domain, e.g. `car-diagnose` |
| `{DOMAIN_ZH}` | Chinese domain alias, e.g. `汽车故障` |
| `{ACTION}` | Canonical action, e.g. `diagnose` |
| `{ACTION_ZH}` | Chinese action alias, e.g. `诊断` |
| `{PARAM}` | Input parameter name, e.g. `symptoms` |
| `{PARAM_ZH}` | Input parameter display name in Chinese |
| `{PARAM_DESC}` | Parameter description |
| `{DIRECTIVE_DESC_EN}` | English directive description |
| `{DIRECTIVE_DESC_ZH}` | Chinese directive description |
| `{ESTIMATED_TIME}` | Estimated execution time, e.g. `30s` |
| `{ESTIMATED_TIME_NOTE}` | Note about timing |
| `{SOURCE}` | Knowledge provenance, free text. Optional — leave empty to omit. e.g. `张师傅口述,十年花店经验` |
| `{VERIFIED}` | Verification record, e.g. `李老师,2025-06-15`. Optional — leave empty to omit. |
| `{STALE_AFTER}` | Freshness deadline, `YYYY-MM-DD`. Optional — leave empty to omit. |
| `{DOC_STATUS}` | Doc lifecycle: `draft` / `stable` / `deprecated`. Optional — leave empty to omit. |

### path/diagnose.json

| Placeholder | What to put |
|-------------|------------|
| `{PACKAGE_ID}` | Same as schema.json |
| `{NAME_EN}` | Same as schema.json |
| `{AI_ROLE_PROMPT}` | Role prompt for AI diagnosis, e.g. `You are a car mechanic. Diagnose strictly based on the following knowledge. Do not fabricate.` |
| `{FALLBACK_PROMPT}` | Fallback prompt when no match found, e.g. `The issue is not in the knowledge base. Provide general advice based on automotive knowledge. State that this is not from the expert database.` |

### knowledge-index.md

Each line: `{filename}.md  ←  {comma-separated keywords}`. Last line is always `NOMATCH`.

### knowledge/*.md

Replace `example.md` with your domain-specific documents.
Each file has this structure: Symptoms → Common Conditions → How to Distinguish → Treatment → Prevention → Notes.
Delete `example.md` when done.

## Quick Start

1. Copy this directory: `cp -r nocode-template my-package`
2. Open `schema.json` and `path/diagnose.json`, replace all `{...}` values
3. Write your knowledge documents in `knowledge/`, delete `example.md`
4. Fill in `knowledge-index.md` with your symptom-to-file mapping
5. Install: `AI:text-cli;install,{PACKAGE_ID}`
6. Test: `AI:{DOMAIN};{ACTION},{test-input}`

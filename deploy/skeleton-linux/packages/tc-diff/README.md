# tc-diff

Text diff processor for path pipelines. Line-level unified diff, similarity ratio, patch application, and word-level diff. Zero external dependencies — Python stdlib `difflib` only. Stateless: reads no files, writes no disk.

## Install

```
AI:text-cli;install,tc-diff
```

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-diff;unified,<text_a>,<text_b>[,<context>,<label_a>,<label_b>]` | Unified diff between two texts; returns `has_diff` for fast no-change routing |
| `tc-diff;similarity,<text_a>,<text_b>` | Similarity ratio (0.0–1.0) and line counts; use as a decision gate before a full diff |
| `tc-diff;patch,<original>,<diff>` | Apply a unified diff to the original text; reports `hunks_applied`/`hunks_total` and conflicts |
| `tc-diff;word-diff,<text_a>,<text_b>[,<format>]` | Word-level diff; `ops` (pipeline-friendly) or `html` (inline `<del>`/`<ins>`) |

## Example

### unified — line-level diff

```
AI:tc-diff;unified,"line one\nline two\nline three","line one\nchanged line\nline three"
→ {"status":"ok","has_diff":true,"diff":"--- a\n+++ b\n@@ -1,3 +1,3 @@\n line one\n-line two\n+changed line\n line three"}
```

### similarity — quick gate

```
AI:tc-diff;similarity,{step1.content},{step2.content}
→ {"status":"ok","ratio":0.873,"lines_a":42,"lines_b":45,"equal":false}
```

### patch — the diff↔restore loop

```
AI:tc-diff;unified,{step1.content},{step2.content} → {step3.diff}
AI:tc-diff;patch,{step1.content},{step3.diff}
→ {"status":"ok","patched":"(restored full text)","hunks_applied":2,"hunks_total":2}
```

### word-diff — fine-grained

```
AI:tc-diff;word-diff,The quick brown fox,The quick red fox jumps
→ {"status":"ok","format":"ops","ratio":0.72,"operations":[
    {"type":"equal","value":"The quick "},
    {"type":"replace","old":"brown","new":"red"},
    {"type":"equal","value":" fox"},
    {"type":"insert","value":" jumps"}
  ]}
```

## Architecture

```
tc-diff/
├── schema.json    — 4 directive declarations
└── handler.py     — pure stdlib difflib processor
```

The diff is not an end — it is a pipeline intermediate. `unified` produces a diff, `patch` consumes it to restore the target text, closing a complete diff–restore loop. `similarity` lets you skip a full diff when ratio < 0.3 (major rewrite) or prioritize review when ratio > 0.8.

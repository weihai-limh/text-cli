# tc-markdown

Read and parse Markdown files: full content, heading structure, or the content under a specific heading. File access is restricted to an allowed base directory to prevent path traversal.

## Install

```
AI:text-cli;install,tc-markdown
```

## Dependencies

Zero dependencies (Python stdlib only).

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-markdown;read,<path>` | Read the full content of a Markdown file |
| `tc-markdown;headings,<path>` | Extract heading structure (level / text / line number) |
| `tc-markdown;section,<path>,<heading>` | Extract content under a heading until the next same-or-higher-level heading |

## Example

```
AI:tc-markdown;read,/root/docs/README.md
AI:tc-markdown;headings,/root/docs/README.md
AI:tc-markdown;section,/root/docs/README.md,Installation
```

## Security

File access is confined to the base directory configured at init time, preventing path traversal.

## Architecture

```
tc-markdown/
├── schema.json    — 3 directive declarations
├── handler.py     — Markdown reader/parser
└── README.md
```

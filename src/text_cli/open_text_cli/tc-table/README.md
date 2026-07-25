# tc-table

Table data processor for path pipelines. Read CSV/TSV/XLSX → JSON arrays → filter / sort / pivot / join → write back. Zero external dependencies for CSV/TSV; `openpyxl` optional for XLSX.

## Install

```
AI:text-cli;install,tc-table
```

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-table;read,<file_path>[,<format>]` | Read a table file → JSON array. Format auto-detected from extension |
| `tc-table;schema,<file_path>` | Column names, inferred types, and 3 sample values |
| `tc-table;filter,<json_data>,<JSON_query>` | Filter rows. Query: `{where:[col,op,val], limit?}` |
| `tc-table;sort,<json_data>,<JSON_query>` | Sort rows. Query: `{by:col, dir?:asc/desc}` |
| `tc-table;pivot,<json_data>,<JSON_query>` | Group + aggregate. Query: `{group, agg, on?}` |
| `tc-table;join,<json_a>,<json_b>,<JSON_query>` | Join two tables. Query: `{on, type?}` |
| `tc-table;write,<json_data>,<file_path>[,<format>]` | Write JSON array to file (CSV/TSV/XLSX) |

### filter operators

`=`, `!=`, `>`, `<`, `>=`, `<=` — numeric comparison · `contains` · `starts` · `ends` · `in` (comma-separated list)

### pivot aggregates

`count` / `sum` / `avg` / `min` / `max`

### join types

`inner` (default) / `left` / `right` / `outer`. Columns with the same name get a `_right` suffix on the right table.

## Example

```
AI:tc-table;read,sales.csv
  → tc-table;filter,<prev>,{"where":["amount",">","200"]}
  → tc-table;sort,<prev>,{"by":"amount","dir":"desc"}
  → tc-table;write,<prev>,top_sales.csv
```

## Dependencies

- CSV / TSV: none (stdlib `csv`).
- XLSX: `pip install openpyxl` (optional; only if you read/write `.xlsx`).

## Architecture

```
tc-table/
├── schema.json    — 7 directive declarations
└── handler.py     — read → transform → write pipeline
```

CSV/TSV output is UTF-8 with BOM; XLSX requires `openpyxl`.

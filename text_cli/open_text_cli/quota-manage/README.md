# quota-manage

Function-level API quota tracker with atomic cycle-reset and consume.

## Install

```
AI:text-cli;install,quota-manage
```

## Dependencies

Zero external dependencies. Python stdlib only (`sqlite3`, `json`, `logging`, `pathlib`).

## Directives

| Directive | Description |
|-----------|-------------|
| `quota;register,<target>,<cycle>,<limit>` | Register a quota rule. Cycles: `day`/`week`/`month`/`year`/`forever` |
| `quota;check,<target>[,<amount>]` | Atomic check + consume. Returns `remaining` or `stop` signal |
| `quota;list` | List all rules with current usage |
| `quota;reset,<target>` | Manually reset counter |
| `quota;unregister,<target>` | Remove a rule |

## Example

```
AI:quota;register,my-api,day,100
AI:quota;check,my-api
→ {"status":"ok","remaining":99,"used":1,"cycle":"day","limit":100}

AI:quota;list
→ {"status":"ok","count":1,"quotas":[{"target":"my-api","cycle":"day","limit":100,"used":1,"remaining":99}]}
```

## Architecture

```
A6 SQL module
  ├── handler.py     — @directive registration + business logic
  └── schema.json    — directive declarations
```

SQLite table: `quota(func_name, cycle_type, cycle_limit, usage_count, usage_date, created_at)`

Atomicity via SQLite `UPDATE ... WHERE usage_count = ?` optimistic locking.

# tc-sql

A unified SQL query protocol layer — a bridge to databases, not a new database. Any data owner joins by declaring its database in `config/sql_permissions.json`; callers reach it through one consistent set of directives. Reads are generic; writes stay in each domain's own dedicated directive.

## Install

```
AI:text-cli;install,tc-sql
```

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-sql;query,<db_alias>,<JSON>` | Query rows. JSON: `{table, columns, where?, limit?}` |
| `tc-sql;tables,<db_alias>` | List all tables in a database |
| `tc-sql;schema,<db_alias>,<JSON>` | Column info (PRAGMA table_info). JSON: `{table}` |
| `tc-sql;count,<db_alias>,<JSON>` | Row count. JSON: `{table, where?}` |

### query

```
AI:tc-sql;query,service,{"table":"call_log","columns":"action,service,detail","where":["action","KEY_REGISTER"],"limit":20}
→ {"status":"ok","table":"call_log","columns":["action","service","detail"],"rows":[...],"count":2}
```

| JSON field | Required | Notes |
|------------|----------|-------|
| `table` | yes | Table name |
| `columns` | yes | Comma-separated columns (no `*` allowed) |
| `where` | no | `[col, value]` — equality only |
| `limit` | no | Max rows; default 100, max 1000 |

### tables

```
AI:tc-sql;tables,service
→ {"status":"ok","database":"service","tables":["call_log","key_registry"],"count":2}
```

### schema

```
AI:tc-sql;schema,service,{"table":"call_log"}
→ per-column cid, name, type, notnull, pk
```

### count

```
AI:tc-sql;count,service,{"table":"key_registry"}
→ {"status":"ok","table":"key_registry","count":42}
```

## Permissions

Controlled by `config/sql_permissions.json`, auto-deployed on install (existing files are not overwritten).

```json
{
  "authenticated": {
    "service": {
      "driver": "sqlite",
      "path": "text_cli_modules/sqlite/service.db",
      "tables": {
        "key_registry": {"ops": ["schema"]},
        "call_log": {"ops": ["query", "schema", "tables", "count"]}
      }
    }
  }
}
```

**Hard rule:** `key_registry` never gets `query` — secret values are read only through the dedicated `key;get` directive.

## Design Principles

- **Read can be generic, write must be dedicated** — queries go through tc-sql, writes through each domain's own directive.
- **Columns ride along in results** — pipelines can index them, AI can read them.
- **JSON prevents injection** — column names and values live in separate fields, naturally isolated.
- **Driver-agnostic** — the permission declaration carries a `driver` field; the connection factory branches inside the handler.

# task-manager

Async task lifecycle management with SQLite persistence. Used by long-running directives (e.g., bim-ifc).

## Install

```
AI:text-cli;install,task-manager
```

## Dependencies

**Runtime modules** (must be deployed to the service):
- `text_cli_modules/sqlite/` — database layer

**Storage**: results written to `TEXT_CLI_MEDIA_DIR/tasks/` (env var, defaults to service media directory).

## Directives

| Directive | Description |
|-----------|-------------|
| `task;status,<task_id>` | Query task status (pending/running/done/error) |
| `task;result,<task_id>` | Get completed task result |
| `task;list` | List all tasks |
| `task;track,<task_id>` | Get cache tracking key |
| `task;cancel,<task_id>` | Cancel pending/running task |

## Example

```
AI:task;list
→ 3 tasks: a1b2c3 (running), d4e5f6 (done), g7h8i9 (error)

AI:task;status,a1b2c3
→ {"status": "running", "progress": "step 2/5"}

AI:task;result,d4e5f6
→ {"status": "done", "result": {...}}
```

## Architecture

```
A6 SQL module
  ├── handler.py          — @directive registration + task lifecycle
  ├── schema.json         — 5 directives
  └── text_cli_modules/sqlite/ — database layer (runtime dependency)
```

"""
task-manager — async task lifecycle with SQLite persistence.

Provides task registration, status tracking, and result storage.
Used by bim-ifc and any other long-running directive.

A6 infrastructure — shares SQLITE_DB_PATH with key/embed/quota.

Author: Tide 🌊 — 2026-05-16
"""

import json
import os
import sqlite3
import threading
import time
from pathlib import Path

RESULTS_DIR = Path(os.environ.get("TEXT_CLI_MEDIA_DIR", "/root/text-cli/media")) / "tasks"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Injected by init (from service SQLITE_DB_PATH)
_db_file: str | None = None
_local = threading.local()

# Dispatch injection (for tracked tasks — real-time poll on status query)
_dispatch_fn = None


def _set_task_dispatch(fn):
    """Inject dispatch callback (called by main.py after init)."""
    global _dispatch_fn
    _dispatch_fn = fn


def _get_db() -> sqlite3.Connection:
    """Thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(_db_file)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def _ensure_table():
    db = _get_db()
    db.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            task_id    TEXT PRIMARY KEY,
            domain     TEXT NOT NULL,
            action     TEXT NOT NULL,
            state      TEXT DEFAULT 'pending',
            params     TEXT,
            result_path TEXT,
            error      TEXT,
            progress   TEXT,
            created_at INTEGER,
            updated_at INTEGER
        )
    """)
    db.execute("CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state)")
    db.commit()


# ── Public API ──────────────────────────────────

def register(domain: str, action: str, params: dict = None) -> str:
    """Register a new task. Returns task_id."""
    _ensure_table()
    ts = int(time.time() * 1000)
    seq = _next_seq()
    task_id = f"{domain}-{action}-{seq:04d}"
    db = _get_db()
    db.execute(
        "INSERT INTO tasks (task_id,domain,action,state,params,created_at,updated_at) "
        "VALUES (?,?,?,'pending',?,?,?)",
        (task_id, domain, action, json.dumps(params or {}), ts, ts),
    )
    db.commit()
    return task_id


def update(task_id: str, state: str, progress: str = "", error: str = ""):
    """Update task state and progress."""
    db = _get_db()
    db.execute(
        "UPDATE tasks SET state=?,progress=?,error=?,updated_at=? WHERE task_id=?",
        (state, progress, error, int(time.time() * 1000), task_id),
    )
    db.commit()


def complete(task_id: str, result: dict):
    """Mark task done and store result."""
    result_path = str(RESULTS_DIR / f"{task_id}.json")
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    Path(result_path).write_text(json.dumps(result, ensure_ascii=False))

    db = _get_db()
    db.execute(
        "UPDATE tasks SET state='done',result_path=?,updated_at=? WHERE task_id=?",
        (result_path, int(time.time() * 1000), task_id),
    )
    db.commit()


def fail(task_id: str, error: str):
    """Mark task as failed."""
    db = _get_db()
    db.execute(
        "UPDATE tasks SET state='error',error=?,updated_at=? WHERE task_id=?",
        (error, int(time.time() * 1000), task_id),
    )
    db.commit()


def cancel(task_id: str) -> bool:
    """Cancel a pending/running task."""
    db = _get_db()
    row = db.execute("SELECT state FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if row and row["state"] in ("pending", "running"):
        db.execute(
            "UPDATE tasks SET state='cancelled',updated_at=? WHERE task_id=?",
            (int(time.time() * 1000), task_id),
        )
        db.commit()
        return True
    return False


def get(task_id: str) -> dict | None:
    """Get task info."""
    db = _get_db()
    row = db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    if d.get("params"):
        try:
            d["params"] = json.loads(d["params"])
        except json.JSONDecodeError:
            pass
    if d["state"] == "done" and d.get("result_path"):
        try:
            d["result"] = json.loads(Path(d["result_path"]).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            pass
    return d


def list_tasks(limit: int = 20) -> list[dict]:
    """List recent tasks."""
    db = _get_db()
    rows = db.execute(
        "SELECT task_id,domain,action,state,created_at FROM tasks ORDER BY created_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]


# ── Tracked task API ────────────────────────────

def track_task(task_id: str, poll_domain: str, poll_action: str, poll_params: list = None) -> str:
    """
    Register a tracked task (owned by external service, polled on status query).
    Returns task_id.
    """
    _ensure_table()
    ts = int(time.time() * 1000)
    poll_info = json.dumps({
        "mode": "tracked",
        "poll": {
            "domain": poll_domain,
            "action": poll_action,
            "params": poll_params or [],
        }
    })
    db = _get_db()
    db.execute(
        "INSERT INTO tasks (task_id,domain,action,state,params,created_at,updated_at) "
        "VALUES (?,?,?,'pending',?,?,?)",
        (task_id, poll_domain, poll_action, poll_info, ts, ts),
    )
    db.commit()
    return task_id


# ── Internal ────────────────────────────────────

def _next_seq() -> int:
    """Get next sequence number from DB max rowid."""
    db = _get_db()
    row = db.execute("SELECT MAX(rowid) FROM tasks").fetchone()
    return (row[0] or 0) + 1


def _mark_stale():
    """On startup, mark stale running tasks as error."""
    db = _get_db()
    db.execute(
        "UPDATE tasks SET state='error',error='service restarted',updated_at=? WHERE state='running'",
        (int(time.time() * 1000),),
    )
    db.commit()


# ── Directive handlers ──────────────────────────

from core.registry import directive


@directive("task", "status", domain_alias="任务", action_aliases={"status": "状态"})
def task_status(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: task;status,<task_id>"})
    task = get(params[0])
    if task is None:
        return json.dumps({"status": "error", "reason": f"Task not found: {params[0]}"})

    # Tracked mode: real-time poll on status query
    task_params = task.get("params", {})
    if isinstance(task_params, dict) and task_params.get("mode") == "tracked":
        if _dispatch_fn is None:
            return json.dumps({"status": "ok", "task": task}, ensure_ascii=False)
        poll = task_params["poll"]
        result = _dispatch_fn(poll["domain"], poll["action"], poll["params"])
        if result is None:
            return json.dumps({"status": "ok", "task": task}, ensure_ascii=False)
        poll_status = result.get("status", "pending")
        if poll_status == "ok":
            update(params[0], "done")
            complete(params[0], result)
            task = get(params[0])
        elif poll_status in ("error", "failed"):
            update(params[0], "error", error=result.get("reason", "unknown"))
            task = get(params[0])

    return json.dumps({"status": "ok", "task": task}, ensure_ascii=False)


@directive("task", "result", domain_alias="任务", action_aliases={"result": "结果"})
def task_result(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: task;result,<task_id>"})
    task = get(params[0])
    if task is None:
        return json.dumps({"status": "error", "reason": f"Task not found: {params[0]}"})
    if task["state"] != "done":
        return json.dumps({"status": "error", "reason": f"Task not done (state={task['state']})"})
    return json.dumps({"status": "ok", "result": task.get("result", {})}, ensure_ascii=False)


@directive("task", "list", domain_alias="任务", action_aliases={"list": "列表"})
def task_list(params: list[str]) -> str:
    tasks = list_tasks()
    return json.dumps({"status": "ok", "tasks": tasks}, ensure_ascii=False)


@directive("task", "track", domain_alias="任务", action_aliases={"track": "追踪"})
def task_track(params: list[str]) -> str:
    """Register a tracked task. task;track,<task_id>,<domain>,<action>,<param1>[,<param2>...]"""
    if len(params) < 4:
        return json.dumps({
            "status": "error",
            "reason": "Usage: task;track,<task_id>,<domain>,<action>,<param1>[,<param2>...]"
        })
    task_id = params[0]
    domain = params[1]
    action = params[2]
    poll_params = params[3:]
    try:
        track_task(task_id, domain, action, poll_params)
        return json.dumps({"status": "ok", "task_id": task_id, "mode": "tracked"})
    except sqlite3.IntegrityError:
        return json.dumps({"status": "error", "reason": f"Task '{task_id}' already exists"})


@directive("task", "cancel", domain_alias="任务", action_aliases={"cancel": "取消"})
def task_cancel(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: task;cancel,<task_id>"})
    ok = cancel(params[0])
    return json.dumps({"status": "ok" if ok else "error", "cancelled": ok})


def init_task_manager(sqlite_db_cfg):
    """Initialize task manager with SQLite DB config."""
    global _db_file
    _db_file = sqlite_db_cfg.get("config") if isinstance(sqlite_db_cfg, dict) else str(sqlite_db_cfg)
    _ensure_table()
    _mark_stale()


# Aliases for internal callers (e.g. bim-ifc handler)
task_manager_register = register
task_manager_track = track_task
task_manager_update = update
task_manager_complete = complete
task_manager_fail = fail

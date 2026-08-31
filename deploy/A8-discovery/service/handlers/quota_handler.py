"""
quota-manage handler — A6 SQL instruction package.

Function-level API quota tracker with atomic cycle-reset + consume.
SQLite-backed, zero external dependencies beyond stdlib sqlite3.

Directives:
    quota;check,<target>                  → atomic check+consume
    quota;register,<target>,<cycle>,<limit> → register rule
    quota;list                            → list all
    quota;reset,<target>                  → manual reset
    quota;unregister,<target>             → remove rule

Cycles: day(日) / week(周) / month(月) / year(年) / forever(永久)

Author: Tide 🌊 — 2026-05-15
"""

import json
import logging
import sqlite3

logger = logging.getLogger(__name__)

from core.registry import directive

DB_FILE: str = ""


def init_quota_handler(db_file: str):
    """Initialise with SQLite database file path."""
    global DB_FILE
    DB_FILE = db_file
    _ensure_table()
    logger.info("quota-manage initialised: %s", db_file)


# ── Table management ────────────────────────────

def _ensure_table():
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quota (
            func_name    TEXT PRIMARY KEY,
            cycle_type   TEXT NOT NULL CHECK(cycle_type IN ('day','week','month','year','forever')),
            cycle_limit  INTEGER NOT NULL,
            usage_count  INTEGER DEFAULT 0,
            usage_date   TEXT NOT NULL DEFAULT (date('now')),
            created_at   TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()


def _get_conn():
    return sqlite3.connect(DB_FILE)


# ── Internal: atomic check + consume ────────────

def check_and_update(target: str, amount: int = 1) -> dict:
    """
    Atomic quota check + consume for a single target.
    Cycle reset detection and counter increment in one SQL statement.

    amount: units to consume (default 1 for call-count; e.g. len(text) for char-based quotas)

    Returns:
        {"status": "ok", "remaining": 2, "used": 3, "cycle": "day", "limit": 5}
        {"status": "stop", "reset_at": "2026-05-16", "limit": 5, "cycle": "day"}
        {"status": "not_found", "target": "unknown_func"}
    """
    if not DB_FILE:
        return {"status": "error", "reason": "quota-manage not initialised"}

    conn = _get_conn()

    # Check if target exists
    cur = conn.execute(
        "SELECT cycle_type, cycle_limit, usage_count, usage_date FROM quota WHERE func_name = ?",
        (target,)
    )
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"status": "not_found", "target": target}

    cycle_type, cycle_limit, usage_count, usage_date = row

    # ── Cycle flip detection ──
    # Build the reset condition in SQL
    now_date = _sqlite_date(conn)
    flipped = False
    new_count = usage_count + amount

    if cycle_type == "day":
        if usage_date != now_date:
            flipped = True
            new_count = amount
    elif cycle_type == "week":
        # ISO week: if usage_date is before current Monday
        cur2 = conn.execute(
            "SELECT date(?, 'weekday 0', '-7 days')",
            (now_date,)
        )
        week_start = cur2.fetchone()[0]
        if usage_date < week_start:
            flipped = True
            new_count = amount
    elif cycle_type == "month":
        if usage_date[:7] != now_date[:7]:
            flipped = True
            new_count = amount
    elif cycle_type == "year" and usage_date[:4] != now_date[:4]:
            flipped = True
            new_count = amount
    # forever: never flips, new_count stays usage_count + amount

    # ── Check limit ──
    if new_count > cycle_limit:
        conn.close()
        reset_at = _next_reset(cycle_type, now_date)
        return {
            "status": "stop",
            "limit": cycle_limit,
            "cycle": cycle_type,
            "reset_at": reset_at,
            "used": usage_count,
        }

    # ── Atomic update ──
    update_date = now_date if (flipped or cycle_type != "forever") else usage_date
    conn.execute(
        """UPDATE quota
           SET usage_count = ?,
               usage_date = ?
           WHERE func_name = ? AND usage_count = ?""",
        (new_count, update_date, target, usage_count)  # optimistic lock
    )
    if conn.execute("SELECT changes()").fetchone()[0] == 0:
        # Race condition: another process modified the row, retry or fail
        conn.rollback()
        conn.close()
        return {"status": "error", "reason": "concurrent update conflict, retry"}

    conn.commit()
    conn.close()

    return {
        "status": "ok",
        "remaining": cycle_limit - new_count,
        "used": new_count,
        "cycle": cycle_type,
        "limit": cycle_limit,
        "reset": flipped,
    }


def _sqlite_date(conn) -> str:
    return conn.execute("SELECT date('now')").fetchone()[0]


def _next_reset(cycle_type: str, today: str) -> str:
    """Calculate next reset date for display."""
    conn = _get_conn()
    try:
        if cycle_type == "day":
            row = conn.execute("SELECT date('now', '+1 day')").fetchone()
        elif cycle_type == "week":
            row = conn.execute("SELECT date('now', 'weekday 0', '+7 days')").fetchone()
        elif cycle_type == "month":
            row = conn.execute("SELECT date('now', 'start of month', '+1 month')").fetchone()
        elif cycle_type == "year":
            row = conn.execute("SELECT date('now', 'start of year', '+1 year')").fetchone()
        else:
            return "never"
        return row[0] if row else "unknown"
    finally:
        conn.close()


# ── Directives ──────────────────────────────────

@directive("quota", "check", domain_alias="配额", action_aliases={"check": "检查"})
def quota_check(params: list[str]) -> dict:
    """Atomic check + consume quota units. quota;check,<target>[,<amount>]"""
    if not params:
        return ({"status": "error", "reason": "Missing target"})
    target = params[0]
    amount = int(params[1]) if len(params) > 1 else 1
    if amount < 1:
        return ({"status": "error", "reason": "Amount must be >= 1"})
    result = check_and_update(target, amount)
    return (result)


@directive("quota", "register", domain_alias="配额", action_aliases={"register": "注册"})
def quota_register(params: list[str]) -> dict:
    """Register a new quota rule."""
    if len(params) < 3:
        return ({
            "status": "error",
            "reason": "Usage: quota;register,<target>,<cycle>,<limit>"
        })

    target, cycle, limit_str = params[0], params[1], params[2]

    # Validate cycle
    _valid_cycles = {"day", "日", "week", "周", "month", "月", "year", "年", "forever", "永久"}
    cn_to_en = {"日": "day", "周": "week", "月": "month", "年": "year", "永久": "forever"}
    cycle = cn_to_en.get(cycle, cycle)
    if cycle not in {"day", "week", "month", "year", "forever"}:
        return ({
            "status": "error",
            "reason": f"Invalid cycle: {cycle}. Use day/week/month/year/forever"
        })

    # Validate limit
    try:
        limit = int(limit_str)
        if limit < 1:
            raise ValueError
    except (ValueError, TypeError):
        return ({
            "status": "error",
            "reason": f"Invalid limit: {limit_str}. Must be a positive integer"
        })

    if not DB_FILE:
        return ({"status": "error", "reason": "quota-manage not initialised"})

    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO quota (func_name, cycle_type, cycle_limit) VALUES (?, ?, ?)",
            (target, cycle, limit)
        )
        conn.commit()
        return ({
            "status": "ok", "target": target, "cycle": cycle, "limit": limit
        })
    except sqlite3.IntegrityError:
        return ({
            "status": "error",
            "reason": f"Target '{target}' already exists. Use quota;unregister first."
        })
    finally:
        conn.close()


@directive("quota", "list", domain_alias="配额", action_aliases={"list": "列表"})
def quota_list(params: list[str]) -> dict:
    """List all quota rules with current usage."""
    if not DB_FILE:
        return ({"status": "error", "reason": "quota-manage not initialised"})

    conn = _get_conn()
    try:
        today = _sqlite_date(conn)
        cur = conn.execute(
            "SELECT func_name, cycle_type, cycle_limit, usage_count, usage_date, created_at FROM quota ORDER BY func_name"
        )
        rows = cur.fetchall()
        items = []
        for row in rows:
            func_name, cycle_type, cycle_limit, usage_count, usage_date, created_at = row

            # Calculate effective usage after considering cycle flip
            effective_count = usage_count
            if cycle_type == "day" and usage_date != today:
                effective_count = 0
            elif cycle_type == "week":
                week_start = conn.execute("SELECT date(?, 'weekday 0', '-7 days')", (today,)).fetchone()[0]
                if usage_date < week_start:
                    effective_count = 0
            elif cycle_type == "month" and usage_date[:7] != today[:7] or cycle_type == "year" and usage_date[:4] != today[:4]:
                effective_count = 0

            items.append({
                "target": func_name,
                "cycle": cycle_type,
                "limit": cycle_limit,
                "used": effective_count,
                "remaining": cycle_limit - effective_count,
                "last_used": usage_date if usage_count > 0 else None,
                "registered_at": created_at,
            })

        return ({"status": "ok", "count": len(items), "quotas": items})
    finally:
        conn.close()


@directive("quota", "reset", domain_alias="配额", action_aliases={"reset": "重置"})
def quota_reset(params: list[str]) -> dict:
    """Manually reset a quota counter."""
    if not params:
        return ({"status": "error", "reason": "Missing target"})
    if not DB_FILE:
        return ({"status": "error", "reason": "quota-manage not initialised"})

    target = params[0]
    conn = _get_conn()
    try:
        cur = conn.execute(
            "UPDATE quota SET usage_count = 0, usage_date = date('now') WHERE func_name = ?",
            (target,)
        )
        if cur.rowcount == 0:
            return ({"status": "not_found", "target": target})
        conn.commit()
        return ({"status": "ok", "target": target, "reset_at": _sqlite_date(conn)})
    finally:
        conn.close()


@directive("quota", "unregister", domain_alias="配额", action_aliases={"unregister": "注销"})
def quota_unregister(params: list[str]) -> dict:
    """Remove a quota rule."""
    if not params:
        return ({"status": "error", "reason": "Missing target"})
    if not DB_FILE:
        return ({"status": "error", "reason": "quota-manage not initialised"})

    target = params[0]
    conn = _get_conn()
    try:
        cur = conn.execute("DELETE FROM quota WHERE func_name = ?", (target,))
        if cur.rowcount == 0:
            return ({"status": "not_found", "target": target})
        conn.commit()
        return ({"status": "ok", "target": target})
    finally:
        conn.close()

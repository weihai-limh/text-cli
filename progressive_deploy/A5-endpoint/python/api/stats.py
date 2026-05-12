from datetime import datetime
from fastapi import APIRouter, Query
from core.database import query_db

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/summary")
async def stats_summary():
    total = query_db("SELECT COUNT(*) as cnt FROM call_logs")
    success = query_db("SELECT COUNT(*) as cnt FROM call_logs WHERE status_code = 200")
    tokens = query_db("SELECT COUNT(*) as cnt FROM access_tokens WHERE is_active = 1")
    days = query_db("SELECT COUNT(DISTINCT date) as cnt FROM daily_stats")

    return {
        "total_calls": total[0]["cnt"] if total else 0,
        "total_success": success[0]["cnt"] if success else 0,
        "active_tokens": tokens[0]["cnt"] if tokens else 0,
        "tracked_days": days[0]["cnt"] if days else 0,
    }


@router.get("/daily")
async def stats_daily(date: str = Query(default=None)):
    if not date:
        date = datetime.utcnow().strftime("%Y-%m-%d")

    rows = query_db(
        "SELECT domain, action, call_count, success_count, avg_response_ms "
        "FROM daily_stats WHERE date = ? ORDER BY call_count DESC",
        (date,),
    )

    return {"date": date, "directives": rows}


@router.get("/token/{prefix}")
async def stats_token(prefix: str):
    rows = query_db(
        "SELECT client_name, used_count, quota, is_active, created_at "
        "FROM access_tokens WHERE token_prefix = ?",
        (prefix,),
    )

    if not rows:
        return {"error": "token not found", "prefix": prefix}

    token_info = rows[0]
    calls = query_db(
        "SELECT directive, status_code, response_time_ms, created_at "
        "FROM call_logs WHERE access_token_prefix = ? ORDER BY created_at DESC LIMIT 50",
        (prefix,),
    )

    return {"token": token_info, "recent_calls": calls}

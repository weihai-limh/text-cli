from fastapi import APIRouter
from core.database import query_db
from core.schema_loader import get_internal_schema

router = APIRouter(tags=["health"])


@router.get("/api/health")
async def health_check():
    db_ok = False
    try:
        query_db("SELECT 1")
        db_ok = True
    except Exception:
        pass

    schema_ok = len(get_internal_schema()) > 0

    backends = []
    seen = set()
    for entry in get_internal_schema().values():
        url = entry.get("url", "")
        if url and url not in seen:
            seen.add(url)
            backends.append({"url": url, "directive_count": 0})
        for b in backends:
            if b["url"] == url:
                b["directive_count"] += 1

    return {
        "liveness": True,
        "readiness": {
            "database": db_ok,
            "schema": schema_ok,
            "backends": backends,
        },
    }

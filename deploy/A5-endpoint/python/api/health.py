from core.database import query_db
from core.schema_loader import get_backend_base_url, get_external_schema
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/text-cli/health")
@router.get("/api/health")
async def health_check():
    db_ok = False
    try:
        query_db("SELECT 1")
        db_ok = True
    except Exception:
        pass

    schema = get_external_schema()
    schema_ok = len(schema) > 0

    backends = []
    seen = set()
    for entry in schema.values():
        url = entry.get("url", "")
        if url and url not in seen:
            seen.add(url)
            backends.append({"url": url, "directive_count": 0})
    for b in backends:
        for entry in schema.values():
            if entry.get("url") == b["url"]:
                b["directive_count"] += 1

    backend_base = get_backend_base_url()

    return {
        "liveness": True,
        "readiness": {
            "database": db_ok,
            "schema": schema_ok,
            "backends": backends,
            "aggregation": {
                "enabled": backend_base is not None,
                "primary_backend": backend_base,
            },
        },
    }

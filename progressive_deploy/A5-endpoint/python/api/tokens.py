import hashlib
import os
import secrets
from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel
from core.database import query_db, execute_db, execute_db_returning

router = APIRouter(prefix="/api/tokens", tags=["tokens"])

ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")


def verify_admin(admin_key: str | None):
    if not ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin API not configured")
    if not admin_key or admin_key != ADMIN_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid admin key")


class TokenCreateRequest(BaseModel):
    client_name: str = ""
    quota: int = -1
    max_requests_per_minute: int = 60


class TokenUpdateRequest(BaseModel):
    client_name: str | None = None
    quota: int | None = None
    max_requests_per_minute: int | None = None
    is_active: bool | None = None


@router.get("")
async def list_tokens(x_admin_key: str = Header(default=None)):
    verify_admin(x_admin_key)
    rows = query_db(
        "SELECT id, token_prefix, client_name, quota, used_count, "
        "max_requests_per_minute, is_active, created_at FROM access_tokens "
        "ORDER BY created_at DESC"
    )
    return {"tokens": rows}


@router.post("")
async def create_token(req: TokenCreateRequest, x_admin_key: str = Header(default=None)):
    verify_admin(x_admin_key)
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    token_prefix = raw_token[:8]

    row_id = execute_db_returning(
        "INSERT INTO access_tokens (token_hash, token_prefix, client_name, quota, max_requests_per_minute) "
        "VALUES (?, ?, ?, ?, ?)",
        (token_hash, token_prefix, req.client_name, req.quota, req.max_requests_per_minute),
    )

    return {
        "id": row_id,
        "token": raw_token,
        "token_prefix": token_prefix,
        "client_name": req.client_name,
        "quota": req.quota,
    }


@router.put("/{token_id}")
async def update_token(token_id: int, req: TokenUpdateRequest, x_admin_key: str = Header(default=None)):
    verify_admin(x_admin_key)
    existing = query_db("SELECT id FROM access_tokens WHERE id = ?", (token_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Token not found")

    fields = []
    params = []
    if req.client_name is not None:
        fields.append("client_name = ?")
        params.append(req.client_name)
    if req.quota is not None:
        fields.append("quota = ?")
        params.append(req.quota)
    if req.max_requests_per_minute is not None:
        fields.append("max_requests_per_minute = ?")
        params.append(req.max_requests_per_minute)
    if req.is_active is not None:
        fields.append("is_active = ?")
        params.append(1 if req.is_active else 0)

    if not fields:
        return {"message": "no fields to update"}

    params.append(token_id)
    execute_db(f"UPDATE access_tokens SET {', '.join(fields)} WHERE id = ?", tuple(params))
    return {"message": "updated", "id": token_id}


@router.delete("/{token_id}")
async def delete_token(token_id: int, x_admin_key: str = Header(default=None)):
    verify_admin(x_admin_key)
    existing = query_db("SELECT id FROM access_tokens WHERE id = ?", (token_id,))
    if not existing:
        raise HTTPException(status_code=404, detail="Token not found")

    execute_db("DELETE FROM access_tokens WHERE id = ?", (token_id,))
    return {"message": "deleted", "id": token_id}

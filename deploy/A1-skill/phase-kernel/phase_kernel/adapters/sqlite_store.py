"""SqliteStore（设计稿 §3.3 / §12.4③）

相位服务自有本地持久化层（承载 PipelineSession / phase_summaries / checkpoint_index）。
非 tc 运行时存储（两条线互不侵入，§12.2）。
零外部依赖：仅用标准库 sqlite3 + json。
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from ..core.models import PipelineSession


class SqliteStore:
    """ports.Store 的 SQLite 实现（独立部署形态）"""

    def __init__(self, db_path: str = "phase.db"):
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _init(self) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS pipelines (
                       pipeline_id TEXT PRIMARY KEY,
                       session_id TEXT,
                       payload TEXT,
                       updated_at TEXT
                   )"""
            )
            conn.commit()
        finally:
            conn.close()

    async def save(self, session: PipelineSession) -> None:
        conn = sqlite3.connect(self._db_path)
        try:
            conn.execute(
                "INSERT OR REPLACE INTO pipelines (pipeline_id, session_id, payload, updated_at) "
                "VALUES (?, ?, ?, ?)",
                (session.pipeline_id, session.session_id,
                 json.dumps(session.to_dict(), ensure_ascii=False), session.updated_at.isoformat()),
            )
            conn.commit()
        finally:
            conn.close()

    async def load(self, pipeline_id: str) -> Optional[PipelineSession]:
        conn = sqlite3.connect(self._db_path)
        try:
            row = conn.execute(
                "SELECT payload FROM pipelines WHERE pipeline_id = ?", (pipeline_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            return None
        return PipelineSession.from_dict(json.loads(row[0]))

    async def restore(self, pipeline_id: str, session_id: Optional[str] = None) -> Optional[PipelineSession]:
        # 相位服务的会话恢复即按 pipeline_id 的 load（跨轮询/跨请求恢复快照）
        return await self.load(pipeline_id)

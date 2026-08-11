"""
Mesh credential injector — per-peer credential injection for federation mesh.

Provides MeshCredentialInjector: an A6-layer component that injects credentials
into proxy request bodies. A3 proxy.py calls injector.inject(body, peer) — the
injector handles per-peer credentials, legacy all_keys fallback, and
degradation/rejection logic based on mesh.require_credentials config.

This module is owned by A6 (SQLite layer). A3 proxy.py does NOT import it
directly — instead, A6 handler_inits instantiates the injector and passes it
into proxy via credential_injector parameter.
"""

from __future__ import annotations

import logging
import sqlite3
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level singleton — populated by init_mesh_credential_injector()
# Uses Optional['MeshCredentialInjector'] (forward ref via __future__.annotations)
CREDENTIAL_INJECTOR: Optional['MeshCredentialInjector'] = None
"""MeshCredentialInjector instance, or None if A6 SQLite not available (A3-only deployment)."""


class MeshCredentialError(Exception):
    """Raised when mesh credentials are required but unavailable."""


def init_mesh_credential_injector(db_path: str):
    """Handler init entrypoint — called via HANDLER_INITS after SQLite is ready.

    Reads mesh.require_credentials from config, instantiates the injector,
    and stores it in the module-level CREDENTIAL_INJECTOR singleton.
    """
    global CREDENTIAL_INJECTOR
    require_creds = False
    try:
        from core.config import load_config
        mesh_config = load_config().get("mesh", {})
        require_creds = mesh_config.get("require_credentials", False)
    except Exception as e:
        logger.debug("Failed to read mesh config, using default require_credentials=False: %s", e)

    CREDENTIAL_INJECTOR = MeshCredentialInjector(db_path, require_credentials=require_creds)
    logger.info(
        "MeshCredentialInjector initialized (db=%s, require_credentials=%s)",
        db_path, require_creds,
    )


class MeshCredentialInjector:
    """Inject per-peer credentials (or all_keys legacy fallback) into proxy bodies.

    Usage:
        injector = MeshCredentialInjector(db_path, require_credentials=False)
        body = injector.inject(body, peer)  # raises MeshCredentialError on reject
    """

    def __init__(self, db_path: str, require_credentials: bool = False):
        self._db_path = db_path
        self._require_credentials = require_credentials
        self._local = threading.local()

    # ── Thread-local SQLite connection ──

    def _get_db(self) -> sqlite3.Connection | None:
        if not self._db_path:
            return None
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    # ── Query helpers ──

    def _get_peer_credentials(self, peer: str) -> dict | None:
        db = self._get_db()
        if db is None:
            return None
        row = db.execute(
            "SELECT * FROM peer_credentials WHERE peer=?", (peer,)
        ).fetchone()
        if row:
            return dict(row)
        return None

    def _get_all_keys(self) -> dict:
        """Legacy fallback: return all keys when no peer is specified."""
        try:
            from text_cli_modules.key.key_registry import get_all_keys
            return get_all_keys(self._db_path)
        except ImportError:
            return {}

    # ── Main injection method ──

    def inject(self, body: dict, peer: str | None) -> dict:
        """Inject credentials into the request body.

        Two paths:
          (A) peer is not None → per-peer credentials from peer_credentials table
          (B) peer is None     → legacy all_keys fallback

        Raises:
            MeshCredentialError: when require_credentials=True and no
                                 credentials are available for the given peer.
        """
        if peer is not None:
            # ── Path A: per-peer credential injection ──
            creds = self._get_peer_credentials(peer)
            if creds:
                body["_injected_credentials"] = {peer: creds}
                logger.info("mesh injector: credentials for peer '%s'", peer)
                return body

            # No credentials found for this peer
            if self._require_credentials:
                raise MeshCredentialError(
                    f"mesh credentials required but unavailable for peer '{peer}'"
                )
            # Degraded: forward without credentials, mark for caller awareness
            body["_mesh_credential_degraded"] = True
            logger.warning(
                "mesh injector: no credentials for peer '%s' (degraded forwarding)", peer
            )
            return body

        else:
            # ── Path B: legacy all_keys fallback ──
            all_keys = self._get_all_keys()
            if all_keys:
                body["_injected_credentials"] = all_keys
                logger.info("mesh injector: injected %d legacy keys", len(all_keys))
            return body

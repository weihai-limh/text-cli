"""ArtifactStore 内存实现（设计稿 块1 数据面 / 执行相位服务 §2.5）

纯内存后端，满足"代码层功能闭环"（mock，不接真实远端拉取）。职责：
- `store`: 存产物 → 生成 pk 自有 URL（`pk://artifacts/{ref}`）。
- `fetch`: 按 ref 取产物。
- `transfer`: 透传/拉取转存分流——数据形态判 http/https URL 且透传开关开 → 透传
  （不落盘，返回远端 URL）；否则 → 拉取转存（落盘生成 pk 自有 URL）。
  转存失败降级直用远端 URL 并标 `_transfer_degraded`。

数据驻留（P4.6）：滚动窗口（`max_artifacts`）+ 终态清理（`finalize_pipeline`）+ 最终产出物表。
"""

from __future__ import annotations

import re
import time
from typing import Any, Optional
from urllib.parse import urlparse


# http/https URL 判定
_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


class InMemoryArtifactStore:
    """内存版 ArtifactStore（进程内闭环，不接真实远端）。

    分流语义（对齐执行相位服务 §2.5）：
    - `payload` 是 http/https URL 且 `allow_passthrough=True` → 透传（返回远端 URL，不落盘）。
    - 否则 → 拉取转存（存进本地 artifacts，生成 pk:// 自有 URL）。
    - 远端拉取失败（`fetch_external` 异常）→ 降级直用远端 URL + `_transfer_degraded` 标记。
    """

    def __init__(self, allow_passthrough: bool = False, max_artifacts: int = 200):
        self.allow_passthrough = allow_passthrough
        self.max_artifacts = max_artifacts
        self._artifacts: dict[str, dict] = {}
        self._pipeline_artifacts: dict[str, list[str]] = {}
        self._finalized: dict[str, list[dict]] = {}  # 最终产出物表（终态清理后保留）

    # ── 数据形态判定 ──

    @staticmethod
    def _is_http_url(payload: Any) -> bool:
        if not isinstance(payload, str):
            return False
        return bool(_URL_RE.match(payload.strip()))

    def _make_pk_url(self, ref: str) -> str:
        return f"pk://artifacts/{ref}"

    # ── 存储 ──

    async def store(self, pipeline_id: str, ref: str, data: Any,
                    media_type: str = "text") -> str:
        self._artifacts[ref] = {
            "pipeline_id": pipeline_id,
            "ref": ref,
            "data": data,
            "media_type": media_type,
            "at": time.time(),
        }
        self._pipeline_artifacts.setdefault(pipeline_id, []).append(ref)
        self._trim(pipeline_id)
        return self._make_pk_url(ref)

    async def fetch(self, ref: str) -> Optional[dict]:
        art = self._artifacts.get(ref)
        return art

    async def fetch_external(self, url: str) -> Optional[str]:
        """拉取远端内容（真实实现走 http；mock 用 url 原文代替，仅用于演示降级路径）。"""
        return url

    async def transfer(self, pipeline_id: str, payload: Any,
                       media_type: str = "text") -> dict:
        """透传/拉取转存分流。

        返回：`{url, passthrough: bool, degraded: bool}`。
        """
        # 1) 透传：已是 http/https URL 且透传开关开 → 不落盘直转远端
        if self._is_http_url(payload) and self.allow_passthrough:
            return {"url": payload.strip(), "passthrough": True, "degraded": False}

        # 2) 拉取转存：非 URL 内容，或透传开关关（保守落盘）
        #    - 是 URL 但透传关 → 尝试拉取转存；拉取失败 → 降级直用远端 URL
        if self._is_http_url(payload):
            try:
                content = await self.fetch_external(payload.strip())
                ref = self._new_ref(pipeline_id)
                url = await self.store(pipeline_id, ref, content, media_type)
                return {"url": url, "passthrough": False, "degraded": False}
            except Exception:
                # 降级：直用远端 URL + 标记
                return {"url": payload.strip(), "passthrough": True,
                        "degraded": True, "_transfer_degraded": True}
        # 3) 纯内容 → 直接转存
        ref = self._new_ref(pipeline_id)
        url = await self.store(pipeline_id, ref, payload, media_type)
        return {"url": url, "passthrough": False, "degraded": False}

    def _new_ref(self, pipeline_id: str) -> str:
        return f"{pipeline_id}_{int(time.time() * 1000)}"

    # ── 数据驻留（P4.6）──

    def _trim(self, pipeline_id: str) -> None:
        """滚动窗口：每个 pipeline 的产物超过 max_artifacts 时淘汰最旧。"""
        refs = self._pipeline_artifacts.get(pipeline_id, [])
        while len(refs) > self.max_artifacts:
            old = refs.pop(0)
            self._artifacts.pop(old, None)

    def finalize_pipeline(self, pipeline_id: str) -> list[dict]:
        """终态清理 + 最终产出物表：整树收束时调用，保留最终产出、清理中间产物。"""
        refs = self._pipeline_artifacts.pop(pipeline_id, [])
        final = []
        for ref in refs:
            art = self._artifacts.pop(ref, None)
            if art is not None:
                final.append(art)
        self._finalized[pipeline_id] = final
        return final

    def finalized(self, pipeline_id: str) -> list[dict]:
        return self._finalized.get(pipeline_id, [])

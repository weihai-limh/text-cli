"""
@cache:// 引用存储通道（运行时能力，非协议标准）。

定位：**包可借用的通道**（非元指令）——包在 handler 内部读写大载荷引用，
不暴露给 AI 的指令表面。AI 只看到指令响应里的 `@cache://<domain>/<key>` 引用。

用法：
    from text_cli_modules.cache import put, get, clean

    ref = put("mock-1700000000000", full_result, domain="model-mock")
    # → "@cache://model-mock/mock-1700000000000"
    data = get(ref)              # 按引用取回
    data = get("mock-...", domain="model-mock")   # 或纯 key + domain

存储：<TEXT_CLI_DATA_DIR>/cache/<domain>/<key>.json（data）+ <key>.meta.json（TTL 元数据）
生命周期：TTL（默认 24h）+ 总量上限 LRU（clean）；key 仅 [\\w.-]（防路径穿越）。

语义边界：引用存储（传递大载荷）≠ 产物缓存（tc-pandoc 确定性复用），不混同。
"""

import json
import os
import re
import time
from pathlib import Path

__all__ = ["put", "get", "clean"]

_SAFE_KEY_RE = re.compile(r"^[\w.-]+$")
DEFAULT_TTL = 24 * 3600        # 24h
DEFAULT_MAX_ENTRIES = 1000     # 总量上限


def _safe(key: str) -> str:
    """key/domain 防注入：仅允许 [\\w.-]，拒绝路径穿越。"""
    if not key or not _SAFE_KEY_RE.match(key):
        raise ValueError(f"invalid cache key: {key!r}")
    return key


def _cache_root() -> Path:
    base = os.environ.get(
        "TEXT_CLI_DATA_DIR",
        os.path.join(os.environ.get("TEXT_CLI_HOME", str(Path.home() / "text-cli")), "data"),
    )
    return Path(base) / "cache"


def _paths(domain: str, key: str) -> tuple[Path, Path]:
    domain = _safe(domain)
    key = _safe(key)
    d = _cache_root() / domain
    d.mkdir(parents=True, exist_ok=True)
    return d / f"{key}.json", d / f"{key}.meta.json"


def put(key: str, data: dict, domain: str = "default", ttl: float = DEFAULT_TTL) -> str:
    """写入引用缓存，返回 @cache://<domain>/<key> 引用串。"""
    data_path, meta_path = _paths(domain, key)
    data_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    meta_path.write_text(json.dumps({"expires_at": time.time() + ttl}), encoding="utf-8")
    return f"@cache://{_safe(domain)}/{_safe(key)}"


def get(ref_or_key: str, domain: str | None = None) -> dict | None:
    """按引用（@cache://<domain>/<key>）或纯 key 取回缓存数据；过期/缺失返回 None。"""
    key = None
    if isinstance(ref_or_key, str) and ref_or_key.startswith("@cache://"):
        parts = ref_or_key[len("@cache://"):].split("/", 1)
        if len(parts) == 2:
            domain, key = parts
    elif isinstance(ref_or_key, str):
        key = ref_or_key
        domain = domain or "default"
    if not key or not domain:
        return None
    try:
        data_path, meta_path = _paths(domain, key)
    except ValueError:
        return None
    if not data_path.is_file() or not meta_path.is_file():
        return None
    try:
        m = json.loads(meta_path.read_text(encoding="utf-8"))
        if m.get("expires_at", 0) <= time.time():
            for p in (data_path, meta_path):
                try:
                    p.unlink()
                except OSError:
                    pass
            return None
        return json.loads(data_path.read_text(encoding="utf-8"))
    except Exception:
        return None


def clean(max_entries: int = DEFAULT_MAX_ENTRIES) -> int:
    """TTL 过期清理 + 总量上限 LRU（按 data 文件 mtime）。返回清理条目数。"""
    root = _cache_root()
    if not root.is_dir():
        return 0
    now = time.time()
    removed = 0

    # TTL 过期清理
    for meta_path in root.rglob("*.meta.json"):
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            expired = m.get("expires_at", 0) <= now
        except Exception:
            expired = True
        if expired:
            data_path = meta_path.with_name(meta_path.name[: -len(".meta.json")] + ".json")
            for p in (meta_path, data_path):
                try:
                    p.unlink()
                except OSError:
                    pass
            removed += 1

    # 总量上限 LRU
    all_data = [p for p in root.rglob("*.json") if not p.name.endswith(".meta.json")]
    if len(all_data) > max_entries:
        all_data.sort(key=lambda p: p.stat().st_mtime)
        for stale in all_data[: len(all_data) - max_entries]:
            meta_path = stale.with_name(stale.name + ".meta.json")
            for p in (stale, meta_path):
                try:
                    p.unlink()
                except OSError:
                    pass
            removed += 1

    return removed

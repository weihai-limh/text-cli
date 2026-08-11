"""aria2 handler — Download management via aria2 JSON-RPC API.

15 directives: download (6), status (6), system (3).
Service runs on NAS DSM proxy. Credentials from A6 key_registry (aria2).
"""

import json
import logging

import requests
import urllib3

from core.registry import directive

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)

ARIA2_URL = "https://10.168.1.110:5001/webman/3rdparty/Aria2/aria2rpc_proxy.cgi"
TIMEOUT = 30

_token: str | None = None

def init_aria2_handler(db_path: str):
    """Load aria2 RPC token from key_registry."""
    global _token
    try:
        from text_cli_modules.key.key_registry import get as key_get
        creds = key_get(db_path, "aria2")
        if creds:
            if isinstance(creds, str):
                _token = creds
            elif isinstance(creds, (list, tuple)):
                _token = creds[0][0] if isinstance(creds[0], (list, tuple)) else creds[0]
            logger.info("aria2 token loaded from key_registry")
        else:
            logger.warning("aria2: aria2 key not configured in key_registry")
    except ImportError:
        logger.warning("aria2: key_registry module not available")

def _rpc(method: str, params: list | None = None) -> dict:
    """Send JSON-RPC 2.0 request to aria2 via NAS DSM proxy."""
    if not _token:
        raise RuntimeError("aria2 RPC token not configured in key_registry")

    rpc_params = [f"token:{_token}"]
    if params:
        rpc_params.extend(params)

    payload = {
        "jsonrpc": "2.0",
        "id": "text-cli",
        "method": f"aria2.{method}",
        "params": rpc_params,
    }

    resp = requests.post(ARIA2_URL, json=payload, timeout=TIMEOUT, verify=False)
    resp.raise_for_status()
    body = resp.json()

    if "error" in body:
        err = body["error"]
        raise RuntimeError(f"aria2 RPC error {err['code']}: {err['message']}")
    return body.get("result", body)

def _parse_json(params: list[str], start: int) -> dict | None:
    if len(params) <= start:
        return None
    try:
        return json.loads(",".join(params[start:]))
    except (json.JSONDecodeError, ValueError):
        return None

def _error(reason: str) -> dict:
    return {"status": "error", "reason": reason}

def _ok(data: dict) -> dict:
    return {"status": "ok", **data}

@directive("aria2", "add-uri",
            domain_alias="aria2", action_aliases={"add-uri": "添加下载"})
def aria2_add_uri(params: list[str]) -> dict:
    """aria2;add-uri,<JSON>"""
    if not params:
        return _error("Usage: aria2;add-uri,<JSON>")
    body = _parse_json(params, 0)
    if body is None or "uris" not in body:
        return _error("JSON must contain {uris: [...]}")

    uris = body["uris"]
    rpc_params: list = [uris]
    if "options" in body:
        rpc_params.append(body["options"])
    if "position" in body:
        if len(rpc_params) == 1:
            rpc_params.append({})
        rpc_params.append(body["position"])

    try:
        result = _rpc("addUri", rpc_params)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"gid": result})

@directive("aria2", "add-torrent",
            domain_alias="aria2", action_aliases={"add-torrent": "添加种子"})
def aria2_add_torrent(params: list[str]) -> dict:
    """aria2;add-torrent,<JSON>"""
    if not params:
        return _error("Usage: aria2;add-torrent,<JSON>")
    body = _parse_json(params, 0)
    if body is None or "torrent_data" not in body:
        return _error("JSON must contain {torrent_data: ...}")

    torrent = body["torrent_data"]
    rpc_params: list = [torrent]
    if "options" in body:
        rpc_params.append(body["options"])
    if "position" in body:
        if len(rpc_params) == 1:
            rpc_params.append({})
        rpc_params.append(body["position"])

    try:
        result = _rpc("addTorrent", rpc_params)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"gid": result})

@directive("aria2", "remove",
            domain_alias="aria2", action_aliases={"remove": "移除下载"})
def aria2_remove(params: list[str]) -> dict:
    """aria2;remove,<gid>"""
    if not params:
        return _error("Usage: aria2;remove,<gid>")
    try:
        result = _rpc("remove", [params[0]])
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"gid": result})

@directive("aria2", "pause",
            domain_alias="aria2", action_aliases={"pause": "暂停下载"})
def aria2_pause(params: list[str]) -> dict:
    """aria2;pause,<gid>"""
    if not params:
        return _error("Usage: aria2;pause,<gid>")
    try:
        result = _rpc("pause", [params[0]])
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"gid": result})

@directive("aria2", "unpause",
            domain_alias="aria2", action_aliases={"unpause": "恢复下载"})
def aria2_unpause(params: list[str]) -> dict:
    """aria2;unpause,<gid>"""
    if not params:
        return _error("Usage: aria2;unpause,<gid>")
    try:
        result = _rpc("unpause", [params[0]])
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"gid": result})

@directive("aria2", "purge",
            domain_alias="aria2", action_aliases={"purge": "清理已完成"})
def aria2_purge(params: list[str]) -> dict:
    """aria2;purge"""
    try:
        _rpc("purgeDownloadResult")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"purged": True})

@directive("aria2", "status",
            domain_alias="aria2", action_aliases={"status": "下载状态"})
def aria2_status(params: list[str]) -> dict:
    """aria2;status,<gid>"""
    if not params:
        return _error("Usage: aria2;status,<gid>")
    try:
        result = _rpc("tellStatus", [params[0]])
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok(_reduce_download(result) if isinstance(result, dict) else {"raw": result})

@directive("aria2", "active",
            domain_alias="aria2", action_aliases={"active": "活动任务"})
def aria2_active(params: list[str]) -> dict:
    """aria2;active[,<keys>]"""
    keys_str = params[0] if params else None
    keys_list = [k.strip() for k in keys_str.split(",")] if keys_str else None

    try:
        if keys_list:
            result = _rpc("tellActive", [keys_list])
        else:
            result = _rpc("tellActive")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, list):
        downloads = [_reduce_download(d) for d in result]
        return _ok({"downloads": downloads, "count": len(downloads)})
    return _ok({"downloads": [], "count": 0})

@directive("aria2", "waiting",
            domain_alias="aria2", action_aliases={"waiting": "等待队列"})
def aria2_waiting(params: list[str]) -> dict:
    """aria2;waiting,<offset>,<num>"""
    if len(params) < 2:
        return _error("Usage: aria2;waiting,<offset>,<num>")
    try:
        offset = int(params[0])
        num = int(params[1])
        result = _rpc("tellWaiting", [offset, num])
    except ValueError:
        return _error("offset and num must be integers")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, list):
        downloads = [_reduce_download(d) for d in result]
        return _ok({"downloads": downloads, "count": len(downloads), "offset": offset})
    return _ok({"downloads": [], "count": 0, "offset": offset})

@directive("aria2", "stopped",
            domain_alias="aria2", action_aliases={"stopped": "已完成任务"})
def aria2_stopped(params: list[str]) -> dict:
    """aria2;stopped,<offset>,<num>"""
    if len(params) < 2:
        return _error("Usage: aria2;stopped,<offset>,<num>")
    try:
        offset = int(params[0])
        num = int(params[1])
        result = _rpc("tellStopped", [offset, num])
    except ValueError:
        return _error("offset and num must be integers")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, list):
        downloads = [_reduce_download(d) for d in result]
        return _ok({"downloads": downloads, "count": len(downloads), "offset": offset})
    return _ok({"downloads": [], "count": 0, "offset": offset})

@directive("aria2", "files",
            domain_alias="aria2", action_aliases={"files": "下载文件"})
def aria2_files(params: list[str]) -> dict:
    """aria2;files,<gid>"""
    if not params:
        return _error("Usage: aria2;files,<gid>")
    try:
        result = _rpc("getFiles", [params[0]])
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, list):
        files = [_reduce_file(f) for f in result]
        return _ok({"gid": params[0], "files": files, "count": len(files)})
    return _ok({"gid": params[0], "files": [], "count": 0})

@directive("aria2", "global-stat",
            domain_alias="aria2", action_aliases={"global-stat": "全局统计"})
def aria2_global_stat(params: list[str]) -> dict:
    """aria2;global-stat"""
    try:
        result = _rpc("getGlobalStat")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, dict):
        return _ok({
            "download_speed": result.get("downloadSpeed", "0"),
            "upload_speed": result.get("uploadSpeed", "0"),
            "num_active": result.get("numActive", "0"),
            "num_waiting": result.get("numWaiting", "0"),
            "num_stopped": result.get("numStopped", "0"),
            "num_stopped_total": result.get("numStoppedTotal", "0"),
        })
    return _ok({"raw": result})

@directive("aria2", "version",
            domain_alias="aria2", action_aliases={"version": "版本信息"})
def aria2_version(params: list[str]) -> dict:
    """aria2;version"""
    try:
        result = _rpc("getVersion")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, dict):
        return _ok({
            "version": result.get("version", ""),
            "enabled_features": result.get("enabledFeatures", []),
        })
    return _ok({"raw": result})

@directive("aria2", "session-info",
            domain_alias="aria2", action_aliases={"session-info": "会话信息"})
def aria2_session_info(params: list[str]) -> dict:
    """aria2;session-info"""
    try:
        result = _rpc("getSessionInfo")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    return _ok({"session_id": result.get("sessionId", "") if isinstance(result, dict) else result})

@directive("aria2", "global-option",
            domain_alias="aria2", action_aliases={"global-option": "全局配置"})
def aria2_global_option(params: list[str]) -> dict:
    """aria2;global-option"""
    try:
        result = _rpc("getGlobalOption")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"aria2 not reachable: {e}")

    if isinstance(result, dict):
        return _ok(_reduce_global_option(result))
    return _ok({"raw": result})

def _reduce_download(item: dict) -> dict:
    return {
        "gid": item.get("gid", ""),
        "status": item.get("status", ""),
        "total_length": item.get("totalLength", "0"),
        "completed_length": item.get("completedLength", "0"),
        "download_speed": item.get("downloadSpeed", "0"),
        "upload_speed": item.get("uploadSpeed", "0"),
        "files": [_reduce_file(f) for f in item.get("files", [])] if item.get("files") else [],
        "dir": item.get("dir", ""),
        "num_seeders": item.get("numSeeders", "0"),
        "connections": item.get("connections", "0"),
        "error_code": item.get("errorCode", "0"),
        "error_message": item.get("errorMessage", ""),
    }

def _reduce_file(item: dict) -> dict:
    return {
        "path": item.get("path", ""),
        "length": item.get("length", "0"),
        "completed_length": item.get("completedLength", "0"),
        "selected": item.get("selected", "true"),
        "uris": [{"uri": u.get("uri", ""), "status": u.get("status", "")}
                  for u in item.get("uris", [])],
    }

def _reduce_global_option(item: dict) -> dict:
    return {
        "download_dir": item.get("dir", ""),
        "max_concurrent_downloads": item.get("max-concurrent-downloads", ""),
        "max_connection_per_server": item.get("max-connection-per-server", ""),
        "max_overall_download_limit": item.get("max-overall-download-limit", ""),
        "max_overall_upload_limit": item.get("max-overall-upload-limit", ""),
        "seed_time": item.get("seed-time", ""),
    }

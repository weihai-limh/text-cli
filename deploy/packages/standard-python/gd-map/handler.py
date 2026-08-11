"""
gd-map handler — Gaode Maps HTTP API instruction package.

Wraps Gaode Maps WebService API with dual-key (key + secret) MD5 signature
auth via key_registry. Zero dependencies beyond stdlib. 4 directives.

Directives:
    gd-map;geocode,<address>                                          → coordinates
    gd-map;reverse-geocode,<lon>,<lat>[,<poi_type>,<radius>]          → address + POIs
    gd-map;static-map,<lon>,<lat>[,<zoom>,<size>,<markers>,<paths>]   → base64 PNG
    gd-map;search,<keyword>,<polygon>                                 → POI list

Key: dual-key via key;register,gd,<key>,<secret>,amap
Quota: tracked via quota-manage (key;quota-track,gd,gd-map;geocode,...)

Markers format: 'lon1 lat1|lon2 lat2|...' → converted to Gaode markers protocol
Paths format: 'lon1,lat1;lon2,lat2;...' → converted to Gaode paths protocol

Author: Tide 🌊 — 2026-05-15
"""

import base64
import hashlib
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

from core.registry import directive

DB_PATH: dict = {}
KEY_SERVICE = "gd"
GD_BASE = "https://restapi.amap.com"

def init_gd_handler(db_path: str):
    global DB_PATH
    DB_PATH = {"config": db_path}

def _get_credentials():
    try:
        from text_cli_modules.key.key_registry import get as key_get
    except ImportError:
        return None, None
    creds = key_get(DB_PATH, KEY_SERVICE)
    if not creds:
        return None, None
    if isinstance(creds, list) and len(creds) >= 2:
        return creds[0], creds[1]
    return None, None

def _generate_sn(params: dict, sk: str) -> str:
    """Gaode signature: MD5(sorted_params&...{sk}) — no path prefix."""
    sorted_items = sorted(params.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_items])
    raw_str = f"{query_string}{sk}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def _gd_get(url_path: str, params: dict) -> tuple[dict | None, str | None]:
    api_key, sk = _get_credentials()
    if not api_key:
        return None, "GD key not configured or quota exhausted. Register: key;register,gd,<key>,<secret>,amap"
    if not sk:
        return None, "GD secret key not configured (dual-key required)"

    params["key"] = api_key
    sig = _generate_sn(params, sk)
    params["sig"] = sig

    query_string = urllib.parse.urlencode(params)
    url = f"{GD_BASE}{url_path}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("status") == "0":
                return None, data.get("info", f"API error: status={data.get('status')}")
            return data, None
    except Exception as e:
        return None, str(e)

def _gd_get_bytes(url_path: str, params: dict) -> tuple[bytes | None, str | None]:
    api_key, sk = _get_credentials()
    if not api_key:
        return None, "GD key not configured"
    if not sk:
        return None, "GD secret key not configured"

    params["key"] = api_key
    sig = _generate_sn(params, sk)
    params["sig"] = sig

    query_string = urllib.parse.urlencode(params)
    url = f"{GD_BASE}{url_path}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(), None
    except Exception as e:
        return None, str(e)

@directive("gd-map", "geocode", domain_alias="高德地图", action_aliases={"geocode": "地理编码"})
def gd_geocode(params: list[str]) -> dict:
    if not params:
        return {"status": "error", "reason": "Missing address"}

    address = params[0]
    data, err = _gd_get("/v3/geocode/geo", {
        "address": address,
        "output": "json",
    })
    if err:
        return {"status": "error", "reason": err}

    geocodes = data.get("geocodes", [])
    if not geocodes:
        return {"status": "error", "reason": "No results"}

    location = geocodes[0].get("location", "")
    parts = location.split(",")
    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "lon": parts[0] if len(parts) > 0 else "",
        "lat": parts[1] if len(parts) > 1 else "",
        "address": address,
        "formatted": geocodes[0].get("formatted_address", ""),
        "level": geocodes[0].get("level", ""),
    }

@directive("gd-map", "reverse-geocode", domain_alias="高德地图", action_aliases={"reverse-geocode": "逆地理编码"})
def gd_reverse_geocode(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Missing lon,lat"}

    lon, lat = params[0], params[1]
    poi_type = params[2] if len(params) > 2 else ""
    radius = params[3] if len(params) > 3 else ""

    api_params = {"location": f"{lon},{lat}", "output": "json"}

    if poi_type:
        api_params["poitype"] = poi_type
        api_params["radius"] = radius or "1000"

    data, err = _gd_get("/v3/geocode/regeo", api_params)
    if err:
        return {"status": "error", "reason": err}

    regeo = data.get("regeocode", {})
    addr = regeo.get("formatted_address", {})

    result = {
        "status": "ok",
        "coord_sys": "gcj02",
        "address": addr.get("formatted_address", "") if isinstance(addr, dict) else str(addr),
    }

    if poi_type:
        pois = regeo.get("pois", [])
        result["pois"] = [
            {"name": p.get("name", ""), "type": p.get("type", ""),
             "address": p.get("address", ""), "location": p.get("location", "")}
            for p in pois[:10]
        ]

    return result

@directive("gd-map", "static-map", domain_alias="高德地图", action_aliases={"static-map": "静态图"})
def gd_static_map(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Missing lon,lat"}

    lon, lat = params[0], params[1]
    zoom = params[2] if len(params) > 2 else "14"
    size = params[3] if len(params) > 3 else "400"
    markers_str = params[4] if len(params) > 4 else ""
    paths_str = params[5] if len(params) > 5 else ""

    try:
        z = int(zoom)
        if z < 1 or z > 17: raise ValueError
    except ValueError:
        return {"status": "error", "reason": "Zoom must be 1-17"}
    try:
        s = int(size)
        if s < 200 or s > 800: raise ValueError
    except ValueError:
        return {"status": "error", "reason": "Size must be 200-800"}

    api_params = {
        "location": f"{lon},{lat}",
        "zoom": zoom,
        "size": f"{size}*{size}",
    }

    if markers_str:
        marker_pairs = [m.strip() for m in markers_str.split("|") if m.strip()]
        points = []
        for mp in marker_pairs:
            parts = mp.split()
            if len(parts) >= 2:
                points.append(f"{parts[0]},{parts[1]}")
        if points:
            api_params["markers"] = f"mid,0xFF0000,A:{';'.join(points)}"

    if paths_str:
        api_params["paths"] = f"5,0x0000ff,1,,:{paths_str}"

    png_bytes, err = _gd_get_bytes("/v3/staticmap", api_params)
    if err:
        return {"status": "error", "reason": err}

    b64 = base64.b64encode(png_bytes).decode('ascii')
    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "url": f"data:image/png;base64,{b64}",
        "center": [lon, lat],
        "zoom": int(zoom),
        "size": int(size),
        "marker_count": len(markers_str.split("|")) if markers_str else 0,
        "has_path": bool(paths_str),
    }

@directive("gd-map", "search", domain_alias="高德地图", action_aliases={"search": "搜索"})
def gd_search(params: list[str]) -> dict:
    if len(params) < 2:
        return {
            "status": "error",
            "reason": "Usage: gd-map;search,<keyword>,<polygon>"
        }

    keyword = params[0]
    polygon_raw = params[1]  # "lon1,lat1;lon2,lat2;..."

    polygon = polygon_raw.replace(";", "|")

    data, err = _gd_get("/v5/place/polygon", {
        "keywords": keyword,
        "polygon": polygon,
        "output": "json",
    })
    if err:
        return {"status": "error", "reason": err}

    pois = data.get("pois", [])
    results = []
    for item in pois[:10]:
        location = item.get("location", "")
        parts = location.split(",") if location else ["", ""]
        results.append({
            "name": item.get("name", ""),
            "lon": parts[0].strip(),
            "lat": parts[1].strip() if len(parts) > 1 else "",
            "address": item.get("address", ""),
            "type": item.get("type", ""),
        })

    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "keyword": keyword,
        "count": len(results),
        "pois": results,
    }

def init_gd_map_handler(db_path: str):
    global DB_PATH; DB_PATH = {'config': db_path}

"""
tx-map handler — Tencent Maps HTTP API instruction package.

Wraps Tencent Maps WebService API with dual-key (SecretId + SecretKey) auth
via key_registry. Signature generated inline (MD5, stdlib only). 5 directives.

Directives:
    tx-map;geocode,<address>                             → GCJ-02 coordinates
    tx-map;reverse-geocode,<lat>,<lng>                   → address name
    tx-map;route,<from_lat>,<from_lng>,<to_lat>,<to_lng>[,<format>] → polyline / roads
    tx-map;static-map,<lat>,<lng>[,<zoom>,<size>]        → base64 PNG data URI
    tx-map;ip,<ip>                                       → city + coordinates

Key: dual-cred via key;register,tx,<api_key>,<secret_key>,tencent_cloud
Quota: tracked via quota-manage (key;quota-track,tx,tx-map;geocode,...)

Author: Tide 🌊 — 2026-05-15
"""

import hashlib
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

from core.registry import directive

DB_PATH: dict = {}
KEY_SERVICE = "tx-map"
TENCENT_BASE = "https://apis.map.qq.com"

def init_tx_handler(db_path: str):
    global DB_PATH
    DB_PATH = {"config": db_path}

def _get_credentials():
    """Retrieve tx dual-key from key_registry. Returns (api_key, secret_key) or (None, None)."""
    try:
        from text_cli_modules.key.key_registry import get as key_get
    except ImportError:
        return None, "key_registry module not installed"
    creds = key_get(DB_PATH, KEY_SERVICE)
    if not creds:
        return None, "TX key not configured or quota exhausted. Register: key;register,tx,<api_key>,<secret_key>,tencent_cloud"
    if isinstance(creds, list) and len(creds) >= 2:
        return creds[0], creds[1]
    return creds, None  # single-key fallback

def _generate_sn(query_path: str, params: dict, sk: str) -> str:
    """Tencent Maps signature: MD5(path?sorted_params{SecretKey})."""
    sorted_items = sorted(params.items())
    query_string = '&'.join([f"{k}={v}" for k, v in sorted_items])
    raw_str = f"{query_path}?{query_string}{sk}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()

def _signed_get(url_path: str, params: dict) -> tuple[dict | None, str | None]:
    """Sign params with Tencent SK and call HTTP GET. Returns (parsed_json, error)."""
    api_key, sk = _get_credentials()
    if not api_key:
        return None, sk  # sk holds the error message from _get_credentials
    if not sk:
        return None, "TX secret key not configured (dual-key required)"

    params["key"] = api_key
    sig = _generate_sn(url_path, params, sk)
    params["sig"] = sig

    query_string = urllib.parse.urlencode(params)
    url = f"{TENCENT_BASE}{url_path}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("status") != 0:
                return None, data.get("message", f"API error: status={data.get('status')}")
            return data, None
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}: {e.reason}"
    except Exception as e:
        return None, str(e)

def _signed_get_bytes(url_path: str, params: dict) -> tuple[bytes | None, str | None]:
    """Same as _signed_get but returns raw bytes (for static map)."""
    api_key, sk = _get_credentials()
    if not api_key:
        return None, "TX key not configured"
    if not sk:
        return None, "TX secret key not configured"

    params["key"] = api_key
    sig = _generate_sn(url_path, params, sk)
    params["sig"] = sig

    query_string = urllib.parse.urlencode(params)
    url = f"{TENCENT_BASE}{url_path}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(), None
    except Exception as e:
        return None, str(e)

def _decompress_polyline(coors: list) -> list:
    """Decompress Tencent Maps polyline encoding."""
    result = coors.copy()
    for i in range(2, len(result)):
        result[i] = result[i - 2] + result[i] / 1000000
    return result

def _polyline_to_pairs(flat: list) -> list[list[float]]:
    """Convert flat [lng1, lat1, lng2, lat2, ...] to [[lat, lng], ...] pairs."""
    pairs = []
    for i in range(0, len(flat) - 1, 2):
        pairs.append([round(flat[i + 1], 6), round(flat[i], 6)])
    return pairs

def _pairs_to_string(pairs: list[list[float]]) -> str:
    """Convert coordinate pairs to semicolon-separated string."""
    return ";".join([f"{lat},{lng}" for lat, lng in pairs])

@directive("tx-map", "geocode", domain_alias="腾讯地图", action_aliases={"geocode": "地理编码"})
def tx_geocode(params: list[str]) -> dict:
    """Convert address → GCJ-02 coordinates."""
    if not params:
        return {"status": "error", "reason": "Missing address"}

    address = params[0]
    data, err = _signed_get("/ws/geocoder/v1/", {
        "address": address,
        "output": "json",
    })
    if err:
        return {"status": "error", "reason": err}

    location = data.get("result", {}).get("location", {})
    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "lat": location.get("lat"),
        "lng": location.get("lng"),
        "type": "gcj02",
        "address": address,
    }

@directive("tx-map", "reverse-geocode", domain_alias="腾讯地图", action_aliases={"reverse-geocode": "逆地理编码"})
def tx_reverse_geocode(params: list[str]) -> dict:
    """Convert GCJ-02 coordinates → address."""
    if len(params) < 2:
        return {"status": "error", "reason": "Missing lat,lng"}

    lat, lng = params[0], params[1]
    data, err = _signed_get("/ws/geocoder/v1/", {
        "location": f"{lat},{lng}",
        "output": "json",
        "get_poi": "0",
    })
    if err:
        return {"status": "error", "reason": err}

    result = data.get("result", {})
    ad_info = result.get("ad_info", {})
    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "coord_sys": "gcj02",
        "name": ad_info.get("name", ""),
        "address": result.get("address", ""),
        "province": ad_info.get("province", ""),
        "city": ad_info.get("city", ""),
        "district": ad_info.get("district", ""),
    }

@directive("tx-map", "route", domain_alias="腾讯地图", action_aliases={"route": "路线规划"})
def tx_route(params: list[str]) -> dict:
    """Plan driving route between two coordinate pairs."""
    if len(params) < 4:
        return {
            "status": "error",
            "reason": "Usage: tx-map;route,<from_lat>,<from_lng>,<to_lat>,<to_lng>[,polyline|roads]"
        }

    from_lat, from_lng = params[0], params[1]
    to_lat, to_lng = params[2], params[3]
    fmt = params[4] if len(params) > 4 else "polyline"

    data, err = _signed_get("/ws/direction/v1/driving/", {
        "from": f"{from_lat},{from_lng}",
        "to": f"{to_lat},{to_lng}",
        "output": "json",
    })
    if err:
        return {"status": "error", "reason": err}

    route = data.get("result", {}).get("routes", [{}])[0]
    distance = route.get("distance", 0)
    duration = route.get("duration", 0)

    if fmt == "roads":
        steps = route.get("steps", [])
        roads = list(dict.fromkeys([
            s.get("road_name", "") for s in steps if s.get("road_name")
        ]))
        return {
            "status": "ok",
            "distance": distance,
            "duration_min": round(duration, 1),
            "roads": roads,
        }

    raw_polyline = route.get("polyline", [])
    if not raw_polyline:
        return {"status": "error", "reason": "No route found"}

    decompressed = _decompress_polyline(raw_polyline)
    pairs = _polyline_to_pairs(decompressed)
    polyline_str = _pairs_to_string(pairs)

    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "coord_sys": "gcj02",
        "distance": distance,
        "duration_min": round(duration, 1),
        "polyline": polyline_str,
        "point_count": len(pairs),
    }

@directive("tx-map", "static-map", domain_alias="腾讯地图", action_aliases={"static-map": "静态图"})
def tx_static_map(params: list[str]) -> dict:
    """Generate static map image → base64 data URI."""
    if len(params) < 2:
        return {"status": "error", "reason": "Missing lat,lng"}

    lat, lng = params[0], params[1]
    zoom = params[2] if len(params) > 2 else "15"
    size = params[3] if len(params) > 3 else "400"

    try:
        z = int(zoom)
        if z < 1 or z > 18:
            return {"status": "error", "reason": "Zoom must be 1-18"}
    except ValueError:
        return {"status": "error", "reason": f"Invalid zoom: {zoom}"}

    try:
        s = int(size)
        if s < 200 or s > 800:
            return {"status": "error", "reason": "Size must be 200-800"}
    except ValueError:
        return {"status": "error", "reason": f"Invalid size: {size}"}

    png_bytes, err = _signed_get_bytes("/ws/staticmap/v2/", {
        "center": f"{lat},{lng}",
        "zoom": zoom,
        "size": f"{size}x{size}",
    })
    if err:
        return {"status": "error", "reason": err}

    import base64
    b64 = base64.b64encode(png_bytes).decode('ascii')
    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "url": f"data:image/png;base64,{b64}",
        "center": [lat, lng],
        "zoom": int(zoom),
        "size": int(size),
    }

@directive("tx-map", "ip", domain_alias="腾讯地图", action_aliases={"ip": "IP定位"})
def tx_ip(params: list[str]) -> dict:
    """Get approximate location from IP address."""
    if not params:
        return {"status": "error", "reason": "Missing IP"}

    ip = params[0]
    data, err = _signed_get("/ws/location/v1/ip", {"ip": ip})
    if err:
        return {"status": "error", "reason": err}

    result = data.get("result", {})
    ad_info = result.get("ad_info", {})
    location = result.get("location", {})

    return {
        "status": "ok",
        "coord_sys": "gcj02",
        "coord_sys": "gcj02",
        "ip": ip,
        "city": (ad_info.get("city", "") or "") + (ad_info.get("district", "") or ""),
        "nation": ad_info.get("nation", ""),
        "province": ad_info.get("province", ""),
        "lat": location.get("lat"),
        "lng": location.get("lng"),
    }

def init_tx_map_handler(db_path: str):
    global DB_PATH; DB_PATH = {'config': db_path}

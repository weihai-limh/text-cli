"""
bd-map handler — Baidu Maps HTTP API instruction package.

Wraps Baidu Maps WebService API with single-key (ak) auth via key_registry.
Zero dependencies beyond stdlib. 4 directives.

Directives:
    bd-map;geocode,<address>                                              → WGS84 coordinates
    bd-map;ip,<ip>[,<coor>]                                              → city
    bd-map;route,<from>,<to>[,<mode>,<is_address>]                       → route polyline
    bd-map;static-map,<lon>,<lat>[,<zoom>,<size>,<markers>,<labels>,<paths>] → base64 PNG

Key: single-key via key;register,bd,<ak>,api_key
Quota: tracked via quota-manage (key;quota-track,bd,bd-map;geocode,...)

Markers: 'lon1 lat1|lon2 lat2'  →  'lon1,lat1;lon2,lat2' (Baidu format)
Labels:  'text1 lon1 lat1|...'  →  'text1,lon1,lat1;...' + auto labelStyles
Paths:   'lon1,lat1;lon2,lat2'  →  passed as-is + auto pathStyles (last param)

Author: Tide 🌊 — 2026-05-15
"""

import base64
import json
import logging
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)

from core.registry import directive

DB_PATH: dict = {}
KEY_SERVICE = "bd"
BD_BASE = "https://api.map.baidu.com"

def init_bd_handler(db_path: str):
    global DB_PATH
    DB_PATH = {"config": db_path}

def _get_key() -> str | None:
    try:
        from text_cli_modules.key.key_registry import get as key_get
    except ImportError:
        return None
    creds = key_get(DB_PATH, KEY_SERVICE)
    if not creds:
        return None
    if isinstance(creds, list):
        return creds[0]
    return creds

def _bd_get(url_path: str, params: dict) -> tuple[dict | None, str | None]:
    ak = _get_key()
    if not ak:
        return None, "BD key not configured or quota exhausted. Register: key;register,bd,<ak>,api_key"

    params["ak"] = ak
    query_string = urllib.parse.urlencode(params)
    base = f"{BD_BASE}{url_path}"
    if "/geoconv" in url_path and not base.endswith("/"):
        base += "/"
    url = f"{base}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get("status") != 0:
                return None, data.get("message", f"API error: status={data.get('status')}")
            return data, None
    except Exception as e:
        return None, str(e)

def _bd_get_bytes(url_path: str, params: dict) -> tuple[bytes | None, str | None]:
    ak = _get_key()
    if not ak:
        return None, "BD key not configured"

    params["ak"] = ak
    query_string = urllib.parse.urlencode(params)
    base = f"{BD_BASE}{url_path}"
    if "/geoconv" in url_path and not base.endswith("/"):
        base += "/"
    url = f"{base}?{query_string}"

    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.read(), None
    except Exception as e:
        return None, str(e)

def _bd_geocode_raw(address: str) -> tuple[float | None, float | None]:
    """Internal geocode → BD09LL coordinates (lon, lat)."""
    data, err = _bd_get("/geocoding/v3", {
        "address": address,
        "output": "json",
    })
    if err or not data:
        return None, None
    loc = data.get("result", {}).get("location", {})
    return loc.get("lng"), loc.get("lat")

@directive("bd-map", "geocode", domain_alias="百度地图", action_aliases={"geocode": "地理编码"})
def bd_geocode(params: list[str]) -> dict:
    if not params:
        return {"status": "error", "reason": "Missing address"}

    address = params[0]
    data, err = _bd_get("/geocoding/v3", {
        "address": address,
        "output": "json",
    })
    if err:
        return {"status": "error", "reason": err}

    location = data.get("result", {}).get("location", {})
    result = data.get("result", {})
    return {
        "status": "ok",
        "coord_sys": "bd09ll",
        "lon": location.get("lng"),
        "lat": location.get("lat"),
        "address": address,
        "formatted": address,
        "level": result.get("level", ""),
    }

@directive("bd-map", "ip", domain_alias="百度地图", action_aliases={"ip": "IP定位"})
def bd_ip(params: list[str]) -> dict:
    if not params:
        return {"status": "error", "reason": "Missing IP"}

    ip = params[0]
    coor = params[1] if len(params) > 1 else "bd09ll"

    data, err = _bd_get("/location/ip", {"ip": ip, "coor": coor})
    if err:
        return {"status": "error", "reason": err}

    content = data.get("content", {})
    addr = content.get("address_detail", {})
    point = content.get("point", {})

    return {
        "status": "ok",
        "coord_sys": "bd09ll",
        "ip": ip,
        "city": addr.get("city", ""),
        "province": addr.get("province", ""),
        "lon": point.get("x"),
        "lat": point.get("y"),
        "coor": coor,
    }

@directive("bd-map", "route", domain_alias="百度地图", action_aliases={"route": "路线规划"})
def bd_route(params: list[str]) -> dict:
    if len(params) < 2:
        return {
            "status": "error",
            "reason": "Usage: bd-map;route,<from>,<to>[,<mode>,<is_address>]"
        }

    from_val = params[0]
    to_val = params[1]
    mode_idx = 2

    if len(params) >= 4 and not ("," in params[0] and "," in params[1]):
        try:
            float(params[0])
            float(params[1])
            from_val = f"{params[0]},{params[1]}"
            to_val = f"{params[2]},{params[3]}"
            mode_idx = 4
        except ValueError:
            pass

    mode = params[mode_idx] if len(params) > mode_idx else "driving"
    is_address = params[mode_idx + 1] if len(params) > mode_idx + 1 else "0"

    valid_modes = {"driving", "transit", "walking", "riding"}
    if mode not in valid_modes:
        return {
            "status": "error",
            "reason": f"Invalid mode: {mode}. Use: {', '.join(sorted(valid_modes))}"
        }

    origin = from_val
    destination = to_val
    if is_address == "1":
        flon, flat = _bd_geocode_raw(from_val)
        tlon, tlat = _bd_geocode_raw(to_val)
        if flon is None or tlon is None:
            return {"status": "error", "reason": "Auto-geocode failed"}
        origin = f"{flat},{flon}"
        destination = f"{tlat},{tlon}"

    data, err = _bd_get(f"/directionlite/v1/{mode}", {
        "origin": origin,
        "destination": destination,
    })
    if err:
        return {"status": "error", "reason": err}

    result = data.get("result", {})
    routes = result.get("routes", [])
    if not routes:
        return {"status": "error", "reason": "No route found"}

    route = routes[0]
    return {
        "status": "ok",
        "coord_sys": "bd09ll",
        "mode": mode,
        "distance": route.get("distance", 0),
        "duration": route.get("duration", 0),
        "from": from_val,
        "to": to_val,
        "steps": route.get("steps", []),
        "raw": data,
    }

@directive("bd-map", "static-map", domain_alias="百度地图", action_aliases={"static-map": "静态图"})
def bd_static_map(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Missing lon,lat"}

    lon, lat = params[0], params[1]
    zoom = params[2] if len(params) > 2 else "14"
    size = params[3] if len(params) > 3 else "400"
    markers_str = params[4] if len(params) > 4 else ""
    labels_str = params[5] if len(params) > 5 else ""
    paths_str = params[6] if len(params) > 6 else ""

    try:
        z = int(zoom)
        if z < 3 or z > 18: raise ValueError
    except ValueError:
        return {"status": "error", "reason": "Zoom must be 3-18"}
    try:
        s = int(size)
        if s < 200 or s > 800: raise ValueError
    except ValueError:
        return {"status": "error", "reason": "Size must be 200-800"}

    api_params = {
        "center": f"{lon},{lat}",
        "zoom": zoom,
        "width": size,
        "height": size,
        "coordtype": "wgs84ll",
    }

    if markers_str:
        pairs = [m.strip() for m in markers_str.split("|") if m.strip()]
        points = []
        for p in pairs:
            parts = p.split()
            if len(parts) >= 2:
                points.append(f"{parts[0]},{parts[1]}")
        if points:
            api_params["markers"] = ";".join(points)

    if labels_str:
        entries = [lb.strip() for lb in labels_str.split("|") if lb.strip()]
        label_points = []
        label_texts = []
        for e in entries:
            parts = e.split()
            if len(parts) >= 3:
                label_texts.append(parts[0])
                label_points.append(f"{parts[0]},{parts[1]},{parts[2]}")
        if label_points:
            api_params["labels"] = ";".join(label_points)
            api_params["labelStyles"] = "|".join([
                f"{t},0,20,0xFF0000,0xFFFFFF,0" for t in label_texts
            ])

    if paths_str:
        api_params["paths"] = paths_str
        api_params["pathStyles"] = "0xff0000,5,1"

    png_bytes, err = _bd_get_bytes("/staticimage/v2", api_params)
    if err:
        return {"status": "error", "reason": err}

    b64 = base64.b64encode(png_bytes).decode('ascii')
    return {
        "status": "ok",
        "coord_sys": "bd09ll",
        "url": f"data:image/png;base64,{b64}",
        "center": [lon, lat],
        "zoom": int(zoom),
        "size": int(size),
        "marker_count": len(markers_str.split("|")) if markers_str else 0,
        "label_count": len(labels_str.split("|")) if labels_str else 0,
        "has_path": bool(paths_str),
    }

@directive("bd-map", "tfcoords", domain_alias="百度地图", action_aliases={"tfcoords": "坐标转换"})
def bd_tfcoords(params: list[str]) -> dict:
    """
    bd-map;tfcoords,<lon>,<lat>,<model>
    Batch: bd-map;tfcoords,<lon1>,<lat1>;<lon2>,<lat2>,<model>

    model: 1=GCJ02→BD09LL  2=WGS84→BD09LL  3=BD09LL→BD09MC
           4=BD09MC→BD09LL  5=BD09LL→GCJ02  6=BD09MC→GCJ02
    """
    if len(params) < 2:
        return {"status": "error", "reason": "Missing params: <lon>,<lat>,<model>"}

    coord_str = params[0]
    model = params[1]

    if len(params) >= 3:
        try:
            float(coord_str)
            coord_str = f"{coord_str},{params[1]}"
            model = params[2]
        except ValueError:
            pass

    ak = _get_key()
    if not ak:
        return {"status": "error", "reason": "BD key not configured"}

    coords_list = []
    if ";" in coord_str:
        for pair in coord_str.split(";"):
            parts = pair.strip().split(",")
            if len(parts) >= 2:
                coords_list.append([float(parts[0].strip()), float(parts[1].strip())])
    else:
        parts = coord_str.split(",")
        if len(parts) >= 2:
            coords_list.append([float(parts[0].strip()), float(parts[1].strip())])

    if not coords_list:
        return {"status": "error", "reason": "Format: <lon>,<lat> or <lon1>,<lat1>;<lon2>,<lat2>"}

    if len(coords_list) > 100:
        return {"status": "error", "reason": "Max 100 coordinates per request"}

    api_coords = ";".join(f"{c[0]},{c[1]}" for c in coords_list)
    data, err = _bd_get("/geoconv/v2", {"coords": api_coords, "model": model})
    if err:
        return {"status": "error", "reason": err}

    if not data or data.get("status") != 0:
        return {"status": "error", "reason": f"Transform failed: {data.get('message', '?') if data else 'no response'}"}

    results = data.get("result", [])
    coords_out = [[r["x"], r["y"]] for r in results]

    coord_sys_map = {"1": "bd09ll", "2": "bd09ll", "3": "bd09mc", "4": "bd09ll", "5": "gcj02", "6": "gcj02"}
    cs = coord_sys_map.get(model, "unknown")

    if len(coords_out) == 1:
        return {"status": "ok", "coord": coords_out[0], "coord_sys": cs, "model": model}
    return {"status": "ok", "coords": coords_out, "coord_sys": cs, "model": model, "count": len(coords_out)}

def init_bd_map_handler(db_path: str):
    global DB_PATH; DB_PATH = {'config': db_path}

init_bd_handler = init_bd_map_handler  # backward compat

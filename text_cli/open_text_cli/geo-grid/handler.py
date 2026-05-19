"""
geo-grid handler — geospatial grid mathematics.

H3 hexagonal grid indexing + center/zoom/distance/resolution/bbox calculations.
Pure math (stdlib) for 5 of 6 directives. H3 requires `pip install h3`.

Directives:
    geo-grid;h3,<lon>,<lat>[,<resolution>]               → H3 cell + boundary
    geo-grid;center,<lon1>,<lat1>,<lon2>,<lat2>          → midpoint
    geo-grid;zoom,<lon1>,<lat1>,<lon2>,<lat2>            → optimal zoom
    geo-grid;zoom-from-distance,<meters>                  → distance→zoom
    geo-grid;h3-resolution,<meters>                       → distance→H3 res
    geo-grid;radius-bbox,<lon>,<lat>,<meters>             → bounding polygon
    geo-grid;offset,<lon>,<lat>,<bearing>,<meters>        → offset coordinate
    geo-grid;route-parse,<json>,<source>,<mode>           → named road coords
"""

import json
import math
import logging

logger = logging.getLogger(__name__)

from core.registry import directive

# ── H3 (optional dependency) ───────────────────

try:
    import h3
    H3_AVAILABLE = True
except ImportError:
    H3_AVAILABLE = False
    logger.info("h3 library not installed — geo-grid;h3 will be unavailable")


# ── Zoom interval tables ───────────────────────

_ZOOM_INTERVALS = [
    (0, 1, 18), (1, 2, 17), (2, 4.5, 16), (4.5, 8, 15),
    (8, 16, 14), (16, 30, 13), (30, 70, 12), (70, 100, 11),
    (200, 250, 10), (250, 400, 9), (400, 650, 8),
    (650, 1300, 7), (1300, 2500, 6), (2500, 5000, 5),
    (5000, 10000, 4), (10000, 70000, 3),
]

_H3_INTERVALS = [
    (0, 0.5, 15), (0.5, 1.5, 14), (1.5, 3.5, 13), (3.5, 9.5, 12),
    (9.5, 24.9, 11), (24.9, 65.9, 10), (65.9, 174.3, 9),
    (174.3, 461.3, 8), (461.3, 1220.6, 7), (1220.6, 3229.4, 6),
    (3229.4, 8544.4, 5), (8544.4, 22606.3, 4), (22606.3, 59810.8, 3),
    (59810.8, 158244.6, 2), (158244.6, 418676, 1),
]


def _lookup_interval(km: float, intervals: list) -> int | None:
    for lower, upper, value in intervals:
        if lower <= km <= upper:
            return value
    return intervals[-1][2] if km > intervals[-1][1] else intervals[0][2]


# ── Directives ─────────────────────────────────

@directive("geo-grid", "h3", domain_alias="地理网格", action_aliases={"h3": "六边形网格"})
def geo_h3(params: list[str]) -> str:
    if not H3_AVAILABLE:
        return json.dumps({
            "status": "error",
            "reason": "h3 library not installed. Run: pip install h3"
        })

    if len(params) < 2:
        return json.dumps({"status": "error", "reason": "Missing lon,lat"})

    try:
        lon, lat = float(params[0]), float(params[1])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Invalid lon/lat"})

    resolution = int(params[2]) if len(params) > 2 else 10
    if resolution < 0 or resolution > 15:
        return json.dumps({"status": "error", "reason": "Resolution must be 0-15"})

    try:
        cell = h3.latlng_to_cell(lat, lon, resolution)
        boundary = h3.cell_to_boundary(cell)
        # boundary is [(lat, lng), ...] → convert to [[lng, lat], ...]
        vertices = [[round(lng, 6), round(lat, 6)] for lat, lng in boundary]
        return json.dumps({
            "status": "ok",
            "cell": cell,
            "resolution": resolution,
            "vertices": vertices,
            "vertex_count": len(vertices),
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"status": "error", "reason": str(e)})


@directive("geo-grid", "center", domain_alias="地理网格", action_aliases={"center": "中心点"})
def geo_center(params: list[str]) -> str:
    if len(params) < 4:
        return json.dumps({"status": "error", "reason": "Missing lon1,lat1,lon2,lat2"})

    try:
        lon1, lat1 = float(params[0]), float(params[1])
        lon2, lat2 = float(params[2]), float(params[3])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Invalid coordinates"})

    return json.dumps({
        "status": "ok",
        "lon": round((lon1 + lon2) / 2, 6),
        "lat": round((lat1 + lat2) / 2, 6),
    }, ensure_ascii=False)


@directive("geo-grid", "zoom", domain_alias="地理网格", action_aliases={"zoom": "缩放计算"})
def geo_zoom(params: list[str]) -> str:
    if len(params) < 4:
        return json.dumps({"status": "error", "reason": "Missing lon1,lat1,lon2,lat2"})

    try:
        lon1, lat1 = float(params[0]), float(params[1])
        lon2, lat2 = float(params[2]), float(params[3])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Invalid coordinates"})

    # Distance in km (approximate longitudinal)
    mid_lat = abs((lat1 + lat2) / 2)
    km_per_deg = 111.32 * math.cos(math.radians(mid_lat))
    distance_km = abs(lon2 - lon1) * km_per_deg

    zoom = _lookup_interval(distance_km, _ZOOM_INTERVALS)

    return json.dumps({
        "status": "ok",
        "zoom": zoom,
        "distance_km": round(distance_km, 2),
    }, ensure_ascii=False)


@directive("geo-grid", "zoom-from-distance", domain_alias="地理网格", action_aliases={"zoom-from-distance": "距离转缩放"})
def geo_zoom_from_distance(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Missing meters"})

    try:
        meters = float(params[0])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Invalid meters value"})

    km = meters / 1000.0
    zoom = _lookup_interval(km, _ZOOM_INTERVALS)

    return json.dumps({
        "status": "ok",
        "meters": meters,
        "zoom": zoom,
    }, ensure_ascii=False)


@directive("geo-grid", "h3-resolution", domain_alias="地理网格", action_aliases={"h3-resolution": "H3分辨率"})
def geo_h3_resolution(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Missing meters"})

    try:
        meters = float(params[0])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Invalid meters value"})

    resolution = _lookup_interval(meters, _H3_INTERVALS)

    return json.dumps({
        "status": "ok",
        "meters": meters,
        "resolution": resolution,
    }, ensure_ascii=False)


@directive("geo-grid", "radius-bbox", domain_alias="地理网格", action_aliases={"radius-bbox": "半径边界框"})
def geo_radius_bbox(params: list[str]) -> str:
    if len(params) < 3:
        return json.dumps({"status": "error", "reason": "Missing lon,lat,meters"})

    try:
        lon, lat = float(params[0]), float(params[1])
        meters = float(params[2])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Invalid values"})

    # Approximate: 1° latitude ≈ 111320m, 1° longitude ≈ 111320m * cos(lat)
    d_lat = meters / 111320.0
    d_lon = meters / (111320.0 * math.cos(math.radians(abs(lat))))

    n, s = lat + d_lat, lat - d_lat
    e, w = lon + d_lon, lon - d_lon

    # 4-corner polygon (clockwise from NW)
    nw = f"{round(w, 6)},{round(n, 6)}"
    ne = f"{round(e, 6)},{round(n, 6)}"
    se = f"{round(e, 6)},{round(s, 6)}"
    sw = f"{round(w, 6)},{round(s, 6)}"

    polygon = f"{nw};{ne};{se};{sw}"

    return json.dumps({
        "status": "ok",
        "polygon": polygon,
        "center": [round(lon, 6), round(lat, 6)],
        "radius_m": meters,
        "bbox": {
            "north": round(n, 6), "south": round(s, 6),
            "east": round(e, 6), "west": round(w, 6),
        },
    }, ensure_ascii=False)


# ═══════════════════════════════════════════════════
# P1: offset + route-parse
# ═══════════════════════════════════════════════════

@directive("geo-grid", "offset", domain_alias="地理网格", action_aliases={"offset": "偏移"})
def geo_grid_offset(params: list[str]) -> str:
    """
    geo-grid;offset,<lon>,<lat>,<bearing>,<dist_km>

    bearing: 0=N, 90=E, 180=S, 270=W
    """
    if len(params) < 4:
        return json.dumps({"status": "error", "reason": "Required: <lon>,<lat>,<bearing>,<dist_km>"})
    try:
        lon = float(params[0])
        lat = float(params[1])
        bearing = float(params[2])
        dist_km = float(params[3])
    except ValueError:
        return json.dumps({"status": "error", "reason": "Parameters must be numeric"})

    R = 6371.0  # Earth radius in km
    lat_rad = math.radians(lat)
    bearing_rad = math.radians(bearing)

    # For east/west offset: delta_lon = dist / (R * cos(lat))
    new_lon = lon + (dist_km * math.sin(bearing_rad)) / (R * math.cos(lat_rad))
    new_lat = lat + (dist_km * math.cos(bearing_rad)) / R
    # Convert degrees: delta_lat = dist * cos(bearing) / R (in radians) → degrees
    new_lat = math.degrees(math.radians(lat) + (dist_km / R) * math.cos(bearing_rad))
    # delta_lon = dist * sin(bearing) / (R * cos(lat_rad)) (in radians) → degrees
    new_lon = math.degrees(math.radians(lon) + (dist_km * math.sin(bearing_rad)) / (R * math.cos(lat_rad)))

    return json.dumps({
        "status": "ok",
        "coord": [round(new_lon, 6), round(new_lat, 6)],
        "origin": [round(lon, 6), round(lat, 6)],
        "bearing": bearing,
        "dist_km": dist_km,
    })


@directive("geo-grid", "route-parse", domain_alias="地理网格", action_aliases={"route-parse": "路线解析"})
def geo_grid_route_parse(params: list[str]) -> str:
    """
    geo-grid;route-parse,<json>,<source>,<mode>[,<n>]

    source: bd (Baidu direction/v2 API response)
    mode: tail-coord (last N named road coordinates)
    n: optional count (default 1)

    Baidu-specific: skips unnamed roads, returns first point of named road path.
    """
    if len(params) < 3:
        return json.dumps({"status": "error", "reason": "Required: <json>,<source>,<mode>[,<n>]"})

    raw = params[0]
    source = params[1]
    mode = params[2]
    n = int(params[3]) if len(params) > 3 else 1

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return json.dumps({"status": "error", "reason": "Invalid JSON"})

    if source != "bd":
        return json.dumps({"status": "error", "reason": f"source={source} not supported (only bd）"})

    if mode != "tail-coord":
        return json.dumps({"status": "error", "reason": f"mode={mode} not supported (only tail-coord）"})

    # ── Baidu route parsing ──
    # Two formats: raw API (result.routes[0].steps) or route handler output (steps)
    if "steps" in data:
        steps = data["steps"]
    else:
        result = data.get("result", {})
        routes = result.get("routes", [])
        if not routes:
            return json.dumps({"status": "error", "reason": "Route data is empty"})
        steps = routes[0].get("steps", [])
    if not steps:
        return json.dumps({"status": "error", "reason": "Route steps are empty"})

    # Collect named road coords from end (skip unnamed roads)
    found = []
    for step in reversed(steps):
        if len(found) >= n:
            break
        road_name = step.get("road_name", "")
        if road_name == "无名路":  # unnamed road
            continue
        path_str = step.get("path", "")
        if path_str:
            # path format: "lng,lat;lng,lat;..."
            first_point = path_str.split(";")[0] if ";" in path_str else path_str
            found.append({
                "coord": first_point,
                "road_name": road_name,
            })

    if not found:
        return json.dumps({"status": "error", "reason": "No named road coordinates found"})

    if n == 1:
        return json.dumps({
            "status": "ok",
            "coord": found[0]["coord"],
            "road_name": found[0]["road_name"],
            "source": source,
            "mode": mode,
        })

    return json.dumps({
        "status": "ok",
        "coords": [f["coord"] for f in found],
        "road_names": [f["road_name"] for f in found],
        "count": len(found),
        "source": source,
        "mode": mode,
    })


# ── Init (noop — no DB needed) ─────────────────

def init_geo_grid_handler():
    pass

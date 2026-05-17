"""
baidu-map geocode output adapter.

Maps baidumap-adapter output (Baidu Agent Plan API raw fields)
to the canonical geocode format used by the map aggregate.
"""

import json


def normalize(raw: dict) -> dict:
    """
    Input (after baidumap generic adapter):
      {"status":"ok", "result": {"location":{"lng":122.1,"lat":37.5}, "level":"城市"}}

    Output (canonical geocode format):
      {"status":"ok", "coord_sys":"bd09ll", "lon":122.1, "lat":37.5, "address":"...", "formatted":"...", "level":"城市"}
    """
    if not isinstance(raw, dict) or raw.get("status") != "ok":
        return raw

    result = raw.get("result", {})

    if isinstance(result, dict):
        location = result.get("location", {})
        return {
            "status": "ok",
            "coord_sys": "bd09ll",
            "lon": location.get("lng"),
            "lat": location.get("lat"),
            "address": result.get("address", ""),
            "formatted": result.get("formatted_address", result.get("address", "")),
            "level": result.get("level", ""),
        }

    return raw

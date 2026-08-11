"""
Unified response envelope — compatible with text-cli service response format.

All textcli-loader results use the same envelope:
    {"rst_types": "text", "rst_data": <handler dict>, "rst_err": ""}
"""

import json


def ok(data: dict, rst_type: str = "text") -> dict:
    """Wrap a successful result in text-cli envelope format.

    data: handler's return dict — placed directly into rst_data.
    If data contains pray_rst_types, it is promoted to rst_types and stripped.
    """
    pray = data.pop("pray_rst_types", None)
    if pray and rst_type == "text":
        rst_type = pray
    return {"rst_types": rst_type, "rst_data": data, "rst_err": ""}


def error(reason: str, code: str = "ERR_EXECUTION") -> dict:
    """Wrap an error in text-cli envelope format.
    
    code must be one of the protocol's closed set (SPEC §1.2.8):
    ERR_NOT_FOUND, ERR_EXECUTION, ERR_ROUTING, INVALID_PARAMS, ACCESS_DENIED, SERVICE_DENIED
    """
    return {
        "rst_types": "text",
        "rst_data": {"status": "error", "reason": reason},
        "rst_err": code,
    }


def to_json(envelope: dict) -> str:
    """Serialize envelope to JSON string."""
    return json.dumps(envelope, ensure_ascii=False)

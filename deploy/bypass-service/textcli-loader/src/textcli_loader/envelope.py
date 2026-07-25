"""
Unified response envelope — compatible with text-cli service response format.

All textcli-loader results use the same envelope:
    {"rst_types": "text", "rst_data": {"text": <result>}, "rst_err": ""}
"""

import json


def ok(text: str) -> dict:
    """Wrap a successful result in text-cli envelope format."""
    return {
        "rst_types": "text",
        "rst_data": {"text": text},
        "rst_err": "",
    }


def error(message: str, code: str = "internal_error") -> dict:
    """Wrap an error in text-cli envelope format."""
    return {
        "rst_types": "text",
        "rst_data": {"text": f"[{code}] {message}"},
        "rst_err": code,
    }


def to_json(envelope: dict) -> str:
    """Serialize envelope to JSON string."""
    return json.dumps(envelope, ensure_ascii=False)

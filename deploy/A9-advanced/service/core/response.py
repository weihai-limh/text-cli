"""
Response envelope helpers — standard success and error response construction.

Handler returns a dict; the skeleton wraps it into the protocol envelope.
The handler MAY include `pray_rst_types` to signal media responses (picture/video/audio/file);
the skeleton promotes it to `rst_types` and strips it from `rst_data`.
"""


def ok(data: dict, rst_type: str = "text") -> dict:
    """Construct a success envelope.

    data: the handler's return dict — placed directly into rst_data.
    rst_type: response type, "text" by default. If data contains pray_rst_types,
              that value takes precedence and is stripped from rst_data.
    """
    pray = data.pop("pray_rst_types", None)
    if pray and rst_type == "text":
        rst_type = pray
    return {"rst_types": rst_type, "rst_data": data, "rst_err": ""}


def error(reason: str, code: str = "ERR_EXECUTION") -> dict:
    """Construct an error envelope.

    reason: human-readable error description.
    code: protocol error code (ERR_EXECUTION / ERR_NOT_FOUND / ERR_ROUTING / ...).
    """
    return {"rst_types": "text", "rst_data": {"status": "error", "reason": reason}, "rst_err": code}

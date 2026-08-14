"""A5 端点协议错误信封构造工具（§8.7 四码闭集）。

端点层（A5）只可产出四码子集：
    ACCESS_DENIED / INVALID_PARAMS / ERR_NOT_FOUND / ERR_ROUTING
禁用 SERVICE_DENIED / ERR_EXECUTION（仅后端运行时使用）。

err() 返回信封 payload dict，配合 JSONResponse(status_code=..., content=err(reason, code)) 使用。
"""


def err(reason: str, code: str) -> dict:
    """构造 A5 端点协议错误信封 payload。

    reason: 业务原因串，原样落入 rst_data.reason（保留可读语义）。
    code:   协议错误码，须为四码闭集之一。
    """
    return {
        'rst_types': 'text',
        'rst_data': {'status': 'error', 'reason': reason},
        'rst_err': code,
    }

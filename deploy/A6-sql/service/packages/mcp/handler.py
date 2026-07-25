"""
MCP handler package — re-exports service/handlers/mcp_handler.py.

This shim allows A3+ service layers to import from `packages.mcp.handler`
instead of reaching directly into service handlers.
"""



def check_mcp_quota(server: str, tool: str = "", dispatch_fn=None) -> dict | None:
    """Stub — MCP quota check not yet implemented.
    
    Returns None (no quota block), allowing all MCP calls to proceed.
    """
    return None

class HelloWorldCmdHandlers:
    """Handlers for hello-world-cmd copilot package."""

    def _handle_hello_world(self, params: list[str]) -> dict:
        name = params[0].strip() if params and params[0].strip() else "World"
        return {"rst_types": "text", "rst_data": {"status": "ok", "result": f"Hello, {name}!"}, "rst_err": ""}

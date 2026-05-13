"""
Sample handlers — demonstrate how to register a new directive handler.
Each @directive decorator registers a domain+action pair in the registry.
"""
from core.registry import directive


@directive("sample", "echo")
def echo(params: list[str]) -> str:
    """Echo handler — returns parameters as-is, used for connectivity testing."""
    return f"Echo result: {', '.join(params)}" if params else "Echo result: (no params)"


@directive("sample", "greet")
def greet(params: list[str]) -> str:
    """Greet handler — returns a greeting for the given name."""
    name = params[0] if params else "World"
    return f"Hello, {name}!"


@directive("sample", "list")
def list_items(params: list[str]) -> str:
    """List handler — shows all available sample directives."""
    return "Sample directives:\n- echo: returns parameters as-is\n- greet: greets the given name\n- list: shows this list"

from core.registry import directive


@directive("hello", "world", domain_alias="你好", action_aliases={"world": "世界"})
def hello_world(params: list[str]) -> dict:
    name = params[0].strip() if params and params[0].strip() else "World"
    return {"status": "ok", "result": f"Hello!{name}!"}

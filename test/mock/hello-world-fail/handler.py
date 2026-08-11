from core.registry import directive


@directive("test-fail", "test", domain_alias="测试失败", action_aliases={"test": "测试"})
def greet(params: list[str]) -> dict:
    name = params[0].strip() if params and params[0].strip() else "World"
    if name == "fail":
        return {"status": "error", "reason": "Intentional failure for degradation chain test"}
    return {"status": "ok", "result": f"Hello!{name}!"}

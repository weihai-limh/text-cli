from core.registry import directive


@directive("示例领域", "回显")
def echo(params: list[str]) -> str:
    return f"回显结果: {', '.join(params)}" if params else "回显结果: (无参数)"


@directive("示例领域", "问候")
def greet(params: list[str]) -> str:
    name = params[0] if params else "世界"
    return f"你好, {name}!"


@directive("示例领域", "列表")
def list_items(params: list[str]) -> str:
    return "示例指令列表:\n- 回显: 回显参数\n- 问候: 问候指定名称\n- 列表: 显示此列表"

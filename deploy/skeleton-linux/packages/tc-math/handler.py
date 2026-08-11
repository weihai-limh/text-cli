"""
tc-math handler — safe arithmetic evaluator for path pipelines.

AST-validated evaluation. Zero dependencies, stdlib math only.
"""
import ast
import math
import operator

from core.registry import directive

_SAFE_FUNCS = {
    'sqrt': math.sqrt, 'sin': math.sin, 'cos': math.cos, 'tan': math.tan,
    'log': math.log, 'log10': math.log10, 'abs': abs, 'ceil': math.ceil,
    'floor': math.floor, 'round': round, 'pi': math.pi, 'e': math.e,
}

_BINOPS = {
    ast.Add: operator.add, ast.Sub: operator.sub,
    ast.Mult: operator.mul, ast.Div: operator.truediv,
    ast.Pow: operator.pow, ast.Mod: operator.mod,
}

_UNOPS = {
    ast.USub: operator.neg, ast.UAdd: operator.pos,
}


def _eval_node(node):
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.BinOp):
        return _BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp):
        return _UNOPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.Call):
        func_name = node.func.id
        if func_name not in _SAFE_FUNCS:
            raise ValueError(f"function not allowed: {func_name}")
        args = [_eval_node(a) for a in node.args]
        return _SAFE_FUNCS[func_name](*args)
    if isinstance(node, ast.Name):
        if node.id not in _SAFE_FUNCS:
            raise ValueError(f"name not allowed: {node.id}")
        return _SAFE_FUNCS[node.id]
    raise ValueError(f"unsupported AST node: {type(node).__name__}")


def _safe_eval(expr: str) -> float:
    tree = ast.parse(expr.strip(), mode='eval')
    return _eval_node(tree.body)


@directive("tc-math", "eval", domain_alias="计算", action_aliases={"eval": "求值"})
def tc_math_eval(params: list[str]) -> dict:
    if not params:
        return {"status": "error", "reason": "Usage: tc-math;eval,<expression>"}
    try:
        result = _safe_eval(params[0])
        return {"status": "ok", "result": result}
    except Exception as e:
        return {"status": "error", "reason": str(e)}


def init_tc_math_handler():
    pass

"""
sample.py — 示例：将 Agent 既有能力转化为 text-cli 指令 (SPEC v1.3.2

如果你已经有这些函数:
    def my_weather(city): ...
    def my_translator(text, lang): ...

只需加一行 @register 即可发布为指令:
    @register(domain="天气", action="查询", category="工具")
    def query_weather(params): ...
"""

from cli import register


@register(domain="示例领域", action="查询", category="示例", description="将既有 API 包装为 text-cli 指令")
def sample_query(params: list[str]) -> str:
    """示例：将既有 API 包装为 text-cli 指令"""
    city = params[0] if params else "未知"
    date = params[1] if len(params) > 1 else "今天"
    return f"{date}{city}: 示例天气数据 (实际替换为你的 API 调用)"


@register(domain="示例领域", action="计算", category="示例", description="将本地工具包装为 text-cli 指令")
def sample_calc(params: list[str]) -> str:
    """示例：将本地工具包装为 text-cli 指令"""
    import ast
    if not params:
        return "请提供计算表达式"
    try:
        result = ast.literal_eval(params[0])
        return f"计算结果: {result}"
    except (ValueError, SyntaxError):
        return f"无法计算: {params[0]}"


@register(domain="示例领域", action="搜索", category="示例", description="将知识库检索包装为 text-cli 指令")
def sample_search(params: list[str]) -> str:
    """示例：将知识库检索包装为 text-cli 指令"""
    query = params[0] if params else ""
    if not query:
        return "请提供搜索关键词"
    return f"搜索「{query}」结果: (实际替换为你的向量检索)"


@register(domain="示例领域", action="列表", category="示例", description="列出所有可用指令")
def list_commands(params: list[str]) -> str:
    """列出所有可用指令"""
    return (
        "可用指令:\n"
        "- AI:sample;query,城市,日期  → 查询天气\n"
        "- AI:sample;calc,表达式      → 计算表达式\n"
        "- AI:sample;search,关键词      → 搜索知识库\n"
        "- AI:sample;list            → 显示此列表"
    )

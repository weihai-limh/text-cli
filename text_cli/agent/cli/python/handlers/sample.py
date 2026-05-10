"""
sample.py — 示例：将 Agent 既有能力转化为 text-cli 指令

如果你已经有这些函数:
    def my_weather(city): ...
    def my_translator(text, lang): ...

只需加一行 @register 即可发布为指令:
    @register("天气", "查询")
    def query_weather(params): ...
"""

from cli.python.cli import register


# ─── 示例 1: 既有 API → 指令 ────────────────────────
#
# 假设你已有一个天气 API 函数:
#
#   def fetch_weather(city: str, date: str) -> str:
#       return requests.get(f"https://api.weather.com/{city}/{date}").text
#
# 只需这样包装:

@register("示例领域", "查询")
def sample_query(params: list[str]) -> str:
    """示例：将既有 API 包装为 text-cli 指令"""
    city = params[0] if params else "未知"
    date = params[1] if len(params) > 1 else "今天"
    return f"{date}{city}: 示例天气数据 (实际替换为你的 API 调用)"


# ─── 示例 2: 本地工具 → 指令 ────────────────────────
#
# 假设你有一个本地计算器:
#
#   def calculate(expr: str) -> float:
#       return eval(expr)
#
# 包装后:

@register("示例领域", "计算")
def sample_calc(params: list[str]) -> str:
    """示例：将本地工具包装为 text-cli 指令"""
    if not params:
        return "请提供计算表达式"
    try:
        # eval 仅示例！实际请用安全表达式解析
        result = eval(params[0])
        return f"计算结果: {result}"
    except Exception:
        return f"无法计算: {params[0]}"


# ─── 示例 3: 知识库 → 指令 ──────────────────────────
#
# 假设你有一个文档检索系统:
#
#   def search_docs(query: str) -> list[str]:
#       return vector_search(query)
#

@register("示例领域", "搜索")
def sample_search(params: list[str]) -> str:
    """示例：将知识库检索包装为 text-cli 指令"""
    query = params[0] if params else ""
    if not query:
        return "请提供搜索关键词"
    return f"搜索「{query}」结果: (实际替换为你的向量检索)"


@register("示例领域", "列表")
def list_commands(params: list[str]) -> str:
    """列出所有可用指令"""
    return (
        "可用指令:\n"
        "- AI:sample;query,城市,日期  → 查询天气\n"
        "- AI:sample;calc,表达式      → 计算表达式\n"
        "- AI:sample;search,关键词      → 搜索知识库\n"
        "- AI:sample;list            → 显示此列表"
    )

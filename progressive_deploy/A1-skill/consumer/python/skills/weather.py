"""
skills/weather.py — 示例：天气查询技能

展示最基本的技能用法：单一指令封装 + 结果格式化 + 错误降级。
"""

from call.python.skill import Skill, skill, SkillResult


@skill("天气查询", domain="天气", action="查询")
class WeatherSkill(Skill):
    """查询指定城市和日期的天气。"""

    def format_result(self, raw: str, params: tuple = ()) -> str:
        city = params[0] if params else "未知"
        date = params[1] if len(params) > 1 else "今天"
        return f"🌤️ {date}{city}: {raw}"

    def on_error(self, params: tuple, error: str) -> str:
        city = params[0] if params else "未知"
        return f"抱歉，暂时无法查询{city}的天气（{error}）"


# ─── 使用示例 ────────────────────────────────────────

if __name__ == "__main__":
    result = WeatherSkill.run("威海", "明天")
    print(result.text)

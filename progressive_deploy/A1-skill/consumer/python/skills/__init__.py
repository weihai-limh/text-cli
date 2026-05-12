"""
skills/ — 预置技能库

每个 .py 文件是一个可复用的 text-cli 技能模块。
Agent 可直接导入使用，也可作为编写自定义技能的参考模板。

技能类型:
    单一技能    → 封装单个指令（weather.py）
    复合技能    → 编排多个指令（translator.py）
    自适应技能  → 根据端点可用性动态选择策略
"""

from call.python.skills.weather import WeatherSkill
from call.python.skills.translator import TranslatorSkill

__all__ = ["WeatherSkill", "TranslatorSkill"]

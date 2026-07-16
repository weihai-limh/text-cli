"""
skill.py — Agent 技能基类：将 text-cli 指令封装为可复用的语义技能

核心理念:
    指令是原子操作（AI:weather;query,北京）
    技能是语义封装（"查询天气" → 选端点 + 发指令 + 格式化结果 + 错误兜底）

技能 = 意图映射 + 指令编排 + 结果加工 + 降级策略

SPEC v1.3 响应格式:
    {"rst_types": "text", "rst_data": {"text": "..."}}

用法:

    from skill import Skill, skill

    @skill("天气查询", domain="天气", action="查询")
    class WeatherSkill(Skill):
        def format_result(self, raw: str) -> str:
            return f"[OK] {raw}"

        def on_error(self, params, error):
            return f"暂时无法查询{params[0]}的天气"

    result = WeatherSkill.run("北京", "明天")
"""

import json
import urllib.request
from dataclasses import dataclass
from typing import Callable


@dataclass
class SkillResult:
    """技能调用结果"""
    success: bool
    text: str
    skill_name: str = ""
    directive: str = ""
    raw: str = ""
    error: str = ""


class Skill:
    """
    技能基类。

    子类只需定义:
    - domain / action → 映射到哪个指令
    - format_result()   → 如何加工原始结果
    - on_error()        → 失败时的兜底回复

    默认通过 urllib 直接调用 text-cli endpoint（零外部依赖）。
    可通过 call_fn 参数注入自定义调用函数。
    """

    domain: str = ""
    action: str = ""
    name: str = ""
    endpoint: str | None = None
    token: str | None = None

    def make_directive(self, *params: str) -> str:
        """将参数列表拼为 text-cli 指令"""
        params_str = ",".join(params)
        return f"AI:{self.domain};{self.action},{params_str}"

    def call(self, *params: str, call_fn: Callable | None = None) -> SkillResult:
        """
        执行技能：发指令 → 解析响应 → 格式化结果。
        子类可覆盖 call() 实现多指令编排。
        """
        directive = self.make_directive(*params)
        endpoint = self.endpoint or "http://localhost:28050/text-cli/cli"
        token = self.token or ""

        try:
            if call_fn:
                raw = call_fn(directive, endpoint=endpoint, token=token)
            else:
                raw = self._call_endpoint(directive, endpoint, token)
        except Exception as e:
            return SkillResult(
                success=False,
                text=self.on_error(params, str(e)),
                skill_name=self.name,
                directive=directive,
                error=str(e),
            )

        text = self.format_result(raw, params)
        return SkillResult(
            success=True,
            text=text,
            skill_name=self.name,
            directive=directive,
            raw=raw,
        )

    def _call_endpoint(self, directive: str, endpoint: str, token: str) -> str:
        """通过 urllib 直接调用 text-cli endpoint（零依赖）。"""
        body = json.dumps({"prompt": directive}).encode("utf-8")
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(endpoint, data=body, headers=headers, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if result.get("rst_types") == "text":
                return result.get("rst_data", {}).get("text", json.dumps(result))
            return json.dumps(result)

    def format_result(self, raw: str, params: tuple = ()) -> str:
        """加工原始结果。子类覆盖此方法实现自定义格式化。"""
        return raw

    def on_error(self, params: tuple, error: str) -> str:
        """错误时返回兜底文本。子类覆盖此方法实现降级策略。"""
        return f"[{self.name}] 指令执行失败: {error}"

    @classmethod
    def run(cls, *params: str, endpoint: str | None = None, token: str | None = None) -> SkillResult:
        """快捷类方法：一行调用技能"""
        instance = cls()
        instance.endpoint = endpoint or instance.endpoint
        instance.token = token or instance.token
        return instance.call(*params)


# ─── 技能注册表 ──────────────────────────────────────

_skills: dict[str, type[Skill]] = {}


def skill(name: str, domain: str, action: str):
    """
    装饰器：将 Skill 子类注册为可发现技能。

    @skill("天气查询", domain="天气", action="查询")
    class WeatherSkill(Skill):
        ...
    """
    def decorator(cls: type[Skill]):
        cls.name = name
        cls.domain = domain
        cls.action = action
        _skills[name] = cls
        return cls
    return decorator


def list_skills() -> dict[str, dict]:
    """列出所有已注册技能"""
    return {
        name: {"domain": s.domain, "action": s.action}
        for name, s in _skills.items()
    }


def get_skill(name: str) -> type[Skill] | None:
    """按名称获取技能类"""
    return _skills.get(name)

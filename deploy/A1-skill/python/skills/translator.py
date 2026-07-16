"""
skills/translator.py — 示例：翻译技能（多指令编排）

展示技能如何编排多个指令调用：先检测语言 → 再翻译 → 最后格式化。
这是"复合技能"的参考实现。
"""

from ..skill import Skill, skill, SkillResult


@skill("智能翻译", domain="翻译", action="翻译")
class TranslatorSkill(Skill):
    """
    智能翻译技能：编排多个指令调用。

    流程:
        1. 调用「翻译;检测」确定源语言
        2. 调用「翻译;翻译」执行翻译
        3. 格式化双语对照结果

    如果某个指令不可用，降级为直接调用「翻译;翻译」（不检测语言）。
    """

    def call(self, *params: str) -> SkillResult:
        if not params:
            return SkillResult(
                success=False,
                text="请提供要翻译的文本和目标语言",
                skill_name=self.name,
            )

        text = params[0]
        target_lang = params[1] if len(params) > 1 else "en"

        # 步骤 1: 检测源语言（可选增强）
        source_lang = self._detect_language(text)

        # 步骤 2: 执行翻译
        directive = f"AI:翻译;翻译,{text},{target_lang}"
        try:
            raw = self._call_endpoint(
                directive,
                endpoint=self.endpoint or "http://localhost:28050/text-cli/cli",
                token=self.token or "",
            )
        except Exception as e:
            return SkillResult(
                success=False,
                text=self.on_error(params, str(e)),
                skill_name=self.name,
                directive=directive,
                error=str(e),
            )

        # 步骤 3: 格式化
        if source_lang:
            formatted = f"[OK] {source_lang} -> {target_lang}\n  {raw}"
        else:
            formatted = f"[OK] ({target_lang}): {raw}"

        return SkillResult(
            success=True,
            text=formatted,
            skill_name=self.name,
            directive=directive,
            raw=raw,
        )

    def _detect_language(self, text: str) -> str | None:
        """
        尝试检测语言（调用额外的指令）。
        如果指令不可用或失败，静默返回 None，不阻断主流程。
        """
        try:
            directive = f"AI:翻译;检测,{text}"
            raw = self._call_endpoint(
                directive,
                endpoint=self.endpoint or "http://localhost:28050/text-cli/cli",
                token=self.token or "",
            )
            return raw.strip()
        except Exception:
            return None  # 非关键步骤，静默降级

    def on_error(self, params: tuple, error: str) -> str:
        return f"抱歉，翻译服务暂时不可用（{error}）"


# ─── 使用示例 ────────────────────────────────────────

if __name__ == "__main__":
    result = TranslatorSkill.run("你好世界", "en")
    print(result.text)

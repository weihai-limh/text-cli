"""i18n 加载器（Phase 重构：key-based 文案表 + lang 驱动）。

设计（docs/i18n_plan_zh.md §4.1）：
- 文案表为**独立 JSON 资源文件**（`i18n/en.json` / `i18n/zh.json`），随 `phase_kernel/` 走；
- 本模块**仅作加载器**（读 JSON + `t()`），**不内嵌 dict**——改文案只改 JSON；
- Python/JS 同构共享同一份 JSON（`js/core.mjs` 同构 `t()`），一份文案两个后端共用。

机制契约（step / rst_err / phase_path）不在此——那些恒英语，非文案。
"""

import json
import os

_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # phase_kernel/
_CACHE = {}


def _load(lang: str) -> dict:
    """按 lang 加载文案表并缓存；文件缺失 → 空 dict（t() 回落不崩）。"""
    if lang not in _CACHE:
        path = os.path.join(_here, "i18n", f"{lang}.json")
        try:
            with open(path, encoding="utf-8") as f:
                _CACHE[lang] = json.load(f)
        except (OSError, ValueError):
            _CACHE[lang] = {}
    return _CACHE[lang]


def t(key: str, lang: str = "zh", **params) -> str:
    """按 lang 取文案并格式化；key/lang 缺失回退 key 本身（不崩）。

    - `t("plan_confirm", lang="en", total=3, summary="...")` → 英文文案格式化。
    - lang 缺 key → 回落 zh；zh 也缺 → 返回 key 字面（可探测漏 key）。
    """
    text = _load(lang).get(key) or _load("zh").get(key) or key
    return text.format(**params) if params else text

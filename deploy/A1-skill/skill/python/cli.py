"""
cli.py — Agent 既有资源 → text-cli 指令 转化工具

核心理念:
    你已经有能力了（函数、API、知识库）。cli.py 让你用最少的代码
    把这些能力包装成 text-cli 标准指令。

最简用法:

    from cli import register

    @register(domain="天气", action="查询", category="工具")
    def weather(params):
        city = params[0]
        return f"{city}: 晴, 20°C"

指令格式:
    AI:领域;动作,参数1,参数2,...
"""

import json
import logging
import sys
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger("text-cli.agent")

# ─── 指令注册表 ───────────────────────────────────────

_registry: dict[str, dict[str, Callable]] = {}
_meta: dict[str, dict[str, dict]] = {}  # domain → action → meta
_package: dict = {}  # package-level meta


def register(
    domain: str,
    action: str,
    *,
    domain_zh: str = "",
    action_zh: str = "",
    name: str = "",
    name_zh: str = "",
    category: str = "",
    description: str = "",
    description_zh: str = "",
    trust: str = "community",
    version: str = "0.1.0",
    requires: dict | None = None,
):
    """
    装饰器：将既有函数注册为 text-cli 指令处理器（SPEC v1.3.2 兼容）。

    @register(
        domain="天气", action="查询",
        domain_zh="天气", action_zh="查询",
        name="Weather Query", name_zh="天气查询",
        category="工具",
        trust="internal",
        version="0.1.0",
        requires={"pip": ["requests"]},
    )
    def query_weather(params: list[str]) -> str:
        return f"{params[0]}: 晴"

    生成的指令: 天气;查询,北京
    """
    def decorator(func: Callable[[list[str]], str]):
        if domain not in _registry:
            _registry[domain] = {}
            _meta[domain] = {}
        _registry[domain][action] = func
        _meta[domain][action] = {
            "domain_zh": domain_zh or domain,
            "action_zh": action_zh or action,
            "description": description or (func.__doc__.split("\n")[0].strip() if func.__doc__ else f"{domain} / {action}"),
            "description_zh": description_zh or description,
            "category": category,
            "trust": trust,
            "version": version,
            "requires": requires or {},
        }
        # 存储包级元数据（首次注册时）
        if not _package:
            _package["name"] = name or ""
            _package["name_zh"] = name_zh or name or ""
        logger.debug("registered: %s;%s → %s", domain, action, func.__name__)
        return func
    return decorator


def set_package_meta(
    package_id: str,
    *,
    package_type: str = "native",
    runtime: str = "python",
    category: str = "",
    trust: str = "community",
    version: str = "0.1.0",
):
    """设置包级元数据（id/type/runtime/category/trust/version）。"""
    _package.update({
        "id": package_id,
        "type": package_type,
        "runtime": runtime,
        "category": category,
        "trust": trust,
        "version": version,
    })


# ─── 协议信封 (SPEC §1.2.2) ─────────────────────────────

def _ok(data: dict) -> dict:
    """构造协议成功信封。pray_rst_types 提升到 rst_types 并从 rst_data 剥离。"""
    rst_types = "text"
    pray = data.pop("pray_rst_types", None)
    if pray and rst_types == "text":
        rst_types = pray
    return {"rst_types": rst_types, "rst_data": data, "rst_err": ""}


def _err(code: str, reason: str = "") -> dict:
    """构造协议错误信封。code 必须是协议闭集错误码（SPEC §1.2.8）。"""
    return {
        "rst_types": "text",
        "rst_data": {"status": "error", "reason": reason or code},
        "rst_err": code,
    }


# ─── 指令分发 ─────────────────────────────────────────

def dispatch(domain: str, action: str, params: list[str]) -> dict:
    """根据领域和动作分发到已注册的处理器，返回协议信封（SPEC §1.2.2）。"""
    actions = _registry.get(domain)
    if not actions:
        return _err("ERR_NOT_FOUND", f"no matching directive: {domain};{action}")
    handler = actions.get(action)
    if not handler:
        return _err("ERR_NOT_FOUND", f"no matching directive: {domain};{action}")
    try:
        result = handler(params)
        # handler 可返回 str（包装为 {result}）或 dict（直接使用）
        if isinstance(result, str):
            return _ok({"status": "ok", "result": result})
        return _ok(result)
    except Exception as e:
        logger.exception("instruction execution exception: %s;%s", domain, action)
        return _err("ERR_EXECUTION", str(e))


# ─── Schema 生成 (SPEC v1.3.2) ──────────────────────────

def generate_schema(package_id: str = "") -> dict:
    """
    从已注册的指令生成 SPEC v1.3.2 兼容的 schema.json。

    包含: id / type / runtime / category / trust / version / directives[].
    """
    from inspect import signature

    pkg_id = package_id or _package.get("id", "agent-directives")

    directives = []
    for domain, actions in _registry.items():
        for action, func in actions.items():
            sig = signature(func)
            meta = _meta.get(domain, {}).get(action, {})
            entry = {
                "domain": domain,
                "domain_zh": meta.get("domain_zh", domain),
                "action": action,
                "action_zh": meta.get("action_zh", action),
                "usage": f"{domain};{action}" + (",{param}" if sig.parameters else ""),
                "usage_zh": f"{meta.get('domain_zh', domain)};{meta.get('action_zh', action)}" + (",{param}" if sig.parameters else ""),
                "description": meta.get("description", f"{domain} / {action}"),
                "description_zh": meta.get("description_zh", meta.get("description", "")),
                "params": [
                    {"name": p.name, "required": p.default is p.empty}
                    for p in sig.parameters.values()
                ] if sig.parameters else [],
                "outputs": meta.get("outputs", ["text"]),
                "estimated_time": meta.get("estimated_time", 500),
            }
            directives.append(entry)

    schema = {
        "id": pkg_id,
        "type": _package.get("type", "native"),
        "name": _package.get("name", pkg_id),
        "name_zh": _package.get("name_zh", _package.get("name", pkg_id)),
        "runtime": _package.get("runtime", "python"),
        "category": _package.get("category", ""),
        "locales": _package.get("locales", ["zh", "en"]),
        "trust": _package.get("trust", "community"),
        "version": _package.get("version", "0.1.0"),
        "description": _package.get("description", ""),
        "description_zh": _package.get("description_zh", _package.get("description", "")),
        "directives": directives,
    }

    # Merge per-directive requires if any directive declares them
    all_requires: dict = {}
    for domain_meta in _meta.values():
        for action_meta in domain_meta.values():
            req = action_meta.get("requires", {})
            for key, val in req.items():
                if key not in all_requires:
                    all_requires[key] = val
    if all_requires:
        schema["requires"] = all_requires

    return schema


def export_schema(package_id: str = "", path: str = "schema.json") -> str:
    """将 SPEC v1.3.2 Schema 写入文件，返回路径。"""
    schema = generate_schema(package_id=package_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    return path


# ─── 命令行入口 ───────────────────────────────────────

def main():
    """
    CLI 入口，加载 handlers/ 目录并支持本地验证。

    python cli.py              # 列出已注册指令
    python cli.py schema        # 生成 Schema
    python cli.py 天气;查询,北京  # 本地分发验证
    """
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")

    # 自动发现 handlers/
    handler_dir = Path(__file__).parent / "handlers"
    if handler_dir.is_dir():
        for f in sorted(handler_dir.glob("*.py")):
            if f.name.startswith("_"):
                continue
            try:
                import importlib.util
                spec = importlib.util.spec_from_file_location(f.stem, str(f))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                logger.info("loaded handler: handlers/%s", f.name)
            except Exception as e:
                logger.warning("load failed %s: %s", f.name, e)

    if len(sys.argv) > 1 and sys.argv[1] == "schema":
        pkg_id = sys.argv[2] if len(sys.argv) > 2 else ""
        path = export_schema(package_id=pkg_id)
        print(f"Schema generated: {path}")
        return

    if len(sys.argv) > 1 and ";" in sys.argv[1]:
        # 本地分发验证: python cli.py 天气;查询,北京
        import re
        raw = sys.argv[1]
        match = re.match(r"^([^;]+);([^,]+)(?:,(.+))?$", raw)
        if match:
            domain = match.group(1).strip()
            action = match.group(2).strip()
            params = [p.strip() for p in (match.group(3) or "").split(",") if p.strip()]
            envelope = dispatch(domain, action, params)
            # 本地验证友好输出
            if envelope["rst_err"]:
                print(f"[{envelope['rst_err']}] {envelope['rst_data'].get('reason', '')}")
            else:
                result = envelope["rst_data"].get("result", envelope["rst_data"])
                print(result)
        else:
            print("invalid directive format")
        return

    # 默认：列出已注册指令
    if _registry:
        for domain, actions in _registry.items():
            for action in actions:
                print(f"  {domain};{action}")
    else:
        print("No directives registered. Create handlers/*.py with @register decorators.")


if __name__ == "__main__":
    main()

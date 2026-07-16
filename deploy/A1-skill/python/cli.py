"""
cli.py — Agent 既有资源 → text-cli 指令 转化工具

核心理念:
    你已经有能力了（函数、API、知识库）。cli.py 让你用最少的代码
    把这些能力包装成 text-cli 标准指令。

最简用法:

    from cli import register, serve

    @register(domain="天气", action="查询", category="工具")
    def weather(params):
        city = params[0]
        return f"{city}: 晴, 20°C"

    serve(package_id="my-weather")  # 启动 HTTP 服务，自动生成 SPEC v1.3 兼容 Schema

指令格式:
    AI:领域;动作,参数1,参数2,...
"""

import json
import logging
import sys
from typing import Callable
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
    category: str = "",
    description: str = "",
    trust: str = "community",
    version: str = "0.1.0",
    requires: dict | None = None,
):
    """
    装饰器：将既有函数注册为 text-cli 指令处理器（SPEC v1.3 兼容）。

    @register(
        domain="天气", action="查询",
        category="工具",
        trust="internal",
        version="0.1.0",
        requires={"pip": ["requests"]},
    )
    def query_weather(params: list[str]) -> str:
        return f"{params[0]}: 晴"

    生成的指令: AI:天气;查询,北京
    """
    def decorator(func: Callable[[list[str]], str]):
        if domain not in _registry:
            _registry[domain] = {}
            _meta[domain] = {}
        _registry[domain][action] = func
        _meta[domain][action] = {
            "description": description or (func.__doc__.split("\n")[0].strip() if func.__doc__ else f"{domain} / {action}"),
            "category": category,
            "trust": trust,
            "version": version,
            "requires": requires or {},
        }
        logger.debug("已注册: AI:%s;%s → %s", domain, action, func.__name__)
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


def dispatch(domain: str, action: str, params: list[str]) -> str:
    """根据领域和动作分发到已注册的处理器。"""
    actions = _registry.get(domain)
    if not actions:
        return f"未找到匹配的指令: {domain};{action}"
    handler = actions.get(action)
    if not handler:
        return f"未找到匹配的指令: {domain};{action}"
    try:
        return handler(params)
    except Exception as e:
        logger.exception("指令执行异常: %s;%s", domain, action)
        return f"指令执行失败: {e}"


# ─── Schema 生成 (SPEC v1.3) ──────────────────────────

def generate_schema(package_id: str = "") -> dict:
    """
    从已注册的指令生成 SPEC v1.3 兼容的 schema.json。

    包含: id / type / runtime / category / trust / version / directives[].
    """
    from inspect import signature

    pkg_id = package_id or _package.get("id", "agent-directives")

    directives = []
    for domain, actions in _registry.items():
        for action, func in actions.items():
            sig = signature(func)
            meta = _meta.get(domain, {}).get(action, {})
            directives.append({
                "domain": domain,
                "action": action,
                "usage": f"AI:{domain};{action}" + (",{参数}" if sig.parameters else ""),
                "description": meta.get("description", f"{domain} / {action}"),
                "params": [
                    {"name": p.name, "required": p.default is p.empty}
                    for p in sig.parameters.values()
                ] if sig.parameters else [],
            })

    schema = {
        "id": pkg_id,
        "type": _package.get("type", "native"),
        "runtime": _package.get("runtime", "python"),
        "category": _package.get("category", ""),
        "trust": _package.get("trust", "community"),
        "version": _package.get("version", "0.1.0"),
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
    """将 SPEC v1.3 Schema 写入文件，返回路径。"""
    schema = generate_schema(package_id=package_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    return path


# ─── 轻量 HTTP 服务 ──────────────────────────────────

def _create_app():
    """创建简易 HTTP 应用（不依赖 FastAPI）。"""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class DirectiveHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/text-cli/cli":
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            prompt = body.get("prompt", "")

            # 解析: AI:领域;动作,参数1,参数2
            import re
            match = re.match(
                r"^\s*AI[:：]([^;]+);([^,]+)(?:,(.+))?\s*$",
                prompt,
            )
            if not match:
                self._respond(400, {"rst_types": "text", "rst_data": {"text": "指令格式无效"}})
                return

            domain = match.group(1).strip()
            action = match.group(2).strip()
            params = [p.strip() for p in (match.group(3) or "").split(",") if p.strip()]

            result = dispatch(domain, action, params)
            self._respond(200, {"rst_types": "text", "rst_data": {"text": result}})

        def do_GET(self):
            if self.path == "/text_cli_schema.json":
                self._respond(200, generate_schema())
            elif self.path == "/health":
                self._respond(200, {"status": "ok"})
            else:
                self.send_error(404)

        def _respond(self, code, data):
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", len(body))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):
            logger.info("%s %s", self.command, self.path)

    return DirectiveHandler


def serve(host: str = "0.0.0.0", port: int = 8000, package_id: str = ""):
    """
    启动轻量 HTTP 指令服务。
    自动生成 SPEC v1.3 Schema 并写入 schema.json。
    """
    from http.server import HTTPServer

    schema_path = export_schema(package_id=package_id)
    directive_count = sum(len(a) for a in _registry.values())
    logger.info("Schema 已生成: %s (%d 条指令, SPEC v1.3)", schema_path, directive_count)

    handler = _create_app()
    server = HTTPServer((host, port), handler)
    logger.info("text-cli Agent 指令服务已启动: http://%s:%s", host, port)
    logger.info("  Schema: http://%s:%s/text_cli_schema.json", host, port)
    logger.info("  调用:   POST http://%s:%s/text-cli/cli", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务已停止")
        server.shutdown()


# ─── 命令行入口 ───────────────────────────────────────

def main():
    """
    CLI 入口，加载 handlers/ 目录并启动服务。

    python cli.py              # 启动服务
    python cli.py schema        # 仅生成 Schema
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
                logger.info("已加载处理器: handlers/%s", f.name)
            except Exception as e:
                logger.warning("加载失败 %s: %s", f.name, e)

    if len(sys.argv) > 1 and sys.argv[1] == "schema":
        pkg_id = sys.argv[2] if len(sys.argv) > 2 else ""
        path = export_schema(package_id=pkg_id)
        print(f"Schema 已生成: {path}")
        return

    serve()


if __name__ == "__main__":
    main()

"""
cli.py — Agent 既有资源 → text-cli 指令 转化工具

核心理念:
    你已经有能力了（函数、API、知识库）。cli.py 让你用最少的代码
    把这些能力包装成 text-cli 标准指令。

最简用法:

    from cli import register, serve

    @register("天气", "查询")
    def weather(params):
        city = params[0]
        return f"{city}: 晴, 20°C"

    serve()  # 启动 HTTP 服务，自动生成 Schema

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


def register(domain: str, action: str):
    """
    装饰器：将既有函数注册为 text-cli 指令处理器。

    @register("天气", "查询")
    def query_weather(params: list[str]) -> str:
        return f"{params[0]}: 晴"

    生成的指令: AI:天气;查询,北京
    """

    def decorator(func: Callable[[list[str]], str]):
        if domain not in _registry:
            _registry[domain] = {}
        _registry[domain][action] = func
        logger.debug("已注册: AI:%s;%s → %s", domain, action, func.__name__)
        return func

    return decorator


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


# ─── Schema 生成 ──────────────────────────────────────

def generate_schema() -> dict:
    """
    从已注册的指令自动生成 Schema JSON。
    可发布到 /text_cli_schema.json 供其他 Agent 发现。
    """
    from inspect import signature, getdoc

    schema = {}
    for domain, actions in _registry.items():
        schema[domain] = {}
        for action, func in actions.items():
            sig = signature(func)
            param_count = len(sig.parameters)
            doc = getdoc(func) or ""
            schema[domain][action] = {
                "description": doc.split("\n")[0] if doc else f"{domain} / {action}",
                "params": param_count,
            }
    return schema


def export_schema(path: str = "text_cli_schema.json") -> str:
    """将 Schema 写入文件，返回路径。"""
    schema = generate_schema()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    return path


# ─── 轻量 HTTP 服务 ──────────────────────────────────

def _create_app():
    """创建简易 HTTP 应用（不依赖 FastAPI）。"""
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class DirectiveHandler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/cli/text_cli":
                self.send_error(404)
                return

            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length))
            prompt = body.get("prompt", "")

            # 简易解析
            import re
            match = re.match(r"^\s*指令[：:]([^;]+);([^,]+)(?:,(.+))?\s*$", prompt)
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


def serve(host: str = "0.0.0.0", port: int = 8000):
    """
    启动轻量 HTTP 指令服务。
    自动生成 Schema 并写入 text_cli_schema.json。
    """
    from http.server import HTTPServer

    schema_path = export_schema()
    logger.info("Schema 已生成: %s (%d 条指令)", schema_path, sum(len(a) for a in _registry.values()))

    handler = _create_app()
    server = HTTPServer((host, port), handler)
    logger.info("text-cli Agent 指令服务已启动: http://%s:%s", host, port)
    logger.info("  Schema: http://%s:%s/text_cli_schema.json", host, port)
    logger.info("  调用:   POST http://%s:%s/cli/text_cli", host, port)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("服务已停止")
        server.shutdown()


# ─── 命令行入口 ───────────────────────────────────────

def main():
    """
    CLI 入口，加载 handlers/ 目录并启动服务。

    python -m cli          # 启动服务
    python -m cli schema   # 仅生成 Schema
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # 自动发现 handlers/
    handler_dir = Path(__file__).parent / "handlers"
    if handler_dir.is_dir():
        for f in sorted(handler_dir.glob("*.py")):
            if f.name.startswith("_"):
                continue
            module_name = f.stem
            try:
                __import__(f"cli.python.handlers.{module_name}")
                logger.info("已加载处理器: handlers/%s", f.name)
            except Exception as e:
                logger.warning("加载失败 %s: %s", f.name, e)

    if len(sys.argv) > 1 and sys.argv[1] == "schema":
        path = export_schema()
        print(f"Schema 已生成: {path}")
        return

    serve()


if __name__ == "__main__":
    main()

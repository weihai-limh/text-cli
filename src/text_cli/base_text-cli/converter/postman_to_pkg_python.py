"""
postman_to_pkg.py — 从 Postman Collection 生成 webapi 指令包 **脚手架**。
输出 schema.json 框架 + handler.py 桩代码，不含完整业务逻辑。

Usage:
    python postman_to_pkg.py collection.json [--out ./my-package/]

Postman Collection → schema.json + handler.py 骨架
拿到骨架后请参考 package-dev-guide_zh.md 补全业务逻辑。
"""

import argparse
import json
import re
import sys
from pathlib import Path

# ── helpers ─────────────────────────────────────────

def _safe_id(name: str) -> str:
    """Convert a name to a safe package id."""
    return re.sub(r"[^a-z0-9-]", "", name.lower().replace(" ", "-").replace("_", "-"))


def _safe_domain(name: str) -> str:
    """Convert collection name to a safe directive domain."""
    domain = _safe_id(name)
    # Postman collection names often have spaces → keep it simple
    return domain[:20] if len(domain) > 20 else domain


def _safe_action(name: str) -> str:
    """Convert an API endpoint name to a safe action name."""
    return _safe_id(name)


def _safe_func(name: str, action: str) -> str:
    """Generate a safe Python function name."""
    return f"{_safe_id(name)}_{_safe_id(action)}".replace("-", "_")


def _extract_path_params(url: str) -> list[str]:
    """Extract path parameters like :id or {{id}} from a URL."""
    params = []
    for match in re.finditer(r":([a-zA-Z0-9_]+)|{{([a-zA-Z0-9_]+)}}", url):
        params.append(match.group(1) or match.group(2))
    return params


def _extract_query_params(raw_url: str, pm_vars: dict) -> list[dict]:
    """Extract query parameters from the raw URL."""
    if "?" not in raw_url:
        return []
    qs = raw_url.split("?")[1]
    params = []
    for pair in qs.split("&"):
        if "=" in pair:
            name, val = pair.split("=", 1)
            name = re.sub(r"{{(.+)}}", r"\1", name).strip()
            val = re.sub(r"{{(.+)}}", r"\1", val).strip()
            default = pm_vars.get(val, val) if val else ""
            params.append({"name": name, "default": default})
    return params


def _format_list(items: list[str], indent: int = 0) -> str:
    """Format a Python list of strings."""
    if not items:
        return "[]"
    prefix = " " * indent
    inner = ",\n".join(f'{prefix}    "{item}"' for item in items)
    return f"[\n{inner},\n{prefix}]"


def _parse_url(raw: str, pm_vars: dict) -> dict:
    """Parse a Postman request URL into components."""
    # Resolve Postman variables
    resolved = raw
    for match in re.finditer(r"{{(.+?)}}", resolved):
        var_name = match.group(1)
        resolved = resolved.replace(match.group(0), pm_vars.get(var_name, f"{{{{{var_name}}}}}"))

    path = resolved
    query = ""
    if "?" in path:
        path, query = path.split("?", 1)

    url_params = _extract_path_params(raw)
    query_params = _extract_query_params(raw, pm_vars)

    # Clean path — keep only the path part (strip protocol + host)
    if "://" in path:
        path = path.split("/", 3)[-1] if len(path.split("/", 3)) > 3 else ""
        path = "/" + path

    return {
        "path": path,
        "url_params": url_params,
        "query_params": query_params,
        "query_raw": query,
    }


# ── item processing ─────────────────────────────────

def _process_item(item: dict, base_url: str, pm_vars: dict) -> dict | None:
    """Process a single Postman Collection item into a directive entry."""
    if "item" in item:
        return None  # skip sub-folders

    request = item.get("request", {})
    if not request:
        return None

    method = request.get("method", "GET")
    url_info = _parse_url(
        request.get("url", {}).get("raw", ""),
        pm_vars,
    )

    # Extract headers (for auth hints)
    headers = {}
    for h in request.get("header", []):
        key = h.get("key", "")
        val = h.get("value", "")
        if key and val:
            headers[key] = val

    action = _safe_action(item.get("name", "unknown"))
    params = [*url_info["url_params"], *(q["name"] for q in url_info["query_params"])]

    return {
        "name": item.get("name", "Unknown"),
        "action": action,
        "method": method,
        "path": url_info["path"],
        "params": params,
        "url_params": url_info["url_params"],
        "query_params": url_info["query_params"],
        "has_body": bool(request.get("body")),
        "body_raw": request.get("body", {}).get("raw", "") if request.get("body") else "",
        "has_auth": bool(headers.get("Authorization") or headers.get("x-api-key", headers.get("api-key", ""))),
        "auth_header": headers.get("Authorization", "") or headers.get("x-api-key", "") or headers.get("api-key", ""),
    }


# ── generator ───────────────────────────────────────

def _generate_schema(domain: str, items: list[dict], pkg_name: str) -> str:
    """Generate schema.json content."""
    directives = []
    for item in items:
        params_desc = {}
        for p in item["params"]:
            if p in item["url_params"]:
                params_desc[p] = "URL path parameter"
            elif any(q["name"] == p for q in item["query_params"]):
                params_desc[p] = "Query parameter"
            else:
                params_desc[p] = ""

        # Path params are required (<...>); query params are optional ([...]).
        usage_parts = [f"<{p}>" if p in item["url_params"] else f"[{p}]"
                       for p in item["params"]]

        directives.append({
            "domain": domain,
            "domain_zh": item["name"],
            "action": item["action"],
            "action_zh": item["name"],
            "usage": f"{domain};{item['action']},{','.join(usage_parts)}" if usage_parts else f"{domain};{item['action']}",
            "usage_zh": f"{item['name']};{item['action']},{','.join(usage_parts)}" if usage_parts else f"{item['name']};{item['action']}",
            "description": f"{item['name']} — {item['method']} {item['path']}",
            "description_zh": f"{item['name']} — {item['method']} {item['path']}",
            "params": item["params"],
            "params_desc": params_desc,
        })

    return json.dumps({
        "id": _safe_id(pkg_name),
        "name": pkg_name,
        "name_zh": pkg_name,
        "version": "0.1.0",
        "description": f"Web API instruction package generated from Postman collection '{pkg_name}'.",
        "description_zh": f"由 Postman 集合 '{pkg_name}' 生成的 Web API 指令包。",
        "runtime": "python",
        "type": "native",
        "category": "webapi",
        "locales": ["zh", "en"],
        "trust": "community",
        "directives": directives,
    }, ensure_ascii=False, indent=2)


def _generate_handler(domain: str, base_url: str, items: list[dict], pkg_name: str) -> str:
    """Generate handler.py content."""
    functions = []
    for item in items:
        params = item["params"]
        param_extract = ""
        if params:
            lines = [f"    {p} = params[{i}] if len(params) > {i} else \"\""
                     for i, p in enumerate(params)]
            param_extract = "\n".join(lines)

        body_build = ""
        if item["has_body"]:
            body_build = "    body = json.loads(params[-1]) if params else {}"

        alias_args = ""
        if item.get("action_zh"):
            alias_args = f', domain_alias="{item["action_zh"]}"'

        functions.append(f"""@directive("{domain}", "{item['action']}"{alias_args})
def {_safe_func(domain, item['action'])}(params: list[str]) -> str:
    \"\"\"{item['name']} — {item['method']} {item['path']}\"\"\"
    method = "{item['method']}"
    path = "{item['path']}"
{param_extract}
{body_build}
    return _api_call(method, path{", headers=headers" if item.get("has_auth") else ""}{", body=body" if item["has_body"] else ""})
""")

    return f'''"""
{pkg_name} — auto-generated webapi instruction handler.

Generated by postman-to-pkg converter. Review and adjust:
  - TODO: Verify {base_url} is correct
  - TODO: Add API key to config or environment variable
  - TODO: Test each endpoint manually
  - TODO: Remove unused directives
"""

import json
import urllib.request
import urllib.error

from core.registry import directive

_BASE_URL = "{base_url}"

# TODO: Set your API key — NEVER commit to version control
_API_KEY = "YOUR_API_KEY_HERE"

# TODO: Custom headers (e.g. Authorization: Bearer {{_API_KEY}})
headers = {{}}


def _api_call(method: str, path: str, headers: dict = None,
              body: dict = None) -> str:
    """Shared HTTP client for all directives."""
    url = _BASE_URL + path
    hdrs = {{**(headers or {{}})}} 
    hdrs.setdefault("Content-Type", "application/json")
    data = json.dumps(body).encode() if body else None

    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.dumps(
                {{"status": "ok", "result": json.loads(resp.read())}},
                ensure_ascii=False,
            )
    except urllib.error.HTTPError as e:
        return json.dumps(
            {{"status": "error", "code": e.code, "reason": e.reason}},
            ensure_ascii=False,
        )


{"".join(functions)}
'''


# ── main ────────────────────────────────────────────

def convert(collection_path: str, output_dir: str):
    """Convert a Postman Collection JSON to a text-cli instruction package."""
    with open(collection_path, "r", encoding="utf-8") as f:
        collection = json.load(f)

    info = collection.get("info", {})
    pkg_name = info.get("name", Path(collection_path).stem)
    domain = _safe_domain(pkg_name)

    # Extract Postman variables
    pm_vars = {}
    for v in collection.get("variable", []):
        pm_vars[v.get("key", "")] = v.get("value", "")

    # Determine base URL from first item or collection variable
    base_url = pm_vars.get("baseUrl", "")
    items = collection.get("item", [])

    # Process items
    directives = []
    skipped = 0
    for item in items:
        result = _process_item(item, base_url, pm_vars)
        if result:
            directives.append(result)
        else:
            skipped += 1

    if not directives:
        print(f"Error: No convertible API endpoints found in {collection_path}")
        sys.exit(1)

    # Create output directory
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    # Generate schema.json
    schema_content = _generate_schema(domain, directives, pkg_name)
    (out / "schema.json").write_text(schema_content, encoding="utf-8")

    # Generate handler.py
    handler_content = _generate_handler(domain, base_url, directives, pkg_name)
    (out / "handler.py").write_text(handler_content, encoding="utf-8")

    # Summary
    print(f"Postman Collection: {collection_path}")
    print(f"  Collection: {pkg_name}")
    print(f"  Base URL  : {base_url}")
    print(f"  Endpoints : {len(directives)} converted, {skipped} skipped")
    print(f"  Output    : {out}/")
    print(f"    schema.json ({len(schema_content)} bytes)")
    print(f"    handler.py  ({len(handler_content)} bytes)")
    print()
    print("Next steps:")
    print(f"  1. Review {out}/handler.py — add API key, verify URLs")
    print(f"  2. Review {out}/schema.json — adjust descriptions, remove unused directives")
    print(f"  3. cd {out} && python -c \"from textcli_loader import load_package, execute; load_package('.'); print(execute('AI:{domain};{directives[0]['action']},')['rst_data']['text'])\"")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Postman Collection JSON to text-cli instruction package"
    )
    parser.add_argument("collection", help="Path to Postman Collection JSON file")
    parser.add_argument(
        "--out", "-o", default=None,
        help="Output directory (default: ./<collection-name>/)"
    )
    args = parser.parse_args()

    output_dir = args.out or f"./{_safe_id(Path(args.collection).stem)}/"
    convert(args.collection, output_dir)


if __name__ == "__main__":
    main()

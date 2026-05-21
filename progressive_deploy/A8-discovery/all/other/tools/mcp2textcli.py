#!/usr/bin/env python3
"""
mcp2textcli — MCP server → text-cli 指令注册表编译器

管道模型：人工语义 JSON → 标准格式输出

输入:  configs/<server>.json   （人工维护，含语义信息）
输出:  <server>-textcli/
       ├── schema.json         （text_cli_schema 条目）
       ├── registry.json       （semantic-registry 条目）
       └── routing.json        （auxiliary_config 路由条目）

用法:
  python3 mcp2textcli.py configs/tencent-maps.json
"""

import json
import os
import sys
from pathlib import Path


def load_config(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def build_schema_entry(config: dict, tool_name: str, tool: dict) -> dict:
    """生成一条 text_cli_schema 条目"""
    domain_zh = config["domain"]["aliases"]["zh"]
    domain_en = config["domain"]["aliases"]["en"]
    action_zh = tool["aliases"]["zh"]
    action_en = tool["aliases"]["en"]
    action_bilingual = f"{action_en}（{action_zh}）"

    # 按 position 排序参数
    params_sorted = sorted(tool["params"], key=lambda p: p["position"])

    # 参数列表（用英文名，位置顺序）
    param_names = [p["name"] for p in params_sorted]
    param_placeholders = "{" + "},{".join(param_names) + "}" if param_names else ""

    # directive
    directive_en = f"AI:{domain_en};{action_en}"
    directive_zh = f"AI:{domain_zh};{action_zh}"

    # prompt_template（英文规范名 + 英文参数占位符）
    prompt_template = f"AI:{domain_en};{action_en}" + (
        f",{param_placeholders}" if param_names else ""
    )

    # trigger_keywords（中英合并）
    keywords_zh = tool["trigger_keywords"].get("zh", [])
    keywords_en = tool["trigger_keywords"].get("en", [])
    all_keywords = list(dict.fromkeys(keywords_zh + keywords_en))  # 去重保序

    # parameters 数组
    parameters = []
    for p in params_sorted:
        param_entry = {
            "name": p["name"],
            "type": p["type"],
            "description": p.get("alias_zh", p["name"]),
        }
        # 如果有枚举值则加入
        if "enum" in p:
            param_entry["enum"] = p["enum"]
        parameters.append(param_entry)

    return {
        "id": f"{config['server']['name']}_{tool['semantic_id'].replace('.', '_')}",
        "name": action_bilingual,
        "category": domain_zh,
        "description": tool["description"],
        "directive": directive_en,
        "directive_zh": directive_zh,
        "parameters": parameters,
        "prompt_template": prompt_template,
        "trigger_keywords": all_keywords,
        "response_type": "text",
        "routing": {
            "type": "mcp",
            "backends": [
                {
                    "type": "mcp",
                    "server": config["server"]["name"],
                    "tool": tool_name,
                    "adapter": tool["adapter"],
                    "timeout_ms": 30000,
                }
            ]
        }
    }


def build_registry_entries(config: dict) -> dict:
    """生成 semantic-registry domains + actions"""
    domain = config["domain"]
    tools = config["tools"]

    domain_entry = {
        "semantic_id": domain["semantic_id"],
        "aliases": domain["aliases"],
        "description": domain["description"],
    }

    action_entries = {}
    for tool_name, tool in tools.items():
        action_entries[tool["semantic_id"]] = {
            "semantic_id": tool["semantic_id"],
            "aliases": tool["aliases"],
            "description": tool["description"],
        }

    return {
        "domains": [domain_entry],
        "actions": list(action_entries.values()),
    }


def build_routing_entries(config: dict) -> dict:
    """生成 routing 配置条目"""
    tools = config["tools"]
    domain_en = config["domain"]["aliases"]["en"]
    domain_zh = config["domain"]["aliases"]["zh"]

    entries = {}
    for tool_name, tool in tools.items():
        action_en = tool["aliases"]["en"]
        action_zh = tool["aliases"]["zh"]

        # 中英文两条路由指向同一个 MCP tool
        key_en = f"{domain_en};{action_en}"
        key_zh = f"{domain_zh};{action_zh}"

        route = {
            "server": config["server"]["name"],
            "tool": tool_name,
            "adapter": tool["adapter"],
            "timeout_ms": 30000,
        }

        entries[key_en] = route
        if key_en != key_zh:
            entries[key_zh] = route

    return entries


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mcp2textcli.py <config.json> [--out <dir>]")
        sys.exit(1)

    config_path = sys.argv[1]
    out_dir = None
    if '--out' in sys.argv:
        idx = sys.argv.index('--out')
        if idx + 1 < len(sys.argv):
            out_dir = Path(sys.argv[idx + 1])

    config = load_config(config_path)
    server_name = config["server"]["name"]
    if out_dir is None:
        out_dir = Path(__file__).parent / f"{server_name}-textcli"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Schema
    schema = {}
    for tool_name, tool in config["tools"].items():
        entry = build_schema_entry(config, tool_name, tool)
        schema[entry["id"]] = entry

    schema_path = out_dir / "schema.json"
    with open(schema_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)
    print(f"  schema.json   — {len(schema)} 条指令 Schema")

    # 2. Registry
    registry = build_registry_entries(config)
    registry_path = out_dir / "registry.json"
    with open(registry_path, 'w', encoding='utf-8') as f:
        json.dump(registry, f, ensure_ascii=False, indent=2)
    print(f"  registry.json — {len(registry['domains'])} domain + {len(registry['actions'])} actions")

    # 3. Routing
    routing = build_routing_entries(config)
    routing_path = out_dir / "routing.json"
    with open(routing_path, 'w', encoding='utf-8') as f:
        json.dump(routing, f, ensure_ascii=False, indent=2)
    print(f"  routing.json  — {len(routing)} 条路由（中英双向）")

    print(f"\n→ {out_dir}/")


if __name__ == "__main__":
    main()

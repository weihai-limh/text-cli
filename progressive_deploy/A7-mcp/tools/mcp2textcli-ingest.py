#!/usr/bin/env python3
"""
mcp2textcli-ingest — 将编译好的指令注册表合入目标系统

合并策略：
  - schema.json:   id 已存在 → 跳过（不覆盖人工修改）
  - registry.json: semantic_id 已存在 → 跳过
  - routing.json:  打印待处理条目，由人工确认后手动合入

用法:
  python3 mcp2textcli-ingest.py configs/ingest.json
"""

import json
import sys
from pathlib import Path


def load_json(path: str) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def merge_schema(source: dict, target_path: str) -> int:
    """合并 schema，返回新增条目数"""
    target = load_json(target_path)
    added = 0
    for sid, entry in source.items():
        if sid in target:
            continue  # 跳过，不覆盖人工修改
        target[sid] = entry
        added += 1
    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(target, f, ensure_ascii=False, indent=2)
    return added


def merge_registry(source: dict, target_path: str) -> dict:
    """合并 registry，返回 {domains_added, actions_added}"""
    target = load_json(target_path)
    existing_ids = {d["semantic_id"] for d in target.get("domains", [])} | \
                   {a["semantic_id"] for a in target.get("actions", [])}

    added_d = 0
    for d in source.get("domains", []):
        if d["semantic_id"] in existing_ids:
            continue
        target.setdefault("domains", []).append(d)
        existing_ids.add(d["semantic_id"])
        added_d += 1

    added_a = 0
    for a in source.get("actions", []):
        if a["semantic_id"] in existing_ids:
            continue
        target.setdefault("actions", []).append(a)
        existing_ids.add(a["semantic_id"])
        added_a += 1

    with open(target_path, 'w', encoding='utf-8') as f:
        json.dump(target, f, ensure_ascii=False, indent=2)
    return {"domains": added_d, "actions": added_a}


def print_routing_tips(source: dict, source_name: str):
    """打印待人工处理的 routing 条目"""
    print(f"\n  ⚠️  Routing 条目需人工合入（{source_name}）：")
    items = list(source.items())
    # 只显示英文规范名（每条 route 中英双向，英文在先）
    shown = set()
    for key, route in items:
        base = route["tool"]  # 同 tool 的中英文只显示一行
        if base not in shown:
            shown.add(base)
            alias_pair = [k for k, v in items if v["tool"] == base]
            alias_str = " / ".join(alias_pair[:2])
            print(f"    {alias_str}")
            print(f"      → {route['server']}.{route['tool']}  [{route['adapter']}]")
    print(f"    共 {len(shown)} 条路由待确认")


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 mcp2textcli-ingest.py <ingest-config.json>")
        sys.exit(1)

    config_path = sys.argv[1]
    cfg = load_json(config_path)
    base_dir = Path(__file__).parent

    sources = cfg.get("sources", [])
    targets_schema = cfg.get("targets", {}).get("schema", [])
    targets_registry = cfg.get("targets", {}).get("registry", [])

    for src_name in sources:
        src_dir = base_dir / f"{src_name}-textcli"
        schema_path = src_dir / "schema.json"
        registry_path = src_dir / "registry.json"
        routing_path = src_dir / "routing.json"

        if not schema_path.exists():
            print(f"  ⚠️  {src_dir} 不存在，跳过")
            continue

        schema_src = load_json(str(schema_path))
        registry_src = load_json(str(registry_path))
        routing_src = load_json(str(routing_path))

        print(f"\n📦 {src_name} ({len(schema_src)} 条指令)")

        # Schema 合并
        for tp in targets_schema:
            n = merge_schema(schema_src, tp)
            print(f"  → schema: {tp.split('/')[-1]}  +{n} 条")

        # Registry 合并
        for tp in targets_registry:
            r = merge_registry(registry_src, tp)
            print(f"  → registry: {tp.split('/')[-1]}  +{r['domains']} domains +{r['actions']} actions")

        # Routing 提示
        print_routing_tips(routing_src, src_name)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
build-all.py — 从 add/ 同步到 progressive_deploy 各层 all/ 目录。

语义：
  all/ = (add/ 构建的骨架) + (部署便利层)
  add/ 是骨架真源，all/ 是开箱即用的完整产物。

规则：
  - add/ 中的文件 → 覆盖 all/ 同名路径（后层覆盖前层）
  - all/ 独有的文件 → 保留不动（Dockerfile、预装包、便利脚本等）
  - add/ 已删的 → --check 告警 (warn, 不阻断 CI)

用法：
  python3 tools/build-all.py              # 同步全部
  python3 tools/build-all.py A3           # 仅同步指定层
  python3 tools/build-all.py --check      # CI 校验: errors 阻断, stale 警告
  python3 tools/build-all.py --check A4   # 校验指定层
"""

import argparse
import filecmp
import os
import pathlib
import shutil
import sys

THIS_FILE = pathlib.Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent

LAYER_CHAIN = [
    ("A2", "A2-copilot"),
    ("A3", "A3-service"),
    ("A4", "A4-paths"),
    ("A6", "A6-sql"),
    ("A7", "A7-mcp"),
    ("A8", "A8-discovery"),
    ("A9", "A9-advanced"),
]

ADD_SUBDIRS = {"service", "copilot", "media", "MCPservice", "aggregate", "other"}


def collect_add(project_root: pathlib.Path, layer_name: str) -> dict[str, pathlib.Path]:
    add_dir = project_root / layer_name / "add"
    if not add_dir.is_dir():
        return {}
    files = {}
    for root, dirs, filenames in os.walk(str(add_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(add_dir)
        if rel_dir != pathlib.Path("."):
            top = str(rel_dir).split(os.sep)[0]
            if top not in ADD_SUBDIRS:
                continue
        for fname in filenames:
            rel = str(rel_dir / fname) if rel_dir != pathlib.Path(".") else fname
            files[rel] = root_path / fname
    return files


def resolve_add_files(layer_id: str, layer_name: str,
                      chain: list[tuple[str, str]],
                      project_root: pathlib.Path) -> dict[str, pathlib.Path]:
    accumulated: dict[str, pathlib.Path] = {}
    for lid, lname in chain:
        layer_files = collect_add(project_root, lname)
        accumulated.update(layer_files)
        if lid == layer_id:
            break
    return accumulated


def build_layer(layer_id: str, layer_name: str,
                chain: list[tuple[str, str]],
                project_root: pathlib.Path) -> dict:
    layer_dir = project_root / layer_name
    all_dir = layer_dir / "all"
    all_dir.mkdir(parents=True, exist_ok=True)
    expected = resolve_add_files(layer_id, layer_name, chain, project_root)

    current_add_files: dict[str, pathlib.Path] = {}
    for root, dirs, filenames in os.walk(str(all_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(all_dir)
        if rel_dir != pathlib.Path("."):
            top = str(rel_dir).split(os.sep)[0]
            if top not in ADD_SUBDIRS:
                continue
        for fname in filenames:
            rel = str(rel_dir / fname)
            current_add_files[rel] = root_path / fname

    overlaid = []
    stale = []
    for rel, src in sorted(expected.items()):
        dst = all_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if filecmp.cmp(str(src), str(dst), shallow=False):
                continue
        shutil.copy2(str(src), str(dst))
        overlaid.append(rel)

    for rel in sorted(current_add_files):
        if rel not in expected and not rel.endswith("/.gitkeep"):
            stale.append(rel)

    return {"overlaid": overlaid, "stale": stale, "total_add": len(expected)}


def build_all(project_root: pathlib.Path = PROJECT_ROOT):
    for lid, lname in LAYER_CHAIN:
        r = build_layer(lid, lname, LAYER_CHAIN, project_root)
        parts = [f"{lid}: {r['total_add']} files from add"]
        if r["overlaid"]:
            parts.append(f"{len(r['overlaid'])} overlaid")
        if r["stale"]:
            parts.append(f"⚠ {len(r['stale'])} stale")
        status = "✅" if not r["stale"] else "⚠️"
        print(f"  {status} {', '.join(parts)}")
        for f in r["overlaid"]:
            print(f"     + {f}")
        for f in r["stale"]:
            print(f"     ~ stale: {f}")


def check_layer(layer_id: str, layer_name: str,
                chain: list[tuple[str, str]],
                project_root: pathlib.Path) -> tuple[bool, str, list[str], list[str]]:
    """校验一层。返回 (ok, msg, errors, warnings)。
    errors=missing/diff(阻断), warnings=stale(不阻断)。"""
    layer_dir = project_root / layer_name
    all_dir = layer_dir / "all"
    if not all_dir.is_dir():
        return False, f"{layer_id}: all/ missing", [], []

    expected = resolve_add_files(layer_id, layer_name, chain, project_root)
    errors = []
    warnings = []

    current_add_files: dict[str, pathlib.Path] = {}
    for root, dirs, filenames in os.walk(str(all_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(all_dir)
        if rel_dir != pathlib.Path("."):
            top = str(rel_dir).split(os.sep)[0]
            if top not in ADD_SUBDIRS:
                continue
        for fname in filenames:
            rel = str(rel_dir / fname) if rel_dir != pathlib.Path(".") else fname
            current_add_files[rel] = root_path / fname

    for rel, src in sorted(expected.items()):
        dst = all_dir / rel
        if not dst.is_file():
            errors.append(f"  - missing: {rel}")
        elif not filecmp.cmp(str(src), str(dst), shallow=False):
            errors.append(f"  ~ diff:    {rel}")

    for rel in sorted(current_add_files):
        if rel not in expected and not rel.endswith("/.gitkeep"):
            warnings.append(f"  ! stale:   {rel}")

    has_errors = len(errors) > 0
    has_warnings = len(warnings) > 0

    if has_errors:
        msg = f"{layer_id}: {len(errors)} error(s)"
        if has_warnings:
            msg += f", {len(warnings)} warning(s)"
        return False, msg, errors, warnings
    if has_warnings:
        return True, f"{layer_id}: OK ({len(expected)} files, {len(warnings)} stale)", [], warnings
    return True, f"{layer_id}: OK ({len(expected)} files)", [], []


def check_all(project_root: pathlib.Path = PROJECT_ROOT) -> bool:
    all_ok = True
    for lid, lname in LAYER_CHAIN:
        ok, msg, errors, warnings = check_layer(lid, lname, LAYER_CHAIN, project_root)
        if ok:
            icon = "⚠️" if warnings else "✅"
            print(f"  {icon} {msg}")
            for w in warnings:
                print(w)
        else:
            print(f"  ❌ {msg}")
            for e in errors:
                print(e)
            for w in warnings:
                print(w)
            all_ok = False
    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="从 add/ 同步骨架到 progressive_deploy 各层 all/ 目录"
    )
    parser.add_argument("target", nargs="?", default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()

    project_root = pathlib.Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"错误: 目录不存在 — {project_root}", file=sys.stderr)
        sys.exit(2)

    target_name = None
    if args.target:
        for lid, lname in LAYER_CHAIN:
            if lid == args.target:
                target_name = lname
                break
        if not target_name:
            print(f"错误: 未知层级 — {args.target}", file=sys.stderr)
            sys.exit(2)

    if args.check:
        if args.target:
            ok, msg, errors, warnings = check_layer(
                args.target, target_name, LAYER_CHAIN, project_root)
            if ok:
                icon = "⚠️" if warnings else "✅"
                print(f"{icon} {msg}")
                for w in warnings:
                    print(w)
                sys.exit(0)
            else:
                print(f"❌ {msg}")
                for e in errors:
                    print(e)
                for w in warnings:
                    print(w)
                sys.exit(1)
        else:
            ok = check_all(project_root)
            sys.exit(0 if ok else 1)
    else:
        if args.target:
            r = build_layer(args.target, target_name, LAYER_CHAIN, project_root)
            print(f"✅ {args.target}: {r['total_add']} add files")
            for f in r["overlaid"]:
                print(f"   + {f}")
            for f in r["stale"]:
                print(f"   ~ stale: {f}")
        else:
            build_all(project_root)


if __name__ == "__main__":
    main()

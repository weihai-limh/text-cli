#!/usr/bin/env python3
"""
build-all.py — 从 add/ 同步到 progressive_deploy 各层 all/ 目录。

语义：
  all/ = (add/ 构建的骨架) + (部署便利层)
  add/ 是骨架真源，all/ 是开箱即用的完整产物。

规则：
  - add/ 中的文件 → 覆盖 all/ 同名路径（后层覆盖前层）
  - all/ 独有的文件 → 保留不动（Dockerfile、预装包、便利脚本等）
  - add/ 已删的 → --check 告警（不自动删 all/）

用法：
  python3 tools/build-all.py              # 同步全部
  python3 tools/build-all.py A3           # 仅同步指定层
  python3 tools/build-all.py --check      # CI 校验
  python3 tools/build-all.py --check A4   # 校验指定层
"""

import argparse
import filecmp
import os
import pathlib
import shutil
import sys

# ═══════════════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════════════

THIS_FILE = pathlib.Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent  # progressive_deploy/

# 构建链：A2 → A3 → A4 → A6 → A7 → A8 → A9（A5 独立体系）
LAYER_CHAIN = [
    ("A2", "A2-copilot"),
    ("A3", "A3-service"),
    ("A4", "A4-paths"),
    ("A6", "A6-sql"),
    ("A7", "A7-mcp"),
    ("A8", "A8-discovery"),
    ("A9", "A9-advanced"),
]

# add/ 中参与构建的子目录（顶层其他文件如 README 不参与）
ADD_SUBDIRS = {"service", "copilot", "media", "MCPservice", "aggregate", "other"}


# ═══════════════════════════════════════════════════════════════════
# 文件收集
# ═══════════════════════════════════════════════════════════════════

def collect_add(project_root: pathlib.Path, layer_name: str) -> dict[str, pathlib.Path]:
    """收集一层 add/ 下参与构建的文件 → {相对路径: 源绝对路径}."""
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
    """累积本层及之前所有层的 add/ 文件（后层覆盖前层）。"""
    accumulated: dict[str, pathlib.Path] = {}
    for lid, lname in chain:
        layer_files = collect_add(project_root, lname)
        accumulated.update(layer_files)
        if lid == layer_id:
            break
    return accumulated


# ═══════════════════════════════════════════════════════════════════
# 构建（叠加模式）
# ═══════════════════════════════════════════════════════════════════

def build_layer(layer_id: str, layer_name: str,
                chain: list[tuple[str, str]],
                project_root: pathlib.Path) -> dict:
    """将 add/ 文件覆盖到 all/，保留 all/ 独有文件不动。

    返回 { overlaid: [path, ...], skipped: 0, stale: [path, ...] }
    """
    layer_dir = project_root / layer_name
    all_dir = layer_dir / "all"
    all_dir.mkdir(parents=True, exist_ok=True)

    # 累积本层应生效的 add 文件
    expected = resolve_add_files(layer_id, layer_name, chain, project_root)

    # 找出 all/ 中由 add 管辖的当前文件
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

    # 覆盖 add → all
    for rel, src in sorted(expected.items()):
        dst = all_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if filecmp.cmp(str(src), str(dst), shallow=False):
                continue  # 相同，跳过
        shutil.copy2(str(src), str(dst))
        overlaid.append(rel)

    # 检测过期文件（all 中有但 add 中已删的）
    for rel in sorted(current_add_files):
        if rel not in expected and not rel.endswith("/.gitkeep"):
            stale.append(rel)

    return {
        "overlaid": overlaid,
        "stale": stale,
        "total_add": len(expected),
    }


def build_all(project_root: pathlib.Path = PROJECT_ROOT):
    """同步全部层。"""
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


# ═══════════════════════════════════════════════════════════════════
# CI 校验
# ═══════════════════════════════════════════════════════════════════

def check_layer(layer_id: str, layer_name: str,
                chain: list[tuple[str, str]],
                project_root: pathlib.Path) -> tuple[bool, str, list[str]]:
    """校验一层的 all/ 是否与 add/ 一致。只检查 add 管辖的文件。

    返回 (ok, message, diffs)。
    """
    layer_dir = project_root / layer_name
    all_dir = layer_dir / "all"

    if not all_dir.is_dir():
        return False, f"{layer_id}: all/ 目录不存在", []

    expected = resolve_add_files(layer_id, layer_name, chain, project_root)

    diffs = []

    # 找 all/ 中由 add 管辖的当前文件
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

    # 检查 add 中的文件在 all 中是否存在且一致
    for rel, src in sorted(expected.items()):
        dst = all_dir / rel
        if not dst.is_file():
            diffs.append(f"  - missing: {rel}")
        elif not filecmp.cmp(str(src), str(dst), shallow=False):
            diffs.append(f"  ~ diff:    {rel}")

    # 检查过期文件
    for rel in sorted(current_add_files):
        if rel not in expected and not rel.endswith("/.gitkeep"):
            diffs.append(f"  ! stale:   {rel}")

    if diffs:
        return False, f"{layer_id}: {len(diffs)} mismatch(es)", diffs
    return True, f"{layer_id}: OK ({len(expected)} add files)", []


def check_all(project_root: pathlib.Path = PROJECT_ROOT) -> bool:
    """校验全部层。"""
    all_ok = True
    for lid, lname in LAYER_CHAIN:
        ok, msg, diffs = check_layer(lid, lname, LAYER_CHAIN, project_root)
        if ok:
            print(f"  ✅ {msg}")
        else:
            print(f"  ❌ {msg}")
            for d in diffs:
                print(d)
            all_ok = False
    return all_ok


# ═══════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="从 add/ 同步骨架到 progressive_deploy 各层 all/ 目录"
    )
    parser.add_argument("target", nargs="?", default=None,
                        help="目标层级 (A2-A9)，省略则全部")
    parser.add_argument("--check", action="store_true",
                        help="CI 校验模式")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT),
                        help="progressive_deploy/ 目录路径")
    args = parser.parse_args()

    project_root = pathlib.Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"错误: 目录不存在 — {project_root}", file=sys.stderr)
        sys.exit(2)

    if args.target:
        target_lid = args.target
        target_name = None
        for lid, lname in LAYER_CHAIN:
            if lid == target_lid:
                target_name = lname
                break
        if not target_name:
            print(f"错误: 未知层级 — {target_lid}", file=sys.stderr)
            sys.exit(2)

    if args.check:
        if args.target:
            ok, msg, diffs = check_layer(target_lid, target_name, LAYER_CHAIN, project_root)
            if ok:
                print(f"✅ {msg}")
                sys.exit(0)
            else:
                print(f"❌ {msg}")
                for d in diffs:
                    print(d)
                sys.exit(1)
        else:
            ok = check_all(project_root)
            sys.exit(0 if ok else 1)
    else:
        if args.target:
            r = build_layer(target_lid, target_name, LAYER_CHAIN, project_root)
            print(f"✅ {target_lid}: {r['total_add']} add files")
            for f in r["overlaid"]:
                print(f"   + {f}")
            for f in r["stale"]:
                print(f"   ~ stale: {f}")
        else:
            build_all(project_root)


if __name__ == "__main__":
    main()

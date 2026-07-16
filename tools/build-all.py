#!/usr/bin/env python3
"""
build-all.py — 从 src/skeleton/ 构建 deploy/ 各层完整制品。

语义：
  src/skeleton/{group}/{layer}/ = 骨架真源（开发者只编辑这里）
  deploy/{layer}/ = 完整可部署产物（由本脚本生成）

规则：
  - 真源文件 → 覆盖 deploy/ 同名路径（后层覆盖前层，A2→A9 逐层累积）
  - deploy/ 独有的文件 → 保留不动（Dockerfile、预装包、便利脚本等，通过 .buildignore 保护）
  - 真源已删的 → --check 告警 (warn, 不阻断 CI)

A0/A1 直通模式：不参与覆盖累积，从 src/skeleton/base/ 直接同步到 deploy/。

用法：
  python tools/build-all.py              # 同步全部
  python tools/build-all.py A3           # 仅同步指定层
  python tools/build-all.py --check      # CI 校验: errors 阻断, stale 警告
  python tools/build-all.py --check A4   # 校验指定层
"""

import argparse
import filecmp
import os
import pathlib
import shutil
import sys

THIS_FILE = pathlib.Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent
SKELETON_ROOT = PROJECT_ROOT / "src" / "skeleton"
DEPLOY_ROOT = PROJECT_ROOT / "deploy"

# 骨架累积链：按 group/layer 格式，A2→A9 逐层覆盖
LAYER_CHAIN = [
    ("A2", "copilot/A2-copilot"),
    ("A3", "service/A3-service"),
    ("A4", "service/A4-paths"),
    ("A6", "service/A6-sql"),
    ("A7", "service/A7-mcp"),
    ("A8", "service/A8-discovery"),
    ("A9", "service/A9-advanced"),
]

# A0/A1 直通层：直接从 src/skeleton/base/ → deploy/，不参与覆盖累积
THROUGH_LAYERS = [
    ("A0", "base/A0-protocol"),
    ("A1", "base/A1-skill"),
]

# 骨架层内的子目录白名单（与旧 ADD_SUBDIRS 对应）
SKELETON_SUBDIRS = {"service", "copilot", "media", "MCPservice", "aggregate", "other"}


def _load_buildignore(project_root: pathlib.Path) -> set[str]:
    """加载 .buildignore 文件。格式与 .gitignore 一致。"""
    ignore_file = project_root / ".buildignore"
    if not ignore_file.is_file():
        return set()
    patterns = set()
    with open(ignore_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.add(line)
    return patterns


BUILDIGNORE = _load_buildignore(PROJECT_ROOT)


def _is_protected(rel_path: str) -> bool:
    """检查文件是否受 .buildignore 保护。"""
    for pattern in BUILDIGNORE:
        if rel_path == pattern or rel_path.startswith(pattern.rstrip("/") + "/"):
            return True
    return False


def collect_source(layer_path: str) -> dict[str, pathlib.Path]:
    """从 src/skeleton/{group}/{layer}/ 收集所有真源文件。"""
    source_dir = SKELETON_ROOT / layer_path
    if not source_dir.is_dir():
        return {}
    files = {}
    for root, dirs, filenames in os.walk(str(source_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(source_dir)
        if rel_dir != pathlib.Path("."):
            top = str(rel_dir).split(os.sep)[0]
            if top not in SKELETON_SUBDIRS:
                continue
        for fname in filenames:
            rel = str(rel_dir / fname) if rel_dir != pathlib.Path(".") else fname
            files[rel] = root_path / fname
    return files


def resolve_source_files(layer_id: str, layer_path: str,
                         chain: list[tuple[str, str]]) -> dict[str, pathlib.Path]:
    """按累积链逐层收集真源文件，后层覆盖前层。"""
    accumulated: dict[str, pathlib.Path] = {}
    for lid, lpath in chain:
        layer_files = collect_source(lpath)
        accumulated.update(layer_files)
        if lid == layer_id:
            break
    return accumulated


def build_layer(layer_id: str, layer_path: str,
                chain: list[tuple[str, str]]) -> dict:
    """构建单层产物：真源 → deploy/{layer}/。"""
    layer_name = layer_path.split("/")[-1]
    deploy_dir = DEPLOY_ROOT / layer_name
    deploy_dir.mkdir(parents=True, exist_ok=True)
    expected = resolve_source_files(layer_id, layer_path, chain)

    current_files: dict[str, pathlib.Path] = {}
    for root, dirs, filenames in os.walk(str(deploy_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(deploy_dir)
        if rel_dir != pathlib.Path("."):
            top = str(rel_dir).split(os.sep)[0]
            if top not in SKELETON_SUBDIRS:
                continue
        for fname in filenames:
            rel = str(rel_dir / fname)
            current_files[rel] = root_path / fname

    overlaid = []
    stale = []
    for rel, src in sorted(expected.items()):
        if _is_protected(rel):
            continue
        dst = deploy_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if filecmp.cmp(str(src), str(dst), shallow=False):
                continue
        shutil.copy2(str(src), str(dst))
        overlaid.append(rel)

    for rel in sorted(current_files):
        if rel not in expected and not rel.endswith("/.gitkeep"):
            if _is_protected(rel):
                continue
            stale.append(rel)

    return {"overlaid": overlaid, "stale": stale, "total_source": len(expected)}


def build_through_layer(layer_id: str, layer_path: str) -> dict:
    """直通构建：src/skeleton/base/{layer}/ → deploy/{layer}/。不参与覆盖累积。"""
    source_dir = SKELETON_ROOT / layer_path
    layer_name = layer_path.split("/")[-1]
    deploy_dir = DEPLOY_ROOT / layer_name
    deploy_dir.mkdir(parents=True, exist_ok=True)

    if not source_dir.is_dir():
        return {"overlaid": [], "stale": [], "total_source": 0}

    expected: dict[str, pathlib.Path] = {}
    for root, dirs, filenames in os.walk(str(source_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(source_dir)
        for fname in filenames:
            rel = str(rel_dir / fname) if rel_dir != pathlib.Path(".") else fname
            expected[rel] = root_path / fname

    overlaid = []
    for rel, src in sorted(expected.items()):
        if _is_protected(rel):
            continue
        dst = deploy_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            if filecmp.cmp(str(src), str(dst), shallow=False):
                continue
        shutil.copy2(str(src), str(dst))
        overlaid.append(rel)

    return {"overlaid": overlaid, "stale": [], "total_source": len(expected)}


def build_all():
    """构建全部层。"""
    print("骨架层（覆盖累积）：")
    for lid, lpath in LAYER_CHAIN:
        r = build_layer(lid, lpath, LAYER_CHAIN)
        parts = [f"{lid}: {r['total_source']} source files"]
        if r["overlaid"]:
            parts.append(f"{len(r['overlaid'])} overlaid")
        if r["stale"]:
            parts.append(f"[WARN] {len(r['stale'])} stale")
        status = "[OK]" if not r["stale"] else "[WARN]️"
        print(f"  {status} {', '.join(parts)}")
        for f in r["overlaid"]:
            print(f"     + {f}")
        for f in r["stale"]:
            print(f"     ~ stale: {f}")

    print("直通层（A0/A1）：")
    for lid, lpath in THROUGH_LAYERS:
        r = build_through_layer(lid, lpath)
        parts = [f"{lid}: {r['total_source']} source files"]
        if r["overlaid"]:
            parts.append(f"{len(r['overlaid'])} overlaid")
        status = "[OK]"
        print(f"  {status} {', '.join(parts)}")
        for f in r["overlaid"]:
            print(f"     + {f}")


def check_layer(layer_id: str, layer_path: str,
                chain: list[tuple[str, str]]) -> tuple[bool, str, list[str], list[str]]:
    """校验一层。返回 (ok, msg, errors, warnings)。"""
    layer_name = layer_path.split("/")[-1]
    deploy_dir = DEPLOY_ROOT / layer_name
    if not deploy_dir.is_dir():
        return False, f"{layer_id}: deploy/{layer_name} missing", [], []

    expected = resolve_source_files(layer_id, layer_path, chain)
    errors = []
    warnings = []

    current_files: dict[str, pathlib.Path] = {}
    for root, dirs, filenames in os.walk(str(deploy_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(deploy_dir)
        if rel_dir != pathlib.Path("."):
            top = str(rel_dir).split(os.sep)[0]
            if top not in SKELETON_SUBDIRS:
                continue
        for fname in filenames:
            rel = str(rel_dir / fname) if rel_dir != pathlib.Path(".") else fname
            current_files[rel] = root_path / fname

    for rel, src in sorted(expected.items()):
        if _is_protected(rel):
            continue
        dst = deploy_dir / rel
        if not dst.is_file():
            errors.append(f"  - missing: {rel}")
        elif not filecmp.cmp(str(src), str(dst), shallow=False):
            errors.append(f"  ~ diff:    {rel}")

    for rel in sorted(current_files):
        if rel not in expected and not rel.endswith("/.gitkeep"):
            if _is_protected(rel):
                continue
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


def check_through_layer(layer_id: str, layer_path: str) -> tuple[bool, str, list[str], list[str]]:
    """校验直通层。"""
    source_dir = SKELETON_ROOT / layer_path
    layer_name = layer_path.split("/")[-1]
    deploy_dir = DEPLOY_ROOT / layer_name

    if not deploy_dir.is_dir():
        return False, f"{layer_id}: deploy/{layer_name} missing", [], []
    if not source_dir.is_dir():
        return True, f"{layer_id}: no source (skip)", [], []

    expected: dict[str, pathlib.Path] = {}
    for root, dirs, filenames in os.walk(str(source_dir)):
        root_path = pathlib.Path(root)
        rel_dir = root_path.relative_to(source_dir)
        for fname in filenames:
            rel = str(rel_dir / fname) if rel_dir != pathlib.Path(".") else fname
            expected[rel] = root_path / fname

    errors = []
    for rel, src in sorted(expected.items()):
        if _is_protected(rel):
            continue
        dst = deploy_dir / rel
        if not dst.is_file():
            errors.append(f"  - missing: {rel}")
        elif not filecmp.cmp(str(src), str(dst), shallow=False):
            errors.append(f"  ~ diff:    {rel}")

    if errors:
        return False, f"{layer_id}: {len(errors)} error(s)", errors, []
    return True, f"{layer_id}: OK ({len(expected)} files)", [], []


def check_all() -> bool:
    """校验全部层。"""
    all_ok = True
    print("骨架层：")
    for lid, lpath in LAYER_CHAIN:
        ok, msg, errors, warnings = check_layer(lid, lpath, LAYER_CHAIN)
        if ok:
            icon = "[WARN]️" if warnings else "[OK]"
            print(f"  {icon} {msg}")
            for w in warnings:
                print(w)
        else:
            print(f"  [ERR] {msg}")
            for e in errors:
                print(e)
            for w in warnings:
                print(w)
            all_ok = False

    print("直通层：")
    for lid, lpath in THROUGH_LAYERS:
        ok, msg, errors, warnings = check_through_layer(lid, lpath)
        if ok:
            print(f"  [OK] {msg}")
        else:
            print(f"  [ERR] {msg}")
            for e in errors:
                print(e)
            all_ok = False

    return all_ok


def main():
    parser = argparse.ArgumentParser(
        description="从 src/skeleton/ 构建 deploy/ 各层完整制品"
    )
    parser.add_argument("target", nargs="?", default=None)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--project-root", default=str(PROJECT_ROOT))
    args = parser.parse_args()

    project_root = pathlib.Path(args.project_root).resolve()
    if not project_root.is_dir():
        print(f"错误: 目录不存在 — {project_root}", file=sys.stderr)
        sys.exit(2)

    # 更新全局路径为指定项目根
    global SKELETON_ROOT, DEPLOY_ROOT, BUILDIGNORE
    SKELETON_ROOT = project_root / "src" / "skeleton"
    DEPLOY_ROOT = project_root / "deploy"
    BUILDIGNORE = _load_buildignore(project_root)

    target_path = None
    target_is_through = False
    if args.target:
        for lid, lpath in LAYER_CHAIN:
            if lid == args.target:
                target_path = lpath
                break
        if not target_path:
            for lid, lpath in THROUGH_LAYERS:
                if lid == args.target:
                    target_path = lpath
                    target_is_through = True
                    break
        if not target_path:
            print(f"错误: 未知层级 — {args.target}", file=sys.stderr)
            sys.exit(2)

    if args.check:
        if args.target:
            if target_is_through:
                ok, msg, errors, warnings = check_through_layer(args.target, target_path)
            else:
                ok, msg, errors, warnings = check_layer(args.target, target_path, LAYER_CHAIN)
            if ok:
                icon = "[WARN]️" if warnings else "[OK]"
                print(f"{icon} {msg}")
                for w in warnings:
                    print(w)
                sys.exit(0)
            else:
                print(f"[ERR] {msg}")
                for e in errors:
                    print(e)
                for w in warnings:
                    print(w)
                sys.exit(1)
        else:
            ok = check_all()
            sys.exit(0 if ok else 1)
    else:
        if args.target:
            if target_is_through:
                r = build_through_layer(args.target, target_path)
            else:
                r = build_layer(args.target, target_path, LAYER_CHAIN)
            print(f"[OK] {args.target}: {r['total_source']} source files")
            for f in r["overlaid"]:
                print(f"   + {f}")
            for f in r["stale"]:
                print(f"   ~ stale: {f}")
        else:
            build_all()


if __name__ == "__main__":
    main()

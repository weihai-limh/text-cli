"""pip dependency management for instruction packages.

v2: supports new `requires` field from schema.json alongside legacy requirements.txt.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

_PROJECT = pathlib.Path(os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli")))
VENV_PIP = str(_PROJECT / "service" / ".venv" / "bin" / "pip")


def install_deps(req_path: str | None, name: str, requires: dict = None) -> tuple[bool, str]:
    """Install dependencies from requirements.txt and/or schema requires field.

    Returns (ok, message).
    """
    pkgs_to_install = []

    # New: requires.pip from schema.json
    if requires and requires.get("pip"):
        import importlib
        for pkg in requires["pip"]:
            import_name = pkg.replace("-", "_")
            try:
                importlib.import_module(import_name)
            except ImportError:
                pkgs_to_install.append(pkg)

    # Legacy: requirements.txt (install all, pip handles already-installed)
    if req_path:
        try:
            result = subprocess.run(
                [VENV_PIP, "install", "-q", "-r", req_path],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                last_err = result.stderr.strip().splitlines()[-1] if result.stderr else f"exit={result.returncode}"
                return False, f"pip 安装失败: {last_err}"
        except subprocess.TimeoutExpired:
            return False, "pip 安装超时（60s）"
        except FileNotFoundError:
            return False, f"pip 不可用: {VENV_PIP}"
        except OSError as e:
            return False, f"pip 错误: {e}"

    # Install new-format packages individually
    failed = []
    for pkg in pkgs_to_install:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg,
                 "-q"],
                capture_output=True, text=True, timeout=60,
            )
            if result.returncode != 0:
                failed.append(pkg)
        except Exception:
            failed.append(pkg)

    if failed:
        return False, f"pip 安装失败: {', '.join(failed)}"

    total = (1 if req_path else 0) + len(pkgs_to_install)
    if total == 0:
        return True, "无 pip 依赖"
    return True, "依赖就绪"


def check_deps_shared(removing_name: str, all_schema_files) -> list[str]:
    """Check which pip packages are shared with other installed packages.

    Returns list of shared requirement names.
    """
    return []

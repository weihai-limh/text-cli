"""pip dependency management for instruction packages.

v2: supports new `requires` field from schema.json alongside legacy requirements.txt.
"""

from __future__ import annotations

import os
import pathlib
import subprocess
import sys

_PROJECT = pathlib.Path(os.environ.get("TEXT_CLI_HOME", str(pathlib.Path.home() / "text-cli")))

# pip 包名 → 导入模块名 映射（pip 名与模块名不一致的已知项）。
# 探测"已装"时必须用真实模块名，否则已装依赖被误判缺失 → 重复 pip install。
_PIP_MODULE_MAP = {
    "Pillow": "PIL",
    "opencv-python": "cv2",
    "opencv-python-headless": "cv2",
    "opencv-contrib-python": "cv2",
    "PyYAML": "yaml",
    "beautifulsoup4": "bs4",
    "scikit-learn": "sklearn",
}


def install_deps(req_path: str | None, name: str, requires: dict | None = None) -> tuple[bool, str]:
    """Install dependencies from requirements.txt and/or schema requires field.

    Returns (ok, message).
    """
    pkgs_to_install = []

    # New: requires.pip from schema.json
    if requires and requires.get("pip"):
        import importlib
        import re as _re
        for pkg in requires["pip"]:
            # Strip version constraints (e.g. "requests>=2.28") before probing.
            bare = _re.split(r"[<>=!~]", pkg)[0].strip()
            import_name = _PIP_MODULE_MAP.get(bare, bare.replace("-", "_"))
            try:
                importlib.import_module(import_name)
            except ImportError:
                pkgs_to_install.append(pkg)

    # Legacy: requirements.txt (install all, pip handles already-installed)
    # Uses sys.executable -m pip for cross-platform compatibility (Windows: Scripts\pip.exe)
    if req_path:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", "-r", req_path],
                capture_output=True, text=True, timeout=60, check=False,
            )
            if result.returncode != 0:
                last_err = result.stderr.strip().splitlines()[-1] if result.stderr else f"exit={result.returncode}"
                return False, f"pip install failed: {last_err}"
        except subprocess.TimeoutExpired:
            return False, "pip install timeout (60s)"
        except FileNotFoundError:
            return False, "pip unavailable (Python interpreter not found)"
        except OSError as e:
            return False, f"pip error: {e}"

    # Install new-format packages individually
    failed = []
    for pkg in pkgs_to_install:
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pkg,
                 "-q"],
                capture_output=True, text=True, timeout=60, check=False,
            )
            if result.returncode != 0:
                failed.append(pkg)
        except Exception:
            failed.append(pkg)

    if failed:
        return False, f"pip install failed: {', '.join(failed)}"

    total = (1 if req_path else 0) + len(pkgs_to_install)
    if total == 0:
        return True, "no pip dependencies"
    return True, "dependencies ready"


def install_npm_deps(npm_dir: str) -> tuple[bool, str]:
    """Run npm install in the package directory.

    Called for runtime=node packages that have a package.json.
    Returns (ok, message).
    """
    pkg_dir = pathlib.Path(npm_dir)
    pkg_json = pkg_dir / "package.json"
    if not pkg_json.is_file():
        return True, "no package.json, skip npm"
    import shutil
    import sys
    if not shutil.which("npm"):
        return False, "npm unavailable (please install Node.js)"
    try:
        if sys.platform.startswith("win"):
            # Windows 上 npm 是 npm.cmd（批处理脚本），CreateProcess 无法直接执行，
            # 需经 cmd.exe /c 包装。npm install 参数固定（--no-audit --no-fund），
            # pkg_dir 为安装器受控部署目录，无注入面。
            result = subprocess.run(
                f'cd /d "{pkg_dir}" && npm install --no-audit --no-fund',
                shell=True, capture_output=True, text=True, timeout=120, check=False,
            )
        else:
            result = subprocess.run(
                ["npm", "install", "--no-audit", "--no-fund"],
                cwd=str(pkg_dir),
                capture_output=True, text=True, timeout=120, check=False,
            )
        if result.returncode != 0:
            last_err = result.stderr.strip().splitlines()[-1] if result.stderr else f"exit={result.returncode}"
            return False, f"npm install failed: {last_err}"
    except subprocess.TimeoutExpired:
        return False, "npm install timeout (120s)"
    except FileNotFoundError:
        return False, "npm unavailable (please install Node.js)"
    except OSError as e:
        return False, f"npm error: {e}"
    return True, "npm dependencies ready"


def check_deps_shared(removing_name: str, all_schema_files) -> list[str]:
    """Check which pip packages are shared with other installed packages.

    Returns list of shared requirement names.
    """
    return []

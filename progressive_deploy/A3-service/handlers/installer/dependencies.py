"""pip dependency management for instruction packages."""

from __future__ import annotations

import subprocess

VENV_PIP = "/path/to/text-cli/service/.venv/bin/pip"


def install_deps(req_path: str | None, name: str) -> tuple[bool, str]:
    """Install pip dependencies from requirements.txt.

    Returns (ok, message).
    """
    if req_path is None:
        return True, "无 pip 依赖"

    try:
        result = subprocess.run(
            [VENV_PIP, "install", "-q", "-r", req_path],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            return True, "依赖就绪"
        return False, f"pip 安装失败: {result.stderr.strip().splitlines()[-1] if result.stderr else 'exit=' + str(result.returncode)}"
    except subprocess.TimeoutExpired:
        return False, "pip 安装超时（60s）"
    except FileNotFoundError:
        return False, f"pip 不可用: {VENV_PIP}"
    except OSError as e:
        return False, f"pip 错误: {e}"


def check_deps_shared(removing_name: str, all_schema_files) -> list[str]:
    """Check which pip packages are shared with other installed packages.

    Returns list of shared requirement names.
    """
    # For now: simple strategy. Uninstall always removes nothing from pip.
    # Full dependency tracking would need to record per-package pip deps at install time.
    return []

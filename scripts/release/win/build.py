"""
text-cli skeleton-win release builder.

Usage:
    python .dev/release-script/win/build.py              # use VERSION file
    python .dev/release-script/win/build.py --version 0.2.0

Assembles deploy/skeleton-win/text-cli-v{VERSION}/ from:
  - deploy/A9-advanced/service/   (full accumulated service)
  - deploy/A2-copilot/copilot/    (local proxy)
  - .dev/release-script/docs/     (distribution docs)
"""

import argparse
import pathlib
import re
import shutil
import sys


class WinReleaseBuilder:
    def __init__(self, version: str):
        self.version = version
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.release_dir = self.project_root / ".dev" / "release-script"
        self.docs_src = self.release_dir / "docs"
        self.output_parent = self.project_root / "deploy" / "skeleton-win"
        self.output_dir = self.output_parent / f"text-cli-v{self.version}"
        self.service_src = self.project_root / "deploy" / "A9-advanced" / "service"
        self.copilot_src = self.project_root / "deploy" / "A2-copilot" / "copilot"

    def run(self):
        self._check_prerequisites()
        self._clean_old()
        self._copy_service()
        self._copy_copilot()
        self._copy_docs()
        self._generate_start_bat()
        self._clean_descriptors()
        self._package_zip()
        self._report()

    # ------------------------------------------------------------------
    def _check_prerequisites(self):
        """Verify source directories exist."""
        if not self.service_src.is_dir():
            sys.exit(f"[ERR] service source not found: {self.service_src}")
        if not self.copilot_src.is_dir():
            sys.exit(f"[ERR] copilot source not found: {self.copilot_src}")
        if not self.docs_src.is_dir():
            sys.exit(f"[ERR] docs template not found: {self.docs_src}")

    def _clean_old(self):
        """Remove previous version directory."""
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _copy_service(self):
        dst = self.output_dir / "service"
        shutil.copytree(self.service_src, dst)
        print(f"[OK] service  -> {dst.name}")

    def _copy_copilot(self):
        dst = self.output_dir / "copilot"
        shutil.copytree(self.copilot_src, dst)
        print(f"[OK] copilot -> {dst.name}")

    def _copy_docs(self):
        dst = self.output_dir / "docs"
        shutil.copytree(self.docs_src, dst)
        # Replace {VERSION} placeholders
        for doc in dst.iterdir():
            if doc.suffix == ".md":
                text = doc.read_text(encoding="utf-8")
                text = text.replace("{VERSION}", self.version)
                doc.write_text(text, encoding="utf-8")
        count = len(list(dst.iterdir()))
        print(f"[OK] docs    -> {dst.name} ({count} files, VERSION={self.version})")

    def _generate_start_bat(self):
        content = f"""@echo off
chcp 65001 >nul
title text-cli v{self.version}

echo ========================================
echo   text-cli v{self.version} - Windows
echo ========================================
echo.

:: env
if "%TEXT_CLI_HOME%"=="" set "TEXT_CLI_HOME=%~dp0"
echo [OK] TEXT_CLI_HOME = %TEXT_CLI_HOME%

:: python check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERR] Python not installed or not in PATH
    pause
    exit /b 1
)

:: pip deps (one-time)
if not exist "%TEXT_CLI_HOME%.deps_ok" (
    echo [INFO] installing Python deps...
    pip install -r "%TEXT_CLI_HOME%service\\requirements.txt" --quiet
    if %errorlevel% neq 0 (
        echo [ERR] pip install failed
        pause
        exit /b 1
    )
    echo. > "%TEXT_CLI_HOME%.deps_ok"
    echo [OK] deps ready
)

:: config init
if not exist "%TEXT_CLI_HOME%copilot\\auxiliary_config.json" (
    if exist "%TEXT_CLI_HOME%copilot\\auxiliary_config.example.json" (
        copy "%TEXT_CLI_HOME%copilot\\auxiliary_config.example.json" "%TEXT_CLI_HOME%copilot\\auxiliary_config.json" >nul
        echo [OK] copilot config initialized
    )
)

:: start copilot (127.0.0.1:20260)
echo.
echo [INFO] starting copilot (http://127.0.0.1:20260)...
start "text-cli-copilot" /MIN python "%TEXT_CLI_HOME%copilot\\text-cli-copilot.py"
ping -n 4 127.0.0.1 >nul
echo [OK] copilot started

:: start service (0.0.0.0:28050)
echo [INFO] starting service (http://0.0.0.0:28050)...
start "text-cli-service" /MIN python "%TEXT_CLI_HOME%service\\main.py"
ping -n 6 127.0.0.1 >nul

:: health check
echo.
echo [INFO] health check...
curl -s http://localhost:28050/text-cli/health 2>nul
if %errorlevel% equ 0 (
    echo.
    echo [OK] text-cli v{self.version} deployed!
    echo.
    echo   copilot : http://127.0.0.1:20260
    echo   service : http://0.0.0.0:28050
    echo.
    echo   test: curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d "{{\\"directive\\": \\"AI:基础应用;天气查询,北京\\"}}"
    echo.
) else (
    echo [WARN] health check failed - check logs
)
echo   docs: docs\\README_zh.md
echo ========================================
pause
"""
        (self.output_dir / "start.bat").write_text(content, encoding="utf-8")
        print(f"[OK] start.bat generated (v{self.version})")

    def _clean_descriptors(self):
        """Remove files not meant for end-user distribution."""
        removals = [
            self.output_dir / "service" / "Dockerfile",
            self.output_dir / "service" / "docker-compose.yml",
            self.output_dir / "service" / "init_config.sh",
            self.output_dir / "service" / ".gitignore",
            self.output_dir / "copilot" / "README_CN.md",
            self.output_dir / "copilot" / "text-cli-copilot_programme_CN.md",
        ]
        for f in removals:
            if f.exists():
                f.unlink()
        print("[OK] deployment descriptors cleaned")

    def _package_zip(self):
        """Compress artifact to .zip via PowerShell Compress-Archive."""
        import hashlib
        import subprocess

        zip_path = self.output_parent / f"text-cli-v{self.version}.zip"
        if zip_path.exists():
            zip_path.unlink()

        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"Compress-Archive -Path '{self.output_dir}' -DestinationPath '{zip_path}'"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[WARN] zip failed: {result.stderr.strip()}")
            self._zip_path = None
            self._zip_sha256 = None
            return

        # SHA256
        sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        sha_path = zip_path.parent / f"text-cli-v{self.version}.sha256"
        sha_path.write_text(sha, encoding="utf-8")

        self._zip_path = zip_path
        self._zip_sha256 = sha
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"[OK] zip     -> {zip_path.name} ({size_mb:.1f} MB)")

    def _report(self):
        total = sum(
            1 for _ in self.output_dir.rglob("*") if _.is_file()
        )
        size_mb = sum(
            f.stat().st_size for f in self.output_dir.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        print()
        print("=" * 50)
        print(f"  text-cli skeleton-win built")
        print("=" * 50)
        print(f"  version : v{self.version}")
        print(f"  output  : {self.output_dir}")
        print(f"  files   : {total}")
        print(f"  size    : {size_mb:.1f} MB")
        if self._zip_path:
            zip_mb = self._zip_path.stat().st_size / (1024 * 1024)
            print(f"  zip     : {self._zip_path.name} ({zip_mb:.1f} MB)")
            print(f"  sha256  : {self._zip_sha256[:16]}...")
        print("=" * 50)


# ------------------------------------------------------------------
def read_version() -> str:
    version_file = (
        pathlib.Path(__file__).resolve().parent.parent.parent.parent / "VERSION"
    )
    if not version_file.is_file():
        sys.exit("[ERR] VERSION file not found at project root")
    v = version_file.read_text(encoding="utf-8").strip()
    if not re.match(r"^\d+\.\d+\.\d+$", v):
        sys.exit(f"[ERR] invalid version format in VERSION: {v!r}")
    return v


def main():
    parser = argparse.ArgumentParser(description="text-cli skeleton-win release builder")
    parser.add_argument(
        "--version", type=str, default=None,
        help="override version from VERSION file",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        sys.exit(f"[ERR] invalid version: {version!r}")

    builder = WinReleaseBuilder(version)
    builder.run()


if __name__ == "__main__":
    main()

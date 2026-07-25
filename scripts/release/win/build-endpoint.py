"""
text-cli endpoint skeleton-win release builder.

Usage:
    python .dev/release-script/win/build-endpoint.py              # use VERSION file
    python .dev/release-script/win/build-endpoint.py --version 0.2.0

Assembles deploy/skeleton-win/text-cli-endpoint-v{VERSION}/ from:
  - deploy/A5-endpoint/python/      (endpoint gateway source)
  - .dev/release-script/docs/       (distribution docs)
"""

import argparse
import pathlib
import re
import shutil
import sys


class WinEndpointBuilder:
    def __init__(self, version: str):
        self.version = version
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.release_dir = self.project_root / ".dev" / "release-script"
        self.docs_src = self.release_dir / "docs"
        self.output_parent = self.project_root / "deploy" / "skeleton-win"
        self.output_dir = self.output_parent / f"text-cli-endpoint-v{self.version}"
        self.source = self.project_root / "deploy" / "A5-endpoint" / "python"

    def run(self):
        self._check_prerequisites()
        self._clean_old()
        self._copy_source()
        self._copy_docs()
        self._generate_start_bat()
        self._clean_descriptors()
        self._package_zip()
        self._report()

    # ------------------------------------------------------------------
    def _check_prerequisites(self):
        if not self.source.is_dir():
            sys.exit(f"[ERR] endpoint source not found: {self.source}")
        if not self.docs_src.is_dir():
            sys.exit(f"[ERR] docs template not found: {self.docs_src}")

    def _clean_old(self):
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _copy_source(self):
        # Copy A5 python source, excluding __pycache__
        for item in self.source.iterdir():
            if item.name == "__pycache__":
                continue
            dst = self.output_dir / item.name
            if item.is_dir():
                shutil.copytree(item, dst, ignore=shutil.ignore_patterns("__pycache__"))
            else:
                shutil.copy2(item, dst)
        print(f"[OK] source  -> {self.output_dir.name}")

    def _copy_docs(self):
        dst = self.output_dir / "docs"
        shutil.copytree(self.docs_src, dst)
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
title text-cli-endpoint v{self.version}

echo ========================================
echo   text-cli endpoint v{self.version} - Windows
echo ========================================
echo.

:: env
if "%TEXT_CLI_ENDPOINT_HOME%"=="" set "TEXT_CLI_ENDPOINT_HOME=%~dp0"
echo [OK] HOME = %TEXT_CLI_ENDPOINT_HOME%

:: python check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERR] Python not installed or not in PATH
    pause
    exit /b 1
)

:: pip deps (one-time)
if not exist "%TEXT_CLI_ENDPOINT_HOME%.deps_ok" (
    echo [INFO] installing Python deps...
    pip install -r "%TEXT_CLI_ENDPOINT_HOME%requirements.txt" --quiet
    if %errorlevel% neq 0 (
        echo [ERR] pip install failed
        pause
        exit /b 1
    )
    echo. > "%TEXT_CLI_ENDPOINT_HOME%.deps_ok"
    echo [OK] deps ready
)

:: start endpoint (0.0.0.0:29050)
echo.
echo [INFO] starting endpoint (http://0.0.0.0:29050)...
cd /d "%TEXT_CLI_ENDPOINT_HOME%"
python -m uvicorn main:app --host 0.0.0.0 --port 29050
"""
        (self.output_dir / "start-endpoint.bat").write_text(content, encoding="utf-8")
        print(f"[OK] start-endpoint.bat generated (v{self.version})")

    def _clean_descriptors(self):
        removals = [
            self.output_dir / ".gitignore",
        ]
        for f in removals:
            if f.exists():
                f.unlink()
        # Remove __pycache__ from subdirectories
        for pyc in self.output_dir.rglob("__pycache__"):
            if pyc.is_dir():
                shutil.rmtree(pyc)
        print("[OK] deployment descriptors cleaned")

    def _package_zip(self):
        import hashlib
        import subprocess

        zip_path = self.output_parent / f"text-cli-endpoint-v{self.version}.zip"
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

        sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        sha_path = zip_path.parent / f"text-cli-endpoint-v{self.version}.sha256"
        sha_path.write_text(sha, encoding="utf-8")

        self._zip_path = zip_path
        self._zip_sha256 = sha
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"[OK] zip     -> {zip_path.name} ({size_mb:.1f} MB)")

    def _report(self):
        total = sum(1 for _ in self.output_dir.rglob("*") if _.is_file())
        size_mb = sum(
            f.stat().st_size for f in self.output_dir.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        print()
        print("=" * 50)
        print(f"  text-cli endpoint skeleton-win built")
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
    parser = argparse.ArgumentParser(description="text-cli endpoint skeleton-win release builder")
    parser.add_argument(
        "--version", type=str, default=None,
        help="override version from VERSION file",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        sys.exit(f"[ERR] invalid version: {version!r}")

    builder = WinEndpointBuilder(version)
    builder.run()


if __name__ == "__main__":
    main()

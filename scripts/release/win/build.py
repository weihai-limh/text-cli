"""
text-cli skeleton-win release builder.

Supports all progressive-deploy layers (A2-A9, excluding A5 which has its own
build-endpoint.py). Each layer's deploy/ directory is a self-contained runtime
— this script copies it as-is and bundles it for Windows distribution.

Two-run semantics:
  - First run: if output dir already exists, attempt to remove it and exit.
    Re-run after the removal succeeds.
  - Second run: output dir is clean, full build proceeds.

Usage:
    python scripts/release/win/build.py                      # default: A9
    python scripts/release/win/build.py --layer A3
    python scripts/release/win/build.py --version 0.2.0
    python scripts/release/win/build.py --layer A2 --version 0.2.0

Assembles deploy/skeleton-win/text-cli-A{LAYER}-v{VER}/ from:
  - deploy/{layer_dir}/              (full self-contained runtime)
  - docs/product_manuals/            (distribution docs)

Output directory uses underscore-separated version (e.g. text-cli-A9-v0_2_0).
"""

import argparse
import pathlib
import re
import shutil
import sys

# ---------------------------------------------------------------------------
# layer → deploy directory mapping (A5 excluded — handled by build-endpoint.py)
# ---------------------------------------------------------------------------
LAYER_DEPLOY_MAP = {
    "A2": "A2-copilot",
    "A3": "A3-service",
    "A4": "A4-paths",
    "A6": "A6-sql",
    "A7": "A7-mcp",
    "A8": "A8-discovery",
    "A9": "A9-advanced",
}


class WinReleaseBuilder:
    def __init__(self, version: str, layer: str):
        self.version = version                                # original form, e.g. "0.1.1"
        self.version_dir = version.replace(".", "_")          # directory-safe, e.g. "0_1_1"
        self.layer = layer
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.docs_src = self.project_root / "docs" / "product_manuals"
        self.deploy_src = self.project_root / "deploy" / LAYER_DEPLOY_MAP[layer]
        self.output_parent = self.project_root / "deploy" / "skeleton-win"
        self.output_name = f"text-cli-{layer}-v{self.version_dir}"
        self.output_dir = self.output_parent / self.output_name

    # ------------------------------------------------------------------
    # public entry
    # ------------------------------------------------------------------
    def run(self):
        self._check_prerequisites()
        self._clean_old()
        self._copy_runtime()
        self._copy_docs()
        self._copy_packages()
        self._copy_protocol()
        self._generate_start_bat()
        self._generate_end_bat()
        self._clean_descriptors()
        self._package_zip()
        self._report()

    # ------------------------------------------------------------------
    # steps
    # ------------------------------------------------------------------
    def _check_prerequisites(self):
        """Verify source directories exist."""
        if not self.deploy_src.is_dir():
            sys.exit(f"[ERR] deploy source not found: {self.deploy_src}")
        if not self.docs_src.is_dir():
            sys.exit(f"[ERR] docs template not found: {self.docs_src}")

    def _clean_old(self):
        """First-run guard: if a previous build exists at the same layer/version,
        attempt to remove it and exit so the user can re-run cleanly."""
        if self.output_dir.exists():
            try:
                shutil.rmtree(self.output_dir)
                print(f"[OK] removed previous build: {self.output_dir.name}")
                print(f"[INFO] output dir cleaned — re-run to generate the build.")
                sys.exit(0)
            except Exception as e:
                print(f"[ERR] cannot remove previous build: {e}")
                print(f"[INFO] please manually delete: {self.output_dir}")
                sys.exit(1)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _copy_runtime(self):
        """Copy the full self-contained deploy layer as runtime root."""
        shutil.copytree(self.deploy_src, self.output_dir, dirs_exist_ok=True)
        count = sum(1 for _ in self.output_dir.rglob("*") if _.is_file())
        print(f"[OK] {self.layer} runtime -> {self.output_dir.name} ({count} files)")

    def _copy_docs(self):
        """Copy distribution docs and replace {VERSION} placeholders."""
        dst = self.output_dir / "docs"
        shutil.copytree(self.docs_src, dst)
        for doc in dst.iterdir():
            if doc.suffix == ".md":
                text = doc.read_text(encoding="utf-8")
                text = text.replace("{VERSION}", self.version)
                doc.write_text(text, encoding="utf-8")
        count = len(list(dst.iterdir()))
        print(f"[OK] docs -> {dst.name} ({count} files, VERSION={self.version})")

    def _copy_packages(self):
        """Bundle deploy/packages/standard-python/ as sibling packages/ directory.

        Only Python packages are relevant for the Python runtime — JS packages
        (base-js/) are excluded. start.bat sets TEXT_CLI_PACKAGE_SOURCE_DIRS
        to point at this packages/ sibling directory.
        """
        pkg_src = self.project_root / "deploy" / "packages" / "standard-python"
        if not pkg_src.is_dir():
            print(f"[WARN] packages source not found: {pkg_src}")
            return
        pkg_dst = self.output_parent / "packages"
        shutil.copytree(pkg_src, pkg_dst, dirs_exist_ok=True)
        count = sum(1 for _ in pkg_dst.rglob("*") if _.is_file())
        print(f"[OK] packages -> {pkg_dst.name} ({count} files)")

    def _copy_protocol(self):
        """Bundle deploy/A0-protocol/ as sibling protocol/ directory.

        The protocol SDK is a pure client-side toolkit — zero dependencies,
        no runtime to start. It ships alongside the runtime as an independent
        sibling directory.
        """
        proto_src = self.project_root / "deploy" / "A0-protocol"
        if not proto_src.is_dir():
            print(f"[WARN] protocol source not found: {proto_src}")
            return
        proto_dst = self.output_parent / "protocol"
        shutil.copytree(proto_src, proto_dst, dirs_exist_ok=True)
        count = sum(1 for _ in proto_dst.rglob("*") if _.is_file())
        print(f"[OK] protocol -> {proto_dst.name} ({count} files)")

    def _generate_start_bat(self):
        """Generate layer-appropriate start.bat.

        A2 is copilot-only (no service, no health check).
        A3+ starts copilot then service with health-check.
        """
        if self.layer == "A2":
            blocks = _a2_blocks(self.version)
        else:
            blocks = _service_blocks(self.version)
        content = _build_bat(blocks)
        (self.output_dir / "start.bat").write_text(content, encoding="utf-8")
        print(f"[OK] start.bat generated ({self.layer}, v{self.version})")

    def _generate_end_bat(self):
        """Generate end.bat for graceful service shutdown."""
        (self.output_dir / "end.bat").write_text(END_BAT, encoding="utf-8")
        print("[OK] end.bat generated")

    def _clean_descriptors(self):
        """Remove __pycache__ directories left by copytree."""
        for pyc in self.output_dir.rglob("__pycache__"):
            if pyc.is_dir():
                shutil.rmtree(pyc, ignore_errors=True)
        print("[OK] runtime artifacts cleaned")

    def _package_zip(self):
        """Compress artifact to .zip via PowerShell Compress-Archive.
        
        Includes runtime directory AND sibling packages/ directory (if built).
        """
        import hashlib
        import subprocess

        zip_path = self.output_parent / f"{self.output_name}.zip"
        if zip_path.exists():
            zip_path.unlink()

        paths_to_zip = [str(self.output_dir)]
        pkg_dir = self.output_parent / "packages"
        if pkg_dir.is_dir():
            paths_to_zip.append(str(pkg_dir))
        proto_dir = self.output_parent / "protocol"
        if proto_dir.is_dir():
            paths_to_zip.append(str(proto_dir))

        paths_arg = ",".join(f"'{p}'" for p in paths_to_zip)
        cmd = [
            "powershell", "-NoProfile", "-Command",
            f"Compress-Archive -Path {paths_arg} -DestinationPath '{zip_path}'"
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"[WARN] zip failed: {result.stderr.strip()}")
            self._zip_path = None
            self._zip_sha256 = None
            return

        sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
        sha_path = zip_path.parent / f"{self.output_name}.sha256"
        sha_path.write_text(sha, encoding="utf-8")

        self._zip_path = zip_path
        self._zip_sha256 = sha
        size_mb = zip_path.stat().st_size / (1024 * 1024)
        print(f"[OK] zip -> {zip_path.name} ({size_mb:.1f} MB)")

    def _report(self):
        total = sum(1 for _ in self.output_dir.rglob("*") if _.is_file())
        size_mb = sum(
            f.stat().st_size for f in self.output_dir.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        print()
        print("=" * 50)
        print(f"  text-cli skeleton-win built")
        print("=" * 50)
        print(f"  layer   : {self.layer}")
        print(f"  version : v{self.version}")
        print(f"  output  : {self.output_dir}")
        print(f"  files   : {total}")
        print(f"  size    : {size_mb:.1f} MB")
        if self._zip_path:
            zip_mb = self._zip_path.stat().st_size / (1024 * 1024)
            print(f"  zip     : {self._zip_path.name} ({zip_mb:.1f} MB)")
            print(f"  sha256  : {self._zip_sha256[:16]}...")
        print("=" * 50)


# ---------------------------------------------------------------------------
# start.bat template blocks
# ---------------------------------------------------------------------------
HEADER = r"""@echo off
chcp 65001 >nul
title text-cli-{layer} v{ver}

echo ========================================
echo   text-cli {layer} v{ver} - Windows
echo ========================================
echo.

:: env
if "%TEXT_CLI_HOME%"=="" set "TEXT_CLI_HOME=%~dp0"
echo [OK] TEXT_CLI_HOME = %TEXT_CLI_HOME%

:: Package source directory (default: sibling packages/ next to extracted archive)
if "%TEXT_CLI_PACKAGE_SOURCE_DIRS%"=="" (
    set "TEXT_CLI_PACKAGE_SOURCE_DIRS=%~dp0..\packages"
)
if not exist "%TEXT_CLI_PACKAGE_SOURCE_DIRS%" (
    echo [WARN] Package source directory not found: %TEXT_CLI_PACKAGE_SOURCE_DIRS%
    echo        To install packages, place them in this directory or set
    echo        TEXT_CLI_PACKAGE_SOURCE_DIRS to your package source location.
) else (
    echo [OK] TEXT_CLI_PACKAGE_SOURCE_DIRS = %TEXT_CLI_PACKAGE_SOURCE_DIRS%
)

:: python check
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERR] Python not installed or not in PATH
    pause
    exit /b 1
)

:: config (text_cli.yaml)
set "CONFIG_YAML=%TEXT_CLI_HOME%service\\config\\text_cli.yaml"
if exist "%CONFIG_YAML%" (
    echo [config] text_cli.yaml found at: service\\config\\text_cli.yaml
) else (
    if exist "%TEXT_CLI_HOME%service\\config\\text_cli.example.yaml" (
        echo [config] text_cli.example.yaml found; rename to text_cli.yaml or start will auto-init
    )
)
echo [config] env vars override YAML settings (see docs/user-manual_zh.md 1.5)"""

COPILOT_BLOCK = """
:: start copilot (127.0.0.1:20260)
echo.
echo [INFO] starting copilot (http://127.0.0.1:20260)...
start "text-cli-copilot" /MIN "%VENV_PYTHON%" "%TEXT_CLI_HOME%copilot\\text-cli-copilot.py"
ping -n 4 127.0.0.1 >nul
echo [OK] copilot started"""

SERVICE_SETUP = """
:: venv deps (isolated from global pip)
set "VENV_PYTHON=%TEXT_CLI_HOME%.venv\\Scripts\\python.exe"
if exist "%VENV_PYTHON%" (
    "%VENV_PYTHON%" -c "import fastapi,uvicorn,pydantic,httpx" >nul 2>&1
    if not errorlevel 1 (
        echo [OK] deps ready (venv)
        goto :deps_done
    )
)
echo [INFO] installing Python deps to .venv...
if not exist "%TEXT_CLI_HOME%.venv" (
    python -m venv "%TEXT_CLI_HOME%.venv"
)
"%VENV_PYTHON%" -m pip install -r "%TEXT_CLI_HOME%service\\requirements.txt" --quiet
if %errorlevel% neq 0 (
    echo [ERR] pip install failed
    pause
    exit /b 1
)
echo [OK] deps ready
:deps_done

:: config init
if not exist "%TEXT_CLI_HOME%copilot\\auxiliary_config.json" (
    if exist "%TEXT_CLI_HOME%copilot\\auxiliary_config.example.json" (
        copy "%TEXT_CLI_HOME%copilot\\auxiliary_config.example.json" "%TEXT_CLI_HOME%copilot\\auxiliary_config.json" >nul
        echo [OK] copilot config initialized
    )
)
if not exist "%TEXT_CLI_HOME%service\\config\\text_cli.yaml" (
    if exist "%TEXT_CLI_HOME%service\\config\\text_cli.example.yaml" (
        copy "%TEXT_CLI_HOME%service\\config\\text_cli.example.yaml" "%TEXT_CLI_HOME%service\\config\\text_cli.yaml" >nul
        echo [OK] text_cli.yaml initialized
    )
)"""

SERVICE_BLOCK = """
:: start service (0.0.0.0:28050)
echo [INFO] starting service (http://0.0.0.0:28050)...
start "text-cli-service" /MIN "%VENV_PYTHON%" "%TEXT_CLI_HOME%service\\main.py"
ping -n 6 127.0.0.1 >nul"""

HEALTH_BLOCK = """
:: health check
echo.
echo [INFO] health check...
curl -s http://localhost:28050/text-cli/health 2>nul
if %errorlevel% equ 0 (
    echo.
    echo [OK] text-cli {layer} v{ver} deployed!
    echo.
    echo   copilot : http://127.0.0.1:20260
    echo   service : http://0.0.0.0:28050
    echo.
    echo   test: curl -X POST http://localhost:28050/text-cli/cli -H "Content-Type: application/json" -d "{{\\\"prompt\\\": \\\"AI:text-cli;query,compact\\\"}}"
    echo.
) else (
    echo [WARN] health check failed - check logs
)
echo   docs: docs\\README_zh.md
echo ========================================
pause"""

A2_FOOTER = """
echo [OK] text-cli {layer} v{ver} deployed!
echo.
echo   copilot : http://127.0.0.1:20260
echo   docs    : docs\\README_zh.md
echo ========================================
pause"""

END_BAT = r"""@echo off
echo Stopping text-cli services...

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :20260 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 echo   copilot PID %%a stopped
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :28050 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 echo   service PID %%a stopped
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :9020 ^| findstr LISTENING') do (
    taskkill /PID %%a /F >nul 2>&1
    if not errorlevel 1 echo   mcp PID %%a stopped
)

echo Done - copilot :20260, service :28050, mcp :9020 stopped.
pause
"""


def _a2_blocks(version: str) -> list[str]:
    """A2 blocks: header + copilot only, no service setup/health-check."""
    return [
        HEADER.format(layer="A2", ver=version),
        COPILOT_BLOCK,
        A2_FOOTER.format(layer="A2", ver=version),
    ]


def _service_blocks(version: str) -> list[str]:
    """A3+ blocks: full service pipeline with health-check."""
    return [
        HEADER.format(layer="A3+", ver=version),
        SERVICE_SETUP,
        COPILOT_BLOCK,
        SERVICE_BLOCK,
        HEALTH_BLOCK.format(layer="A3+", ver=version),
    ]


def _build_bat(blocks: list[str]) -> str:
    """Join template blocks and replace stray {layer}/{ver} in multiline blocks."""
    return "\n".join(b.strip("\n") for b in blocks) + "\n"


# ---------------------------------------------------------------------------
# entry point
# ---------------------------------------------------------------------------
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
        "--layer", type=str, default="A9",
        choices=list(LAYER_DEPLOY_MAP.keys()),
        help="deploy layer to package (default: A9)",
    )
    parser.add_argument(
        "--version", type=str, default=None,
        help="override version from VERSION file",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        sys.exit(f"[ERR] invalid version: {version!r}")

    builder = WinReleaseBuilder(version, args.layer)
    builder.run()


if __name__ == "__main__":
    main()

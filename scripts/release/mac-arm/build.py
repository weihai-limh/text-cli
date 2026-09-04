"""
text-cli skeleton-mac (macOS Apple Silicon) release builder.

Ports scripts/release/ubuntu/build.py for macOS arm64 distribution. The only
substantial platform differences from Linux are:
  - end.sh stops services with `lsof` (macOS has no `fuser`)
  - start.sh notes macOS Python install (brew / python.org, not apt)

Everything else (layer→deploy map, doc templating, two-run semantics,
.tar.gz + .sha256 packaging) is identical to the Linux builder.

Usage:
    python scripts/release/mac-arm/build.py                      # default: A9
    python scripts/release/mac-arm/build.py --layer A3
    python scripts/release/mac-arm/build.py --version 0.2.0

Assembles deploy/skeleton-mac/text-cli-A{LAYER}-v{VER}/ from:
  - deploy/{layer_dir}/              (full self-contained runtime)
  - docs/product_manuals/            (distribution docs)
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


class MacArmReleaseBuilder:
    def __init__(self, version: str, layer: str):
        self.version = version
        self.version_dir = version.replace(".", "_")
        self.layer = layer
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.docs_src = self.project_root / "docs" / "product_manuals"
        self.deploy_src = self.project_root / "deploy" / LAYER_DEPLOY_MAP[layer]
        self.output_parent = self.project_root / "deploy" / "skeleton-mac"
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
        self._generate_start_sh()
        self._generate_end_sh()
        self._clean_descriptors()
        self._package_tar()
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
        """Bundle deploy/packages/standard-python/ as sibling packages/ directory."""
        pkg_src = self.project_root / "deploy" / "packages" / "standard-python"
        if not pkg_src.is_dir():
            print(f"[WARN] packages source not found: {pkg_src}")
            return
        pkg_dst = self.output_parent / "packages"
        shutil.copytree(pkg_src, pkg_dst, dirs_exist_ok=True)
        count = sum(1 for _ in pkg_dst.rglob("*") if _.is_file())
        print(f"[OK] packages -> {pkg_dst.name} ({count} files)")

    def _copy_protocol(self):
        """Bundle deploy/A0-protocol/ as sibling protocol/ directory."""
        proto_src = self.project_root / "deploy" / "A0-protocol"
        if not proto_src.is_dir():
            print(f"[WARN] protocol source not found: {proto_src}")
            return
        proto_dst = self.output_parent / "protocol"
        shutil.copytree(proto_src, proto_dst, dirs_exist_ok=True)
        count = sum(1 for _ in proto_dst.rglob("*") if _.is_file())
        print(f"[OK] protocol -> {proto_dst.name} ({count} files)")

    def _generate_start_sh(self):
        """Generate layer-appropriate start.sh."""
        if self.layer == "A2":
            blocks = _a2_blocks(self.version)
        else:
            blocks = _service_blocks(self.version)
        content = _build_sh(blocks)
        start_sh = self.output_dir / "start.sh"
        start_sh.write_text(content, encoding="utf-8")
        start_sh.chmod(0o755)
        print(f"[OK] start.sh generated ({self.layer}, v{self.version})")

    def _generate_end_sh(self):
        """Generate end.sh for graceful service shutdown via lsof (macOS)."""
        end_sh = self.output_dir / "end.sh"
        end_sh.write_text("""#!/bin/bash
echo "Stopping text-cli services..."

lsof -ti tcp:20260 | xargs kill 2>/dev/null || true
lsof -ti tcp:28050 | xargs kill 2>/dev/null || true
lsof -ti tcp:9020  | xargs kill 2>/dev/null || true

echo "Done - copilot :20260, service :28050, mcp :9020 stopped."
""", encoding="utf-8")
        end_sh.chmod(0o755)
        print("[OK] end.sh generated")

    def _clean_descriptors(self):
        """Remove __pycache__ directories left by copytree."""
        for pyc in self.output_dir.rglob("__pycache__"):
            if pyc.is_dir():
                shutil.rmtree(pyc, ignore_errors=True)
        print("[OK] runtime artifacts cleaned")

    def _package_tar(self):
        """Compress artifact to .tar.gz (Unix consistent with Linux builder)."""
        import hashlib
        import tarfile

        tar_path = self.output_parent / f"{self.output_name}.tar.gz"
        if tar_path.exists():
            tar_path.unlink()

        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(self.output_dir, arcname=self.output_dir.name)
                pkg_dir = self.output_parent / "packages"
                if pkg_dir.is_dir():
                    tar.add(pkg_dir, arcname="packages")
                proto_dir = self.output_parent / "protocol"
                if proto_dir.is_dir():
                    tar.add(proto_dir, arcname="protocol")
        except Exception as e:
            print(f"[WARN] tar failed: {e}")
            self._tar_path = None
            self._tar_sha256 = None
            return

        sha = hashlib.sha256(tar_path.read_bytes()).hexdigest()
        sha_path = tar_path.parent / f"{self.output_name}.sha256"
        sha_path.write_text(sha, encoding="utf-8")

        self._tar_path = tar_path
        self._tar_sha256 = sha
        size_mb = tar_path.stat().st_size / (1024 * 1024)
        print(f"[OK] tar.gz -> {tar_path.name} ({size_mb:.1f} MB)")

    def _report(self):
        total = sum(1 for _ in self.output_dir.rglob("*") if _.is_file())
        size_mb = sum(
            f.stat().st_size for f in self.output_dir.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        print()
        print("=" * 50)
        print(f"  text-cli skeleton-mac built")
        print("=" * 50)
        print(f"  layer   : {self.layer}")
        print(f"  version : v{self.version}")
        print(f"  output  : {self.output_dir}")
        print(f"  files   : {total}")
        print(f"  size    : {size_mb:.1f} MB")
        if self._tar_path:
            tar_mb = self._tar_path.stat().st_size / (1024 * 1024)
            print(f"  tar.gz  : {self._tar_path.name} ({tar_mb:.1f} MB)")
            print(f"  sha256  : {self._tar_sha256[:16]}...")
        print("=" * 50)


# ---------------------------------------------------------------------------
# start.sh template blocks
# ---------------------------------------------------------------------------
HEADER = """#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_HOME="${{TEXT_CLI_HOME:-$DIR}}"

echo "========================================"
echo "  text-cli {layer} v{ver} - macOS (Apple Silicon)"
echo "========================================"
echo ""
echo "[OK] TEXT_CLI_HOME = $TEXT_CLI_HOME"

# python check
if ! command -v python3 &>/dev/null; then
    echo "[ERR] python3 not installed or not in PATH"
    exit 1
fi

# config (text_cli.yaml)
CONFIG_YAML="$TEXT_CLI_HOME/service/config/text_cli.yaml"
if [ -f "$CONFIG_YAML" ]; then
    echo "[config] text_cli.yaml found at: service/config/text_cli.yaml"
elif [ -f "$TEXT_CLI_HOME/service/config/text_cli.example.yaml" ]; then
    echo "[config] text_cli.example.yaml found; rename to text_cli.yaml or start will auto-init"
fi
echo "[config] env vars override YAML settings (see docs/user-manual_zh.md 1.5)"

# Package source directory (default: sibling packages/ next to extracted archive)
if [ -z "$TEXT_CLI_PACKAGE_SOURCE_DIRS" ]; then
    export TEXT_CLI_PACKAGE_SOURCE_DIRS="$TEXT_CLI_HOME/../packages"
fi
if [ -d "$TEXT_CLI_PACKAGE_SOURCE_DIRS" ]; then
    echo "[OK] TEXT_CLI_PACKAGE_SOURCE_DIRS = $TEXT_CLI_PACKAGE_SOURCE_DIRS"
else
    echo "[WARN] Package source directory not found: $TEXT_CLI_PACKAGE_SOURCE_DIRS"
    echo "       To install packages, place them in this directory or set"
    echo "       TEXT_CLI_PACKAGE_SOURCE_DIRS to your package source location."
fi"""

COPILOT_BLOCK = """
# start copilot (127.0.0.1:20260)
# A2 (copilot-only) has no SERVICE_SETUP; fall back to system python3.
if [ -z "${VENV_PYTHON:-}" ] || [ ! -x "$VENV_PYTHON" ]; then
    VENV_PYTHON="$(command -v python3)"
fi
echo ""
echo "[INFO] starting copilot (http://127.0.0.1:20260)..."
"$VENV_PYTHON" "$TEXT_CLI_HOME/copilot/text-cli-copilot.py" &
COPILOT_PID=$!
sleep 3
echo "[OK] copilot started (PID=$COPILOT_PID)" """

SERVICE_SETUP = """
# venv deps (isolated from global pip)
VENV_PYTHON="$TEXT_CLI_HOME/.venv/bin/python"
if [ -x "$VENV_PYTHON" ]; then
    "$VENV_PYTHON" -c "import fastapi,uvicorn,pydantic,httpx" >/dev/null 2>&1
    if [ $? -eq 0 ]; then
        echo "[OK] deps ready (venv)"
        VENV_READY=1
    fi
fi
if [ -z "$VENV_READY" ]; then
    echo "[INFO] installing Python deps to .venv..."
    if [ ! -d "$TEXT_CLI_HOME/.venv" ]; then
        python3 -m venv "$TEXT_CLI_HOME/.venv"
        if [ $? -ne 0 ]; then
            echo "[ERR] failed to create venv"
            echo "       On macOS, install Python 3 via: brew install python3  (python.org / brew builds include venv)"
            exit 1
        fi
    fi
    "$VENV_PYTHON" -m pip install -r "$TEXT_CLI_HOME/service/requirements.txt" --quiet
    if [ $? -ne 0 ]; then
        echo "[ERR] pip install failed"
        exit 1
    fi
    echo "[OK] deps ready"
fi

# config init
if [ ! -f "$TEXT_CLI_HOME/copilot/auxiliary_config.json" ]; then
    if [ -f "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" ]; then
        cp "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" "$TEXT_CLI_HOME/copilot/auxiliary_config.json"
        echo "[OK] copilot config initialized"
    fi
fi
if [ ! -f "$TEXT_CLI_HOME/service/config/text_cli.yaml" ]; then
    if [ -f "$TEXT_CLI_HOME/service/config/text_cli.example.yaml" ]; then
        cp "$TEXT_CLI_HOME/service/config/text_cli.example.yaml" "$TEXT_CLI_HOME/service/config/text_cli.yaml"
        echo "[OK] text_cli.yaml initialized"
    fi
fi"""

SERVICE_BLOCK = """
# start service (0.0.0.0:28050)
echo "[INFO] starting service (http://0.0.0.0:28050)..."
"$VENV_PYTHON" "$TEXT_CLI_HOME/service/main.py" &
SERVICE_PID=$!
sleep 5"""

HEALTH_BLOCK = """
# health check
echo ""
echo "[INFO] health check..."
if curl -s http://localhost:28050/text-cli/health >/dev/null 2>&1; then
    echo ""
    echo "[OK] text-cli {layer} v{ver} deployed!"
    echo ""
    echo "  copilot : http://127.0.0.1:20260"
    echo "  service : http://0.0.0.0:28050"
    echo ""
    TEST_BODY='{{\"directive\":\"AI:text-cli;query,compact\"}}'
    echo ""
    echo "  test: curl -X POST http://localhost:28050/text-cli/cli -H 'Content-Type: application/json' -d $TEST_BODY"
    echo ""
else
    echo "[WARN] health check failed - check logs"
fi
echo "  docs: docs/README_zh.md"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop all services"
wait"""

A2_FOOTER = """
echo "[OK] text-cli {layer} v{ver} deployed!"
echo ""
echo "  copilot : http://127.0.0.1:20260"
echo "  docs    : docs/README_zh.md"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop"
wait"""


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


def _build_sh(blocks: list[str]) -> str:
    """Join template blocks, stripping leading/trailing whitespace."""
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
    parser = argparse.ArgumentParser(description="text-cli skeleton-mac release builder")
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

    builder = MacArmReleaseBuilder(version, args.layer)
    builder.run()


if __name__ == "__main__":
    main()

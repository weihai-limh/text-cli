"""
text-cli endpoint skeleton-linux release builder.

A5 endpoint is a through-layer gateway. Unlike the main build script which
supports multiple accumulation layers (A2-A9), the endpoint has platform
variants (python FastAPI, js Cloudflare Workers).

Two-run semantics:
  - First run: if output dir already exists, attempt to remove it and exit.
    Re-run after the removal succeeds.
  - Second run: output dir is clean, full build proceeds.

Usage:
    python scripts/release/ubuntu/build-endpoint.py                        # default: python
    python scripts/release/ubuntu/build-endpoint.py --variant python
    python scripts/release/ubuntu/build-endpoint.py --version 0.2.0

Assembles deploy/skeleton-linux/text-cli-endpoint-{VARIANT}-v{VER}/ from:
  - deploy/A5-endpoint/{variant}/    (endpoint gateway source)
  - docs/product_manuals/            (distribution docs)

Output directory uses underscore-separated version (e.g. text-cli-endpoint-python-v0_2_0).
"""

import argparse
import pathlib
import re
import shutil
import sys

# ---------------------------------------------------------------------------
# variant → deploy subdirectory mapping
# ---------------------------------------------------------------------------
VARIANT_MAP = {
    "python": "deploy/A5-endpoint/python",
    # "js": "deploy/A5-endpoint/js",   # TODO: implement JS (Cloudflare Workers) variant
}


class LinuxEndpointBuilder:
    def __init__(self, version: str, variant: str):
        self.version = version
        self.version_dir = version.replace(".", "_")
        self.variant = variant
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.docs_src = self.project_root / "docs" / "product_manuals"
        self.deploy_src = self.project_root / VARIANT_MAP[variant]
        self.output_parent = self.project_root / "deploy" / "skeleton-linux"
        self.output_name = f"text-cli-endpoint-{variant}-v{self.version_dir}"
        self.output_dir = self.output_parent / self.output_name

    # ------------------------------------------------------------------
    # public entry
    # ------------------------------------------------------------------
    def run(self):
        self._check_prerequisites()
        self._clean_old()
        self._copy_runtime()
        self._copy_docs()
        self._copy_protocol()
        self._generate_start_sh()
        self._clean_descriptors()
        self._package_tar()
        self._report()

    # ------------------------------------------------------------------
    # steps
    # ------------------------------------------------------------------
    def _check_prerequisites(self):
        """Verify source directories exist."""
        if not self.deploy_src.is_dir():
            sys.exit(f"[ERR] endpoint source not found: {self.deploy_src}")
        if not self.docs_src.is_dir():
            sys.exit(f"[ERR] docs template not found: {self.docs_src}")

    def _clean_old(self):
        """First-run guard: if a previous build exists at the same variant/version,
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
        """Copy the full self-contained endpoint source as runtime root."""
        shutil.copytree(self.deploy_src, self.output_dir, dirs_exist_ok=True)
        count = sum(1 for _ in self.output_dir.rglob("*") if _.is_file())
        print(f"[OK] {self.variant} endpoint -> {self.output_dir.name} ({count} files)")

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

    def _copy_protocol(self):
        """Bundle deploy/A0-protocol/ as sibling protocol/ directory.

        The protocol SDK is a pure client-side toolkit — zero dependencies,
        no runtime to start. It ships alongside the endpoint as an independent
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

    def _generate_start_sh(self):
        """Generate variant-appropriate start-endpoint.sh.

        python: uvicorn on 0.0.0.0:29050
        js:     not yet implemented (Cloudflare Workers via wrangler).
        """
        if self.variant == "python":
            content = _python_start_sh(self.version)
        elif self.variant == "js":
            # TODO: generate JS start script
            sys.exit("[ERR] JS variant not yet implemented")
        else:
            sys.exit(f"[ERR] unknown variant: {self.variant}")

        start_sh = self.output_dir / "start-endpoint.sh"
        start_sh.write_text(content, encoding="utf-8")
        start_sh.chmod(0o755)
        print(f"[OK] start-endpoint.sh generated ({self.variant}, v{self.version})")

    def _clean_descriptors(self):
        """Remove variant-specific runtime artifacts not meant for distribution."""
        if self.variant == "python":
            for pyc in self.output_dir.rglob("__pycache__"):
                if pyc.is_dir():
                    shutil.rmtree(pyc, ignore_errors=True)
        elif self.variant == "js":
            # TODO: JS variant cleanup
            pass
        print("[OK] runtime artifacts cleaned")

    def _package_tar(self):
        """Compress artifact to .tar.gz.

        Includes endpoint runtime AND sibling protocol/ directory (if built).
        """
        import hashlib
        import tarfile

        tar_path = self.output_parent / f"{self.output_name}.tar.gz"
        if tar_path.exists():
            tar_path.unlink()

        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(self.output_dir, arcname=self.output_dir.name)
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
        print(f"  text-cli endpoint skeleton-linux built")
        print("=" * 50)
        print(f"  variant : {self.variant}")
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
# start-endpoint.sh template — python variant
# ---------------------------------------------------------------------------
def _python_start_sh(version: str) -> str:
    return f"""#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_ENDPOINT_HOME="${{TEXT_CLI_ENDPOINT_HOME:-$DIR}}"

echo "========================================"
echo "  text-cli endpoint v{version} - Linux"
echo "========================================"
echo ""
echo "[OK] HOME = $TEXT_CLI_ENDPOINT_HOME"

# python check
if ! command -v python3 &>/dev/null; then
    echo "[ERR] python3 not installed or not in PATH"
    exit 1
fi

# pip deps (one-time)
if [ ! -f "$TEXT_CLI_ENDPOINT_HOME/.deps_ok" ]; then
    echo "[INFO] installing Python deps..."
    pip3 install -r "$TEXT_CLI_ENDPOINT_HOME/requirements.txt" --quiet
    if [ $? -ne 0 ]; then
        echo "[ERR] pip install failed"
        exit 1
    fi
    touch "$TEXT_CLI_ENDPOINT_HOME/.deps_ok"
    echo "[OK] deps ready"
fi

# start endpoint (0.0.0.0:29050)
echo ""
echo "[INFO] starting endpoint (http://0.0.0.0:29050)..."
cd "$TEXT_CLI_ENDPOINT_HOME"
python3 -m uvicorn main:app --host 0.0.0.0 --port 29050
"""


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
    parser = argparse.ArgumentParser(description="text-cli endpoint skeleton-linux release builder")
    parser.add_argument(
        "--variant", type=str, default="python",
        choices=list(VARIANT_MAP.keys()),
        help="endpoint platform variant (default: python)",
    )
    parser.add_argument(
        "--version", type=str, default=None,
        help="override version from VERSION file",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        sys.exit(f"[ERR] invalid version: {version!r}")

    builder = LinuxEndpointBuilder(version, args.variant)
    builder.run()


if __name__ == "__main__":
    main()

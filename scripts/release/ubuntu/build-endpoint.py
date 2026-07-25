"""
text-cli endpoint skeleton-linux release builder.

Usage:
    python .dev/release-script/ubuntu/build-endpoint.py              # use VERSION file
    python .dev/release-script/ubuntu/build-endpoint.py --version 0.2.0

Assembles deploy/skeleton-linux/text-cli-endpoint-v{VERSION}/ from:
  - deploy/A5-endpoint/python/      (endpoint gateway source)
  - .dev/release-script/docs/       (distribution docs)
"""

import argparse
import os
import pathlib
import re
import shutil
import sys
import tarfile


class LinuxEndpointBuilder:
    def __init__(self, version: str):
        self.version = version
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.release_dir = self.project_root / ".dev" / "release-script"
        self.docs_src = self.release_dir / "docs"
        self.output_parent = self.project_root / "deploy" / "skeleton-linux"
        self.output_dir = self.output_parent / f"text-cli-endpoint-v{self.version}"
        self.source = self.project_root / "deploy" / "A5-endpoint" / "python"

    def run(self):
        self._check_prerequisites()
        self._clean_old()
        self._copy_source()
        self._copy_docs()
        self._generate_start_sh()
        self._clean_descriptors()
        self._package_tar()
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

    def _generate_start_sh(self):
        content = f"""#!/bin/bash
# text-cli endpoint v{self.version} — Linux start script

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "========================================"
echo "  text-cli endpoint v{self.version} - Linux"
echo "========================================"
echo ""

# python check
if ! command -v python3 &>/dev/null; then
    echo "[ERR] python3 not found in PATH"
    exit 1
fi

# pip deps (one-time)
if [ ! -f "$SCRIPT_DIR/.deps_ok" ]; then
    echo "[INFO] installing Python deps..."
    pip install -r "$SCRIPT_DIR/requirements.txt" --quiet
    if [ $? -ne 0 ]; then
        echo "[ERR] pip install failed"
        exit 1
    fi
    touch "$SCRIPT_DIR/.deps_ok"
    echo "[OK] deps ready"
fi

# start endpoint (0.0.0.0:29050)
echo ""
echo "[INFO] starting endpoint (http://0.0.0.0:29050)..."
cd "$SCRIPT_DIR"
python3 -m uvicorn main:app --host 0.0.0.0 --port 29050
"""
        script = self.output_dir / "start-endpoint.sh"
        script.write_text(content, encoding="utf-8")
        os.chmod(script, 0o755)
        print(f"[OK] start-endpoint.sh generated (v{self.version})")

    def _clean_descriptors(self):
        removals = [
            self.output_dir / ".gitignore",
        ]
        for f in removals:
            if f.exists():
                f.unlink()
        for pyc in self.output_dir.rglob("__pycache__"):
            if pyc.is_dir():
                shutil.rmtree(pyc)
        print("[OK] deployment descriptors cleaned")

    def _package_tar(self):
        import hashlib

        tar_path = self.output_parent / f"text-cli-endpoint-v{self.version}.tar.gz"
        if tar_path.exists():
            tar_path.unlink()

        with tarfile.open(tar_path, "w:gz") as tar:
            tar.add(self.output_dir, arcname=self.output_dir.name)

        sha = hashlib.sha256(tar_path.read_bytes()).hexdigest()
        sha_path = tar_path.parent / f"text-cli-endpoint-v{self.version}.sha256"
        sha_path.write_text(sha, encoding="utf-8")

        self._tar_path = tar_path
        self._tar_sha256 = sha
        size_mb = tar_path.stat().st_size / (1024 * 1024)
        print(f"[OK] tar.gz  -> {tar_path.name} ({size_mb:.1f} MB)")

    def _report(self):
        total = sum(1 for _ in self.output_dir.rglob("*") if _.is_file())
        size_mb = sum(
            f.stat().st_size for f in self.output_dir.rglob("*") if f.is_file()
        ) / (1024 * 1024)
        print()
        print("=" * 50)
        print(f"  text-cli endpoint skeleton-linux built")
        print("=" * 50)
        print(f"  version : v{self.version}")
        print(f"  output  : {self.output_dir}")
        print(f"  files   : {total}")
        print(f"  size    : {size_mb:.1f} MB")
        if self._tar_path:
            tar_mb = self._tar_path.stat().st_size / (1024 * 1024)
            print(f"  tar.gz  : {self._tar_path.name} ({tar_mb:.1f} MB)")
            print(f"  sha256  : {self._tar_sha256[:16]}...")
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
    parser = argparse.ArgumentParser(description="text-cli endpoint skeleton-linux release builder")
    parser.add_argument(
        "--version", type=str, default=None,
        help="override version from VERSION file",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        sys.exit(f"[ERR] invalid version: {version!r}")

    builder = LinuxEndpointBuilder(version)
    builder.run()


if __name__ == "__main__":
    main()

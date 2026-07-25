"""
text-cli skeleton-linux release builder.

Usage:
    python .dev/release-script/ubuntu/build.py              # use VERSION file
    python .dev/release-script/ubuntu/build.py --version 0.2.0

Assembles deploy/skeleton-linux/text-cli-v{VERSION}/ from:
  - deploy/A9-advanced/service/   (full accumulated service)
  - deploy/A2-copilot/copilot/    (local proxy)
  - .dev/release-script/docs/     (distribution docs)
"""

import argparse
import pathlib
import re
import shutil
import sys


class LinuxReleaseBuilder:
    def __init__(self, version: str):
        self.version = version
        self.project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
        self.release_dir = self.project_root / ".dev" / "release-script"
        self.docs_src = self.release_dir / "docs"
        self.output_parent = self.project_root / "deploy" / "skeleton-linux"
        self.output_dir = self.output_parent / f"text-cli-v{self.version}"
        self.service_src = self.project_root / "deploy" / "A9-advanced" / "service"
        self.copilot_src = self.project_root / "deploy" / "A2-copilot" / "copilot"

    def run(self):
        self._check_prerequisites()
        self._clean_old()
        self._copy_service()
        self._copy_copilot()
        self._copy_docs()
        self._generate_start_sh()
        self._clean_descriptors()
        self._package_tar()
        self._report()

    # ------------------------------------------------------------------
    def _check_prerequisites(self):
        if not self.service_src.is_dir():
            sys.exit(f"[ERR] service source not found: {self.service_src}")
        if not self.copilot_src.is_dir():
            sys.exit(f"[ERR] copilot source not found: {self.copilot_src}")
        if not self.docs_src.is_dir():
            sys.exit(f"[ERR] docs template not found: {self.docs_src}")

    def _clean_old(self):
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
        for doc in dst.iterdir():
            if doc.suffix == ".md":
                text = doc.read_text(encoding="utf-8")
                text = text.replace("{VERSION}", self.version)
                doc.write_text(text, encoding="utf-8")
        count = len(list(dst.iterdir()))
        print(f"[OK] docs    -> {dst.name} ({count} files, VERSION={self.version})")

    def _generate_start_sh(self):
        content = f"""#!/bin/bash
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
export TEXT_CLI_HOME="${{TEXT_CLI_HOME:-$DIR}}"

echo "========================================"
echo "  text-cli v{self.version} - Linux"
echo "========================================"
echo ""
echo "[OK] TEXT_CLI_HOME = $TEXT_CLI_HOME"

# python check
if ! command -v python3 &>/dev/null; then
    echo "[ERR] python3 not installed or not in PATH"
    exit 1
fi

# pip deps (one-time)
if [ ! -f "$TEXT_CLI_HOME/.deps_ok" ]; then
    echo "[INFO] installing Python deps..."
    pip3 install -r "$TEXT_CLI_HOME/service/requirements.txt" --quiet
    if [ $? -ne 0 ]; then
        echo "[ERR] pip install failed"
        exit 1
    fi
    touch "$TEXT_CLI_HOME/.deps_ok"
    echo "[OK] deps ready"
fi

# config init
if [ ! -f "$TEXT_CLI_HOME/copilot/auxiliary_config.json" ]; then
    if [ -f "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" ]; then
        cp "$TEXT_CLI_HOME/copilot/auxiliary_config.example.json" "$TEXT_CLI_HOME/copilot/auxiliary_config.json"
        echo "[OK] copilot config initialized"
    fi
fi

# start copilot (127.0.0.1:20260)
echo ""
echo "[INFO] starting copilot (http://127.0.0.1:20260)..."
python3 "$TEXT_CLI_HOME/copilot/text-cli-copilot.py" &
COPILOT_PID=$!
sleep 3
echo "[OK] copilot started (PID=$COPILOT_PID)"

# start service (0.0.0.0:28050)
echo "[INFO] starting service (http://0.0.0.0:28050)..."
python3 "$TEXT_CLI_HOME/service/main.py" &
SERVICE_PID=$!
sleep 5

# health check
echo ""
echo "[INFO] health check..."
if curl -s http://localhost:28050/text-cli/health >/dev/null 2>&1; then
    echo ""
    echo "[OK] text-cli v{self.version} deployed!"
    echo ""
    echo "  copilot : http://127.0.0.1:20260"
    echo "  service : http://0.0.0.0:28050"
    echo ""
    echo "  test: curl -X POST http://localhost:28050/text-cli/cli -H 'Content-Type: application/json' -d '{{\"directive\":\"AI:基础应用;天气查询,北京\"}}'"
    echo ""
else
    echo "[WARN] health check failed - check logs"
fi
echo "  docs: docs/README_zh.md"
echo "========================================"
echo ""
echo "Press Ctrl+C to stop all services"
wait
"""
        start_sh = self.output_dir / "start.sh"
        start_sh.write_text(content, encoding="utf-8")
        start_sh.chmod(0o755)
        print(f"[OK] start.sh generated (v{self.version})")

    def _clean_descriptors(self):
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

    def _package_tar(self):
        import hashlib
        import subprocess
        import tarfile

        tar_path = self.output_parent / f"text-cli-v{self.version}.tar.gz"
        if tar_path.exists():
            tar_path.unlink()

        try:
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(self.output_dir, arcname=self.output_dir.name)
        except Exception as e:
            print(f"[WARN] tar failed: {e}")
            self._tar_path = None
            self._tar_sha256 = None
            return

        sha = hashlib.sha256(tar_path.read_bytes()).hexdigest()
        sha_path = self.output_parent / f"text-cli-v{self.version}.sha256"
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
        print(f"  text-cli skeleton-linux built")
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
    parser = argparse.ArgumentParser(description="text-cli skeleton-linux release builder")
    parser.add_argument(
        "--version", type=str, default=None,
        help="override version from VERSION file",
    )
    args = parser.parse_args()

    version = args.version or read_version()
    if not re.match(r"^\d+\.\d+\.\d+$", version):
        sys.exit(f"[ERR] invalid version: {version!r}")

    builder = LinuxReleaseBuilder(version)
    builder.run()


if __name__ == "__main__":
    main()

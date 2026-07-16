#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_DIR"

echo "=== text-cli fork sync ==="
echo "Upstream: $(git remote get-url upstream)"
echo "Fork:     $(git remote get-url origin)"
echo ""

echo "[1/4] Fetching upstream..."
git fetch upstream --prune

echo "[2/4] Switching to main..."
git checkout main

echo "[3/4] Fast-forward main to upstream/main..."
git merge --ff-only upstream/main

echo "[4/4] Pushing to fork (origin)..."
git push origin main --tags

echo ""
echo "=== Sync complete ==="
git log --oneline -3

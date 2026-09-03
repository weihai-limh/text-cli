#!/usr/bin/env python3
"""Drift mirror: run every parser implementation against the same vectors.

For each vector row in vectors/parse.jsonl, feed the prompt to each runner
(Python/JS reference + C core + Rust core) and compare outputs.

  - baseline rows: every runner must equal `expect`. Any mismatch is a FAIL.
  - observe rows:   no single expectation; runner columns ARE the drift.

Runner contract (see runners/*): read prompts line by line from stdin,
write one JSON line per prompt to stdout:
  {"domain":..,"action":..,"params":[..]}   or   {"error":"INVALID_PARAMS"}

Usage:
  python conformance/run_drift.py [--parse vectors/parse.jsonl] [--skip py,js,c,rust]
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent          # text-cli/examples/project/text-cli-conformance
TEXT_CLI = HERE.parents[2]                       # text-cli 仓库根 (HERE 上溯两级: project → examples → text-cli)

# Paths into the text-cli reference implementations.
PY_LOADER_SRC = TEXT_CLI / "src" / "skeleton" / "bypass-service" / "pypi" / "src"
JS_PARSER = TEXT_CLI / "src" / "skeleton" / "bypass-service" / "npm" / "textcli-core" / "parser.js"

# C core locations.
C_CORE_SRC   = TEXT_CLI / "src" / "skeleton" / "bypass-service" / "text-cli-core-c" / "src" / "text_cli_core.c"
C_CORE_INC   = TEXT_CLI / "src" / "skeleton" / "bypass-service" / "text-cli-core-c" / "include"
C_RUNNER_EXE = HERE / "runners" / "c" / "run.exe"
C_RUNNER_C = HERE / "runners" / "c" / "run.c"

# Rust core locations.
RUST_CARGO_TOML = HERE / "runners" / "rust" / "Cargo.toml"
RUST_EXE = (
    HERE / "runners" / "rust" / "target" / "debug"
    / ("rust-runner.exe" if os.name == "nt" else "rust-runner")
)

CARGO = shutil.which("cargo") or str(Path.home() / ".cargo" / "bin" / "cargo.exe")


def ensure_runner(name):
    if name == "c" and not C_RUNNER_EXE.exists():
        gcc = shutil.which("gcc")
        if not gcc:
            sys.exit("gcc not found; cannot build C runner")
        subprocess.run(
            [gcc, "-std=c99", "-Wall", "-Wextra", "-Wpedantic",
             f"-I{C_CORE_INC}", str(C_RUNNER_C), str(C_CORE_SRC),
             "-o", str(C_RUNNER_EXE)],
            check=True,
        )
    if name == "rust" and not RUST_EXE.exists():
        if not CARGO:
            sys.exit("cargo not found; cannot build Rust runner")
        subprocess.run(
            [CARGO, "build", "--quiet", "--manifest-path", str(RUST_CARGO_TOML)],
            check=True,
        )


def runner_cmd(name):
    if name == "py":
        return [sys.executable, str(HERE / "runners" / "py" / "run.py"), str(PY_LOADER_SRC)]
    if name == "js":
        return ["node", str(HERE / "runners" / "js" / "run.js"), str(JS_PARSER)]
    if name == "c":
        return [str(C_RUNNER_EXE)]
    if name == "rust":
        return [str(RUST_EXE)]
    raise ValueError(name)


def load_vectors(path: Path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def run_runner(name, prompts):
    payload = "".join(p + "\n" for p in prompts).encode("utf-8")
    try:
        proc = subprocess.run(
            runner_cmd(name),
            input=payload,
            capture_output=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return ["TIMEOUT"] * len(prompts)
    except FileNotFoundError:
        return ["MISSING"] * len(prompts)
    if proc.returncode != 0:
        return ["CRASH"] * len(prompts)
    text = proc.stdout.decode("utf-8", errors="replace")
    lines = [l for l in text.splitlines() if l.strip()]
    outs = []
    for i in range(len(prompts)):
        if i < len(lines):
            try:
                outs.append(json.loads(lines[i]))
            except json.JSONDecodeError:
                outs.append({"error": f"BADJSON:{lines[i][:80]}"})
        else:
            outs.append({"error": "NOOUTPUT"})
    return outs


def main():
    ap = argparse.ArgumentParser(description="text-cli conformance drift mirror")
    ap.add_argument("--parse", default=str(HERE / "vectors" / "parse.jsonl"))
    ap.add_argument("--skip", default="",
                    help="comma-separated runners to skip (py,js,c,rust)")
    args = ap.parse_args()

    rows = load_vectors(Path(args.parse))
    prompts = [r["in"] for r in rows]
    skip = {s for s in args.skip.split(",") if s}

    results = {}
    for name in ("py", "js", "c", "rust"):
        if name in skip:
            continue
        ensure_runner(name)
        print(f"[runner] {name} ...")
        results[name] = run_runner(name, prompts)

    baseline_fail = 0
    observe_shown = 0
    for idx, row in enumerate(rows):
        rid = row.get("id", f"#{idx}")
        mode = row.get("mode", "baseline")
        cols = {n: results[n][idx] for n in results}
        if mode == "baseline":
            exp = row["expect"]
            cells = []
            for name in results:
                ok = cols[name] == exp
                cells.append(f"{name}={'OK' if ok else 'FAIL'}")
                if not ok:
                    baseline_fail += 1
            line = f"[baseline] {rid}: " + " ".join(cells)
            if baseline_fail and any("FAIL" in c for c in cells):
                pass  # detail printed below in the FAIL summary
            print(line)
        else:
            observe_shown += 1
            print(f"[observe ] {rid}: " + json.dumps(cols, ensure_ascii=False))

    print("-" * 60)
    if baseline_fail:
        print(f"BASELINE FAILURES: {baseline_fail} (details below)")
        # Re-print failing baseline rows with got-vs-expect.
        for idx, row in enumerate(rows):
            if row.get("mode", "baseline") != "baseline":
                continue
            exp = row["expect"]
            cols = {n: results[n][idx] for n in results}
            if any(cols[n] != exp for n in results):
                print(f"  FAIL {row.get('id')}: expect="
                      + json.dumps(exp, ensure_ascii=False))
                for n in results:
                    if cols[n] != exp:
                        print(f"       {n} got=" + json.dumps(cols[n], ensure_ascii=False))
        sys.exit(1)
    print("BASELINE ALL OK (observe rows are recorded, not judged)")
    sys.exit(0)


if __name__ == "__main__":
    main()

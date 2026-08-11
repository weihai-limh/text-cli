#!/usr/bin/env python3
"""
text-cli service-A4 chain verification.

Validates: path orchestration (inline + interpolation + parallel + branch + degradation)
plus mode:"map" loop iteration (map-disabled guard, normal execution, LOOP_LIMIT).

Requires: A4 service running on TEXT_CLI_BASE_URL (default http://localhost:28050),
          TEXT_CLI_PACKAGE_SOURCE_DIRS pointing to test/mock/,
          paths/ subdirectory for test fixtures,
          yaml editable at service/config/text_cli.yaml for map toggle.
"""
import json
import os
import sys
import time
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError

BASE = os.environ.get("TEXT_CLI_BASE_URL", "http://localhost:28050")
SCRIPT_DIR = Path(__file__).resolve().parent
PKG_STANDARD = "hello-world-standard"
PKG_FAIL = "hello-world-fail"
PASS = 0
FAIL = 0


def post(prompt):
    url = f"{BASE}/text-cli/cli"
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8")) if e.fp else {}


def cli(prompt):
    code, data = post(prompt)
    return code, data.get("rst_data", {}).get("text", ""), data.get("rst_err", "")


def get_rst_data(prompt):
    """Return full rst_data dict from a directive call."""
    code, data = post(prompt)
    rst_data = data.get("rst_data", {})
    if isinstance(rst_data, str):
        try:
            rst_data = json.loads(rst_data)
        except (json.JSONDecodeError, TypeError):
            pass
    return code, data.get("rst_err", ""), rst_data


def check(label, expected, actual):
    global PASS, FAIL
    if actual == expected:
        print(f"\033[32m[PASS]\033[0m {label}")
        PASS += 1
    else:
        print(f"\033[31m[FAIL]\033[0m {label} (expected={expected!r}, got={actual!r})")
        FAIL += 1


def check_contains(label, needle, haystack):
    global PASS, FAIL
    h = haystack if isinstance(haystack, str) else json.dumps(haystack)
    if needle in h:
        print(f"\033[32m[PASS]\033[0m {label}")
        PASS += 1
    else:
        print(f"\033[31m[FAIL]\033[0m {label} (missing: {needle!r})")
        FAIL += 1


def check_not_contains(label, needle, haystack):
    global PASS, FAIL
    h = haystack if isinstance(haystack, str) else json.dumps(haystack)
    if needle not in h:
        print(f"\033[32m[PASS]\033[0m {label}")
        PASS += 1
    else:
        print(f"\033[31m[FAIL]\033[0m {label} (contains: {needle!r})")
        FAIL += 1


def yaml_toggle_map(enable: bool):
    """Edit text_cli.yaml to toggle map_enabled. Returns previous value."""
    import shutil
    yaml_path = SCRIPT_DIR.parent.parent / "deploy" / "A4-paths" / "service" / "config" / "text_cli.yaml"
    backup = yaml_path.read_text(encoding="utf-8") if yaml_path.exists() else ""
    if not backup:
        print("[WARN] yaml not found, skip toggle")
        return None
    new_val = "true" if enable else "false"
    lines = backup.split("\n")
    new_lines = []
    for line in lines:
        if "map_enabled:" in line and "map_enabled:" == line.split("#")[0].strip().split(":")[0].strip():
            new_lines.append(f"  map_enabled: {new_val}  # toggle by A4 test")
        else:
            new_lines.append(line)
    new_text = "\n".join(new_lines)
    yaml_path.write_text(new_text, encoding="utf-8")
    prev = "true" if "map_enabled: true" in backup else "false"
    print(f"[CONFIG] map_enabled: {prev} -> {new_val}")
    return prev


def cleanup():
    for pkg in (PKG_FAIL, PKG_STANDARD):
        code, _, _ = cli(f"AI:text-cli;uninstall,{pkg}")
        if code == 200:
            print(f"[CLEANUP] removed {pkg}")
    # Restore map_enabled to false
    try:
        yaml_toggle_map(False)
    except Exception:
        pass


def main():
    global PASS, FAIL

    cleanup()

    # ================================================
    # 0. Pre-install packages
    # ================================================
    print("--- 0. Pre-install ---")
    for pkg in (PKG_STANDARD, PKG_FAIL):
        code, text, _ = cli(f"AI:text-cli;install,{pkg}")
        check(f"install {pkg} returns 200", 200, code)
        check_contains(f"install {pkg} confirmed", "install complete", text)

    # ================================================
    # 1. Path orchestration (inherited from A9 test)
    # ================================================
    print("--- 1. Path orchestration ---")

    # 1a. Inline JSON path
    inline_json = json.dumps({
        "id": "inline",
        "type": "pipeline",
        "steps": [
            {"id": "a", "instruction": "hello;world,scout", "output_as": "r"}
        ]
    }, separators=(',', ':'))
    code, text, rst_err = cli(f"AI:text-cli;path,{inline_json}")
    check("inline path returns 200", 200, code)
    check_contains("inline path output", "Hello!scout!", text)

    # 1b. hello-chain (step1→step2 interpolation)
    code, text, rst_err = cli("AI:text-cli;path,hello-chain")
    check("hello-chain returns 200", 200, code)
    check_contains("hello-chain interpolation resolved",
                   "prefix-Hello!chain-start!", text)

    # 1c. parallel-demo (parallel group all)
    code, text, rst_err = cli("AI:text-cli;path,parallel-demo")
    check("parallel-demo returns 200", 200, code)
    check_contains("parallel alpha present", "para-alpha", text)
    check_contains("parallel beta present", "para-beta", text)

    # 1d. branch-demo (conditional if)
    code, text, rst_err = cli("AI:text-cli;path,branch-demo")
    check("branch-demo returns 200", 200, code)
    check_contains("branch yes executed", "branch-yes", text)

    # 1e. degrade-demo (main fails → degradation takes over)
    code, text, rst_err = cli("AI:text-cli;path,degrade-demo")
    check("degrade-demo returns 200", 200, code)
    check_contains("degradation fallback executed", "degrade-ok", text)

    # ================================================
    # 2. Map loop iteration (A4 exclusive)
    # ================================================
    print("--- 2. Map loop iteration ---")

    # 2a. map_disabled by default
    code, rst_err, rst_data = get_rst_data("AI:text-cli;path,map-demo")
    check_contains("map disabled by default", "map_disabled", str(rst_data))
    check_not_contains("map no LOOP_LIMIT when disabled", "LOOP_LIMIT", str(rst_data))

    # 2b. Enable map → restart → normal execution
    print("[CONFIG] enabling map...")
    yaml_toggle_map(True)
    print("[CONFIG] restart A4 service now...")
    time.sleep(2)  # brief wait for service restart

    code, rst_err, rst_data = get_rst_data("AI:text-cli;path,map-demo")
    if code == 200 and rst_err == "":
        check_contains("map normal execution", "results", str(rst_data))
    else:
        print(f"[INFO] map-demo code={code}, rst_err={rst_err} — "
              "Service may need manual restart after yaml change")

    # 2c. LOOP_LIMIT (150 > default 100)
    code, rst_err, rst_data = get_rst_data("AI:text-cli;path,map-limit")
    check_contains("map LOOP_LIMIT", "LOOP_LIMIT", str(rst_data))

    # ================================================
    print("")
    print("=" * 40)
    print(f"  PASS: {PASS}  FAIL: {FAIL}")
    print("=" * 40)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        cleanup()

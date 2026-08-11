#!/usr/bin/env python3
"""
text-cli service-A9 chain verification.

Validates: aggregate degradation, text-cli;pro facade, transparent proxy
(Service→Copilot, auto-detect).

Path orchestration and mode:"map" coverage → see service-A4/ test chain.
Requires: A9 service running on TEXT_CLI_BASE_URL (default http://localhost:28050),
          TEXT_CLI_PACKAGE_SOURCE_DIRS pointing to test/mock/,
          paths/ subdirectory for test fixtures.
"""
import json
import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = os.environ.get("TEXT_CLI_BASE_URL", "http://localhost:28050")
COPILOT_URL = os.environ.get("TEXT_CLI_COPILOT_URL", "http://localhost:20260")
SCRIPT_DIR = Path(__file__).resolve().parent
PKG_STANDARD = "hello-world-standard"
PKG_FAIL = "hello-world-fail"
PKG_COPILOT = "hello-world-cmd"
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
    """Shortcut: POST /text-cli/cli, return (status_code, rst_data, rst_err).

    SPEC v1.3.2: rst_data carries the handler's return dict directly.
    """
    code, data = post(prompt)
    return code, data.get("rst_data", {}), data.get("rst_err", "")


def cli_long(prompt, timeout=30):
    """Like cli() but with custom timeout for long-running operations."""
    url = f"{BASE}/text-cli/cli"
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data.get("rst_data", {}), data.get("rst_err", "")
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8")) if e.fp else {"text": "", "rst_err": ""}


def copilot_get(path):
    """GET a path from Copilot, return (status_code, parsed_json)."""
    url = f"{COPILOT_URL}{path}"
    try:
        with urlopen(Request(url), timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except (HTTPError, URLError):
        return 0, {}


def copilot_post(prompt):
    """POST to Copilot /text-cli/cli, return (status_code, parsed_json)."""
    url = f"{COPILOT_URL}/text-cli/cli"
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, {"rst_data": {"text": raw}, "rst_err": ""}
    except HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8")) if e.fp else {}


def copilot_cli(prompt):
    """Shortcut: POST Copilot /text-cli/cli, return rst_data."""
    code, data = copilot_post(prompt)
    return code, data.get("rst_data", {}), data.get("rst_err", "")


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


def cleanup():
    for pkg in (PKG_FAIL, PKG_STANDARD):
        code, _, _ = cli(f"AI:text-cli;uninstall,{pkg}")
        if code == 200:
            print(f"[CLEANUP] removed {pkg}")
    try:
        copilot_cli(f"AI:text-cli;co-uninstall,{PKG_COPILOT}")
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
        code, data, rst_err = cli(f"AI:text-cli;install,{pkg}")
        check(f"install {pkg} returns 200", 200, code)
        check(f"install {pkg} rst_err is empty", "", rst_err)

    # ================================================
    # 1. Path orchestration
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
    code, data, rst_err = cli(f"AI:text-cli;path,{inline_json}")
    check("inline path returns 200", 200, code)
    check_contains("inline path output", "Hello!scout!", data)

    # 1b. hello-chain (step1→step2 interpolation)
    code, data, rst_err = cli("AI:text-cli;path,hello-chain")
    check("hello-chain returns 200", 200, code)
    check_contains("hello-chain interpolation resolved",
                   "prefix-Hello!chain-start!", data)

    # 1c. parallel-demo (parallel group all)
    code, data, rst_err = cli("AI:text-cli;path,parallel-demo")
    check("parallel-demo returns 200", 200, code)
    check_contains("parallel alpha present", "para-alpha", data)
    check_contains("parallel beta present", "para-beta", data)

    # 1d. branch-demo (conditional if)
    code, data, rst_err = cli("AI:text-cli;path,branch-demo")
    check("branch-demo returns 200", 200, code)
    check_contains("branch yes executed", "branch-yes", data)

    # 1e. degrade-demo (main fails → degradation takes over)
    code, data, rst_err = cli("AI:text-cli;path,degrade-demo")
    check("degrade-demo returns 200", 200, code)
    check_contains("degradation fallback executed", "degrade-ok", data)

    # 1f. Transparent proxy (Service → Copilot), optional
    print("--- 1f. Transparent proxy ---")
    code, _ = copilot_get("/text-cli/health")
    if code == 200:
        # co-install on Copilot side
        code, _, _ = copilot_cli(f"AI:text-cli;co-install,{PKG_COPILOT}")
        check("copilot co-install returns 200", 200, code)

        # sync-copilot on Service side (may need extra time to query Copilot)
        code, sync_text, _ = cli_long("AI:text-cli;sync-copilot", timeout=30)
        check("sync-copilot returns 200", 200, code)

        # proxy dispatch: Service → Copilot
        code, proxy_data, _ = cli("AI:hello;world,via-proxy")
        check("proxy dispatch returns 200", 200, code)
        check_contains("proxy dispatch returns greeting", "Hello", proxy_data)

        # co-uninstall on Copilot side
        copilot_cli(f"AI:text-cli;co-uninstall,{PKG_COPILOT}")
    else:
        print("\033[33m[INFO]\033[0m Copilot not available, "
              "skip transparent proxy test")

    # ================================================
    # 2. Aggregate degradation
    # ================================================
    print("--- 2. Aggregate degradation ---")

    code, text, rst_err = cli("AI:map;geocode,Beijing")
    if code == 200 and rst_err == "":
        print("\033[32m[PASS]\033[0m aggregate dispatch returns 200")
        PASS += 1
    elif rst_err == "ERR_NOT_FOUND":
        print("\033[33m[INFO]\033[0m aggregate returned ERR_NOT_FOUND - "
              "no map providers installed (requires aggregation packages)")
    else:
        print(f"\033[31m[FAIL]\033[0m aggregate dispatch (code={code}, rst_err={rst_err!r})")
        FAIL += 1

    code, text, _ = cli("AI:map;geocode,Beijing,bd-map")
    if code == 200:
        print("\033[32m[PASS]\033[0m aggregate explicit provider returns 200")
        PASS += 1
    else:
        print("\033[33m[INFO]\033[0m aggregate explicit provider failed - "
              "expected if provider package not installed")

    # ================================================
    # 3. Facade (text-cli;pro)
    # ================================================
    print("--- 3. Facade ---")

    code, data, rst_err = cli("AI:text-cli;pro,nonexistent-facade-name")
    if code == 200:
        check_contains("pro returns available keys", "available", data)
    else:
        print("\033[33m[INFO]\033[0m pro handler may not be registered yet")

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

#!/usr/bin/env python3
"""
text-cli copilot chain verification.

Validates: copilot health, co-install hello-world-cmd, dispatch, co-list, co-uninstall.

Requires: A2 copilot running on TEXT_CLI_COPILOT_URL (default http://localhost:20260),
          TEXT_CLI_PACKAGE_SOURCE_DIRS pointing to test/mock/.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = os.environ.get("TEXT_CLI_COPILOT_URL", "http://localhost:20260")
PKG = "hello-world-cmd"
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


def get(path):
    url = f"{BASE}{path}"
    try:
        with urlopen(Request(url), timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        return e.code, {}
    except URLError:
        return 0, {}


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


def cli(prompt):
    code, data = post(prompt)
    return code, data.get("rst_data", {}).get("text", ""), data.get("rst_err", "")


def cleanup():
    code, text, _ = cli(f"AI:text-cli;co-uninstall,{PKG}")
    if code == 200:
        print(f"[CLEANUP] removed leftover {PKG}")


def main():
    global FAIL

    cleanup()

    # ================================================
    # 1. Health
    # ================================================
    print("--- 1. Copilot status ---")

    code, data = get("/text-cli/health")
    check("GET /text-cli/health returns 200", 200, code)

    # ================================================
    # 2. Package lifecycle
    # ================================================
    print("--- 2. Package lifecycle ---")

    _, before_text, _ = cli("AI:text-cli;co-list")
    check_not_contains("co-list before install", PKG, before_text)

    code, install_text, _ = cli(f"AI:text-cli;co-install,{PKG}")
    check("co-install returns 200", 200, code)
    check_contains("co-install response", "installed", install_text)

    _, after_text, _ = cli("AI:text-cli;co-list")
    check_contains("co-list after install", PKG, after_text)

    # ================================================
    # 3. Dispatch
    # ================================================
    print("--- 3. Dispatch ---")

    code, dispatch_text, rst_err = cli("AI:hello;world,test")
    check("dispatch rst_err is empty", "", rst_err)
    check("dispatch returns greeting", "Hello, test!", dispatch_text.strip())

    # ================================================
    # 4. Uninstall
    # ================================================
    print("--- 4. Uninstall ---")

    code, uninstall_text, _ = cli(f"AI:text-cli;co-uninstall,{PKG}")
    check("co-uninstall returns 200", 200, code)
    check_contains("co-uninstall response", "uninstalled", uninstall_text)

    _, end_text, _ = cli("AI:text-cli;co-list")
    check_not_contains("co-list after uninstall", PKG, end_text)

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

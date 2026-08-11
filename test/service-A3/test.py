#!/usr/bin/env python3
"""
text-cli service-A3 chain verification.

Validates: protocol compliance, directive dispatch after install+restart,
package lifecycle (install -> uninstall).

Requires: A3 service running on TEXT_CLI_BASE_URL (default http://localhost:28050),
          TEXT_CLI_PACKAGE_SOURCE_DIRS pointing to test/mock/.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = os.environ.get("TEXT_CLI_BASE_URL", "http://localhost:28050")
PKG = "hello-world-standard"
PASS = 0
FAIL = 0


# --- helpers ---

def post(path, prompt):
    """POST to /text-cli/cli, return (status_code, parsed_json)."""
    url = f"{BASE}{path}"
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8")) if e.fp else {}
        except Exception:
            body = {}
        return e.code, body


def get(path):
    """GET a path, return (status_code, parsed_json)."""
    url = f"{BASE}{path}"
    req = Request(url)
    try:
        with urlopen(req, timeout=10) as resp:
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
    """Shortcut: POST /text-cli/cli, return (status_code, rst_data, rst_err).

    SPEC v1.3.2: rst_data carries the handler's return dict directly — no {"text": "..."} nesting.
    """
    code, data = post("/text-cli/cli", prompt)
    rst_data = data.get("rst_data", {})
    # Flatten for string-based assertions: use the dict itself, serialized for contains checks
    return code, rst_data, data.get("rst_err", "")


def cleanup():
    """Defensive uninstall before tests."""
    try:
        code, text, _ = cli(f"AI:text-cli;uninstall,{PKG}")
        if code == 200:
            print(f"[CLEANUP] removed leftover {PKG}")
    except Exception:
        pass  # service may not have the package installed yet


# --- main ---

def main():
    global PASS, FAIL

    cleanup()

    # ================================================
    # 1. Protocol compliance (no packages needed)
    # ================================================
    print("--- 1. Protocol compliance ---")

    code, data = get("/text-cli/health")
    check("GET /health returns status ok", "ok", data.get("status", ""))

    # text-cli;query without params — handler now returns dict, rst_err must be empty.
    code, query_data, rst_err = cli("AI:text-cli;query")
    check("POST valid prompt returns 200", 200, code)
    check("query rst_err is empty", "", rst_err)

    code, _, _ = cli("")
    check("POST empty prompt returns 400", 400, code)

    # ================================================
    # 2. Package lifecycle
    # ================================================
    print("--- 2. Package lifecycle ---")

    # 2a. query compact before install — should not contain hello;world
    _, before_data, _ = cli("AI:text-cli;query,compact")
    check_not_contains("query before install", "hello;world", before_data)

    # 2b. install — handler now returns dict, rst_err must be empty.
    code, install_data, rst_err = cli(f"AI:text-cli;install,{PKG}")
    check("install returns 200", 200, code)
    check("install rst_err is empty", "", rst_err)

    # 2c. query compact after install — must contain hello;world
    _, after_data, _ = cli("AI:text-cli;query,compact")
    check_contains("query after install includes hello;world",
                   "hello;world", after_data)

    # 2d. dispatch after install (hot-load, no restart needed)
    code, dispatch_data, rst_err = cli("AI:hello;world,test")
    check("dispatch after install returns 200", 200, code)
    check("dispatch rst_err is empty", "", rst_err)
    check_contains("dispatch returns greeting", "Hello", dispatch_data)

    # 2e. uninstall — handler now returns dict, rst_err must be empty.
    code, uninstall_data, rst_err = cli(f"AI:text-cli;uninstall,{PKG}")
    check("uninstall returns 200", 200, code)
    check("uninstall rst_err is empty", "", rst_err)

    # 2f. query compact after uninstall — should not contain hello;world
    _, end_data, _ = cli("AI:text-cli;query,compact")
    check_not_contains("query after uninstall", "hello;world", end_data)

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

#!/usr/bin/env python3
"""
text-cli pypi (textcli-loader) chain verification.

Validates: load_package, execute, list_directives, envelope format.

Requires: pip install textcli-loader
          mock/hello-world-standard/ available.
"""
import json
import os
import sys
from pathlib import Path

PASS = 0
FAIL = 0

SCRIPT_DIR = Path(__file__).resolve().parent
MOCK_DIR = Path(os.environ.get("TEXT_CLI_MOCK_DIR", str(SCRIPT_DIR / ".." / "mock")))
PKG_PATH = MOCK_DIR / "hello-world-standard"


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


def main():
    # ---- Import ----
    try:
        from textcli_loader import load_package, execute, list_directives
    except ImportError as e:
        print(f"\033[31m[FAIL]\033[0m textcli_loader not installed: {e}")
        print("  pip install textcli-loader")
        return 1

    # ---- Schema validation ----
    print("--- 1. Schema ---")
    schema_path = PKG_PATH / "schema.json"
    if not schema_path.exists():
        print(f"\033[31m[FAIL]\033[0m schema.json missing: {schema_path}")
        return 1
    schema = json.loads(schema_path.read_text())
    check("schema has id", "hello-world-standard", schema.get("id", ""))
    check("schema has runtime python", "python", schema.get("runtime", ""))
    check("schema version is 0.1.0", "0.1.0", schema.get("version", ""))

    # ---- Load ----
    print("--- 2. Load ---")
    meta = load_package(str(PKG_PATH))
    check("load_package returns id", "hello-world-standard", meta.get("id", ""))
    directives = meta.get("directives", [])
    check("directives list not empty", True, len(directives) > 0)

    # ---- List ----
    print("--- 3. List directives ---")
    lines = list_directives(meta)
    check_contains("list_directives includes hello;world", "hello;world", "\n".join(lines))

    # ---- Execute ----
    print("--- 4. Execute ---")
    result = execute("AI:hello;world,test")
    check("execute returns dict", True, isinstance(result, dict))
    check("envelope rst_types is text", "text", result.get("rst_types", ""))
    check("envelope rst_err is empty", "", result.get("rst_err", ""))
    check("envelope rst_data.text", {"result": "Hello!test!"},
          result.get("rst_data", {}).get("text", ""))

    # ---- Error path ----
    result = execute("AI:unknown;test")
    check("unknown directive returns rst_err", False, result.get("rst_err", "") == "")

    # ================================================
    print("")
    print("=" * 40)
    print(f"  PASS: {PASS}  FAIL: {FAIL}")
    print("=" * 40)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

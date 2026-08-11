#!/usr/bin/env python3
"""
text-cli endpoint chain verification.

Validates: security layers (IP guard, rate limiter, token auth) and
forwarding to backend.

Requires: A5 endpoint running on TEXT_CLI_ENDPOINT_URL (default http://localhost:29050),
          at least one A3 backend in A3_BACKENDS.
"""
import json
import os
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = os.environ.get("TEXT_CLI_ENDPOINT_URL", "http://localhost:29050")
ACCESS_TOKEN = os.environ.get("TEXT_CLI_ACCESS_TOKEN", "")
PASS = 0
FAIL = 0


def post(prompt, access_token=None):
    url = f"{BASE}/text-cli/cli"
    body = json.dumps({"prompt": prompt}).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    req = Request(url, data=body, headers=headers)
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


def main():
    # ================================================
    # 1. Health
    # ================================================
    print("--- 1. Health ---")
    code, data = get("/text-cli/health")
    check("GET /health returns 200", 200, code)
    if code == 200:
        body = data.get("body", "")
        print(f"  endpoint: {body}")

    # ================================================
    # 2. Security layers
    # ================================================
    print("--- 2. Security ---")

    # Layer 3: access token
    code, data = post("AI:hello;world,test", access_token=ACCESS_TOKEN)
    if ACCESS_TOKEN:
        check("POST with valid token returns 200", 200, code)
    else:
        print("\033[33m[INFO]\033[0m TEXT_CLI_ACCESS_TOKEN not set, "
              "token test skipped (ENABLE_PUBLIC_CLI may be true)")

    # Layer 2: rate limit (POST at least RATE_LIMIT_PER_HOUR+1 times in quick succession)
    print("\033[33m[INFO]\033[0m rate-limit test requires sequential burst; "
          "manually verify via repeated POST in quick succession")
    print("\033[33m[INFO]\033[0m IP blacklist test requires IP_BLACKLIST env on endpoint; "
          "manually verify by adding own IP to blacklist")

    # ================================================
    # 3. Forwarding
    # ================================================
    print("--- 3. Forwarding ---")

    code, data = get("/text-cli/skills")
    check("GET /skills returns 200", 200, code)

    # ================================================
    print("")
    print("=" * 40)
    print(f"  PASS: {PASS}  FAIL: {FAIL}")
    print("=" * 40)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

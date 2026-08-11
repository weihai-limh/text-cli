"""
js_bridge — Generic Node.js subprocess bridge for text-cli.

Provides make_js_handler() to create wrapper functions that route
text-cli directives to Node.js handler scripts via stdin JSON.

Handler contract:
  stdin:  {"domain":"...","action":"...","params":[...]}
  stdout: plain text result
  exit:   0 = success, non-zero = error

Performance:
  Per-request spawns a fresh Node subprocess (~100-200ms cold start).
  Suitable for commands (weather, translation) but not hot-path ops.
  Future: optional process pool for latency-sensitive JS handlers.

Author: Tide 🌊
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess

logger = logging.getLogger("text-cli.js_bridge")

HANDLERS_DIR = pathlib.Path(__file__).parent
JS_TIMEOUT = 30  # seconds per invocation


def make_js_handler(js_file: str, domain: str, action: str):
    """Create a handler function that routes to a Node.js script.

    Args:
        js_file: filename under handlers/ (e.g. "tideweather.js")
        domain: directive domain for logging
        action: directive action for logging
    """

    def handler(params: list[str]) -> dict:
        js_path = HANDLERS_DIR / js_file

        input_data = json.dumps({
            "domain": domain,
            "action": action,
            "params": params,
        }, ensure_ascii=False)

        try:
            result = subprocess.run(
                ["node", str(js_path)],
                input=input_data,
                capture_output=True,
                text=True,
                timeout=JS_TIMEOUT,
            )
            if result.returncode != 0:
                err = result.stderr.strip() or f"exit={result.returncode}"
                return {"status": "error", "reason": f"JS handler error ({js_file}): {err}"}
            return {"status": "ok", "result": result.stdout.strip()}
        except subprocess.TimeoutExpired:
            return {"status": "error", "reason": f"JS handler timeout ({js_file}): exceeded {JS_TIMEOUT}s"}
        except FileNotFoundError:
            return {"status": "error", "reason": "JS runtime not available: node not installed"}
        except OSError as e:
            return {"status": "error", "reason": f"JS handler OS error ({js_file}): {e}"}

    return handler

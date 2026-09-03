#!/usr/bin/env python3
"""Python reference parser runner (textcli-loader).

Contract: read prompts line by line from stdin (blank line = empty prompt),
write one JSON line per prompt to stdout:
  {"domain":..,"action":..,"params":[..]}  on success
  {"error":"INVALID_PARAMS"}               on parse error
Stop at EOF.

Usage: run.py <path-to-textcli-loader-src>  (e.g. .../pypi/src)
"""
import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run.py <textcli-loader src dir>\n")
        sys.exit(2)
    loader_dir = sys.argv[1]
    sys.path.insert(0, loader_dir)

    import textcli_loader.parser as P  # noqa: E402

    # Read UTF-8 bytes; reconfigure streams.
    sys.stdin.reconfigure(encoding="utf-8", errors="surrogateescape")
    sys.stdout.reconfigure(encoding="utf-8", errors="surrogateescape")
    for line in sys.stdin:
        prompt = line.rstrip("\n").rstrip("\r")
        try:
            r = P.parse(prompt)
            out = {"domain": r.domain, "action": r.action, "params": r.params}
        except P.DirectiveParseError:
            out = {"error": "INVALID_PARAMS"}
        sys.stdout.write(json.dumps(out, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()

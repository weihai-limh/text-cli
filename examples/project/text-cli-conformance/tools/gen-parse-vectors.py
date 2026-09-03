#!/usr/bin/env python3
"""Cross-validate parse vectors against the two reference parsers.

For each probe prompt, run both the Python textcli-loader parser and the
JS textcli-core parser, then print {domain, action, params|error} for each.
  - both agree   => candidate baseline row for vectors/parse.jsonl
  - both differ  => observe row (this is exactly the drift conformance hunts)

Usage:
  python tools/gen-parse-vectors.py > cmp.txt

NOTE: some probe strings intentionally contain non-ASCII text (Chinese city
names, the legacy "directive:" prefix). These are DATA, not code -- they
exercise UTF-8 byte handling and are legal in UTF-8 source files.
"""
import json
import subprocess
import sys
from pathlib import Path

PY_PARSER_DIR = (
    Path(__file__).resolve().parents[4]
    / "text-cli"
    / "src"
    / "skeleton"
    / "bypass-service"
    / "pypi"
    / "src"
)
JS_PARSER = (
    Path(__file__).resolve().parents[4]
    / "text-cli"
    / "src"
    / "skeleton"
    / "bypass-service"
    / "npm"
    / "textcli-core"
    / "parser.js"
)

PROBES = [
    # basic splitting
    "AI:tc-math;eval,2+3*4",
    "AI:a;b,c,d",
    "AI:a;b",
    "AI:weather;query,\u5317\u4eac,\u660e\u5929",
    "AI:a;b,c,,d",
    "AI:a;b,c,",
    "AI:a;b, c , d ",
    "AI:Weather;Query,\u5317\u4eac",
    "  AI:a;b,c  ",
    # bracket depth
    "AI:a;b,c,{x:1,y:2}",
    "AI:a;b,{a:{b:1,c:[1,2]}},z",
    "AI:a;b,{x:1},y",
    "AI:a;b,{x:1,y:2",
    "AI:a;b,[1,2,3],z",
    "AI:a;b,[{a:1},{a:2}],z",
    "AI:a;b,{x:1,[2,3]},tail",
    # quotes / escapes
    'AI:a;b,"x,y",z',
    "AI:a;b,'x,y',z",
    "AI:a;b,c\\,d,e",
    "AI:a;b,c\\\\d",
    'AI:a;b,{text: "has, comma"}',
    # error shapes
    "AI:;b,c",
    "AI:a;,c",
    "AI:abc",
    "",
    # legacy prefix (observability only -- core-c/rust are AI:-only)
    "\u6307\u4ee4:a;b,c",
    # too many params
    "AI:a;b," + ",".join(f"p{i}" for i in range(1, 56)),
]


def run_py(prompt: str):
    sys.path.insert(0, str(PY_PARSER_DIR))
    import textcli_loader.parser as P  # type: ignore

    try:
        r = P.parse(prompt)
        return {"domain": r.domain, "action": r.action, "params": r.params}
    except P.DirectiveParseError as e:
        return {"error": e.code}
    except Exception as e:  # noqa: BLE001
        return {"error": type(e).__name__}


def run_js(prompt: str):
    js = r"""
const { parse } = require(String.raw`%s`);
const input = JSON.parse(process.argv[1]);
const r = parse(input);
if (r.error) { console.log(JSON.stringify({ error: r.error })); }
else { console.log(JSON.stringify({ domain: r.domain, action: r.action, params: r.params })); }
""" % str(JS_PARSER)
    r = subprocess.run(
        ["node", "-e", js, json.dumps(prompt)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    out = r.stdout.strip()
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        return {"error": f"node-fail: {out[:120]!r} stderr={r.stderr[:120]!r}"}


def main():
    for p in PROBES:
        py = run_py(p)
        js = run_js(p)
        same = py == js
        flag = "SAME" if same else "DIFF"
        row = {
            "probe": p,
            "py": py,
            "js": js,
        }
        print(f"[{flag}] " + json.dumps(row, ensure_ascii=False))


if __name__ == "__main__":
    main()

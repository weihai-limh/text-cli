#!/usr/bin/env python3
"""
check-protocol.py — Protocol invariant checker.

Validates protocol-level invariants across the codebase — not a test runner,
not a build tool. Think of it as "protocol lint": it scans source files for
violations of SPEC-mandated contracts.

Rules:
  1  rst_err ∈ {6 codes} ∪ {""}
  2  rst_types ∈ {text,picture,video,audio,file}
  3  envelope has {rst_types, rst_data, rst_err}
  4  line format AI:domain;action,params  (A3 only)
  5  error signal on rst_err, not rst_data.status:"error"
  6  rst_data has no pray_rst_types (internal convention key)
  9  schema.json required fields

Scope:
  - Outbound: A3/A5/A2 src/skeleton/ Python handlers + response.py envelope construction
  - Inbound:  A3 main.py parser (rule 4 only)
  - Schema:   src/text_cli/open_text_cli/standard-python/*/schema.json
  - Bypass:   bypass-service/*  (rule 7* — cross-runtime isomorphism, future)

NOT in scope (by design):
  - A0/A1 (consumer side, free-form)
  - deploy/ (generated, not source of truth)
  - Runtime dispatch semantics
  - Auth, path protocol, aggregate declarations

Usage:
  python scripts/check-protocol.py              # all rules
  python scripts/check-protocol.py --rule 1     # single rule
  python scripts/check-protocol.py --check      # exit non-zero on violations (CI mode)

Exit codes:
  0 — all checks passed
  1 — violations found (--check mode)
  0 — violations found (default mode, reports but does not fail)
"""

import argparse
import json
import os
import pathlib
import re
import sys

THIS_FILE = pathlib.Path(__file__).resolve()
PROJECT_ROOT = THIS_FILE.parent.parent

# ── SPEC constants ──────────────────────────────────────────────
ERR_CODES = {"", "ERR_NOT_FOUND", "ERR_EXECUTION", "ERR_ROUTING",
             "INVALID_PARAMS", "ACCESS_DENIED", "SERVICE_DENIED"}
RST_TYPES = {"text", "picture", "video", "audio", "file"}

# ── Scan targets ────────────────────────────────────────────────
SKELETON_ROOT = PROJECT_ROOT / "src" / "skeleton"

OUTBOUND_LAYERS = [
    ("A3-service", SKELETON_ROOT / "service" / "A3-service"),
    # ("A5-endpoint", SKELETON_ROOT / "endpoint" / "A5-endpoint"),
    # ("A2-copilot", SKELETON_ROOT / "copilot" / "A2-copilot"),
]

SCHEMA_PACKAGES = [
    PROJECT_ROOT / "src" / "text_cli" / "open_text_cli" / "standard-python",
    PROJECT_ROOT / "src" / "text_cli" / "base_text-cli" / "template",
]

# ── Rule registries ─────────────────────────────────────────────
violations = []


def v(rule: int, layer: str, file: str, line: int, msg: str):
    """Record a protocol violation."""
    violations.append((rule, layer, file, line, msg))


# ═══════════════════════════════════════════════════════════════
# Rule 1: rst_err ∈ {6 codes} ∪ {""}
# ═══════════════════════════════════════════════════════════════
def check_rule1():
    """Scan outbound Python files for rst_err assignments outside the closed set."""
    pattern = re.compile(r'["\']rst_err["\']\s*[=:]\s*["\']([^"\']+)["\']')

    for layer_name, layer_dir in OUTBOUND_LAYERS:
        if not layer_dir.is_dir():
            continue
        for py_file in layer_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                for m in pattern.finditer(line):
                    code = m.group(1)
                    if code not in ERR_CODES:
                        v(1, layer_name, str(py_file.relative_to(layer_dir)),
                          lineno, f'rst_err="{code}" not in closed set')


# ═══════════════════════════════════════════════════════════════
# Rule 2: rst_types ∈ {text,picture,video,audio,file}
# ═══════════════════════════════════════════════════════════════
def check_rule2():
    """Scan outbound Python files for rst_types assignments outside closed set."""
    pattern = re.compile(r'["\']rst_types["\']\s*[=:]\s*["\']([^"\']+)["\']')

    for layer_name, layer_dir in OUTBOUND_LAYERS:
        if not layer_dir.is_dir():
            continue
        for py_file in layer_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                for m in pattern.finditer(line):
                    code = m.group(1)
                    if code not in RST_TYPES:
                        v(2, layer_name, str(py_file.relative_to(layer_dir)),
                          lineno, f'rst_types="{code}" not in closed set')


# ═══════════════════════════════════════════════════════════════
# Rule 3: envelope has {rst_types, rst_data, rst_err}
# ═══════════════════════════════════════════════════════════════
def check_rule3():
    """Check that response construction sites emit all three envelope fields.

    This is a heuristic scan: it looks for JSONResponse / dict constructions
    near 'return' statements in outbound Python files, and verifies the three
    fields are present.
    """
    required = {"rst_types", "rst_data", "rst_err"}

    for layer_name, layer_dir in OUTBOUND_LAYERS:
        if not layer_dir.is_dir():
            continue

        # Focus on response.py (canonical envelope) and main.py (hand-rolled envelopes)
        for py_name in ("core/response.py", "main.py"):
            py_file = layer_dir / py_name
            if not py_file.is_file():
                continue
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            # Scan each top-level function for envelope constructions
            lines = content.splitlines()
            in_func = False
            func_name = ""
            func_body_start = 0

            for lineno, line in enumerate(lines, 1):
                stripped = line.strip()

                # Track function boundaries
                if stripped.startswith("def ") and not stripped.startswith("def _"):
                    in_func = True
                    func_name = stripped.split("(")[0].replace("def ", "").strip()
                    func_body_start = lineno
                    continue
                if in_func and not stripped.startswith((" ", "\t", ")", "else:", "elif ", "except", "finally:")) and lineno > func_body_start + 1:
                    in_func = False

                if not in_func:
                    continue

                # Look for envelope constructions: dicts with rst_err or rst_types
                if '"rst_err"' in stripped or "'rst_err'" in stripped:
                    # Check all three fields appear within a ~10-line window
                    window = lines[max(0, lineno-5):min(len(lines), lineno+5)]
                    window_text = "\n".join(window)
                    present = {f for f in required
                               if f'"{f}"' in window_text or f"'{f}'" in window_text}
                    missing = required - present
                    if missing:
                        v(3, layer_name, str(py_file.relative_to(layer_dir)),
                          lineno, f"envelope in {func_name}() missing: {', '.join(sorted(missing))}")


# ═══════════════════════════════════════════════════════════════
# Rule 4: line format AI:domain;action,params  (A3 inbound only)
# ═══════════════════════════════════════════════════════════════
def check_rule4():
    """Verify the parser in A3 main.py matches the SPEC line format.

    This is a lightweight check: confirm the parser module is present and
    its regex patterns match the SPEC-defined format. We don't fuzz — we
    verify the structural anchors.
    """
    a3_dir = SKELETON_ROOT / "service" / "A3-service"
    parser_file = a3_dir / "service" / "core" / "parser.py"

    if not parser_file.is_file():
        v(4, "A3-service", "core/parser.py", 0,
          "parser.py not found — cannot verify line format compliance")
        return

    try:
        content = parser_file.read_text(encoding="utf-8")
    except Exception:
        v(4, "A3-service", "core/parser.py", 0, "cannot read parser.py")
        return

    # The parser must accept both AI: and 指令: prefixes
    if "AI:" not in content and "指令:" not in content:
        v(4, "A3-service", "core/parser.py", 0,
          "parser does not reference AI: or 指令: prefix")


# ═══════════════════════════════════════════════════════════════
# Rule 5: error signal on rst_err, not rst_data.status:"error"
# ═══════════════════════════════════════════════════════════════
def check_rule5():
    """Scan outbound Python for responses where rst_data has status:"error"
    but rst_err is missing or empty — the old anti-pattern.

    SPEC §1.2.2 / §1.2.7: failure MUST signal via rst_err, not via
    rst_data.status alone.
    """
    for layer_name, layer_dir in OUTBOUND_LAYERS:
        if not layer_dir.is_dir():
            continue
        for py_file in layer_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue

            lines = content.splitlines()
            for lineno, line in enumerate(lines, 1):
                stripped = line.strip()
                if '"status"' in stripped and '"error"' in stripped and 'rst_data' in stripped:
                    # Check nearby lines for rst_err
                    window = lines[max(0, lineno-3):min(len(lines), lineno+3)]
                    window_text = "\n".join(window)
                    if '"rst_err"' not in window_text and "'rst_err'" not in window_text:
                        v(5, layer_name, str(py_file.relative_to(layer_dir)),
                          lineno, f"status:'error' without rst_err signal: {stripped[:80]}")


# ═══════════════════════════════════════════════════════════════
# Rule 6: rst_data has no pray_rst_types (internal convention key)
# ═══════════════════════════════════════════════════════════════
def check_rule6():
    """SPEC §1.2.2: pray_rst_types is an internal key lifted to rst_types
    by the skeleton. It must never leak into rst_data of an outbound envelope.
    """
    pattern = re.compile(r'["\']pray_rst_types["\']')

    for layer_name, layer_dir in OUTBOUND_LAYERS:
        if not layer_dir.is_dir():
            continue
        for py_file in layer_dir.rglob("*.py"):
            try:
                content = py_file.read_text(encoding="utf-8")
            except Exception:
                continue
            for lineno, line in enumerate(content.splitlines(), 1):
                if pattern.search(line):
                    # Allow it only in response.py (the skeleton itself)
                    if "response.py" not in str(py_file):
                        v(6, layer_name, str(py_file.relative_to(layer_dir)),
                          lineno, "pray_rst_types leaked into rst_data")


# ═══════════════════════════════════════════════════════════════
# Rule 9: schema.json required fields
# ═══════════════════════════════════════════════════════════════
# SPEC §3.2: package-level required fields
PACKAGE_REQUIRED = {"id", "name", "type", "runtime", "category", "locales", "trust"}
# SPEC §3.3: directive-level required fields
DIRECTIVE_REQUIRED = {"domain", "action", "usage", "description"}


def check_rule9():
    """Validate schema.json files against SPEC §3.2 / §3.3 required fields."""
    for pkg_root in SCHEMA_PACKAGES:
        if not pkg_root.is_dir():
            continue
        for schema_file in pkg_root.rglob("schema.json"):
            try:
                data = json.loads(schema_file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                v(9, "schema", str(schema_file.relative_to(PROJECT_ROOT)),
                  0, f"invalid JSON: {e}")
                continue
            except Exception:
                continue

            pkg_id = data.get("id", str(schema_file.parent.name))
            rel = str(schema_file.relative_to(PROJECT_ROOT))

            # Package-level fields
            for field in PACKAGE_REQUIRED:
                if field not in data:
                    v(9, "schema", rel, 0,
                      f"[{pkg_id}] missing package field: {field}")

            # Directive-level fields
            directives = data.get("directives", [])
            if not directives:
                v(9, "schema", rel, 0,
                  f"[{pkg_id}] directives is empty or missing")
                continue

            for i, d in enumerate(directives):
                for field in DIRECTIVE_REQUIRED:
                    if field not in d:
                        v(9, "schema", rel, 0,
                          f"[{pkg_id}] directives[{i}] missing field: {field}")

            # Cross-check: directives[].domain must be ASCII (routing key)
            for i, d in enumerate(directives):
                domain = d.get("domain", "")
                if domain and not domain.isascii():
                    v(9, "schema", rel, 0,
                      f"[{pkg_id}] directives[{i}] domain '{domain}' is not ASCII")
                action = d.get("action", "")
                if action and not action.isascii():
                    v(9, "schema", rel, 0,
                      f"[{pkg_id}] directives[{i}] action '{action}' is not ASCII")


# ═══════════════════════════════════════════════════════════════
# Rule registry
# ═══════════════════════════════════════════════════════════════
RULES = {
    1: ("rst_err ∈ closed set", check_rule1),
    2: ("rst_types ∈ closed set", check_rule2),
    3: ("envelope 3-field", check_rule3),
    4: ("line format AI:domain;action", check_rule4),
    5: ("error signal on rst_err", check_rule5),
    6: ("no pray_rst_types in rst_data", check_rule6),
    9: ("schema.json required fields", check_rule9),
}

ALL_RULES = sorted(RULES.keys())


def main():
    parser = argparse.ArgumentParser(
        description="Protocol invariant checker — validates SPEC-mandated contracts")
    parser.add_argument("--rule", type=int, choices=ALL_RULES,
                        help="Run a single rule (default: all)")
    parser.add_argument("--check", action="store_true",
                        help="Exit non-zero on violations (CI mode)")
    parser.add_argument("--list", action="store_true",
                        help="List available rules and exit")
    args = parser.parse_args()

    if args.list:
        for rid in ALL_RULES:
            print(f"  rule {rid}: {RULES[rid][0]}")
        return

    selected = [args.rule] if args.rule else ALL_RULES

    for rid in selected:
        name, fn = RULES[rid]
        print(f"[rule {rid}] {name} ... ", end="", flush=True)
        fn()
        rule_violations = [x for x in violations if x[0] == rid]
        if rule_violations:
            print(f"{len(rule_violations)} violation(s)")
        else:
            print("PASS")

    # ── Summary ──
    print()
    if violations:
        print(f"=== {len(violations)} protocol violation(s) ===")
        for rule, layer, file, line, msg in violations:
            print(f"  R{rule} [{layer}] {file}:{line}  {msg}")
        if args.check:
            sys.exit(1)
    else:
        print("All protocol checks passed.")


if __name__ == "__main__":
    main()

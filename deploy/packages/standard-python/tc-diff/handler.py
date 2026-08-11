"""
tc-diff handler — Text diff processor for path pipelines.

Line-level unified diff, similarity ratio, patch application, word-level diff.
Zero external dependencies, stdlib difflib only.

Directives:
    tc-diff;unified,<text_a>,<text_b>[,<context>,<label_a>,<label_b>]  — unified diff
    tc-diff;similarity,<text_a>,<text_b>                                — similarity ratio
    tc-diff;patch,<original>,<diff>                                     — apply diff to original
    tc-diff;word-diff,<text_a>,<text_b>[,<format>]                      — word-level ops/HTML
"""
import difflib
import logging
import re

from core.registry import directive

logger = logging.getLogger(__name__)


def init_tc_diff_handler():
    logger.info("tc-diff initialised")



def _unified(text_a, text_b, context=3, label_a="a", label_b="b"):
    a_lines = [line + "\n" for line in text_a.splitlines()]
    b_lines = [line + "\n" for line in text_b.splitlines()]
    diff_lines = list(difflib.unified_diff(
        a_lines, b_lines,
        fromfile=label_a, tofile=label_b,
        n=context
    ))
    return "".join(diff_lines) if diff_lines else ""


def _count_hunks(diff_text):
    count = 0
    for line in diff_text.splitlines():
        if line.startswith("@@") and line.endswith("@@"):
            count += 1
    return count


def _similarity(text_a, text_b):
    a_lines = text_a.splitlines()
    b_lines = text_b.splitlines()
    matcher = difflib.SequenceMatcher(None, a_lines, b_lines)
    ratio = matcher.ratio()
    return {
        "ratio": round(ratio, 4),
        "lines_a": len(a_lines),
        "lines_b": len(b_lines),
        "equal": ratio == 1.0,
    }



_HUNK_RE = re.compile(r'^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@')


def _parse_hunk_header(line):
    m = _HUNK_RE.match(line)
    if not m:
        return None
    old_start = int(m.group(1))
    old_count = int(m.group(2)) if m.group(2) else 1
    new_start = int(m.group(3))
    new_count = int(m.group(4)) if m.group(4) else 1
    return (old_start, old_count, new_start, new_count)


def _patch(original, diff_text):
    original_lines = original.splitlines()
    original_ends_with_newline = original.endswith("\n") or original.endswith("\r\n")
    diff_lines = diff_text.splitlines()

    result = []
    orig_idx = 0
    diff_idx = 0
    hunks_total = 0
    hunks_applied = 0
    conflicts = []

    while diff_idx < len(diff_lines):
        line = diff_lines[diff_idx]

        if line.startswith("---") or line.startswith("+++"):
            diff_idx += 1
            continue

        if line.startswith("@@") and line.endswith("@@"):
            hunks_total += 1
            parsed = _parse_hunk_header(line)
            if not parsed:
                return _patch_error("invalid hunk header", line)
            old_start, old_count, new_start, new_count = parsed
            diff_idx += 1

            expected_idx = old_start - 1
            if orig_idx > expected_idx:
                conflicts.append({
                    "hunk": hunks_total,
                    "reason": f"context rewind: at line {orig_idx+1}, hunk expects line {old_start}"
                })
                diff_idx = _skip_hunk(diff_lines, diff_idx)
                continue

            if orig_idx < expected_idx:
                result.extend(original_lines[orig_idx:expected_idx])
                orig_idx = expected_idx

            hunk_ok = True
            hunk_old_idx = orig_idx

            while diff_idx < len(diff_lines):
                hline = diff_lines[diff_idx]
                if hline.startswith("@@") and hline.endswith("@@"):
                    break
                if hline.startswith("---") or hline.startswith("+++"):
                    break

                if hline.startswith(" "):
                    ctx = hline[1:]
                    if hunk_old_idx >= len(original_lines):
                        hunk_ok = False
                    elif original_lines[hunk_old_idx] != ctx:
                        hunk_ok = False
                    if hunk_ok:
                        result.append(original_lines[hunk_old_idx])
                        hunk_old_idx += 1
                elif hline.startswith("-"):
                    rm = hline[1:]
                    if hunk_old_idx >= len(original_lines):
                        hunk_ok = False
                    elif original_lines[hunk_old_idx] != rm:
                        hunk_ok = False
                    if hunk_ok:
                        hunk_old_idx += 1
                elif hline.startswith("+"):
                    result.append(hline[1:])
                elif hline.startswith("\\"):
                    pass
                else:
                    hunk_ok = False

                diff_idx += 1

            if hunk_ok:
                hunks_applied += 1
                orig_idx = hunk_old_idx
            else:
                conflicts.append({
                    "hunk": hunks_total,
                    "reason": f"context mismatch near line {orig_idx+1}"
                })
            continue

        diff_idx += 1

    if orig_idx < len(original_lines):
        result.extend(original_lines[orig_idx:])

    patched = "\n".join(result)
    if original_ends_with_newline and patched:
        patched += "\n"
    resp = {
        "status": "conflict" if conflicts else "ok",
        "patched": patched,
        "hunks_applied": hunks_applied,
        "hunks_total": hunks_total,
        "lines_result": len(patched.splitlines()) if patched else 0,
    }
    if conflicts:
        resp["conflicts"] = conflicts
    return resp


def _skip_hunk(diff_lines, idx):
    while idx < len(diff_lines):
        line = diff_lines[idx]
        if line.startswith("@@") and line.endswith("@@"):
            break
        idx += 1
    return idx


def _patch_error(reason, line=None):
    err = {"status": "error", "reason": reason}
    if line is not None:
        err["line"] = line.strip()
    return err



_WS_RE = re.compile(r'(\s+|\S+)')


def _tokenize(text):
    return _WS_RE.findall(text)


def _ops_to_html(ops):
    parts = []
    for op in ops:
        t = op["type"]
        if t == "equal":
            parts.append(_html_escape(op["value"]))
        elif t == "replace":
            parts.append("<del>")
            parts.append(_html_escape(op["old"]))
            parts.append("</del><ins>")
            parts.append(_html_escape(op["new"]))
            parts.append("</ins>")
        elif t == "delete":
            parts.append("<del>")
            parts.append(_html_escape(op["value"]))
            parts.append("</del>")
        elif t == "insert":
            parts.append("<ins>")
            parts.append(_html_escape(op["value"]))
            parts.append("</ins>")
    return "".join(parts)


def _html_escape(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _word_diff(text_a, text_b, fmt="ops"):
    tokens_a = _tokenize(text_a)
    tokens_b = _tokenize(text_b)
    matcher = difflib.SequenceMatcher(None, tokens_a, tokens_b)
    ops = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            ops.append({"type": "equal", "value": "".join(tokens_a[i1:i2])})
        elif tag == "replace":
            ops.append({
                "type": "replace",
                "old": "".join(tokens_a[i1:i2]),
                "new": "".join(tokens_b[j1:j2]),
            })
        elif tag == "delete":
            ops.append({"type": "delete", "value": "".join(tokens_a[i1:i2])})
        elif tag == "insert":
            ops.append({"type": "insert", "value": "".join(tokens_b[j1:j2])})

    ratio = round(matcher.ratio(), 4)
    if fmt == "html":
        return {"status": "ok", "format": "html", "ratio": ratio, "html": _ops_to_html(ops)}
    return {"status": "ok", "format": "ops", "ratio": ratio, "operations": ops}



@directive("tc-diff", "unified", domain_alias="文本差异", action_aliases={"unified": "统一差异"})
def tc_diff_unified(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-diff;unified,<text_a>,<text_b>[,<context>,<label_a>,<label_b>]"}

    text_a = params[0]
    text_b = params[1]
    ctx = int(params[2]) if len(params) > 2 and params[2] else 3
    label_a = params[3] if len(params) > 3 and params[3] else "a"
    label_b = params[4] if len(params) > 4 and params[4] else "b"

    diff = _unified(text_a, text_b, context=ctx, label_a=label_a, label_b=label_b)

    return {
        "status": "ok",
        "has_diff": diff != "",
        "lines_a": text_a.count("\n") + (1 if text_a else 0),
        "lines_b": text_b.count("\n") + (1 if text_b else 0),
        "diff": diff,
        "hunks": _count_hunks(diff),
    }


@directive("tc-diff", "similarity", domain_alias="文本差异", action_aliases={"similarity": "相似度"})
def tc_diff_similarity(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-diff;similarity,<text_a>,<text_b>"}

    result = _similarity(params[0], params[1])
    result["status"] = "ok"
    return result


@directive("tc-diff", "patch", domain_alias="文本差异", action_aliases={"patch": "应用补丁"})
def tc_diff_patch(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-diff;patch,<original>,<diff>"}

    original = params[0]
    diff_text = params[1]

    if not diff_text.strip():
        return {
            "status": "ok",
            "patched": original,
            "hunks_applied": 0,
            "hunks_total": 0,
            "lines_result": original.count("\n") + (1 if original else 0),
        }

    if not original and not diff_text.strip():
        return {
            "status": "ok",
            "patched": "",
            "hunks_applied": 0,
            "hunks_total": 0,
            "lines_result": 0,
        }

    result = _patch(original, diff_text)
    return result


@directive("tc-diff", "word-diff", domain_alias="文本差异", action_aliases={"word-diff": "词级差异"})
def tc_diff_word_diff(params: list[str]) -> dict:
    if len(params) < 2:
        return {"status": "error", "reason": "Usage: tc-diff;word-diff,<text_a>,<text_b>[,<format>]"}

    text_a = params[0]
    text_b = params[1]
    fmt = params[2] if len(params) > 2 and params[2] else "ops"

    if fmt not in ("ops", "html"):
        return {"status": "error", "reason": "format must be 'ops' or 'html'"}

    result = _word_diff(text_a, text_b, fmt=fmt)
    return result

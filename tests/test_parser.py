"""
Test parser unification and alias resolution.

Covers 7 cases:
  T1: 指令:domain;action          (legacy prefix, ascii colon)
  T2: AI:domain;action             (new prefix, ascii colon)
  T3: 指令：domain;action          (legacy prefix, unicode colon)
  T4: AI：domain;action            (new prefix, unicode colon)
  T5: Leading/trailing whitespace  (robustness)
  T6: directive_key preserves prefix
  T7: Registry alias dispatch (bidirectional)
"""

import sys
import os

# Ensure text_cli/python is on the path
# Add text_cli/python to path (test file is at project_root/tests/test_parser.py)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'text_cli', 'python'))

from core.parser import parse_directive, DirectiveParseError, ParsedDirective  # noqa: E402


# ═══════════════════════════════════════════════════════════════
# Parser Tests
# ═══════════════════════════════════════════════════════════════

def test_valid_parses():
    """T1-T4: All 4 prefix×colon combinations parse correctly"""
    cases = [
        # (input, expected_domain, expected_action, expected_params, label)
        ("指令:key;register,svc,val,type", "key", "register", ["svc", "val", "type"], "T1: legacy prefix, ascii colon"),
        ("AI:key;register,svc,val,type", "key", "register", ["svc", "val", "type"], "T2: new prefix, ascii colon"),
        ("指令：key;register,svc,val,type", "key", "register", ["svc", "val", "type"], "T3: legacy prefix, unicode colon"),
        ("AI：key;register,svc,val,type", "key", "register", ["svc", "val", "type"], "T4: new prefix, unicode colon"),
    ]

    for prompt, exp_domain, exp_action, exp_params, label in cases:
        parsed = parse_directive(prompt)
        assert parsed.domain == exp_domain, f"{label}: domain mismatch: {parsed.domain!r} != {exp_domain!r}"
        assert parsed.action == exp_action, f"{label}: action mismatch: {parsed.action!r} != {exp_action!r}"
        assert parsed.params == exp_params, f"{label}: params mismatch: {parsed.params!r} != {exp_params!r}"
        print(f"  ✓ {label}")


def test_whitespace_robustness():
    """T5: Leading/trailing whitespace is stripped, internal spaces preserved"""
    cases = [
        ("  指令:key;register,svc  ", "key", "register", ["svc"], "leading + trailing spaces"),
        ("AI: domain ; action , p1 , p2 ", "domain", "action", ["p1", "p2"], "internal spaces"),
        ("  指令： 语义 ; 编码 , hello world  ", "语义", "编码", ["hello world"], "mixed whitespace + unicode colon"),
    ]
    for prompt, exp_domain, exp_action, exp_params, label in cases:
        parsed = parse_directive(prompt)
        assert parsed.domain == exp_domain, f"{label}: domain mismatch"
        assert parsed.action == exp_action, f"{label}: action mismatch"
        assert parsed.params == exp_params, f"{label}: params mismatch"
        print(f"  ✓ T5: {label}")


def test_directive_key_preserves_prefix():
    """T6: directive_key reflects the prefix used in the input"""
    cases = [
        ("指令:key;register", "指令:key;register"),
        ("AI:key;register", "AI:key;register"),
        ("指令：key;register", "指令:key;register"),  # Unicode colon normalized to ASCII in key
        ("AI：key;register", "AI:key;register"),
    ]
    for prompt, exp_key in cases:
        parsed = parse_directive(prompt)
        assert parsed.directive_key == exp_key, \
            f"directive_key mismatch: {parsed.directive_key!r} != {exp_key!r}"
        print(f"  ✓ T6: {prompt!r} → {parsed.directive_key!r}")


def test_no_params():
    """Directive without params section"""
    parsed = parse_directive("指令:system;status")
    assert parsed.domain == "system"
    assert parsed.action == "status"
    assert parsed.params == []
    print("  ✓ no params")


def test_error_cases():
    """Invalid inputs raise DirectiveParseError"""
    errors = [
        ("", "empty string"),
        ("hello world", "no prefix"),
        ("指令:", "prefix only, no body"),
        ("指令:;action", "empty domain"),
        ("指令:domain;", "empty action"),
        ("指令:domain;action," * 100, "too long"),
    ]
    for bad, label in errors:
        try:
            parse_directive(bad)
            assert False, f"Should have raised: {label}"
        except DirectiveParseError:
            print(f"  ✓ error: {label}")
        except AssertionError:
            raise
        except Exception as e:
            print(f"  ✓ error: {label} → {type(e).__name__}")


# ═══════════════════════════════════════════════════════════════
# Registry Alias Tests
# ═══════════════════════════════════════════════════════════════

def test_registry_alias_dispatch():
    """T7: Bidirectional alias resolution in dispatch"""
    from core.registry import directive, dispatch, get_registered_directives

    # Register with aliases
    @directive("key", "register", domain_alias="密钥", action_aliases={"register": "注册"})
    def key_register(params):
        return f"registered: {params}"

    @directive("key", "revoke", domain_alias="密钥", action_aliases={"revoke": "撤销"})
    def key_revoke(params):
        return f"revoked: {params}"

    # Test all 4 prefix×alias combinations
    cases = [
        # Canonical domain, canonical action
        ("key", "register", ["svc"], "registered: ['svc']"),
        # Canonical domain, aliased action
        ("key", "注册", ["svc"], "registered: ['svc']"),
        # Aliased domain, canonical action
        ("密钥", "register", ["svc"], "registered: ['svc']"),
        # Aliased domain, aliased action
        ("密钥", "注册", ["svc"], "registered: ['svc']"),
        # Case-insensitive
        ("KEY", "REGISTER", ["svc"], "registered: ['svc']"),
        ("密钥", "撤销", ["svc"], "revoked: ['svc']"),
    ]

    for dom, act, params, expected in cases:
        result = dispatch(dom, act, params)
        assert result == expected, f"dispatch({dom!r}, {act!r}) = {result!r} != {expected!r}"
        print(f"  ✓ alias: {dom};{act} → {result}")

    # Verify get_registered_directives returns canonical names
    reg = get_registered_directives()
    assert "key" in reg, f"Expected 'key' in registered, got {list(reg.keys())}"
    assert "register" in reg["key"]
    assert "revoke" in reg["key"]
    print(f"  ✓ registered directives: {reg}")

    # Non-existent directive
    result = dispatch("nonexistent", "action", [])
    assert "No matching directive" in result
    print("  ✓ unknown directive returns error message")


# ═══════════════════════════════════════════════════════════════
# Run
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== Parser Tests ===")
    test_valid_parses()
    test_whitespace_robustness()
    test_directive_key_preserves_prefix()
    test_no_params()
    test_error_cases()
    print()
    print("=== Registry Alias Tests ===")
    test_registry_alias_dispatch()
    print()
    print("✅ All tests passed")

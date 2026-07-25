"""
Smoke test for textcli-loader — verifies package can be loaded and executed.
"""

import json
import sys
import tempfile
import textwrap
from pathlib import Path


def test_smoke_load_and_execute():
    """End-to-end: create a temp package, load it, execute a directive."""
    # 1. Create a temporary package
    tmp = Path(tempfile.mkdtemp())
    pkg_dir = tmp / "my-date-calc"
    pkg_dir.mkdir()

    schema = {
        "id": "my-date-calc",
        "name_zh": "日期计算",
        "runtime": "python",
        "type": "native",
        "directives": [
            {"domain": "date-calc", "action": "add-days",
             "description": "Add N days to a date"}
        ]
    }
    (pkg_dir / "schema.json").write_text(
        json.dumps(schema, ensure_ascii=False), encoding="utf-8")

    handler = textwrap.dedent("""\
    from textcli_loader.registry import directive
    from datetime import datetime, timedelta

    @directive("date-calc", "add-days", domain_alias="日期计算", action_aliases={"add-days": "加天"})
    def add_days(params):
        d = datetime.strptime(params[0], "%Y-%m-%d")
        d = d + timedelta(days=int(params[1]))
        return d.strftime("%Y-%m-%d")
    """)
    (pkg_dir / "handler.py").write_text(handler, encoding="utf-8")

    # 2. Load the package
    from textcli_loader import load_package, execute, info

    meta = load_package(str(pkg_dir))
    assert meta["id"] == "my-date-calc"
    assert len(meta["directives"]) == 1
    assert meta["directives"][0]["domain"] == "date-calc"

    # 3. Execute a directive
    result = execute("AI:date-calc;add-days,2026-01-01,30")
    assert result["rst_err"] == ""
    assert "2026-01-31" in result["rst_data"]["text"], result

    # 4. Execute with Chinese alias
    result_cn = execute("AI:日期计算;加天,2026-01-01,30")
    assert result_cn["rst_err"] == ""
    assert "2026-01-31" in result_cn["rst_data"]["text"], result_cn

    # 5. Execute with mixed alias
    result_mixed = execute("AI:date-calc;加天,2026-01-01,30")
    assert result_mixed["rst_err"] == ""
    assert "2026-01-31" in result_mixed["rst_data"]["text"], result_mixed

    # 6. Info
    i = info(meta)
    assert i["loader"] == "textcli-loader"
    assert "date-calc" in i["registered"]

    # 7. Error cases — unknown directive returns "not found" string
    err = execute("AI:unknown;test")
    assert "No matching directive" in err["rst_data"]["text"], err

    # Cleanup
    import shutil
    shutil.rmtree(tmp)


if __name__ == "__main__":
    test_smoke_load_and_execute()
    print("✓ All smoke tests passed")

"""
Response adapters — normalize raw skill output to text-cli standard format.

Each adapter takes raw stdout (str) and optional adapter_config (dict),
returning a dict with "status": "ok" at minimum.

Pattern mirrors MCP bridge's adapter system.
"""

import json
import re


def passthrough(raw: str, config: dict = None) -> dict:
    """Pass raw text through as-is, wrapped in standard response."""
    return {"status": "ok", "result": raw}


def json_parse(raw: str, config: dict = None) -> dict:
    """Parse raw as JSON, wrap in standard response."""
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {"status": "ok", **data}
        return {"status": "ok", "result": data}
    except json.JSONDecodeError:
        return {"status": "error", "reason": f"JSON parse failed: {raw[:100]}"}


def md2tcjson(raw: str, config: dict = None) -> dict:
    """Convert structured Markdown to text-cli standard JSON.

    Parses patterns:
        ## Section Name          → top-level key (lowercased, underscores)
        - **Title** (meta)       → list item with title + meta
          URL line               → url field
          Description line       → snippet field

    Config can specify:
        sections: list of section names to extract (default: all)
    """
    if not raw or not raw.strip():
        return {"status": "ok", "result": raw}

    sections = config.get("sections", None) if config else None
    result = {"status": "ok"}

    current_section = None
    current_item = None
    current_field = None
    section_text = []
    list_accumulator = []

    for line in raw.split("\n"):
        stripped = line.strip()
        if not stripped or stripped == "---":
            continue

        # ## Section Header
        m = re.match(r'^##\s+(.+)', stripped)
        if m:
            if current_section:
                if section_text:
                    result[current_section] = "\n".join(section_text)
                    section_text = []
                elif list_accumulator:
                    result[current_section] = list_accumulator
                    list_accumulator = []

            section_name = m.group(1).strip().lower().replace(" ", "_")
            section_name = re.sub(r'[^a-z0-9_]', '', section_name)

            if sections is None or section_name in sections:
                current_section = section_name
                current_item = None
                current_field = None
                section_text = []
            else:
                current_section = None
            continue

        if current_section is None:
            continue

        # - **Title** (metadata)
        m = re.match(r'^[-*]\s+\*\*(.+?)\*\*\s*(?:\((.+?)\))?\s*$', stripped)
        if m:
            if current_item:
                list_accumulator.append(current_item)
            current_item = {"title": m.group(1).strip()}
            if m.group(2):
                meta_str = m.group(2).strip()
                for kv in meta_str.split(","):
                    if ":" in kv:
                        k, v = kv.split(":", 1)
                        k = k.strip().lower().replace(" ", "_")
                        current_item[re.sub(r'[^a-z0-9_]', '', k)] = v.strip()
            current_field = None
            continue

        # URL line
        m = re.match(r'^(https?://\S+)', stripped)
        if m and current_item is not None:
            current_item["url"] = m.group(1)
            continue

        # Regular text
        if current_item is not None:
            current_item["snippet"] = stripped
        elif current_field:
            if current_field not in result:
                result[current_field] = stripped
            else:
                if not isinstance(result[current_field], list):
                    result[current_field] = [result[current_field]]
                result[current_field].append(stripped)
        elif current_section and list_accumulator:
            pass
        elif current_section:
            section_text.append(stripped)

    # Flush
    if current_item:
        list_accumulator.append(current_item)
    if current_section:
        if section_text:
            result[current_section] = "\n".join(section_text)
        elif list_accumulator:
            result[current_section] = list_accumulator

    # Count for array fields
    for key, val in list(result.items()):
        if isinstance(val, list):
            key_count = f"{key}_count" if not key.endswith("s") else f"{key[:-1]}_count"
            if key_count not in result:
                result[key_count] = len(val)

    if len(result) == 1:
        return {"status": "ok", "result": raw}

    return result


def baidumap(raw: str, config: dict = None) -> dict:
    """Normalize Baidu Maps Agent Plan API response.

    Baidu uses status: 0 for success. Normalizes to text-cli standard.
    """
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"status": "error", "reason": f"Non-JSON response: {raw[:200]}"}

    if not isinstance(data, dict):
        return {"status": "ok", "result": data}

    baidu_status = data.get("status")
    if baidu_status == 0:
        return {"status": "ok", **{k: v for k, v in data.items() if k != "status"}}
    else:
        return {
            "status": "error",
            "reason": data.get("message", f"Baidu API status={baidu_status}"),
            "baidu_status": baidu_status,
        }


# Registry
ADAPTERS = {
    "passthrough": passthrough,
    "json_parse": json_parse,
    "md2tcjson": md2tcjson,
    "baidumap": baidumap,
}

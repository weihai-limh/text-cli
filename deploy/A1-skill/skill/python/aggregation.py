"""
aggregation.py — A1 endpoint registry + sync tool

Zero dependencies beyond Python stdlib.

Functions:
  load_endpoints(path)     — read agent-endpoints.json, return dict
  resolve_token(raw)       — resolve ${VAR} env references or return literal
  sync_endpoints(...)      — aggregate directives from all endpoints
  register_endpoint(text)  — parse NL text, register new endpoint
  list_endpoints(path)      — list endpoint names
  remove_endpoint(name)     — remove endpoint by name
"""

import json
import os
import re
import urllib.request
import urllib.error
import ssl

# ─── Default template ────────────────────────────────

DEFAULT_ENDPOINTS = {
    "endpoints": {
        "local-service": {
            "url": "http://127.0.0.1:28050/text-cli/cli",
            "auth": "none",
            "rank": 1,
            "trust": "internal",
        }
    }
}

# ─── Path helpers ────────────────────────────────────

def _default_path(path, filename="agent-endpoints.json"):
    """Resolve path to filename, falling back to cwd or ~/.text-cli/."""
    if path is not None:
        return path
    cwd_path = os.path.join(os.getcwd(), filename)
    if os.path.isfile(cwd_path):
        return cwd_path
    config_dir = os.path.join(os.path.expanduser("~"), ".text-cli")
    os.makedirs(config_dir, exist_ok=True)
    return os.path.join(config_dir, filename)


def _default_output_path(endpoints_path=None):
    """Resolve output path for agent-text-cli-schema.json."""
    if endpoints_path:
        return os.path.join(os.path.dirname(endpoints_path), "agent-text-cli-schema.json")
    config_dir = os.path.join(os.path.expanduser("~"), ".text-cli")
    return os.path.join(config_dir, "agent-text-cli-schema.json")


# ─── 1. load_endpoints ───────────────────────────────

def load_endpoints(path=None):
    """
    Read agent-endpoints.json and return the parsed dict.

    Falls back to DEFAULT_ENDPOINTS template if the file does not exist.

    Args:
        path: Optional path to agent-endpoints.json. Defaults to cwd or config dir.

    Returns:
        dict with "endpoints" key.
    """
    path = _default_path(path)
    if not os.path.isfile(path):
        return DEFAULT_ENDPOINTS
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ─── 2. resolve_token ────────────────────────────────

def resolve_token(raw):
    """
    Resolve a token value with optional env-var substitution.

    Args:
        raw: A string or None.

    Returns:
        - None if raw is None
        - os.environ[VAR_NAME] if raw is '${VAR_NAME}'
        - raw as-is otherwise (literal string)
    """
    if raw is None:
        return None
    _TOKEN_RE = re.compile(r"^\$\{(.+)\}$")
    m = _TOKEN_RE.match(str(raw))
    if m:
        return os.environ.get(m.group(1))
    return raw


# ─── 3. sync_endpoints ───────────────────────────────

def sync_endpoints(endpoints_path=None, output_path=None):
    """
    Aggregate directives from all configured endpoints.

    Steps:
      1. Load endpoints from agent-endpoints.json.
      2. For each endpoint, POST the discover directive to its URL.
      3. For each directive returned, append {source, rank} metadata.
      4. Write aggregated schema to agent-text-cli-schema.json (no tokens).
      5. Return summary with sync stats.

    Args:
        endpoints_path: Path to agent-endpoints.json (optional).
        output_path:    Path for agent-text-cli-schema.json output (optional).

    Returns:
        dict: {"synced": N, "failed": N, "total_directives": N}
    """
    if endpoints_path is None:
        endpoints_path = _default_path(None)
    if output_path is None:
        output_path = _default_output_path(endpoints_path)

    data = load_endpoints(endpoints_path)
    endpoints = data.get("endpoints", {})

    synced = 0
    failed = 0
    aggregated = {}

    for endpoint_name, cfg in endpoints.items():
        url = cfg.get("url", "")
        rank = cfg.get("rank", 1)
        auth = cfg.get("auth", "none")

        if not url:
            failed += 1
            continue

        # ── Build auth headers ──
        headers = {"Content-Type": "application/json"}
        if auth != "none":
            token = resolve_token(auth)
            if token:
                headers["Authorization"] = "Bearer " + token

        # ── Call discover ──
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps({"prompt": "AI:text-cli;query,json"}).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            ctx = ssl.create_default_context()
            with urllib.request.urlopen(req, context=ctx, timeout=30) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except Exception:
            failed += 1
            continue

        # ── Extract directives ──
        directives = payload.get("rst_data", [])
        if isinstance(directives, dict):
            directives = [directives]
        if not isinstance(directives, list):
            directives = []

        for directive in directives:
            d_name = (
                directive.get("directive")
                or directive.get("name")
                or ""
            )
            if not d_name:
                continue
            entry = aggregated.setdefault(d_name, [])
            source_entry = {"source": endpoint_name, "rank": rank}
            if source_entry not in entry:
                entry.append(source_entry)

        synced += 1

    # ── Write schema (source names + ranks only, no tokens) ──
    schema = {"directives": aggregated}
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(schema, f, indent=2, ensure_ascii=False)

    total_directives = len(aggregated)
    return {
        "synced": synced,
        "failed": failed,
        "total_directives": total_directives,
    }


# ─── 4. register_endpoint ────────────────────────────

def register_endpoint(nl_text, path=None):
    """
    Parse natural language text and register a new endpoint in agent-endpoints.json.

    Supported patterns:
      - "add endpoint https://example.com/text-cli/cli, token MY_TOKEN"
      - "add endpoint https://example.com/text-cli/cli"
      - URL is mandatory; token, name, rank are optional.

    Args:
        nl_text: Natural language description.
        path:    Path to agent-endpoints.json (optional).

    Returns:
        dict: The registered endpoint configuration.

    Raises:
        ValueError: If no URL is found in the text.
    """
    # Extract URL
    url_match = re.search(r"https?://\S+", nl_text)
    if not url_match:
        raise ValueError("No URL found in text. Example: add endpoint https://my-api.example.com/text-cli/cli, token MY_TOKEN")
    url = url_match.group(0).rstrip(",.;")

    # Extract token (after "token" keyword)
    token_match = re.search(r"token\s+(\S+)", nl_text, re.IGNORECASE)
    auth = resolve_token(token_match.group(1)) if token_match else "none"

    # Extract rank (after "rank" keyword)
    rank_match = re.search(r"rank\s+(\d+)", nl_text, re.IGNORECASE)
    rank = int(rank_match.group(1)) if rank_match else 1

    # Derive name from hostname
    host_match = re.search(r"https?://([^/]+)", url)
    name = host_match.group(1) if host_match else "custom-endpoint"

    # Explicit name override
    name_match = re.search(r"(?:name|as)\s+(\S+)", nl_text, re.IGNORECASE)
    if name_match:
        name = name_match.group(1).rstrip(",.;")

    # Load or create
    data = load_endpoints(path)
    if "endpoints" not in data:
        data["endpoints"] = {}

    data["endpoints"][name] = {
        "url": url,
        "auth": auth if auth != "none" else "none",
        "rank": rank,
        "trust": "external",
    }

    path = _default_path(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return data["endpoints"][name]


# ─── 5. list_endpoints ───────────────────────────────

def list_endpoints(path=None):
    """
    List all endpoint names from agent-endpoints.json.

    Args:
        path: Path to agent-endpoints.json (optional).

    Returns:
        list[str]: Endpoint names.
    """
    data = load_endpoints(path)
    return list(data.get("endpoints", {}).keys())


# ─── 6. remove_endpoint ──────────────────────────────

def remove_endpoint(name, path=None):
    """
    Remove an endpoint by name from agent-endpoints.json.

    Args:
        name: Endpoint name to remove.
        path: Path to agent-endpoints.json (optional).

    Returns:
        bool: True if the endpoint was removed, False if not found.
    """
    data = load_endpoints(path)
    endpoints = data.get("endpoints", {})
    if name not in endpoints:
        return False

    del endpoints[name]

    path = _default_path(path)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    return True


# ─── CLI entry ────────────────────────────────────────

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("usage: python aggregation.py <sync|list|add|remove> [...]")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "sync":
        result = sync_endpoints()
        print(json.dumps(result, indent=2))

    elif cmd == "list":
        names = list_endpoints()
        for n in names:
            print(n)

    elif cmd == "add":
        text = " ".join(sys.argv[2:])
        if not text:
            print("usage: python aggregation.py add <natural-language-description>")
            sys.exit(1)
        try:
            endpoint = register_endpoint(text)
            print(json.dumps(endpoint, indent=2))
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif cmd == "remove":
        if len(sys.argv) < 3:
            print("usage: python aggregation.py remove <name>")
            sys.exit(1)
        ok = remove_endpoint(sys.argv[2])
        print("OK" if ok else "Not found")

    else:
        print(f"Unknown command: {cmd}")
        print("Available: sync, list, add, remove")
        sys.exit(1)

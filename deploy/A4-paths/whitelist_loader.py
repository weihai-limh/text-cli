"""
Whitelist loader for copilot cmd_engine.

Reads all *_whitelist.json files from the whitelists dir,
aggregates into a queryable index for the terminal handler.

Format per whitelist file:
{
  "tool": "openclaw",
  "commands": [
    {
      "action": "gateway-status",
      "action_cn": "网关状态",
      "args": ["gateway", "status"],
      "args_pattern": "^$",
      "timeout": 10
    }
  ]
}

Author: Tide 🌊 · 2026-05-14
"""

import json
import pathlib
import re
from typing import Optional


class WhitelistIndex:
    """Aggregated whitelist from installed cmd packages."""

    def __init__(self, whitelist_dir: str):
        self.dir = pathlib.Path(whitelist_dir)
        # { "tool;action" → WhitelistEntry }
        self._index: dict[str, dict] = {}
        self._tool_actions: dict[str, set[str]] = {}
        self._load()

    def _load(self):
        """Glob all *_whitelist.json and build index."""
        if not self.dir.exists():
            return

        for f in sorted(self.dir.glob("*_whitelist.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue

            tool = data.get("tool", "")
            if not tool:
                continue

            self._tool_actions[tool] = set()

            for cmd in data.get("commands", []):
                action = cmd.get("action", "")
                if not action:
                    continue

                key = f"{tool};{action}"
                self._index[key] = {
                    "tool": tool,
                    "action": action,
                    "action_cn": cmd.get("action_cn", action),
                    "args": cmd.get("args", []),
                    "args_pattern": cmd.get("args_pattern"),
                    "timeout": cmd.get("timeout", 30),
                    "description": cmd.get("description", ""),
                    "_compiled": re.compile(cmd["args_pattern"]) if cmd.get("args_pattern") else None,
                }
                self._tool_actions[tool].add(action)

                # Also index Chinese alias
                action_cn = cmd.get("action_cn", "")
                if action_cn and action_cn != action:
                    key_cn = f"{tool};{action_cn}"
                    self._index[key_cn] = self._index[key]

    def lookup(self, domain: str, action: str) -> Optional[dict]:
        """Look up a whitelist entry by domain;action or domain;action_cn."""
        return self._index.get(f"{domain};{action}")

    def list_tools(self) -> list[str]:
        """List all available tool names."""
        return sorted(self._tool_actions.keys())

    def list_actions(self, tool: str) -> list[str]:
        """List available actions for a tool."""
        return sorted(self._tool_actions.get(tool, set()))

    def __len__(self):
        return len(self._index)

    def __repr__(self):
        return f"WhitelistIndex({len(self)} entries across {len(self._tool_actions)} tools)"

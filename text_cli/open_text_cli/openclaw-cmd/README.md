# openclaw-cmd

Manage OpenClaw gateway, skills, and sessions via CLI.

## Install

```
AI:text-cli;install,openclaw-cmd
```

## Dependencies

**Runtime**: `cmd`. Requires `openclaw` CLI installed on the copilot host.
Copilot executes commands via whitelist-based shell invocation.

## Directives

| Directive | Description |
|-----------|-------------|
| `openclaw;gateway-status` | Check OpenClaw gateway running status |
| `openclaw;session-list` | List active OpenClaw sessions |

## Example

```
AI:openclaw;gateway-status
→ Gateway is running (pid 12345, uptime 3d 2h)

AI:openclaw;session-list
→ 3 active sessions: main, nexus, tide
```

## Architecture

```
cmd runtime package (whitelist-based)
  ├── schema.json      — directive declarations
  └── whitelist.json   — action → shell command mapping

Execution: copilot reads whitelist.json, validates args against pattern,
runs the shell command, and returns stdout.
```

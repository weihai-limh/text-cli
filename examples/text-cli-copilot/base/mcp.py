"""
MCP deploy handler (base edition) — pure protocol layer, no Agent framework dependency

Directive:
  mcp;deploy (alias: MCP;部署),<server>,<target_dir>

  server:      MCP server config name (matches configs/<server>.json)
  target_dir:  output directory for compiled schema + registry + routing files

Compiles an mcp2textcli config JSON → text-cli schema.json + registry.json + routing.json.
Pure compilation — does not couple to any service restart or ingestion logic.

Requires: mcp2textcli toolchain at ./tools/mcp2textcli/ (included).

Usage:
  from mcp import mcp_deploy
  mcp_deploy(['tencent-maps', '/path/to/output'])
"""

import json
import os
import subprocess
from pathlib import Path

from core import ok, error


def mcp_deploy(params: list, mcp2textcli_dir: str = None) -> dict:
    """Compile MCP server config into text-cli directive registry.

    Args:
        params: [server_name, target_directory]
        mcp2textcli_dir: path to mcp2textcli toolchain (default: ./tools/mcp2textcli)

    Returns:
        ok with compilation summary, or error.
    """
    if len(params) < 2:
        return error('missing_param',
                     'Need two parameters:\n'
                     '  1. MCP server name (configs/<name>.json)\n'
                     '  2. Output directory')

    server = params[0].strip()
    target_dir = Path(params[1].strip()).resolve()

    if mcp2textcli_dir is None:
        mcp2textcli_dir = os.environ.get(
            'MCP2TEXTCLI_DIR',
            str(Path(__file__).resolve().parent / 'tools' / 'mcp2textcli')
        )

    mcp2_dir = Path(mcp2textcli_dir)
    config_file = mcp2_dir / 'configs' / f'{server}.json'
    compile_script = mcp2_dir / 'mcp2textcli.py'

    # 1. Check config exists
    if not config_file.exists():
        configs_dir = mcp2_dir / 'configs'
        available = []
        if configs_dir.exists():
            available = sorted(
                f.stem for f in configs_dir.glob('*.json')
                if not f.name.startswith('_') and f.name != 'ingest.json'
            )
        return error('config_missing',
                     f'Config not found: {config_file}\n'
                     f'Available: {", ".join(available) if available else "(none)"}')

    # 2. Ensure target directory
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        return error('target_error', f'Cannot create output directory: {e}')

    steps = []

    # 3. Compile
    try:
        result = subprocess.run(
            ['python3', str(compile_script), str(config_file),
             '--out', str(target_dir)],
            capture_output=True, text=True,
            timeout=30,
            cwd=str(mcp2_dir),
        )

        if result.returncode == 0:
            steps.append(f'Compiled: {server}')
            out = result.stdout.strip()
            if out:
                steps.append(f'   {out}')
        else:
            err = (result.stderr or result.stdout)[:500]
            return error('compile_failed', f'Compilation failed:\n{err}')
    except subprocess.TimeoutExpired:
        return error('compile_timeout', 'Compilation timeout (30s)')
    except Exception as e:
        return error('compile_error', f'Compilation exception: {e}')

    # 4. Verify outputs
    outputs = []
    for fname in ('schema.json', 'registry.json', 'routing.json'):
        fp = target_dir / fname
        if fp.exists():
            size = fp.stat().st_size
            outputs.append(f'   {fname} [{size:,} bytes]')
    if outputs:
        steps.append('Outputs:')
        steps.extend(outputs)
    else:
        steps.append('Warning: no output files — compilation may have produced nothing')

    return ok('\n'.join(steps))

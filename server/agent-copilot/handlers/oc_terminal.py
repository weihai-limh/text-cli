"""
Terminal handler mixin — Skill proxy directives
"""

import json
import subprocess
from core import ok, error


class TerminalHandlers:
    """Terminal;weather (future: search, extract, summarize)"""

    def _handle_terminal_weather(self, params: list) -> dict:
        if not params or not params[0]:
            return error('missing_param', 'Missing parameter: city_name')
        city = params[0]
        try:
            result = subprocess.run(
                ['curl', '-s', f'wttr.in/{city}?format=j1'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return error('external_error', 'Weather query failed: wttr.in unreachable')
            data = json.loads(result.stdout)
            current = data['current_condition'][0]
            text = f"{city}: {current['temp_C']}°C, {current['weatherDesc'][0]['value']}"
            return ok(text)
        except subprocess.TimeoutExpired:
            return error('timeout', 'Weather query timed out (15s)')
        except (json.JSONDecodeError, KeyError):
            return error('external_error', 'Weather data parse failed, wttr.in response format invalid')
        except Exception as e:
            return error('internal_error', f'Weather query error: {e}')

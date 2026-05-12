"""
System status handler mixin.
"""

import time
from pathlib import Path
from core import ok, error


class SystemHandlers:
    """system;health (alias: 系统;健康) / system;status (alias: 系统;状态)"""

    def _handle_system_health(self, params: list) -> dict:
        uptime = time.time() - self.start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        mem_mb = self._get_mem_mb()

        creds = self.config.get('credentials', {})
        smtp_configured = bool(creds.get('email;send', {}).get('value', ''))
        git_token_configured = bool(creds.get('git;push', {}).get('value', ''))
        git_workdir_valid = Path(self.git_workdir).is_dir()
        remote_url = self.get_remote_url() if git_workdir_valid else None

        report = (
            f"text-cli-copilot v{self.config['endpoint_info']['version']} running\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Uptime: {hours}h {minutes}m {seconds}s\n"
            f"Memory: {mem_mb:.1f} MB (RSS)\n"
            f"Registered directives: {len(self._handlers)}\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Git workdir: {self.git_workdir} {'OK' if git_workdir_valid else 'NOT FOUND'}\n"
            f"Git remote: {remote_url or 'UNREACHABLE'}\n"
            f"Git token: {'CONFIGURED' if git_token_configured else 'NOT SET (SSH)'}\n"
            f"SMTP password: {'CONFIGURED' if smtp_configured else 'NOT SET'}\n"
            f"Path whitelist: {len(self.config['security'].get('path_whitelist', []))} entries\n"
            f"\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n"
            f"Endpoint: http://{self.config['server']['host']}:{self.config['server']['port']}"
        )

        return ok(report,
                  uptime_seconds=int(uptime),
                  memory_mb=round(mem_mb, 1),
                  handlers=len(self._handlers),
                  smtp_configured=smtp_configured,
                  git_token_configured=git_token_configured)

    def _handle_system_status(self, params: list) -> dict:
        uptime = time.time() - self.start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)

        total = self._request_count
        errors = self._error_count
        error_rate = errors / total if total > 0 else 0
        rph = (total / (uptime / 3600)) if uptime > 0 else 0

        if total == 0:
            mood = '😴 idle'
        elif error_rate == 0:
            mood = '😊 all good'
        elif error_rate < 0.1:
            mood = '🙂 minor issues'
        elif error_rate < 0.3:
            mood = '😐 bumpy'
        elif error_rate < 0.5:
            mood = '😟 rough'
        else:
            mood = '😵 needs help'

        if rph > 60:
            busy = '🔥 overloaded'
        elif rph > 10:
            busy = '⚡ steady'
        elif rph > 1:
            busy = '🌊 relaxed'
        elif total > 0:
            busy = '🍃 idle'
        else:
            busy = '💤 sleeping'

        if hours >= 24:
            age = f'{hours // 24}d{hours % 24}h'
        elif hours >= 1:
            age = f'{hours}h{minutes}m'
        else:
            age = f'{minutes}m'

        report = (
            f'{mood}  {busy}\n'
            f'\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n'
            f'Working {age}, handled {total} requests\n'
            f'Errors {errors}, error rate {error_rate:.1%}\n'
            f'\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\u2501\n'
            f'Activity: ~{rph:.0f} req/h\n'
            f'Memory: {self._get_mem_mb():.1f} MB\n'
            f'Directives: {len(self._handlers)} available'
        )

        return ok(report,
                  mood=mood.split()[0],
                  busy_level=busy.split()[0],
                  total_requests=total,
                  error_count=errors,
                  error_rate=round(error_rate, 3),
                  requests_per_hour=round(rph, 1))

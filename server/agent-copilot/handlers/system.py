"""
系统状态 handler mixin。
"""

import time
from pathlib import Path
from core import ok, error


class SystemHandlers:
    """系统;健康 / 系统;状态"""

    def _handle_system_health(self, params: list) -> dict:
        uptime = time.time() - self.start_time
        hours = int(uptime // 3600)
        minutes = int((uptime % 3600) // 60)
        seconds = int(uptime % 60)
        mem_mb = self._get_mem_mb()

        creds = self.config.get('credentials', {})
        smtp_configured = bool(creds.get('邮件;发送', {}).get('value', ''))
        git_token_configured = bool(creds.get('Git;推送', {}).get('value', ''))
        git_workdir_valid = Path(self.git_workdir).is_dir()
        remote_url = self.get_remote_url() if git_workdir_valid else None

        report = (
            f"text-cli-copilot v{self.config['endpoint_info']['version']} 运行中\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"运行时间: {hours}h {minutes}m {seconds}s\n"
            f"内存占用: {mem_mb:.1f} MB (RSS)\n"
            f"已注册指令: {len(self._handlers)} 条\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"Git 工作目录: {self.git_workdir} {'✅' if git_workdir_valid else '❌ 不存在'}\n"
            f"Git 远程: {remote_url or '❌ 不可达'}\n"
            f"Git Token: {'✅ 已配置' if git_token_configured else '⚠ 未配置 (SSH)'}\n"
            f"SMTP 密码: {'✅ 已配置' if smtp_configured else '❌ 未配置'}\n"
            f"路径白名单: {len(self.config['security'].get('path_whitelist', []))} 个目录\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"服务端点: http://{self.config['server']['host']}:{self.config['server']['port']}"
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
            mood = '😴 还没人找我'
        elif error_rate == 0:
            mood = '😊 一切顺利'
        elif error_rate < 0.1:
            mood = '🙂 偶有小错'
        elif error_rate < 0.3:
            mood = '😐 有些坎坷'
        elif error_rate < 0.5:
            mood = '😟 不太顺利'
        else:
            mood = '😵 需要帮助'

        if rph > 60:
            busy = '🔥 忙不过来了'
        elif rph > 10:
            busy = '⚡ 节奏正好'
        elif rph > 1:
            busy = '🌊 不紧不慢'
        elif total > 0:
            busy = '🍃 悠闲'
        else:
            busy = '💤 空闲中'

        if hours >= 24:
            age = f'{hours // 24}天{hours % 24}小时'
        elif hours >= 1:
            age = f'{hours}小时{minutes}分钟'
        else:
            age = f'{minutes}分钟'

        report = (
            f'{mood}  {busy}\n'
            f'━━━━━━━━━━━━━━━━\n'
            f'已工作 {age}，处理 {total} 次请求\n'
            f'出错 {errors} 次，错误率 {error_rate:.1%}\n'
            f'━━━━━━━━━━━━━━━━\n'
            f'活跃度：~{rph:.0f} req/h\n'
            f'内存：{self._get_mem_mb():.1f} MB\n'
            f'指令：{len(self._handlers)} 条可用'
        )

        return ok(report,
                  mood=mood.split()[0],
                  busy_level=busy.split()[0],
                  total_requests=total,
                  error_count=errors,
                  error_rate=round(error_rate, 3),
                  requests_per_hour=round(rph, 1))

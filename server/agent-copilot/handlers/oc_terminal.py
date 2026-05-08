"""
终端 handler mixin — Skill 代理指令
"""

import json
import subprocess
from core import ok, error


class TerminalHandlers:
    """终端;天气（未来: 搜索, 提取, 摘要）"""

    def _handle_terminal_weather(self, params: list) -> dict:
        if not params or not params[0]:
            return error('missing_param', '缺少参数: 城市名')
        city = params[0]
        try:
            result = subprocess.run(
                ['curl', '-s', f'wttr.in/{city}?format=j1'],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0:
                return error('external_error', f'天气查询失败: wttr.in 不可达')
            data = json.loads(result.stdout)
            current = data['current_condition'][0]
            text = f"{city} 当前: {current['temp_C']}°C, {current['weatherDesc'][0]['value']}"
            return ok(text)
        except subprocess.TimeoutExpired:
            return error('timeout', '天气查询超时 (15s)')
        except (json.JSONDecodeError, KeyError):
            return error('external_error', '天气数据解析失败，wttr.in 响应格式异常')
        except Exception as e:
            return error('internal_error', f'天气查询异常: {e}')

"""
Git 操作 handler mixin。
"""

import subprocess
from core import ok, error


class GitHandlers:
    """Git;状态 / Git;推送"""

    def _handle_git_status(self, params: list) -> dict:
        try:
            result = subprocess.run(
                ['git', 'status'],
                cwd=self.git_workdir, capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            if not output.strip():
                output = '(empty output)'
            return ok(output.strip())
        except FileNotFoundError:
            return error('git_not_found', '系统中未找到 git 命令')
        except subprocess.TimeoutExpired:
            return error('timeout', 'git status 超时 (30s)')
        except Exception as e:
            return error('internal_error', f'git status 失败: {e}')

    def _handle_git_push(self, params: list) -> dict:
        if not params or not params[0]:
            return error('missing_param', '缺少参数: 分支名')
        branch = params[0]

        if not self.check_branch(branch):
            return error('branch_denied',
                        f'分支 {branch} 不在推送白名单内')

        creds = self.config.get('credentials', {})
        git_creds = creds.get('Git;推送', {})
        cred = self.resolve_credential(git_creds.get('value'))

        remote_url = self.get_remote_url()
        if remote_url is None:
            return error('no_remote', f'无法获取远程仓库 URL ({self.git_remote_name})')

        remote_name = self.git_remote_name

        # Mode 1: 指令服务器注入（代码预留）
        if cred['mode'] == 'inject':
            return error('not_implemented',
                        '凭据注入模式 (Mode 1) 尚未实现，请使用环境变量或 SSH')

        # Mode 2: HTTPS (token from env/plaintext)
        if cred['mode'] == 'https' and cred.get('token'):
            try:
                token = cred['token']
                if remote_url.startswith('https://'):
                    inline_url = remote_url.replace('https://', f'https://{token}@')
                elif remote_url.startswith('http://'):
                    inline_url = remote_url.replace('http://', f'http://{token}@')
                else:
                    if '@' in remote_url:
                        _, path = remote_url.split('@', 1)
                        path = path.replace(':', '/', 1)
                        inline_url = f'https://{token}@{path}'
                    else:
                        inline_url = f'https://{token}@{remote_url}'

                result = subprocess.run(
                    ['git', 'push', inline_url, branch],
                    cwd=self.git_workdir, capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    output = result.stdout + result.stderr
                    return ok(output.strip() or f'推送成功: {branch} → {remote_name}/{branch}',
                             auth_mode='https')
                else:
                    print(f"[copilot] HTTPS push 失败，降级 SSH: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                return error('timeout', 'git push 超时 (30s)')
            except Exception as e:
                print(f"[copilot] HTTPS push 异常，降级 SSH: {e}")

        # Mode 2 (token 为空) / Mode 3: SSH / HTTPS 降级
        try:
            result = subprocess.run(
                ['git', 'push', remote_name, branch],
                cwd=self.git_workdir, capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return ok(output.strip() or f'推送成功: {branch} → {remote_name}/{branch}',
                         auth_mode='ssh')
            else:
                return error('push_failed',
                            f'推送失败: {output.strip() or result.stderr.strip()}')
        except subprocess.TimeoutExpired:
            return error('timeout', 'git push 超时 (30s)')
        except Exception as e:
            return error('push_failed', f'推送异常: {e}')

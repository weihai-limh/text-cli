"""
Git operations handler mixin.
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
            return error('git_not_found', 'git command not found on system')
        except subprocess.TimeoutExpired:
            return error('timeout', 'git status timed out (30s)')
        except Exception as e:
            return error('internal_error', f'git status failed: {e}')

    def _handle_git_push(self, params: list) -> dict:
        if not params or not params[0]:
            return error('missing_param', 'Missing parameter: branch_name')
        branch = params[0]

        if not self.check_branch(branch):
            return error('branch_denied',
                        f'Branch {branch} not in push whitelist')

        creds = self.config.get('credentials', {})
        git_creds = creds.get('Git;推送', {})
        cred = self.resolve_credential(git_creds.get('value'))

        remote_url = self.get_remote_url()
        if remote_url is None:
            return error('no_remote', f'Cannot get remote repo URL ({self.git_remote_name})')

        remote_name = self.git_remote_name

        # Mode 1: Copilot server injects (reserved for future)
        if cred['mode'] == 'inject':
            return error('not_implemented',
                        'Credential injection mode (Mode 1) not yet implemented, use env var or SSH')

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
                    return ok(output.strip() or f'Push successful: {branch} → {remote_name}/{branch}',
                             auth_mode='https')
                else:
                    print(f"[copilot] HTTPS push failed, falling back to SSH: {result.stderr.strip()}")
            except subprocess.TimeoutExpired:
                return error('timeout', 'git push timed out (30s)')
            except Exception as e:
                print(f"[copilot] HTTPS push error, falling back to SSH: {e}")

        # Mode 2 (empty token) / Mode 3: SSH / HTTPS fallback
        try:
            result = subprocess.run(
                ['git', 'push', remote_name, branch],
                cwd=self.git_workdir, capture_output=True, text=True, timeout=30
            )
            output = result.stdout + result.stderr
            if result.returncode == 0:
                return ok(output.strip() or f'Push successful: {branch} → {remote_name}/{branch}',
                         auth_mode='ssh')
            else:
                return error('push_failed',
                            f'Push failed: {output.strip() or result.stderr.strip()}')
        except subprocess.TimeoutExpired:
            return error('timeout', 'git push timed out (30s)')
        except Exception as e:
            return error('push_failed', f'Push error: {e}')

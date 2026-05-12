"""
File operations handler mixin.
"""

import json
import shutil

from core import ok, error


class FileHandlers:
    """file;read (alias: 文件;读取) / file;write (alias: 文件;写入) / file;list (alias: 文件;列表) / file;move (alias: 文件;移动)"""

    def _handle_file_read(self, params: list) -> dict:
        if not params:
            return error('missing_param', 'Missing parameter: file_path')
        path_str = params[0]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {path_str}')
        if not p.exists():
            return error('file_not_found', f'File not found: {path_str}')
        if not p.is_file():
            return error('not_a_file', f'Path is not a file: {path_str}')
        if p.stat().st_size > 10 * 1024 * 1024:
            return error('file_too_large', f'File exceeds 10MB limit: {path_str}')
        try:
            content = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return error('encoding_error',
                        f'File is not UTF-8 encoded: {path_str}')
        except Exception as e:
            return error('read_error', f'Read failed: {e}')
        return ok(content, size=len(content.encode('utf-8')))

    def _handle_file_write(self, params: list) -> dict:
        if len(params) < 2:
            return error('missing_param', 'Missing parameter: file_path and/or content')
        path_str = params[0]
        content = params[1]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {path_str}')
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            size = len(content.encode('utf-8'))
            return ok(f'Write successful: {path_str} ({size} bytes)', size=size)
        except Exception as e:
            return error('write_error', f'Write failed: {e}')

    def _handle_file_list(self, params: list) -> dict:
        dir_path = params[0] if params else '.'
        p = self.check_path(dir_path)
        if p is None:
            return error('path_denied', f'Path not in whitelist: {dir_path}')
        if not p.exists():
            return error('file_not_found', f'Path not found: {dir_path}')
        if not p.is_dir():
            p = p.parent
        try:
            entries = []
            for item in sorted(p.iterdir()):
                stat = item.stat()
                entry = {
                    'name': item.name,
                    'type': 'dir' if item.is_dir() else 'file',
                    'size': stat.st_size,
                    'mtime': int(stat.st_mtime),
                }
                if item.is_symlink():
                    entry['type'] = 'link'
                entries.append(entry)
            text = json.dumps(entries, ensure_ascii=False, indent=2)
            return ok(text, count=len(entries), directory=str(p))
        except PermissionError:
            return error('permission_denied', f'Permission denied: {dir_path}')
        except Exception as e:
            return error('list_error', f'List failed: {e}')

    def _handle_file_move(self, params: list) -> dict:
        if len(params) < 2:
            return error('missing_param', 'Missing parameter: source_path and/or dest_path')
        src_str = params[0]
        dst_str = params[1]
        src = self.check_path(src_str)
        dst = self.check_path(dst_str)
        if src is None:
            return error('path_denied', f'Source path not in whitelist: {src_str}')
        if dst is None:
            return error('path_denied', f'Dest path not in whitelist: {dst_str}')
        if not src.exists():
            return error('file_not_found', f'Source path not found: {src_str}')
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return ok(f'Move successful: {src_str} → {dst_str}',
                      from_path=str(src_str), to_path=str(dst))
        except shutil.Error as e:
            return error('move_error', f'Move failed: {e}')
        except PermissionError:
            return error('permission_denied', f'Permission denied: {src_str}')
        except Exception as e:
            return error('move_error', f'Move failed: {e}')

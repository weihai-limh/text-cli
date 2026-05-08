"""
文件操作 handler mixin。
"""

import json
import shutil

from core import ok, error


class FileHandlers:
    """文件;读取 / 文件;写入 / 文件;列表 / 文件;移动"""

    def _handle_file_read(self, params: list) -> dict:
        if not params:
            return error('missing_param', '缺少参数: 文件路径')
        path_str = params[0]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'路径不在白名单内: {path_str}')
        if not p.exists():
            return error('file_not_found', f'文件不存在: {path_str}')
        if not p.is_file():
            return error('not_a_file', f'路径不是文件: {path_str}')
        if p.stat().st_size > 10 * 1024 * 1024:
            return error('file_too_large', f'文件超过 10MB 限制: {path_str}')
        try:
            content = p.read_text(encoding='utf-8')
        except UnicodeDecodeError:
            return error('encoding_error',
                        f'文件不是 UTF-8 编码，请使用其他方式读取: {path_str}')
        except Exception as e:
            return error('read_error', f'读取失败: {e}')
        return ok(content, size=len(content.encode('utf-8')))

    def _handle_file_write(self, params: list) -> dict:
        if len(params) < 2:
            return error('missing_param', '缺少参数: 文件路径 和/或 内容')
        path_str = params[0]
        content = params[1]
        p = self.check_path(path_str)
        if p is None:
            return error('path_denied', f'路径不在白名单内: {path_str}')
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding='utf-8')
            size = len(content.encode('utf-8'))
            return ok(f'写入成功: {path_str} ({size} 字节)', size=size)
        except Exception as e:
            return error('write_error', f'写入失败: {e}')

    def _handle_file_list(self, params: list) -> dict:
        dir_path = params[0] if params else '.'
        p = self.check_path(dir_path)
        if p is None:
            return error('path_denied', f'路径不在白名单内: {dir_path}')
        if not p.exists():
            return error('file_not_found', f'路径不存在: {dir_path}')
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
            return error('permission_denied', f'无权访问: {dir_path}')
        except Exception as e:
            return error('list_error', f'列表失败: {e}')

    def _handle_file_move(self, params: list) -> dict:
        if len(params) < 2:
            return error('missing_param', '缺少参数: 源路径 和/或 目标路径')
        src_str = params[0]
        dst_str = params[1]
        src = self.check_path(src_str)
        dst = self.check_path(dst_str)
        if src is None:
            return error('path_denied', f'源路径不在白名单内: {src_str}')
        if dst is None:
            return error('path_denied', f'目标路径不在白名单内: {dst_str}')
        if not src.exists():
            return error('file_not_found', f'源路径不存在: {src_str}')
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return ok(f'移动成功: {src_str} → {dst_str}',
                      from_path=str(src_str), to_path=str(dst))
        except shutil.Error as e:
            return error('move_error', f'移动失败: {e}')
        except PermissionError:
            return error('permission_denied', f'无权操作: {src_str}')
        except Exception as e:
            return error('move_error', f'移动失败: {e}')

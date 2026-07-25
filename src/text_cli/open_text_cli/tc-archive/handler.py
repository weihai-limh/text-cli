"""
tc-archive handler — Archive compression/decompression for path pipelines.

Create, extract, list archives (zip/tar/tar.gz/tar.bz2/tar.xz).
Zero external dependencies, stdlib zipfile + tarfile only.
Path whitelist + zip bomb defense.

Directives:
    tc-archive;create,<archive_path>,<source_path>[,<format>]  — create archive
    tc-archive;extract,<archive_path>,<dest_dir>               — extract archive
    tc-archive;list,<archive_path>                             — list contents
"""
import json
import logging
import os
import tarfile
import zipfile
from pathlib import Path

from core.registry import directive

logger = logging.getLogger(__name__)

_config = {}

_DEFAULT_ALLOWED_PATHS = ["./"]
_DEFAULT_MAX_SIZE_MB = 500
_DEFAULT_MAX_FILES = 10000
_DEFAULT_MAX_FILE_MB = 100

_EXT_TO_FORMAT = {
    ".zip": "zip",
    ".tar": "tar",
    ".tar.gz": "tar.gz",
    ".tgz": "tar.gz",
    ".tar.bz2": "tar.bz2",
    ".tbz2": "tar.bz2",
    ".tar.xz": "tar.xz",
}


def init_tc_archive_handler(project_root: str):
    global _config
    config_path = Path(project_root) / "config" / "tc_archive.json"
    try:
        _config = json.loads(config_path.read_text(encoding="utf-8"))
        logger.info("tc-archive config loaded from %s", config_path)
    except (FileNotFoundError, json.JSONDecodeError):
        _config = {}
        logger.warning("tc-archive config not found or invalid, using defaults")

    _config.setdefault("allowed_paths", _DEFAULT_ALLOWED_PATHS)
    _config.setdefault("max_uncompressed_size_mb", _DEFAULT_MAX_SIZE_MB)
    _config.setdefault("max_files", _DEFAULT_MAX_FILES)
    _config.setdefault("max_file_size_mb", _DEFAULT_MAX_FILE_MB)
    logger.info("tc-archive initialised")



def _resolve(path_str: str) -> Path:
    return Path(path_str).resolve()


def _is_within(path: Path, allowed: list[Path]) -> bool:
    for root in allowed:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            continue
    return False


def _validate_path(path_str: str, label: str, allowed: list[Path]) -> Path:
    path = _resolve(path_str)
    if not _is_within(path, allowed):
        raise ValueError(f"{label} '{path_str}' is outside allowed paths")
    return path


def _validate_entry_name(name: str) -> str:
    if os.path.isabs(name):
        raise ValueError(f"absolute path in archive entry: '{name}'")
    parts = Path(name).parts
    if ".." in parts:
        raise ValueError(f"path traversal in archive entry: '{name}'")
    return name


def _detect_format(archive_path: str, explicit_format: str = None) -> str:
    if explicit_format:
        fmt = explicit_format.lower()
        if fmt in ("zip", "tar", "tar.gz", "tar.bz2", "tar.xz"):
            return fmt
        raise ValueError(f"unsupported format: '{explicit_format}'")
    name = archive_path.lower()
    for ext, fmt in sorted(_EXT_TO_FORMAT.items(), key=lambda x: -len(x[0])):
        if name.endswith(ext):
            return fmt
    return "zip"


def _safe_extract_zip(zf: zipfile.ZipFile, dest_dir: Path, allowed: list[Path]):
    max_size = _config["max_uncompressed_size_mb"] * 1024 * 1024
    max_files = _config["max_files"]
    max_file_size = _config["max_file_size_mb"] * 1024 * 1024

    total_bytes = 0
    file_count = 0

    for info in zf.infolist():
        file_count += 1
        if file_count > max_files:
            raise ValueError(
                f"archive contains more than {max_files} files ({file_count}+). Possible zip bomb."
            )

        name = _validate_entry_name(info.filename)
        if not name or name.endswith("/"):
            continue

        target = (dest_dir / name).resolve()
        if not _is_within(target, allowed):
            raise ValueError(f"extract target '{name}' resolves outside allowed paths")

        declared_size = info.file_size
        if declared_size > max_file_size:
            raise ValueError(
                f"entry '{name}' declared size {declared_size} exceeds max {max_file_size}"
            )

        target.parent.mkdir(parents=True, exist_ok=True)

        with zf.open(info) as src, open(target, "wb") as dst:
            chunk_size = 64 * 1024
            written = 0
            while True:
                chunk = src.read(chunk_size)
                if not chunk:
                    break
                written += len(chunk)
                if written > max_file_size:
                    dst.close()
                    try:
                        target.unlink()
                    except OSError:
                        pass
                    raise ValueError(
                        f"entry '{name}' actual size exceeds max {max_file_size}. Possible zip bomb."
                    )
                dst.write(chunk)

            total_bytes += written
            if total_bytes > max_size:
                raise ValueError(
                    f"total uncompressed size exceeds max {_config['max_uncompressed_size_mb']} MB. Possible zip bomb."
                )

    return file_count, total_bytes


def _safe_extract_tar(tf: tarfile.TarFile, dest_dir: Path, allowed: list[Path]):
    max_size = _config["max_uncompressed_size_mb"] * 1024 * 1024
    max_files = _config["max_files"]
    max_file_size = _config["max_file_size_mb"] * 1024 * 1024

    total_bytes = 0
    file_count = 0

    for member in tf:
        file_count += 1
        if file_count > max_files:
            raise ValueError(
                f"archive contains more than {max_files} entries ({file_count}+). Possible zip bomb."
            )

        name = _validate_entry_name(member.name)
        if not name or name.endswith("/"):
            if member.isdir():
                (dest_dir / name).mkdir(parents=True, exist_ok=True)
            continue

        target = (dest_dir / name).resolve()
        if not _is_within(target, allowed):
            raise ValueError(f"extract target '{name}' resolves outside allowed paths")

        if member.isfile():
            if member.size > max_file_size:
                raise ValueError(
                    f"entry '{name}' size {member.size} exceeds max {max_file_size}"
                )

            target.parent.mkdir(parents=True, exist_ok=True)

            with tf.extractfile(member) as src, open(target, "wb") as dst:
                chunk_size = 64 * 1024
                written = 0
                while True:
                    chunk = src.read(chunk_size)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > max_file_size:
                        dst.close()
                        try:
                            target.unlink()
                        except OSError:
                            pass
                        raise ValueError(
                            f"entry '{name}' actual size exceeds max {max_file_size}. Possible zip bomb."
                        )
                    dst.write(chunk)

                total_bytes += written

    if total_bytes > max_size:
        raise ValueError(
            f"total uncompressed size exceeds max {_config['max_uncompressed_size_mb']} MB. Possible zip bomb."
        )

    return file_count, total_bytes


def _size_human(bytes_val: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}" if unit != "B" else f"{bytes_val} B"
        bytes_val /= 1024
    return f"{bytes_val:.2f} TB"


def _format_from_ext(path: str) -> str:
    for ext in (".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2"):
        if path.lower().endswith(ext):
            return ext
    return Path(path).suffix.lower()



def _create_archive(archive_path: Path, source_path: Path, fmt: str) -> dict:
    if archive_path.exists():
        raise ValueError(f"archive path already exists: '{archive_path}'")

    if not source_path.exists():
        raise ValueError(f"source path not found: '{source_path}'")

    file_count = 0

    if fmt == "zip":
        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            if source_path.is_file():
                zf.write(source_path, source_path.name)
                file_count = 1
            else:
                base = source_path
                for root, dirs, files in os.walk(source_path):
                    for name in dirs + files:
                        fp = Path(root) / name
                        arcname = str(fp.relative_to(base))
                        zf.write(fp, arcname)
                        file_count += 1

    elif fmt in ("tar", "tar.gz", "tar.bz2", "tar.xz"):
        mode_map = {"tar": "w", "tar.gz": "w:gz", "tar.bz2": "w:bz2", "tar.xz": "w:xz"}
        mode = mode_map[fmt]
        with tarfile.open(archive_path, mode) as tf:
            tf.add(source_path, arcname=source_path.name)
        file_count = _count_files(source_path)

    else:
        raise ValueError(f"unsupported format: '{fmt}'")

    size_bytes = archive_path.stat().st_size
    return {
        "format": fmt,
        "size_bytes": size_bytes,
        "size_human": _size_human(size_bytes),
        "files": file_count,
    }


def _count_files(path: Path) -> int:
    if path.is_file():
        return 1
    count = 0
    for root, dirs, files in os.walk(path):
        count += len(dirs) + len(files)
    return count



def _extract_archive(archive_path: Path, dest_dir: Path, allowed: list[Path]) -> dict:
    if not archive_path.exists():
        raise ValueError(f"archive not found: '{archive_path}'")

    dest_dir.mkdir(parents=True, exist_ok=True)

    ext = _format_from_ext(str(archive_path))
    files = 0
    total_size = 0

    if ext in (".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2"):
        with tarfile.open(archive_path, "r:*") as tf:
            files, total_size = _safe_extract_tar(tf, dest_dir, allowed)
    elif ext == ".zip":
        with zipfile.ZipFile(archive_path, "r") as zf:
            files, total_size = _safe_extract_zip(zf, dest_dir, allowed)
    else:
        raise ValueError(f"unsupported archive format: '{ext}'")

    return {
        "files": files,
        "size_bytes": total_size,
        "size_human": _size_human(total_size),
    }



def _list_archive(archive_path: Path) -> dict:
    if not archive_path.exists():
        raise ValueError(f"archive not found: '{archive_path}'")

    ext = _format_from_ext(str(archive_path))
    entries = []
    total_size = 0
    file_count = 0

    if ext in (".tar", ".tar.gz", ".tar.bz2", ".tar.xz", ".tgz", ".tbz2"):
        fmt = _detect_format(str(archive_path))
        with tarfile.open(archive_path, "r:*") as tf:
            for member in tf.getmembers():
                entry = {
                    "name": member.name,
                    "size": member.size if member.isfile() else 0,
                    "type": "dir" if member.isdir() else "file",
                }
                entries.append(entry)
                if member.isfile():
                    total_size += member.size
                    file_count += 1

    elif ext == ".zip":
        fmt = "zip"
        with zipfile.ZipFile(archive_path, "r") as zf:
            for info in zf.infolist():
                entry = {
                    "name": info.filename,
                    "size": info.file_size,
                    "type": "dir" if info.is_dir() else "file",
                }
                entries.append(entry)
                if not info.is_dir():
                    total_size += info.file_size
                    file_count += 1
    else:
        raise ValueError(f"unsupported archive format: '{ext}'")

    return {
        "format": fmt,
        "files": file_count,
        "uncompressed_size_bytes": total_size,
        "uncompressed_size_human": _size_human(total_size),
        "entries": entries,
    }



@directive("tc-archive", "create", domain_alias="压缩归档", action_aliases={"create": "创建归档"})
def tc_archive_create(params: list[str]) -> str:
    if len(params) < 2:
        return json.dumps({
            "status": "error",
            "reason": "Usage: tc-archive;create,<archive_path>,<source_path>[,<format>]",
        }, ensure_ascii=False)

    try:
        allowed = [_resolve(p) for p in _config["allowed_paths"]]

        archive_path = _validate_path(params[0], "archive_path", allowed)
        source_path = _validate_path(params[1], "source_path", allowed)
        fmt = _detect_format(str(archive_path), params[2] if len(params) > 2 else None)

        result = _create_archive(archive_path, source_path, fmt)
        result["status"] = "ok"
        result["path"] = str(archive_path)
        result["source"] = str(source_path)
        return json.dumps(result, ensure_ascii=False)

    except ValueError as e:
        logger.exception("tc-archive create failed")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("tc-archive create unexpected error")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)


@directive("tc-archive", "extract", domain_alias="压缩归档", action_aliases={"extract": "解压归档"})
def tc_archive_extract(params: list[str]) -> str:
    if len(params) < 2:
        return json.dumps({
            "status": "error",
            "reason": "Usage: tc-archive;extract,<archive_path>,<dest_dir>",
        }, ensure_ascii=False)

    try:
        allowed = [_resolve(p) for p in _config["allowed_paths"]]

        archive_path = _validate_path(params[0], "archive_path", allowed)
        dest_dir = _validate_path(params[1], "dest_dir", allowed)

        result = _extract_archive(archive_path, dest_dir, allowed)
        result["status"] = "ok"
        result["path"] = str(dest_dir)
        return json.dumps(result, ensure_ascii=False)

    except ValueError as e:
        logger.exception("tc-archive extract failed")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("tc-archive extract unexpected error")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)


@directive("tc-archive", "list", domain_alias="压缩归档", action_aliases={"list": "列出内容"})
def tc_archive_list(params: list[str]) -> str:
    if not params:
        return json.dumps({
            "status": "error",
            "reason": "Usage: tc-archive;list,<archive_path>",
        }, ensure_ascii=False)

    try:
        allowed = [_resolve(p) for p in _config["allowed_paths"]]

        archive_path = _validate_path(params[0], "archive_path", allowed)

        result = _list_archive(archive_path)
        result["status"] = "ok"
        result["path"] = str(archive_path)
        return json.dumps(result, ensure_ascii=False)

    except ValueError as e:
        logger.exception("tc-archive list failed")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)
    except Exception as e:
        logger.exception("tc-archive list unexpected error")
        return json.dumps({"status": "error", "reason": str(e)}, ensure_ascii=False)

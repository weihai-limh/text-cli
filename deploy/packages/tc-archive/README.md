# tc-archive

Archive compression/decompression for path pipelines. Create, extract, and list archives (zip / tar / tar.gz / tar.bz2 / tar.xz). Zero external dependencies — Python stdlib `zipfile` + `tarfile`. Path whitelist and zip-bomb defense are built in.

## Install

```
AI:text-cli;install,tc-archive
```

## Dependencies

None. Python stdlib only (`zipfile`, `tarfile`, `pathlib`).

## Directives

| Directive | Description |
|-----------|-------------|
| `tc-archive;create,<archive_path>,<source_path>[,<format>]` | Create a compressed archive from a directory or file |
| `tc-archive;extract,<archive_path>,<dest_dir>` | Extract an archive to a destination directory |
| `tc-archive;list,<archive_path>` | List archive contents without extracting |

Format is auto-detected from the archive extension, or set explicitly: `zip` (default), `tar`, `tar.gz`, `tar.bz2`, `tar.xz`.

## Supported Formats

| Format | Extensions |
|--------|------------|
| ZIP | `.zip` |
| TAR (no compression) | `.tar` |
| TAR + Gzip | `.tar.gz`, `.tgz` |
| TAR + Bzip2 | `.tar.bz2`, `.tbz2` |
| TAR + LZMA | `.tar.xz` |

## Security

- **Path whitelist**: all operations are confined to configured directories (default `./`).
- **Path-traversal defense**: archive entries containing `..` or absolute paths are rejected.
- **Zip-bomb defense**: total uncompressed size capped at 500 MB, file count at 10000, single-file size at 100 MB (configurable in `config/tc_archive.json`).

## Example

### create

```
AI:tc-archive;create,project.zip,./my_project
→ {"status":"ok","path":"project.zip","format":"zip","size_human":"1.95 MB","files":42}

AI:tc-archive;create,data.tar.gz,./data,tar.gz
→ {"status":"ok","path":"data.tar.gz","format":"tar.gz","size_human":"850.32 KB","files":15}
```

### extract

```
AI:tc-archive;extract,project.zip,./extracted
→ {"status":"ok","path":"./extracted","files":42,"size_human":"4.88 MB"}
```

### list

```
AI:tc-archive;list,project.zip
→ {"status":"ok","path":"project.zip","format":"zip","files":42,
    "entries":[{"name":"README.md","size":1024,"type":"file"},...]}
```

## Architecture

```
tc-archive/
├── schema.json             — 3 directive declarations
├── handler.py              — archive operations
├── config/
│   └── tc_archive.json     — security whitelist + limits
└── README.md
```

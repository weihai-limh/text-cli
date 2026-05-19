# tc-media

Load and download media files. Public URLs are passed through directly. Local files validated against a whitelist.

## Install

```
AI:text-cli;install,tc-media
```

## Dependencies

- `requests` (pip): HTTP download support.

## Configuration

Edit `PATH_WHITELIST` in handler.py to add local media directories.
Set `MEDIA_DOWNLOAD_DIR` env var to change download target (default: `/tmp/media`).

## Directives

| Directive | Description |
|-----------|-------------|
| `image;load,<URL or path>` | Load/passthrough image |
| `video;load,<URL or path>` | Load/passthrough video |
| `audio;load,<URL or path>` | Load/passthrough audio |
| `file;load,<URL or path>` | Load/passthrough file |
| `media;download,<URL>[,<save_name>]` | Download media to local |

## Example

```
AI:image;load,https://example.com/photo.jpg
→ {"status": "ok", "type": "picture", "url": "https://example.com/photo.jpg"}

AI:media;download,https://example.com/video.mp4
→ {"status": "ok", "type": "video", "name": "abc123.mp4", "size": 5242880}
```

## Architecture

```
Python package with pip dependency
  ├── handler.py    — @directive registration + HTTP + filesystem
  └── schema.json   — 5 directives
```

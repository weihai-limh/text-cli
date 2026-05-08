"""
handler mixin 聚合 — 所有 domain 的 handler 在此汇集。
"""

from handlers.files import FileHandlers
from handlers.git import GitHandlers
from handlers.mail import MailHandlers
from handlers.system import SystemHandlers
from handlers.ai import AIHandlers
from handlers.oc_terminal import TerminalHandlers
from handlers.codec import CodecHandlers

__all__ = [
    'FileHandlers',
    'GitHandlers',
    'MailHandlers',
    'SystemHandlers',
    'AIHandlers',
    'TerminalHandlers',
    'CodecHandlers',
]

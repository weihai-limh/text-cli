"""
Handler mixin aggregation — all domain handlers collected here.
"""

from handlers.files import FileHandlers
from handlers.git import GitHandlers
from handlers.mail import MailHandlers
from handlers.system import SystemHandlers
from handlers.ai import AIHandlers
from handlers.oc_terminal import TerminalHandlers
from handlers.codec import CodecHandlers
from handlers.key import KeyHandlers
from handlers.media import MediaHandlers
from handlers.json_proc import JsonProcHandlers

__all__ = [
    'FileHandlers',
    'GitHandlers',
    'MailHandlers',
    'SystemHandlers',
    'AIHandlers',
    'TerminalHandlers',
    'CodecHandlers',
    'KeyHandlers',
    'MediaHandlers',
    'JsonProcHandlers',
]

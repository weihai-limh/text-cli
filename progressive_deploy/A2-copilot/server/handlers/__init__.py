"""
Handler mixin aggregation — 骨架 mixin。

包 handler（files/git/mail/system/media/render/mcp/terminal/browser）
由包安装时注入。此处仅保留骨架。

Author: Tide 🌊
"""

from handlers.codec import CodecHandlers
from handlers.key import KeyHandlers
from handlers.skill_bridge import SkillBridgeHandlers

__all__ = [
    'CodecHandlers',
    'KeyHandlers',
    'SkillBridgeHandlers',
]

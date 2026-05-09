"""
text-cli-modules/embed — 嵌入服务业务模块

依赖: text_cli_modules.embed.embedding_3 (bigmodel/embedding-3)
边界: 不依赖 service/copilot/Worker
弹性: api_key 参数注入
"""

from text_cli_modules.embed.embedding_3 import encode, encode_batch, similarity, match, MODE_DIMS

__all__ = [
    'encode',
    'encode_batch',
    'similarity',
    'match',
    'MODE_DIMS',
]

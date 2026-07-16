"""
stream_subscriber_registry — IM 流订阅注册表。

当前为兼容桩，提供空集合避免 ModuleNotFoundError。
v2 将实现完整的流订阅生命周期。
"""

# 空集合，调用方检查空值即可
STREAM_SUBSCRIBERS = set()


def init_subscribers():
    """初始化（当前未实现）。"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(
        "stream_subscriber_registry is not yet implemented — subscribers disabled"
    )

"""
text-cli-modules/ai — AI 推理业务模块

提供:
  - text_inference: 纯文本推理（时段感知 + 模型回退链）
  - vision_inference: 视觉推理（文本 + 图片）
  - get_period: 时段检测

依赖: text_cli_modules.key.key_registry (获取 API key)
边界: 不依赖 service/copilot 内部模块
弹性: api_keys 参数注入，纯函数，零状态
"""

from text_cli_modules.ai.inference import (
    text_inference,
    vision_inference,
    get_period,
    MODEL_REGISTRY,
)

__all__ = [
    'text_inference',
    'vision_inference',
    'get_period',
    'MODEL_REGISTRY',
]

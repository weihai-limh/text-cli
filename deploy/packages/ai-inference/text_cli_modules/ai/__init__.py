"""
text-cli-modules/ai — AI inference business module.

Exposes:
  - text_inference: plain-text inference (time-aware + model fallback chain)
  - vision_inference: vision inference (text + image)
  - get_period: time-period detection

Dependency: text_cli_modules.key.key_registry (API key retrieval)
Boundary: does not depend on service/copilot internal modules
Elasticity: api_keys injected as a parameter; pure functions, zero state

NOTE: MODEL_REGISTRY is config-injected (see inference.set_model_registry).
This package ships with an EMPTY registry — providers must be configured at
deployment time via config/model_aliases.json.
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

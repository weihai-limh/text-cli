"""相位 action 枚举（设计稿 §3.1；ported from synth-loop phase_chat_orchestrator）

四 action（confirm/reject/regenerate/abort）+ check_result（长任务轮询决策点）。
"""

from __future__ import annotations

from enum import Enum


class PhaseAction(str, Enum):
    CONFIRM = "confirm"
    REJECT = "reject"
    REGENERATE = "regenerate"
    REGENERATE_NEW_CTX = "regenerate_with_new_context"
    ABORT = "abort"
    CHECK_RESULT = "check_result"

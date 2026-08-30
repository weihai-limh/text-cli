"""相位推理引擎（包根重导出；设计稿 §3.3 / §9.3 门面 import 路径）

实现位于 core/orchestrator.py。此处重导出，使门面与调用方可用：
    from phase_kernel.orchestrator import PhaseReasoningEngine
"""

from .core.orchestrator import PhaseReasoningEngine

__all__ = ["PhaseReasoningEngine"]

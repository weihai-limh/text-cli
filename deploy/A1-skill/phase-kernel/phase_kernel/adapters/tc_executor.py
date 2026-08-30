"""TCExecutor（设计稿 §七.4 / §3.1；适配器层，唯一允许 import 执行后端）

封装 tc 运行时四能力（call/discover/poll）→ ports.Executor。
填 synth-loop 现状 steps:[] 空桩缺口（设计稿 §八）：经 compile_path 组装真实 tc path 信封。
execute 走 tc 一维契约 `AI:text-cli;path,{...}`；poll 走 tc 异步五态轮询。

纪律：core/ 零 tc import；只有本适配器（adapters/）碰 tc 协议。
HTTP 用标准库 urllib（零外部依赖）；可通过 _client 注入异步 callable 便于测试。
"""

from __future__ import annotations

import asyncio
import json
import urllib.request
from typing import Any, Callable, Optional

from ..core.models import PhaseDef, PhaseResult


def _default_http(base_url: str, token: Optional[str]):
    """标准库 urllib 实现的 tc /text-cli/cli 调用（异步包装）"""
    def _post(prompt: str) -> dict:
        url = f"{base_url.rstrip('/')}/text-cli/cli"
        body = json.dumps({"prompt": prompt}).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST",
                                      headers={"Content-Type": "application/json"})
        if token:
            req.add_header("Service-token", token)
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    return _post


class TCExecutor:
    """tc 执行适配器（实现 ports.Executor）"""

    def __init__(self, base_url: str, token: Optional[str] = None,
                 alias: Optional[str] = None,
                 http_client: Optional[Callable[[str], Any]] = None):
        self.base_url = base_url
        self.token = token
        self.alias = alias
        self._client = http_client or _default_http(base_url, token)

    def compile_path(self, phase: PhaseDef) -> dict:
        """把相位译成 tc path 信封（设计稿 §八：填 steps 空桩）。

        synth-loop 现状 steps:[] 写死；此处用 phase.steps（由 Planner/plan_compiler 提供）
        组装真实 path，不再写死空桩。执行相位服务（Phase 7）：path 内联 JSON 投递，
        非预注册（动态 path 无 id 引用），故 id 取 endpoint_hint/alias 兜底。
        """
        steps = phase.steps or [{"action": "execute", "description": phase.description}]
        return {
            "id": phase.endpoint_hint or self.alias or "local",
            "name": phase.name,
            "steps": steps,
        }

    async def execute(self, phase: PhaseDef, context: dict) -> PhaseResult:
        path = self.compile_path(phase)
        # 执行相位服务（Phase 7）：内联 JSON 投递 `AI:text-cli;path,{path_json},{input_json}`，
        # 动态 path 不注册、无 path_id 引用；第二参为相位输入。
        input_json = context.get("input") if isinstance(context, dict) else None
        prompt = f"AI:text-cli;path,{json.dumps(path, ensure_ascii=False)},{json.dumps(input_json, ensure_ascii=False)}"
        envelope = await asyncio.to_thread(self._client, prompt)
        return PhaseResult.from_envelope(envelope)

    async def poll(self, task_id: str) -> PhaseResult:
        prompt = f"AI:text-cli;poll,{task_id}"
        envelope = await asyncio.to_thread(self._client, prompt)
        return PhaseResult.from_envelope(envelope)

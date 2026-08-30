"""相位服务门面（设计稿 §9 / §12.3'；折叠态，纯标准库独立服务）

纪律（§9.2）：只用标准库 http.server，不引入 FastAPI；机制协议无关、不绑 web 框架。
对外只暴露折叠态单指令 `phase;run`（§12.3'）；展开态五能力作为内部协议流，不暴露为端口。

职责（§9.4）：收 phase;run → 内部驱动引擎 → 包成 SPEC 三字段信封；Service-token 鉴权；
自身本地 DB 持久化（SqliteStore）。
"""

from __future__ import annotations

import asyncio
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

from ..orchestrator import PhaseReasoningEngine
from ..adapters import TCExecutor, TCPlanner, SqliteStore, MechanicalPlanner, StrataMatcher
from ..adapters.artifact_store import InMemoryArtifactStore
from ..core.models import PhaseStatus


# ═══════════════════════════════════════════════════════════
# 折叠态指令解析（§12.3'）
# ═══════════════════════════════════════════════════════════

def parse_cli(prompt: str) -> tuple[str, dict]:
    """解析 phase;run 指令（对外句柄别名 tc-phase; 归一化为内部 phase;）。

    入口句柄：对外暴露为 `tc-phase`（标明 tc 生态上游编排组件）；进入 parse_cli 后
    统一归一化为内部 `phase;` 形态，之后所有内部逻辑（engine/orchestrator/decide_kind）
    完全不动——只改入口句柄，不改内部模型名（见开发计划 P0）。

    形式：
      phase;run,<goal>[,<lang>][,<mode>]             新发起（mode: structural|chain，默认 structural）
      phase;run,<pipeline_id>,<action>[,<feedback>]  回传驱动（人干预/轮询）
    返回 (action, params)。
    """
    text = prompt.strip()
    # 入口句柄别名归一化：tc-phase;* → phase;*（仅入口层改动）
    if text.startswith("tc-phase;"):
        text = "phase;" + text[len("tc-phase;"):]
    if not text.startswith("phase;run"):
        # 兼容展开态内部流（内部协议流，不对外暴露，但服务可识别）
        if text.startswith("phase;"):
            rest = text[len("phase;"):]
            parts = [p.strip() for p in rest.split(",", 2)]
            action = parts[0]
            params = {"pipeline_id": parts[1]} if len(parts) > 1 else {}
            if len(parts) > 2:
                params["feedback"] = parts[2]
            return action, params
        raise ValueError("unknown directive")
    rest = text[len("phase;run"):].lstrip(",")
    parts = [p.strip() for p in rest.split(",", 3)]
    goal = parts[0]
    if len(parts) >= 2 and _looks_like_pipeline_id(parts[1]):
        # 回传驱动
        action = parts[1]
        params = {"pipeline_id": goal, "action": action}
        if len(parts) >= 3:
            params["feedback"] = parts[2]
        return "run", params
    # 新发起
    lang = parts[1] if len(parts) > 1 else "zh"
    mode = parts[2] if len(parts) > 2 else "structural"  # 链式模式透传（P1）
    return "run", {"goal": goal, "lang": lang, "mode": mode}


def _looks_like_pipeline_id(s: str) -> bool:
    # pipeline_id 为 uuid；action 为 confirm/reject/regenerate/abort/check_result
    return s in {"confirm", "reject", "regenerate", "abort", "check_result"}


# ═══════════════════════════════════════════════════════════
# 协议服务
# ═══════════════════════════════════════════════════════════

PHASE_SCHEMA = {
    "id": "tc-phase", "type": "native-service", "name": "Phase Reasoning", "name_zh": "相位推理",
    "runtime": "python", "version": "0.1.0", "locales": ["zh", "en"], "trust": "internal",
    "auth": {"enabled": True, "header": "Service-token"},
    "mechanism": ["async", "discovery"],
    "category": "orchestration",
    "description": "Multi-step intervenable phase reasoning over tc backends. Collapsed to a single run instruction.",
    "description_zh": "基于 tc 后端的、多步可干预的相位推理；折叠为单条 run 指令。",
    "directives": [
        {"domain": "tc-phase", "domain_zh": "相位", "action": "run", "action_zh": "运行",
         "usage": "tc-phase;run,<目标>[,<lang>][,<mode>]", "usage_zh": "相位;运行,<目标>[,<语言>][,<模式>]",
         "params": ["goal", "lang?", "mode?"],
         "outputs": ["pipeline_id", "phase_index", "phase_total", "phase_name", "status",
                     "pending_gate", "available_actions", "artifact_ref"]}
    ],
    "internal_flows": [
        {"action": "enter", "description": "Implicit on first run; creates session row in phase DB."},
        {"action": "state", "description": "Read-only phase surface, echoed via run polling / discovery."},
        {"action": "action", "description": "confirm/reject/regenerate/abort as async input event to the run task."},
        {"action": "rollback", "description": "Triggered internally by reject/regenerate via rollback_to(checkpoint)."},
        {"action": "list", "description": "Management-side bypass via discovery over phase DB."},
    ],
}


class PhaseHandler(BaseHTTPRequestHandler):
    engine: Optional[PhaseReasoningEngine] = None
    artifact_store: Optional[InMemoryArtifactStore] = None
    auth_enabled: bool = True
    service_token: str = "phase-secret"
    lang: str = "zh"  # 服务级默认语言（i18n；main 从 PHASE_LANG 读取；_dispatch 回落）

    def _send(self, rst_data: dict, rst_err: str = "", rst_types: str = "text", code: int = 200) -> None:
        envelope = {"rst_types": rst_types, "rst_data": rst_data, "rst_err": rst_err}
        payload = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(payload)
        self.wfile.flush()
        self.close_connection = True

    def _check_auth(self) -> bool:
        if not self.auth_enabled:
            return True
        return self.headers.get("Service-token") == self.service_token

    def do_POST(self):
        if not self._check_auth():
            self._send({}, "SERVICE_DENIED")
            return
        if self.path == "/packets/update":
            self._handle_packet_update()
            return
        if self.path.startswith("/pipelines/") and self.path.endswith("/gate"):
            self._handle_gate()
            return
        if self.path != "/text-cli/cli":
            self._send({}, "ERR_NOT_FOUND")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            action, params = parse_cli(body.get("prompt", ""))
        except Exception as e:
            self._send({}, "INVALID_PARAMS")
            return

        try:
            result = asyncio.run(self._dispatch(action, params))
        except ValueError:
            self._send({}, "INVALID_PARAMS")
            return
        except Exception as e:  # 引擎内部异常 → 闭集错误码，不泄露堆栈
            self._send({"error": str(e)[:200]}, "ERR_EXECUTION")
            return

        self._send(result)

    def _handle_packet_update(self) -> None:
        """POST /packets/update —— 产物写入数据面（块1：叶子 path 注入数据面 URL）

        请求体：{"pipeline_id", "data", "media_type"} 或 {"pipeline_id", "url"}。
        经 ArtifactStore.transfer 分流（透传 / 拉取转存），返回 {url, passthrough, degraded}。
        """
        if self.artifact_store is None:
            self._send({}, "ERR_NOT_FOUND")
            return
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            pipeline_id = str(body.get("pipeline_id", ""))
            data = body.get("data", body.get("url"))
            media_type = str(body.get("media_type", "text"))
            if not pipeline_id or data is None:
                self._send({}, "INVALID_PARAMS")
                return
            result = asyncio.run(self.artifact_store.transfer(pipeline_id, data, media_type))
        except Exception:
            self._send({}, "ERR_EXECUTION")
            return
        self._send(result)

    def _handle_gate(self) -> None:
        """POST /pipelines/{pid}/phases/{phase_path}/gate —— 人闸受控写入口（Phase 重构 P4）

        请求体：{"verdict": "approve"|"retry"|"abort_tree", "feedback"?: str}
        （本期 verdict 集不含 redirect，设计预留）。
        phase_path 为 `-` 连接的树路径（如 `0-1`），定位 session 内相位。
        """
        if self.engine is None:
            self._send({}, "ERR_NOT_FOUND")
            return
        try:
            rest = self.path[len("/pipelines/"):]
            path_part, _, _ = rest.rpartition("/gate")
            pid, _, phases_part = path_part.partition("/phases/")
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            verdict = body.get("verdict", "")
            feedback = body.get("feedback") or ""
            if verdict not in ("approve", "retry", "abort_tree"):
                self._send({}, "INVALID_PARAMS")
                return
            phase_path = [int(x) for x in phases_part.split("-")] if phases_part else None
            result = asyncio.run(self._run_gate(pid, verdict, feedback, phase_path))
        except Exception:
            self._send({}, "ERR_EXECUTION")
            return
        self._send(result)

    async def _run_gate(self, pid: str, verdict: str, feedback: str, phase_path) -> dict:
        """按 phase_path 定位相位并执行人闸三态（approve/retry/abort_tree）。"""
        session = await self.engine.store.load(pid)
        if session is None:
            return {"error": "pipeline not found"}
        if verdict == "abort_tree":
            await self.engine.gate_executor.abort_tree(session)
            await self.engine.store.save(session)
            return {"verdict": "abort_tree", "status": "aborted",
                    "phase_path": phase_path}
        # 按 phase_path 定位相位（遍历树，path 匹配）
        from ..core import fractal
        target = None
        for _p, ph in fractal.iter_phases(session.phases):
            if _p == phase_path:
                target = ph
                break
        if target is None:
            return {"error": "phase not found"}
        if verdict == "approve":
            await self.engine.gate_executor.approve_phase(session, target)
        else:  # retry
            await self.engine.gate_executor.retry_phase(session, target, feedback)
        await self.engine.store.save(session)
        return {"verdict": verdict, "phase_path": phase_path,
                "status": target.status.value}

    def do_GET(self):
        if self.path == "/text-cli/health":
            self._send({"status": "ok", "mechanism": ["async", "discovery"],
                        "degraded_mode": bool(getattr(self.engine, "degraded_mode", False))})
        elif self.path == "/text-cli/schema":
            self._send(PHASE_SCHEMA)
        elif self.path.startswith("/packets/artifacts/"):
            self._handle_packet_fetch()
        elif self.path.startswith("/pipelines/") and self.path.endswith("/gate"):
            # 人闸只读查询面（与 POST 决策对称，gate-manager §6.2）：查相位待闸状态
            self._handle_gate_query()
        elif self.path == "/text-cli/cli":
            self._send({}, "ERR_NOT_FOUND")
        else:
            self._send({}, "ERR_NOT_FOUND")

    def _handle_gate_query(self) -> None:
        """GET /pipelines/{pid}/phases/{phase_path}/gate —— 人闸只读查询（对称补全）

        返回该相位待闸状态（复用 _to_envelope 受控面语义）：status / pending_gate /
        available_actions / artifact_ref。phase_path 为 `-` 连接树路径（如 `0-1`）。
        """
        if self.engine is None:
            self._send({}, "ERR_NOT_FOUND")
            return
        try:
            rest = self.path[len("/pipelines/"):]
            path_part, _, _ = rest.rpartition("/gate")
            pid, _, phases_part = path_part.partition("/phases/")
            phase_path = [int(x) for x in phases_part.split("-")] if phases_part else None
            result = asyncio.run(self._query_gate(pid, phase_path))
        except Exception:
            self._send({}, "ERR_EXECUTION")
            return
        self._send(result)

    async def _query_gate(self, pid: str, phase_path) -> dict:
        """按 phase_path 查询相位待闸状态（只读，不落盘）。"""
        session = await self.engine.store.load(pid)
        if session is None:
            return {"error": "pipeline not found"}
        from ..core import fractal
        target = None
        for _p, ph in fractal.iter_phases(session.phases):
            if _p == phase_path:
                target = ph
                break
        if target is None:
            return {"error": "phase not found"}
        # 复用受控相位面：status / pending_gate / available_actions
        pending_gate = None
        available_actions = []
        if target.status == PhaseStatus.AWAITING_PATH_CONFIRM:
            pending_gate = "path_edit"; available_actions = ["confirm", "reject", "abort"]
        elif target.status == PhaseStatus.AWAITING_APPROVAL:
            pending_gate = "human_approval"; available_actions = ["confirm", "reject"]
        elif target.status == PhaseStatus.RUNNING:
            available_actions = ["check_result", "abort"]
        return {
            "pipeline_id": pid,
            "phase_path": phase_path,
            "status": target.status.value,
            "pending_gate": pending_gate,
            "available_actions": available_actions,
            "artifact_ref": getattr(target, "artifact_ref", None),
        }

    def _handle_packet_fetch(self) -> None:
        """GET /packets/artifacts/{ref} —— 拉取数据面产物（块1）"""
        if self.artifact_store is None:
            self._send({}, "ERR_NOT_FOUND")
            return
        ref = self.path[len("/packets/artifacts/"):]
        art = asyncio.run(self.artifact_store.fetch(ref))
        if art is None:
            self._send({}, "ERR_NOT_FOUND")
            return
        self._send({"ref": art["ref"], "data": art["data"], "media_type": art["media_type"]})

    async def _dispatch(self, action: str, params: dict) -> dict:
        # i18n：请求级 lang（parse_cli 已解析）回落服务级默认 self.lang（PHASE_LANG，§4.4b）
        lang = params.get("lang") or self.lang
        if action != "run":
            # 展开态内部流（phase;enter/state/action/rollback/list）→ 统一收敛到 run 的协议流
            if "pipeline_id" in params and "action" in params:
                return self._to_envelope(await self.engine.handle(
                    params.get("feedback", ""),
                    synth_pipeline={"id": params["pipeline_id"], "action": params["action"]},
                    lang=lang))
            raise ValueError("unknown action")
        if "goal" in params:
            return self._to_envelope(await self.engine.handle(
                params["goal"], user_id="phase-service", mode=params.get("mode", "structural"),
                lang=lang))
        if "pipeline_id" in params and "action" in params:
            return self._to_envelope(await self.engine.handle(
                params.get("feedback", ""),
                synth_pipeline={"id": params["pipeline_id"], "action": params["action"]},
                lang=lang))
        raise ValueError("run needs goal or pipeline_id+action")

    def _to_envelope(self, resp: dict) -> dict:
        """把引擎结果包成受控相位面（§12.4①：rst_data 仅含受控字段，不吐内部 PipelineSession）"""
        sp = resp.get("synth_pipeline", {})
        step = sp.get("step", "")
        pending_gate = None
        available_actions = []
        if step == "awaiting_path_confirm":
            pending_gate = "path_edit"; available_actions = ["confirm", "reject", "abort"]
        elif step == "awaiting_approval":
            pending_gate = "human_approval"; available_actions = ["confirm", "reject"]
        elif step == "executing":
            available_actions = ["check_result", "abort"]
        elif step == "awaiting_plan_confirm":
            available_actions = ["confirm", "reject", "regenerate"]
        return {
            "content": resp.get("content", ""),
            "pipeline_id": sp.get("id"),
            "phase_index": sp.get("phase_index"),
            "phase_total": sp.get("phase_total"),
            "status": step,
            "pending_gate": pending_gate,
            "available_actions": available_actions,
            "artifact_ref": sp.get("artifact_ref"),
        }

    def log_message(self, *args):  # 静默默认访问日志
        pass


def build_engine(tc_base_url: Optional[str] = None, service_token: Optional[str] = None,
                 db_path: str = "phase.db", no_strata: bool = True,
                 llm: Optional[Any] = None) -> PhaseReasoningEngine:
    """装配相位引擎（§9.3 __main__ 注入点）

    独立部署默认 --no-strata（纯机械兜底，零 LLM，可独立跑）；
    给定 tc_base_url 时注入 TCExecutor 真连 tc。

    `llm`（Phase 重构 P1）：可选异步 callable(messages)->str。传入则 serve 装配
    `LlmInferenceReceiver` 作为推理缝默认填缝（pk 经 `context_patch`→`inference_result`
    发起推理，serve 身兼宿主 + 接入方）；None → 接收器机械兜底（serve 零 LLM 也能闭环）。
    """
    store = SqliteStore(db_path)
    from ..serve.inference_receiver import LlmInferenceReceiver
    if tc_base_url:
        executor = TCExecutor(tc_base_url, token=service_token)
        planner = TCPlanner(llm=None)  # Phase 4 升级：接 strata/LLM
    else:
        # 自包含形态：LocalExecutor 由 Phase 5 提供；此处用机械执行器（直接 success）
        from ..adapters.local_executor import LocalExecutor
        executor = LocalExecutor()
        planner = MechanicalPlanner() if no_strata else TCPlanner(llm=None)
    # Phase 重构 P1：推理缝默认填缝（serve llm 接收器）；llm=None → 机械兜底。
    inference_seam = LlmInferenceReceiver(llm=llm)
    return PhaseReasoningEngine(executor=executor, planner=planner, store=store,
                                degraded_mode=(tc_base_url is None),
                                inference_seam=inference_seam)


def main(host: str = "0.0.0.0", port: int = 28050) -> None:
    tc_base_url = os.environ.get("PHASE_TC_URL")
    token = os.environ.get("PHASE_SERVICE_TOKEN", "phase-secret")
    db_path = os.environ.get("PHASE_DB", "phase.db")
    no_strata = os.environ.get("PHASE_NO_STRATA", "1") != "0"
    lang = os.environ.get("PHASE_LANG", "zh")  # 服务级默认语言（i18n，§4.4b）
    engine = build_engine(tc_base_url=tc_base_url, service_token=token, db_path=db_path, no_strata=no_strata)
    PhaseHandler.engine = engine
    PhaseHandler.artifact_store = InMemoryArtifactStore(allow_passthrough=False)
    PhaseHandler.auth_enabled = True
    PhaseHandler.service_token = token
    PhaseHandler.lang = lang
    httpd = ThreadingHTTPServer((host, port), PhaseHandler)
    print(f"phase-kernel serve on http://{host}:{port}  (tc={'on' if tc_base_url else 'off'})")
    httpd.serve_forever()


if __name__ == "__main__":
    main()

"""
call.py — text-cli 指令调用（Python）

从 conf.json 或环境变量读取端点/令牌配置。
指令文本通过参数传入，不再依赖命令行展开。

用法:
    from call import call_directive

    result = call_directive("AI:tc-datetime;now")
    print(result)  # "2026-05-26T..."

环境变量:
    TEXT_CLI_ENDPOINT         覆盖端点地址
    TEXT_CLI_SERVICE_TOKEN    覆盖 Service Token
    TEXT_CLI_ACCESS_TOKEN     覆盖 Access Token

配置文件:
    ../conf.json（与本文件相对路径）
    { "endpoint": "...", "service_token": "...", "access_token": "..." }
"""

import json
import os
import pathlib

import requests

_CONF_PATH = pathlib.Path(__file__).resolve().parent / "conf.json"


def _load_conf() -> dict:
    """加载 conf.json，返回配置字典。文件不存在或格式错误时返回空字典。"""
    if not _CONF_PATH.exists():
        return {}
    try:
        with open(_CONF_PATH, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _get_config(key: str, env_name: str, default: str = "") -> str:
    """按优先级取值: 环境变量 > conf.json > default"""
    env_val = os.environ.get(env_name)
    if env_val is not None:
        return env_val
    conf = _load_conf()
    return conf.get(key, default)


DEFAULT_ENDPOINT = "https://test.text-cli.com/cli/text_cli"
TIMEOUT = 10


def call_directive(
    directive: str,
    endpoint: str | None = None,
    service_token: str | None = None,
    access_token: str | None = None,
    timeout: int = TIMEOUT,
) -> str:
    """
    调用 text-cli 指令，返回文本结果。

    参数:
        directive:     指令文本，格式 "AI:域;动作,参数1,参数2"
        endpoint:      端点 URL，默认从 conf.json / 环境变量读取
        service_token: Service Token，默认从 conf.json / 环境变量读取
        access_token:  Access Token，默认从 conf.json / 环境变量读取
        timeout:       HTTP 超时秒数

    返回:
        指令执行结果文本

    异常:
        ValueError:     服务返回错误
        ConnectionError: 网络不可达
        TimeoutError:    请求超时
    """
    url = endpoint or _get_config("endpoint", "TEXT_CLI_ENDPOINT", DEFAULT_ENDPOINT)
    st = service_token or _get_config("service_token", "TEXT_CLI_SERVICE_TOKEN")
    at = access_token or _get_config("access_token", "TEXT_CLI_ACCESS_TOKEN")

    headers = {"Content-Type": "application/json"}
    if at:
        headers["Authorization"] = f"Bearer {at}"
    if st:
        headers["Service-token"] = st

    try:
        resp = requests.post(
            url,
            json={"prompt": directive},
            headers=headers,
            timeout=timeout,
        )
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as e:
        error_body = e.response.text if e.response is not None else str(e)
        status = e.response.status_code if e.response is not None else 0
        raise ValueError(f"HTTP {status}: {error_body}") from e
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"无法连接至 {url}: {e}") from e
    except requests.exceptions.Timeout as e:
        raise TimeoutError(f"请求超时 ({timeout}s): {url}") from e

    if data.get("rst_types") == "text":
        return data["rst_data"]["text"]

    return json.dumps(data, ensure_ascii=False)


def call_directive_batch(
    directives: list[str],
    endpoint: str | None = None,
    service_token: str | None = None,
    access_token: str | None = None,
) -> list[dict]:
    """
    批量调用多个指令（串行执行）。

    返回:
        [{"directive": str, "result": str, "error": str|None}, ...]
    """
    results = []
    for d in directives:
        try:
            r = call_directive(
                d, endpoint=endpoint,
                service_token=service_token, access_token=access_token,
            )
            results.append({"directive": d, "result": r, "error": None})
        except Exception as e:
            results.append({"directive": d, "result": "", "error": str(e)})
    return results

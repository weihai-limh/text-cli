"""
call.py — text-cli 指令调用（Python）

用法:
    from call import call_directive

    result = call_directive("AI:weather;query,明天,威海")
    print(result)  # "明天威海: 晴, 15-22°C"

环境变量:
    TEXT_CLI_TOKEN    鉴权 Token
    TEXT_CLI_ENDPOINT 端点地址
"""

import json
import os

import requests

DEFAULT_ENDPOINT = "https://test.text-cli.com/cli/text_cli"
TIMEOUT = 10


def call_directive(
    directive: str,
    endpoint: str | None = None,
    token: str | None = None,
    timeout: int = TIMEOUT,
) -> str:
    """
    调用 text-cli 指令，返回文本结果。

    参数:
        directive: 指令文本，格式 "AI:领域;动作,参数1,参数2"（`指令:` 仍兼容）
        endpoint:  端点 URL，默认取环境变量 TEXT_CLI_ENDPOINT 或公共端点
        token:     Access Token / Service Token，默认取环境变量 TEXT_CLI_TOKEN
        timeout:   HTTP 超时秒数

    返回:
        指令执行结果文本

    异常:
        ValueError:     指令格式错误或端点返回错误
        ConnectionError: 网络不可达
        TimeoutError:    请求超时
    """
    url = endpoint or os.getenv("TEXT_CLI_ENDPOINT", DEFAULT_ENDPOINT)
    auth_token = token or os.getenv("TEXT_CLI_TOKEN", "")

    headers = {"Content-Type": "application/json"}
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"

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
    token: str | None = None,
) -> list[dict]:
    """
    批量调用多个指令（串行执行）。

    返回:
        [{"directive": str, "result": str, "error": str|None}, ...]
    """
    results = []
    for d in directives:
        try:
            r = call_directive(d, endpoint=endpoint, token=token)
            results.append({"directive": d, "result": r, "error": None})
        except Exception as e:
            results.append({"directive": d, "result": "", "error": str(e)})
    return results

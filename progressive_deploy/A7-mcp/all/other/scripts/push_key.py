"""
推送密钥到 text-cli-service

用法:
  python3 push_key.py zhipu    # 从环境变量 ZHIPU_KEY 读取
  python3 push_key.py zhipu <你的key>    # 直接传入

密钥注册后会存入 SQLite key_registry 表，
后续 AI辅助;推理 等指令自动读取。
"""

import json
import os
import sys
import urllib.request
import urllib.error

SERVICE_URL = os.getenv("TEXT_CLI_SERVICE_URL", "http://localhost:8001/cli/text_cli")
SERVICE_TOKEN = os.getenv("TEXT_CLI_TOKEN", "")

# key 注册表：服务名 → 环境变量名
KEY_MAP = {
    "zhipu": "ZHIPU_KEY",
    "xunfei": "XUNFEI_KEY",
    "modelscope": "MODELSCOPE_KEY",
}


def push_key(service_name: str, key_value: str):
    """推送一把密钥到 service"""
    prompt = f"指令:密钥;注册,{service_name},{key_value},api_key"

    body = json.dumps({"prompt": prompt}).encode("utf-8")
    req = urllib.request.Request(
        SERVICE_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Service-token": SERVICE_TOKEN,
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        return data
    except urllib.error.HTTPError as e:
        err = e.read().decode()
        return {"error": f"HTTP {e.code}", "detail": err}
    except Exception as e:
        return {"error": str(e)}


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 push_key.py zhipu              # 从环境变量 ZHIPU_KEY 读取")
        print("  python3 push_key.py zhipu <你的key>    # 直接传入")
        print(f"\n已注册的服务名: {', '.join(KEY_MAP.keys())}")
        sys.exit(1)

    service = sys.argv[1]

    if service not in KEY_MAP:
        print(f"未知服务: {service}")
        print(f"可选: {', '.join(KEY_MAP.keys())}")
        sys.exit(1)

    # 获取密钥值：命令行 > 环境变量
    if len(sys.argv) >= 3:
        key_value = sys.argv[2]
        source = "命令行参数"
    else:
        env_name = KEY_MAP[service]
        key_value = os.getenv(env_name, "")
        source = f"环境变量 ${env_name}"
        if not key_value:
            print(f"错误: 未提供密钥值，且 ${env_name} 为空")
            sys.exit(1)

    print(f"推送 {service} 密钥 ({source})...")
    result = push_key(service, key_value)

    if "error" in result:
        print(f"❌ 推送失败: {result['error']}")
        if "detail" in result:
            print(f"   {result['detail']}")
        sys.exit(1)

    rst = result.get("rst_data", {})
    if isinstance(rst, dict):
        text = rst.get("text", str(result))
    else:
        text = str(rst)

    if "失败" in text or "错误" in text:
        print(f"❌ {text}")
        sys.exit(1)

    print(f"✅ {text}")


if __name__ == "__main__":
    main()

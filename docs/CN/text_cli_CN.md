# 如何开发一个指令包

text-cli 的指令包是自包含的能力单元——一个目录，几条指令，安装即用。

---

## 一、指令包是什么

一个指令包 = 一组 text-cli 指令 + 自描述 + 依赖声明。安装后，指令注册到服务的 dispatch 引擎，通过 `AI:域;动作,参数` 调用。

```
xx-cloud/
  handler.py          ← @directive 装饰器注册指令
  schema.json         ← 自描述（元数据 + 指令声明）
  requirements.txt    ← pip 依赖
```

不需要改 main.py——`handler_inits.py` 自动加载，manifest 追踪来源。

---

## 二、写 handler.py

```python
from core.registry import directive

@directive("xx-cloud", "translation")
def translate(params: list[str]) -> str:
    if not params:
        return json.dumps({"status": "error", "reason": "Usage: xx-cloud;translation,<text>"})
    text = params[0]
    # 调 API，返回结果
    return json.dumps({"status": "ok", "data": {"result": translated}})

def init_xx_cloud_handler():
    pass  # 凭证等延迟加载
```

关键约定：
- 返回 JSON 字符串，含 `status: "ok" | "error"`
- `init_<包名>_handler(db_path=None)` 是 handler_inits 加载的入口
- params 是字符串列表，handler 自己解析

---

## 三、写 schema.json

```json
{
  "id": "xx-cloud",
  "name": "XX Cloud",
  "name_cn": "XX云",
  "type": "native",
  "runtime": "python",
  "category": "云服务",
  "locales": ["cn", "en"],
  "trust": "internal",
  "description": "Cloud API integration.",
  "description_cn": "云服务 API 集成。",
  "requires": {
    "pip": ["requests>=2.28"],
    "tc_packages": ["task-manager", "quota-manage"]
  },
  "directives": [
    {
      "domain": "xx-cloud",
      "domain_cn": "XX云",
      "action": "translation",
      "action_cn": "翻译",
      "usage": "xx-cloud;translation,<text>",
      "usage_cn": "XX云;翻译,<文本>",
      "description": "Translate text.",
      "description_cn": "翻译文本。",
      "params": ["text"],
      "params_desc": {
        "text": "Text to translate"
      }
    }
  ]
}
```

必填字段：`id`、`type`、`runtime`、`directives`。`type` 决定 install 的部署策略——`native` 复制 handler.py，`nocode` 不复制 handler。

---

## 四、依赖声明

| 字段 | 说明 | install 行为 |
|------|------|-------------|
| `requires.pip` | Python 包 | `pip install` |
| `requires.tc_packages` | 其他指令包 | 检查是否已安装，否则拒绝 |
| `requires.binaries` | 系统二进制 | 检查是否在 PATH 中 |
| `requires.os_packages` | 系统包 | 提示手动安装 |
| `credentials` | 需要的凭据 | 记录在 manifest 中，运行时从 key_registry 获取 |

---

## 五、安装

```bash
# 从本地目录安装
AI:text-cli;install,xx-cloud

# 从 /root/text-cli-package/ 安装
AI:text-cli;install,xx-cloud

# 强制覆盖
AI:text-cli;install,xx-cloud,--force
```

install 做了什么：
1. 验证 schema.json
2. 安装 pip 依赖
3. 复制 handler 到 service/handlers/
4. 追加 handler_inits.py 条目
5. 写入 manifest（installed_packages.json）

---

## 六、生命周期

```
开发          安装          运行          导出          分享
tide-scripts → service → handler 运行 → exports/ → 另一个 service
    ↑                                              │
    └───────── 可被 install 消费 ←──────────────────┘
```

```
AI:text-cli;export,xx-cloud    → 单包导出
AI:text-cli;export-all         → 全量导出
AI:text-cli;packages           → 列出已安装包
AI:text-cli;uninstall,xx-cloud → 卸载
```

---

## 七、handler_inits 自动加载

不再在 main.py 里加 try/except。install 自动向 `config/handler_inits.py` 追加：

```python
HANDLER_INITS = [
    ("handlers.xx_cloud_handler", "init_xx_cloud_handler", None, None),
]
```

重启后自动加载。uninstall 自动移除条目。加包零 main.py 改动。

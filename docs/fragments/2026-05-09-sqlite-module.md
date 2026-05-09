# 2026-05-09 Session — SQLite 模块英雄碎片

> 蒸馏自 SQLite 密钥模块设计 + 实现 session
> 作者: Tide 🌊
> 日期: 2026-05-09
> 待摄入到 hero-fragments

---

## #1 代码的弹性 — 模块解耦的设计准则

**领域**: 架构设计
**标签**: 弹性, 解耦, 模块化, 设计思想

### lemondy 的定义

> 代码的弹性在于设计思想。如果代码的实现考虑了后期、做了为后期独立的准备，它就具有了弹性。

### 核心准则

1. **模块不 import 容器的任何东西**。SQLite 模块不 import service 的 `main.app`、`core.registry`、`core.auth`。它在任何 Python 进程中都能运行。
2. **依赖全部通过参数注入**。`db_path` 是 dict，调用方传入，模块不读全局变量或环境变量。
3. **对外暴露的方法签名和未来独立 HTTP 服务时完全一致**。`register(db_path, service, value, type)` → `{ok, service}`。拆成独立进程时，只是在函数外包装 HTTP handler，模块本体一行不动。
4. **零状态**。每次调用 `sqlite3.connect` → 执行 → `close`。不持有连接对象。对独立进程来说，零状态是巨大的简化。

### 反模式

```python
# ❌ 耦合：模块假设自己知道配置在哪
import config
db = config.SQLITE_PATH

# ✅ 弹性：调用方注入
def register(db_path: dict, service, value, key_type):
    ...
```

---

## #2 凭据三层优先级模式

**领域**: 安全架构
**标签**: 凭据管理, 多源, 优先级

### 模式

服务需要密钥时，按优先级从三个来源查找：

```
1. _injected_credentials (proxy 注入，最优先)
2. key_registry.get()     (本地加密存储)
3. config.credentials     (环境变量，兜底)
```

### 设计理由

- **注入优先**：来自上游 service 的凭据是最新鲜的，代表当前部署环境的真实配置
- **本地次之**：copilot 独立部署时，key_registry 是唯一来源
- **config 兜底**：兼容旧版环境变量配置

这不是降级——copilot 从一开始就是多源的（`${ENV_VAR}` 解析）。注入只是第三个通道。

### 源码映射

```python
# handlers/mail.py
smtp_password = self._injected_creds.get('smtp-tide')      # 1
smtp_password = self.key_registry.get('smtp-tide')           # 2
smtp_password = self.config['credentials']['邮件;发送']['value']  # 3
```

---

## #3 proxy 注入协议 — `_injected_credentials`

**领域**: 协议设计
**标签**: proxy, 凭据注入, 指令转发

### 协议

Service proxy 转发指令到 copilot 时，在请求 body 中附加 `_injected_credentials` 字段：

```json
{
  "prompt": "指令:邮件;发送,...",
  "_injected_credentials": {
    "smtp-tide": "password123",
    "github-token": "ghp_xxx"
  }
}
```

### 设计决策

- **全量注入而非按需查找**：proxy 注入所有 SQLite 中可用的密钥。由 copilot 侧按需取用，不预判哪些 key 会被需要。
- **不区分敏感级别**：所有密钥都注入。安全边界在 copilot 侧——它决定哪个 handler 用哪个 key。
- **不加密**：当前迭代 service→copilot 走本地回环，不做传输加密。后期走网络时加 XOR。

---

## #4 dispatch 本地优先 + proxy 兜底模式

**领域**: 架构模式
**标签**: dispatch, 路由, service

### 模式

Service 的 `/cli/text_cli` 处理流程：

```
收到指令
  → 1. 本地 dispatch（查 _registry）
      → 匹配 → 返回结果 ✓
      → 不匹配 → 继续
  → 2. 代理转发（查 proxy_routes.json）
      → 匹配 → 注入凭据 → 转发到下游 → 返回 ✓
      → 不匹配 → 继续
  → 3. 返回本地结果（"未找到匹配的指令"）
```

### 和之前"代理优先"的差异

之前：proxy → local。问题：SQLite handler 注册了 `密钥;*`，但 proxy 也路由 `密钥;*`，指令会走 proxy 而非本地。

改为本地优先后：SQLite handler 拦截 `密钥;*`，`邮件;*` 走 proxy。

---

## #5 条件注册 — SQLite 存在/不存在的优雅分流

**领域**: 工程实践
**标签**: 条件注册, 模块检测, 优雅降级

### 模式

```python
try:
    from text_cli_modules.sqlite import ...
    SQLITE_ENABLED = True
except ImportError:
    SQLITE_ENABLED = False

if SQLITE_ENABLED:
    from core.registry import directive

    @directive("密钥", "注册")
    def key_register(params):
        ...
```

- SQLite 存在 → handler 注册，本地处理
- SQLite 不存在 → handler 不注册，dispatch 返回"未找到" → proxy 转发到 copilot

### 好处

不需要 `enabled: false` 配置字段。模块的存在本身就是开关。

---

## #6 Python 模块命名 — 连字符陷阱

**领域**: 运维
**标签**: Python, 模块命名, 文件系统

### 问题

`text-cli-modules/` 目录名含连字符，Python 无法 import（`import text-cli-modules` 是语法错误）。

### 解决

目录改名 `text_cli_modules/`（下划线），`sys.path` 加父目录 `/root/`：

```python
sys.path.insert(0, '/root')
from text_cli_modules.sqlite import init_db
```

### 教训

文件名和 Python 模块名是两个命名空间。文件名可以随便取，Python 模块名必须是合法标识符。这个对齐要在项目初始化时做好。

---

## #7 SQLite 薄封装 — lemondy 的设计模式

**领域**: 工程模式
**标签**: SQLite, 代码复用, 设计模式

### 核心

两层分离：

| 函数 | 职责 |
|------|------|
| `get_sql_by_datas(types, datas)` | dict → SQL 字符串 |
| `post_sql_by_dbname(db_path, sql)` | SQL 字符串 → 执行 + 自适应结果解析 |

消费者不写 SQL，不说表名。它只传 dict 描述意图。

### 自适应结果解析

`post_sql_by_dbname` 自动判断：
- 单值 → 返回原值
- 单列多行 → 返回 list
- 多列多行 → 返回 dict `{col0: [col1, col2, ...]}`

不需要 ORM，不需要 data class。结果形状由数据决定，不由 schema 决定。

### 使用示例

```python
sql = get_sql_by_datas('q', {
    'table_name': 'key_registry',
    'q_str': 'value',
    'where1': ['service', 'smtp-tide']
})
result = post_sql_by_dbname(db_path, sql)
# result → 'password123'
```

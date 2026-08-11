# tc-sql — SQL 查询桥

> 查询协议层——不是新数据库，是通向数据库的桥。
> 任何数据拥有方通过声明加入，调用方通过统一指令访问。

---

## 指令

### 查询

```
tc-sql;query,<数据库代称>,<JSON>
```

```json
{"table": "call_log", "columns": "action,service,detail", "where": ["action", "KEY_REGISTER"], "limit": 20}
```

返回：

```json
{"status":"ok","table":"call_log","columns":["action","service","detail"],"rows":[...],"count":2}
```

| JSON 字段 | 必须 | 说明 |
|-----------|------|------|
| `table` | ✅ | 表名 |
| `columns` | ✅ | 列名，逗号分隔（禁止 `*`） |
| `where` | 否 | `[列名, 值]`，只支持等值条件 |
| `limit` | 否 | 行数上限，默认 100，最大 1000 |

### 表列表

```
tc-sql;tables,<数据库代称>
```

返回：`{"status":"ok","database":"service","tables":["call_log","key_registry"],"count":2}`

### 表结构

```
tc-sql;schema,<数据库代称>,{"table":"<表名>"}
```

返回每列的 cid、name、type、notnull、pk。

### 计数

```
tc-sql;count,<数据库代称>,{"table":"<表名>","where":["列名","值"]}
```

返回：`{"status":"ok","table":"key_registry","count":42}`

---

## 权限

权限由 `config/sql_permissions.json` 控制。安装时自动部署到 service 的 config 目录——已存在的文件不会被覆盖。

```json
{
  "authenticated": {
    "service": {
      "driver": "sqlite",
      "path": "text_cli_modules/sqlite/service.db",
      "tables": {
        "key_registry": {"ops": ["schema"]},
        "call_log": {"ops": ["query", "schema", "tables", "count"]}
      }
    }
  }
}
```

**红线**：`key_registry` 永远不给 `query` 权限——密钥值通过专用指令 `key;get` 访问。

---

## 设计原则

- **读可以通用，写必须专用**——查询走 tc-sql，写入走各域专用指令
- **列名在结果中**——管道可索引，AI 可读
- **JSON 防注入**——列名和值在不同字段，天然隔离
- **驱动无关**——权限声明 `driver` 字段，连接工厂在 handler 内做分支

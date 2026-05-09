# text-cli-copilot 开发任务清单

> 基于 `text-cli-copilot_programme_CN.md` v1.2 生成。
> 日期：2026-05-07
> 状态：待开工

---

## 阶段 1：骨架验证

**目标**：HTTP 服务启动 → Token 校验 → 指令解析 → curl 可验证

### 1.1 项目结构初始化

- [ ] 创建 `text-cli-copilot.py`（零依赖，stdlib only）
- [ ] 创建 `auxiliary_config.json`（基于 §5 完整配置）
- [ ] 实现 `Copilot._load_config()`——JSON 读取 + `${VAR}` 解析
- [ ] 实现 `Copilot._resolve_env()`——启动时一次性替换所有占位符

### 1.2 HTTP 服务

- [ ] 基于 `http.server` 实现 `POST /cli/text_cli`
- [ ] 请求体 JSON 解析（`{"prompt": "..."}`）
- [ ] Token 校验——读取 `Authorization: Bearer xxx`，与 config `server.token` 比对
- [ ] 401 响应（Token 不匹配时）
- [ ] 启动日志——打印 `listening on 127.0.0.1:20260`

### 1.3 指令解析器

- [ ] 实现 `_parse_instruction(prompt)` → `{domain, action, params}`
- [ ] 双前缀识别（`指令:` / `directive:`）
- [ ] 分号分割领域和动作
- [ ] 逗号分割参数，最后一个参数贪婪匹配
- [ ] 空 prompt / 格式错误 → 返回 `rst_err: "parse_error"`

### 1.4 text-cli 标准响应

- [ ] `_ok(text, **extra)` → `{"rst_types": "text", "rst_data": {"text": ..., ...}}`
- [ ] `_error(code, detail)` → `{"rst_types": "text", "rst_data": {"text": "..."}, "rst_err": "..."}`
- [ ] 所有响应头 `Content-Type: application/json`

### 1.5 Dispatch 骨架

- [ ] 实现 `_dispatch(domain, action)` → handler 查找（alias_map + handlers）
- [ ] `unknown_instruction` 错误处理
- [ ] 阶段 1 验证用临时 handler（返回假数据即可）

**检查点 C1** 🎯：以下命令全部返回预期响应

```bash
python text-cli-copilot.py &
# 1. 有效请求
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:Git;状态"}' | python -m json.tool

# 2. Token 错误
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer wrong" \
  -d '{"prompt": "指令:Git;状态"}'

# 3. 格式错误
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "这不是指令"}'

# 4. 英文前缀
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "directive:git;status"}'
```

---

## 阶段 2：文件操作

**目标**：`文件;读取` + `文件;写入` 跑通，路径白名单生效

### 2.1 路径白名单校验

- [ ] 实现 `_check_path(path)`——前缀匹配 + 精确匹配
- [ ] 越界 → `rst_err: "path_denied"`，不做任何操作
- [ ] 解析 `../` 等相对路径组件后校验（防绕过）

### 2.2 `文件;读取` handler

- [ ] `_handle_文件_读取(params)` 
- [ ] `pathlib.Path.read_text(encoding='utf-8')`
- [ ] 文件不存在 → `rst_err: "file_not_found"`
- [ ] 文件 >10MB → `rst_err: "file_too_large"`
- [ ] 成功 → `rst_data.text = 内容, rst_data.size = 字节数`
- [ ] 非 UTF-8 文件 → `rst_err: "encoding_error"` + 提示（非静默截断）

### 2.3 `文件;写入` handler

- [ ] `_handle_文件_写入(params)`
- [ ] 自动创建父目录（`Path.mkdir(parents=True, exist_ok=True)`）
- [ ] 写入后返回字节数确认

### 2.4 英文 alias 验证

- [ ] `directive:file;read,/path` → 走到 `_handle_文件_读取`
- [ ] `directive:file;write,/path,content` → 走到 `_handle_文件_写入`

**检查点 C2** 🎯：

```bash
# 读文件（白名单内）
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:文件;读取,auxiliary_config.json"}'

# 读文件（白名单外 → 拒绝）
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:文件;读取,/etc/passwd"}'

# 写文件
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:文件;写入,/tmp/test_copilot.txt,Hello 辅助服务器"}'

# 英文 alias
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "directive:file;read,auxiliary_config.json"}'
```

---

## 阶段 3：Git 操作

**目标**：`Git;状态` + `Git;推送`（Mode 2 + Mode 3），SSH 降级

### 3.1 `Git;状态` handler

- [ ] `_handle_Git_状态(params)`
- [ ] `subprocess.run(['git', 'status'], cwd=workdir, capture_output=True, timeout=30)`
- [ ] git 不存在或非 git 目录 → 友好错误

### 3.2 凭据解析器

- [ ] 实现 `_resolve_credential(cred_value)`（逻辑见 §5.2）
- [ ] Mode 1（`https://`）→ `{mode: 'inject', url: ...}` —— 代码预留
- [ ] Mode 2（`${VAR}`）→ `{mode: 'https', token: resolved}`
- [ ] Mode 2（明文）→ `{mode: 'https', token: raw}`
- [ ] Mode 3（null/空）→ `{mode: 'ssh'}`

### 3.3 `Git;推送` handler——HTTPS 路径

- [ ] 分支名校验（allowed_branches + 通配符 `feat/*`）
- [ ] 自动获取 remote URL（`git remote get-url origin`）
- [ ] HTTPS push：`git push https://TOKEN@remote_url branch`（inline URL，不修改仓库 remote）
- [ ] HTTPS 成功 → `rst_data.auth_mode = "https"`

### 3.4 `Git;推送` handler——SSH 降级

- [ ] HTTPS 失败 → 自动尝试 `git push remote_name branch`（SSH）
- [ ] SSH 成功 → `rst_data.auth_mode = "ssh"`
- [ ] 两者都失败 → `rst_err: "push_failed"` + stderr

### 3.5 安全约束

- [ ] 分支不在白名单 → `rst_err: "branch_denied"`
- [ ] subprocess timeout 30s → `rst_err: "timeout"`
- [ ] 非 git 目录 → `rst_err: "not_git_repo"`

**检查点 C3** 🎯：

```bash
# Git 状态
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:Git;状态"}'

# Git 推送（SSH 模式，前提：本地有 SSH key）
curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:Git;推送,main"}'
```

---

## 阶段 4：邮件发送

**目标**：`邮件;发送` 通过 SMTP 发出邮件

### 4.1 SMTP 连接

- [ ] 从 config `credentials["邮件;发送"]` 读取 SMTP 配置
- [ ] `smtplib.SMTP_SSL(smtp_host, smtp_port)` 连接
- [ ] `server.login(smtp_user, smtp_password)` 认证
- [ ] 连接失败 → `rst_err: "smtp_connect_failed"`
- [ ] 认证失败 → `rst_err: "smtp_auth_failed"`

### 4.2 邮件发送

- [ ] `_handle_邮件_发送(params)`
- [ ] 构建 MIME 邮件（from + to + subject + body，UTF-8 编码）
- [ ] `server.sendmail(from, to, message.as_string())`
- [ ] 发送成功 → `rst_data.text = "邮件已发送至 xxx"`

### 4.3 附件支持（可选参数）

- [ ] 第 4 个参数为附件路径时，附加文件
- [ ] 附件路径 → 白名单校验

### 4.4 安全

- [ ] SMTP 密码在 config 中以 `${SMTP_PASSWORD}` 占位，启动时解析
- [ ] Agent 指令中不传递密码

**检查点 C4** 🎯：

```bash
# 发送邮件（需要先设置 SMTP_PASSWORD 等环境变量）
export SMTP_USER="claw1@10000.world"
export SMTP_PASSWORD="xxx"
export SMTP_FROM="claw1@10000.world"

curl -s -X POST http://localhost:20260/cli/text_cli \
  -H "Authorization: Bearer <token>" \
  -d '{"prompt": "指令:邮件;发送,limh@10000.world,copilot 测试,辅助服务器邮件功能验证通过"}'
```

---

## 阶段 5：发现端点

**目标**：`GET /text_cli_schema.json` 返回指令清单

### 5.1 Schema 端点

- [ ] 实现 `GET /text_cli_schema.json`（无需 Token 鉴权）
- [ ] 返回 `endpoint` 信息（name + url + version）
- [ ] 返回 `directives` 数组——由 `config.operations` 自动生成
- [ ] 每条 directive 含 `id` + `aliases` + `description` + `description_en` + `parameters` + `parameters_en` + `returns`
- [ ] 如果 config 新增了一条 operation，Schema 自动反映

### 5.2 验证

- [ ] 对比返回的 Schema 与技术方案 §3.2 的一致

**检查点 C5** 🎯：

```bash
curl -s http://localhost:20260/text_cli_schema.json | python -m json.tool
# 验证：
# [ ] 5 条指令全部出现
# [ ] 每条都有 aliases + description_en
# [ ] endpoint.url = "http://localhost:20260"
```

---

## 阶段 6：集成验证

**目标**：所有指令端到端跑通，文档对齐

### 6.1 全指令回归

- [ ] 5 条指令 × (中文 + 英文) = 10 种调用方式全部 200 OK
- [ ] 5 条指令的错误路径（越界/不存在/格式错误）全部返回正确错误码
- [ ] Token 校验覆盖（正确 token + 错误 token + 无 token）

### 6.2 文档对齐

- [ ] README 或启动文档——告诉用户怎么配环境变量、怎么启动
- [ ] 配置模板——`auxiliary_config.json` 加注释说明每个字段
- [ ] old_code 目录标记——说明 port_20260.py 已被替代

### 6.3 与 Agent Skill 联调（后续）

- [ ] 在 `endpoints.json` 注册 `localhost:20260`
- [ ] 同步 Skill 拉取 Schema → 聚合到 `agent-text-cli-schema.json`
- [ ] Agent 通过文本指令调 copilot

**检查点 C6** 🎯：全指令回归 + 文档就绪

---

## 检查点汇总

| 检查点 | 阶段 | 验证方式 | 关键验收标准 |
|--------|------|---------|-------------|
| **C1** | 骨架 | curl 4 条命令 | 服务启动、Token 校验、指令解析、中英前缀 |
| **C2** | 文件 | curl 4 条命令 | 读成功、越界拒绝、写成功、英文 alias |
| **C3** | Git | curl 2 条命令 | git status 正常、SSH push 正常 |
| **C4** | 邮件 | curl 1 条命令 | SMTP 发送成功（需配环境变量） |
| **C5** | 发现 | curl 1 条命令 | Schema 返回 5 条指令 + 多语言字段 |
| **C6** | 集成 | 全指令回归 | 5 指令 × 2 语言 = 10 种全部 OK |

---

## 优先级

```
P0（必须）: C1 → C2 → 核心可用
P1（核心）: C3 → 本地 Git 操作可用
P2（增强）: C4 → 邮件可用
P3（生态）: C5 → 多源聚合可发现
P4（收尾）: C6 → 全链路验证
```

P0+P1 完成后 copilot 即可投入使用。P2+P3 让它完整。P4 让它优雅。

---

*由 Tide 🌊 基于 `text-cli-copilot_programme_CN.md` v1.2 + `指令辅助服务器_思维路标_CN.md` 生成。*

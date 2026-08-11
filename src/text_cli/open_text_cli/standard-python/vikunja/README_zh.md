# vikunja — 自托管任务管理

通过 text-cli 指令管线管理 Vikunja 的任务、项目、标签、关系和用户。

## 安装

```
AI:text-cli;install,vikunja
```

## 前置条件

- Vikunja v2.3+ 实例运行中（详见 [DEPLOY.md](DEPLOY.md)）
- Bearer Token 已注册到 key_registry：`AI:key;register,vikunja,<token>,api_key`
- DNS/hosts 中 `vikunja.lan` 指向 Vikunja 宿主机

## 指令（25 条）

### 任务（8 条）

| 动作 | 签名 | 说明 |
|------|------|------|
| list-tasks | `vikunja;list-tasks[,<JSON>]` | 列出任务，支持筛选/排序/分页 |
| create-task | `vikunja;create-task,<JSON>` | 在项目中创建任务 |
| get-task | `vikunja;get-task,<task_id>` | 获取任务详情 |
| update-task | `vikunja;update-task,<task_id>,<JSON>` | 更新任务字段 |
| delete-task | `vikunja;delete-task,<task_id>` | 删除任务 |
| done | `vikunja;done,<task_id>` | 标记完成任务 |
| undone | `vikunja;undone,<task_id>` | 取消完成任务 |
| assignees | `vikunja;assignees,<task_id>` | 获取任务分配用户 |

### 分配（1 条）

| 动作 | 签名 | 说明 |
|------|------|------|
| assign | `vikunja;assign,<task_id>,<user_id>` | 分配用户到任务 |

### 项目（6 条）

| 动作 | 签名 | 说明 |
|------|------|------|
| list-projects | `vikunja;list-projects[,<JSON>]` | 列出项目 |
| create-project | `vikunja;create-project,<JSON>` | 创建项目 |
| get-project | `vikunja;get-project,<project_id>` | 获取项目详情 |
| update-project | `vikunja;update-project,<project_id>,<JSON>` | 更新项目 |
| delete-project | `vikunja;delete-project,<project_id>` | 删除项目 |
| project-tasks | `vikunja;project-tasks,<project_id>[,<JSON>]` | 获取项目下的任务 |

### 标签（5 条）

| 动作 | 签名 | 说明 |
|------|------|------|
| list-labels | `vikunja;list-labels[,<JSON>]` | 列出标签 |
| create-label | `vikunja;create-label,<JSON>` | 创建标签 |
| get-label | `vikunja;get-label,<label_id>` | 获取标签详情 |
| update-label | `vikunja;update-label,<label_id>,<JSON>` | 更新标签 |
| delete-label | `vikunja;delete-label,<label_id>` | 删除标签 |

### 关系（3 条）

| 动作 | 签名 | 说明 |
|------|------|------|
| list-relations | `vikunja;list-relations,<task_id>` | 列出任务关系 |
| create-relation | `vikunja;create-relation,<task_id>,<JSON>` | 创建任务关系 |
| delete-relation | `vikunja;delete-relation,<task_id>,<JSON>` | 删除任务关系 |

### 用户（2 条）

| 动作 | 签名 | 说明 |
|------|------|------|
| list-users | `vikunja;list-users` | 列出用户 |
| get-user | `vikunja;get-user,<user_id>` | 获取用户详情 |

## 示例

```
# 创建任务
AI:vikunja;create-task,{"title":"买菜","priority":3,"project_id":5}

# 列出未完成任务，按优先级排序
AI:vikunja;list-tasks,{"filter_by":[{"column":"done","value":false,"comparator":"equals"}],"sort_by":[{"column":"priority","order":"desc"}]}

# 创建标签并查看
AI:vikunja;create-label,{"title":"紧急","color":"#ff0000"}
AI:vikunja;list-labels

# 路径管线：基于关系的任务路由
AI:vikunja;list-relations,{task_id}
  → 检查阻塞关系
  → AI:vikunja;done,{task_id}  （若无阻塞）
```

## 文件结构

```
vikunja/
├── DESIGN.md
├── DESIGN_v1.md          ← 原始提案（lemondy）
├── schema.json           ← 25 条指令声明
├── handler.py            ← @directive 实现
├── README.md             ← 纯英文
├── README_CN.md          ← 本文件
├── DEPLOY.md             ← Docker 部署指南
└── demo.py               ← API 参考文档
```

## 设计说明

- **鉴权**：Bearer Token 从 `key_registry("vikunja")` 读取
- **API 基址**：`http://vikunja.lan:3466/api/v1`
- **API 版本**：Vikunja v2.3
- **返回格式**：展开——业务字段在 `status` 同级，无 `data` 嵌套层

# vikunja — Self-hosted Task Management

Manage Vikunja tasks, projects, labels, relations, and users via the text-cli instruction pipeline.

## Install

```
AI:text-cli;install,vikunja
```

## Prerequisites

- Vikunja v2.3+ instance running (see [DEPLOY.md](DEPLOY.md))
- Bearer token registered in key_registry: `AI:key;register,vikunja,<token>,api_key`
- DNS/hosts entry `vikunja.lan` pointing to the Vikunja host

## Directives (25)

### Tasks (8)

| Action | Signature | Description |
|--------|-----------|-------------|
| list-tasks | `vikunja;list-tasks[,<JSON>]` | List tasks with filter/sort/page |
| create-task | `vikunja;create-task,<JSON>` | Create a task in a project |
| get-task | `vikunja;get-task,<task_id>` | Get task details |
| update-task | `vikunja;update-task,<task_id>,<JSON>` | Update task fields |
| delete-task | `vikunja;delete-task,<task_id>` | Delete a task |
| done | `vikunja;done,<task_id>` | Mark task as done |
| undone | `vikunja;undone,<task_id>` | Mark task as not done |
| assignees | `vikunja;assignees,<task_id>` | Get assigned users |

### Assignment (1)

| Action | Signature | Description |
|--------|-----------|-------------|
| assign | `vikunja;assign,<task_id>,<user_id>` | Assign user to task |

### Projects (6)

| Action | Signature | Description |
|--------|-----------|-------------|
| list-projects | `vikunja;list-projects[,<JSON>]` | List projects |
| create-project | `vikunja;create-project,<JSON>` | Create a project |
| get-project | `vikunja;get-project,<project_id>` | Get project details |
| update-project | `vikunja;update-project,<project_id>,<JSON>` | Update project |
| delete-project | `vikunja;delete-project,<project_id>` | Delete project |
| project-tasks | `vikunja;project-tasks,<project_id>[,<JSON>]` | List tasks in a project |

### Labels (5)

| Action | Signature | Description |
|--------|-----------|-------------|
| list-labels | `vikunja;list-labels[,<JSON>]` | List labels |
| create-label | `vikunja;create-label,<JSON>` | Create a label |
| get-label | `vikunja;get-label,<label_id>` | Get label details |
| update-label | `vikunja;update-label,<label_id>,<JSON>` | Update label |
| delete-label | `vikunja;delete-label,<label_id>` | Delete label |

### Relations (3)

| Action | Signature | Description |
|--------|-----------|-------------|
| list-relations | `vikunja;list-relations,<task_id>` | List task relations |
| create-relation | `vikunja;create-relation,<task_id>,<JSON>` | Create a relation |
| delete-relation | `vikunja;delete-relation,<task_id>,<JSON>` | Delete a relation |

### Users (2)

| Action | Signature | Description |
|--------|-----------|-------------|
| list-users | `vikunja;list-users` | List all users |
| get-user | `vikunja;get-user,<user_id>` | Get user details |

## Examples

```
# Create a task
AI:vikunja;create-task,{"title":"Buy groceries","priority":3,"project_id":5}

# List undone tasks sorted by priority
AI:vikunja;list-tasks,{"filter_by":[{"column":"done","value":false,"comparator":"equals"}],"sort_by":[{"column":"priority","order":"desc"}]}

# Create a label and check it
AI:vikunja;create-label,{"title":"urgent","color":"#ff0000"}
AI:vikunja;list-labels

# Path pipeline: relation-based routing
AI:vikunja;list-relations,{task_id}
  → check for blocking relations
  → AI:vikunja;done,{task_id}  (if unblocked)
```

## Architecture

```
vikunja/
├── DESIGN.md
├── DESIGN_v1.md          ← original proposal (lemondy)
├── schema.json           ← 25 directives
├── handler.py            ← @directive implementations
├── README.md             ← this file
├── README_CN.md          ← 中文
├── DEPLOY.md             ← Docker deployment guide
└── demo.py               ← API docs reference
```

- **Auth**: Bearer token from `key_registry("vikunja")`
- **Base URL**: `http://vikunja.lan:3466/api/v1` (configurable via hosts/DNS)
- **API version**: Vikunja v2.3
- **Response format**: Flattened — business fields at `status` level, no `data` nesting

"""vikunja handler — Self-hosted task management via Vikunja API.

25 directives: task CRUD (8), assignment (1), project CRUD (6),
label CRUD (5), task relations (3), users (2).
Credentials from A6 key_registry (vikunja).
"""

import json
import logging

import requests

from core.registry import directive

logger = logging.getLogger(__name__)

VIKUNJA_BASE = "http://vikunja.lan:3466/api/v1"
TIMEOUT = 15

_token: str | None = None

def init_vikunja_handler(db_path: str):
    """Load Vikunja Bearer token from key_registry."""
    global _token
    try:
        from text_cli_modules.key.key_registry import get as key_get
        creds = key_get(db_path, "vikunja")
        if creds:
            if isinstance(creds, str):
                _token = creds
            elif isinstance(creds, (list, tuple)):
                _token = creds[0][0] if isinstance(creds[0], (list, tuple)) else creds[0]
            logger.info("vikunja token loaded from key_registry")
        else:
            logger.warning("vikunja: vikunja key not configured in key_registry")
    except ImportError:
        logger.warning("vikunja: key_registry module not available")

def _request(method: str, path: str, json_data: dict | None = None,
             params: dict | None = None) -> dict:
    """Send authenticated request to Vikunja API, return JSON body."""
    if not _token:
        raise RuntimeError("vikunja token not configured in key_registry")

    url = f"{VIKUNJA_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {_token}",
        "Content-Type": "application/json",
    }
    resp = requests.request(method, url, json=json_data, params=params,
                            headers=headers, timeout=TIMEOUT)
    if not resp.ok:
        return _map_error(resp)
    try:
        return resp.json()
    except ValueError:
        return {}

def _map_error(resp) -> dict:
    """Map HTTP status to structured error."""
    code = resp.status_code
    try:
        body = resp.json()
        detail = body.get("message", "")
    except ValueError:
        detail = resp.text[:200] if resp.text else ""
    reason_map = {
        400: f"invalid request{f': {detail}' if detail else ''}",
        401: "vikunja authentication failed",
        403: "vikunja permission denied",
        404: "vikunja resource not found",
        422: f"validation failed{f': {detail}' if detail else ''}",
        429: "vikunja rate limited, retry later",
    }
    reason = reason_map.get(code, f"vikunja error HTTP {code}{f': {detail}' if detail else ''}")
    return {"status": "error", "reason": reason, "http_code": code}

def _parse_json(params: list[str], start: int) -> dict | None:
    """Parse JSON from params starting at index."""
    if len(params) <= start:
        return None
    try:
        return json.loads(",".join(params[start:]))
    except (json.JSONDecodeError, ValueError):
        return None

def _error(reason: str) -> dict:
    return {"status": "error", "reason": reason}

def _ok(data: dict) -> dict:
    return {"status": "ok", **data}

@directive("vikunja", "list-tasks",
            domain_alias="Vikunja", action_aliases={"list-tasks": "列出任务"})
def vikunja_list_tasks(params: list[str]) -> dict:
    """vikunja;list-tasks[,<JSON>]"""
    extra = _parse_json(params, 0) or {}
    try:
        data = _request("GET", "/tasks", params=extra)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and "status" in data:
        return data  # pass through error

    tasks = _extract_tasks(data)
    return _ok({"tasks": tasks, "count": len(tasks), "total": len(tasks)})

@directive("vikunja", "create-task",
            domain_alias="Vikunja", action_aliases={"create-task": "创建任务"})
def vikunja_create_task(params: list[str]) -> dict:
    """vikunja;create-task,<JSON>"""
    if not params:
        return _error("Usage: vikunja;create-task,<JSON>")
    body = _parse_json(params, 0)
    if body is None:
        return _error("JSON parameter parse failed")
    try:
        project_id = body.get("project_id") if isinstance(body, dict) else None
        if project_id:
            task_body = {k: v for k, v in body.items() if k != "project_id"}
            data = _request("PUT", f"/projects/{project_id}/tasks", json_data=task_body)
        else:
            data = _request("PUT", "/projects/1/tasks", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_task(data))

@directive("vikunja", "get-task",
            domain_alias="Vikunja", action_aliases={"get-task": "获取任务"})
def vikunja_get_task(params: list[str]) -> dict:
    """vikunja;get-task,<task_id>"""
    if not params:
        return _error("Usage: vikunja;get-task,<task_id>")
    try:
        data = _request("GET", f"/tasks/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_task(data))

@directive("vikunja", "update-task",
            domain_alias="Vikunja", action_aliases={"update-task": "更新任务"})
def vikunja_update_task(params: list[str]) -> dict:
    """vikunja;update-task,<task_id>,<JSON>"""
    if len(params) < 2:
        return _error("Usage: vikunja;update-task,<task_id>,<JSON>")
    body = _parse_json(params, 1)
    if body is None:
        return _error("JSON parameter parse failed")
    try:
        data = _request("POST", f"/tasks/{params[0]}", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_task(data))

@directive("vikunja", "delete-task",
            domain_alias="Vikunja", action_aliases={"delete-task": "删除任务"})
def vikunja_delete_task(params: list[str]) -> dict:
    """vikunja;delete-task,<task_id>"""
    if not params:
        return _error("Usage: vikunja;delete-task,<task_id>")
    try:
        data = _request("DELETE", f"/tasks/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"id": int(params[0]), "deleted": True})

@directive("vikunja", "done",
            domain_alias="Vikunja", action_aliases={"done": "完成任务"})
def vikunja_done(params: list[str]) -> dict:
    """vikunja;done,<task_id>"""
    if not params:
        return _error("Usage: vikunja;done,<task_id>")
    try:
        data = _request("POST", f"/tasks/{params[0]}", json_data={"done": True})
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"id": int(params[0]), "done": True})

@directive("vikunja", "undone",
            domain_alias="Vikunja", action_aliases={"undone": "取消完成"})
def vikunja_undone(params: list[str]) -> dict:
    """vikunja;undone,<task_id>"""
    if not params:
        return _error("Usage: vikunja;undone,<task_id>")
    try:
        data = _request("POST", f"/tasks/{params[0]}", json_data={"done": False})
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"id": int(params[0]), "done": False})

@directive("vikunja", "assignees",
            domain_alias="Vikunja", action_aliases={"assignees": "任务参与人"})
def vikunja_assignees(params: list[str]) -> dict:
    """vikunja;assignees,<task_id>"""
    if not params:
        return _error("Usage: vikunja;assignees,<task_id>")
    try:
        data = _request("GET", f"/tasks/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    assignees_list = data.get("assignees") or []
    users = []
    for a in assignees_list:
        users.append({
            "id": a.get("id"),
            "username": a.get("username", ""),
            "name": a.get("name", ""),
        })
    return _ok({"task_id": data.get("id"), "assignees": users, "count": len(users)})

@directive("vikunja", "assign",
            domain_alias="Vikunja", action_aliases={"assign": "分配用户"})
def vikunja_assign(params: list[str]) -> dict:
    """vikunja;assign,<task_id>,<user_id>"""
    if len(params) < 2:
        return _error("Usage: vikunja;assign,<task_id>,<user_id>")
    try:
        body = {"user_id": int(params[1])}
        data = _request("PUT", f"/tasks/{params[0]}/assignees", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"task_id": int(params[0]), "user_id": int(params[1]), "assigned": True})

@directive("vikunja", "list-projects",
            domain_alias="Vikunja", action_aliases={"list-projects": "列出项目"})
def vikunja_list_projects(params: list[str]) -> dict:
    """vikunja;list-projects[,<JSON>]"""
    extra = _parse_json(params, 0) or {}
    try:
        data = _request("GET", "/projects", params=extra)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    projects = data if isinstance(data, list) else data.get("data", data)
    if not isinstance(projects, list):
        projects = []
    reduced = [_reduce_project(p) for p in projects]
    return _ok({"projects": reduced, "count": len(reduced)})

@directive("vikunja", "create-project",
            domain_alias="Vikunja", action_aliases={"create-project": "创建项目"})
def vikunja_create_project(params: list[str]) -> dict:
    """vikunja;create-project,<JSON>"""
    if not params:
        return _error("Usage: vikunja;create-project,<JSON>")
    body = _parse_json(params, 0)
    if body is None:
        return _error("JSON parameter parse failed")
    try:
        data = _request("PUT", "/projects", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_project(data))

@directive("vikunja", "get-project",
            domain_alias="Vikunja", action_aliases={"get-project": "获取项目"})
def vikunja_get_project(params: list[str]) -> dict:
    """vikunja;get-project,<project_id>"""
    if not params:
        return _error("Usage: vikunja;get-project,<project_id>")
    try:
        data = _request("GET", f"/projects/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_project(data))

@directive("vikunja", "update-project",
            domain_alias="Vikunja", action_aliases={"update-project": "更新项目"})
def vikunja_update_project(params: list[str]) -> dict:
    """vikunja;update-project,<project_id>,<JSON>"""
    if len(params) < 2:
        return _error("Usage: vikunja;update-project,<project_id>,<JSON>")
    body = _parse_json(params, 1)
    if body is None:
        return _error("JSON parameter parse failed")
    try:
        data = _request("POST", f"/projects/{params[0]}", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_project(data))

@directive("vikunja", "delete-project",
            domain_alias="Vikunja", action_aliases={"delete-project": "删除项目"})
def vikunja_delete_project(params: list[str]) -> dict:
    """vikunja;delete-project,<project_id>"""
    if not params:
        return _error("Usage: vikunja;delete-project,<project_id>")
    try:
        data = _request("DELETE", f"/projects/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"id": int(params[0]), "deleted": True})

@directive("vikunja", "project-tasks",
            domain_alias="Vikunja", action_aliases={"project-tasks": "项目任务"})
def vikunja_project_tasks(params: list[str]) -> dict:
    """vikunja;project-tasks,<project_id>[,<JSON>]"""
    if not params:
        return _error("Usage: vikunja;project-tasks,<project_id>[,<JSON>]")
    extra = _parse_json(params, 1) or {}
    try:
        data = _request("GET", f"/projects/{params[0]}/tasks", params=extra)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    tasks = _extract_tasks(data)
    return _ok({"project_id": int(params[0]), "tasks": tasks, "count": len(tasks)})

@directive("vikunja", "list-labels",
            domain_alias="Vikunja", action_aliases={"list-labels": "列出标签"})
def vikunja_list_labels(params: list[str]) -> dict:
    """vikunja;list-labels[,<JSON>]"""
    extra = _parse_json(params, 0) or {}
    try:
        data = _request("GET", "/labels", params=extra)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    labels = data if isinstance(data, list) else data.get("data", data)
    if not isinstance(labels, list):
        labels = []
    reduced = [_reduce_label(l) for l in labels]
    return _ok({"labels": reduced, "count": len(reduced)})

@directive("vikunja", "create-label",
            domain_alias="Vikunja", action_aliases={"create-label": "创建标签"})
def vikunja_create_label(params: list[str]) -> dict:
    """vikunja;create-label,<JSON>"""
    if not params:
        return _error("Usage: vikunja;create-label,<JSON>")
    body = _parse_json(params, 0)
    if body is None:
        return _error("JSON parameter parse failed")
    try:
        data = _request("PUT", "/labels", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_label(data))

@directive("vikunja", "get-label",
            domain_alias="Vikunja", action_aliases={"get-label": "获取标签"})
def vikunja_get_label(params: list[str]) -> dict:
    """vikunja;get-label,<label_id>"""
    if not params:
        return _error("Usage: vikunja;get-label,<label_id>")
    try:
        data = _request("GET", f"/labels/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_label(data))

@directive("vikunja", "update-label",
            domain_alias="Vikunja", action_aliases={"update-label": "更新标签"})
def vikunja_update_label(params: list[str]) -> dict:
    """vikunja;update-label,<label_id>,<JSON>"""
    if len(params) < 2:
        return _error("Usage: vikunja;update-label,<label_id>,<JSON>")
    body = _parse_json(params, 1)
    if body is None:
        return _error("JSON parameter parse failed")
    try:
        data = _request("PUT", f"/labels/{params[0]}", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok(_reduce_label(data))

@directive("vikunja", "delete-label",
            domain_alias="Vikunja", action_aliases={"delete-label": "删除标签"})
def vikunja_delete_label(params: list[str]) -> dict:
    """vikunja;delete-label,<label_id>"""
    if not params:
        return _error("Usage: vikunja;delete-label,<label_id>")
    try:
        data = _request("DELETE", f"/labels/{params[0]}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"id": int(params[0]), "deleted": True})

@directive("vikunja", "list-relations",
            domain_alias="Vikunja", action_aliases={"list-relations": "列出任务关系"})
def vikunja_list_relations(params: list[str]) -> dict:
    """vikunja;list-relations,<task_id>"""
    if not params:
        return _error("Usage: vikunja;list-relations,<task_id>")
    try:
        data = _request("GET", f"/tasks/{params[0]}/relations")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    relations = data if isinstance(data, list) else data.get("data", data)
    if not isinstance(relations, list):
        relations = []
    reduced = [_reduce_relation(r) for r in relations]
    return _ok({"task_id": int(params[0]), "relations": reduced, "count": len(reduced)})

@directive("vikunja", "create-relation",
            domain_alias="Vikunja", action_aliases={"create-relation": "创建任务关系"})
def vikunja_create_relation(params: list[str]) -> dict:
    """vikunja;create-relation,<task_id>,<JSON>"""
    if len(params) < 2:
        return _error("Usage: vikunja;create-relation,<task_id>,<JSON>")
    body = _parse_json(params, 1)
    if body is None or "other_task_id" not in body or "relation_kind" not in body:
        return _error("JSON must contain {other_task_id, relation_kind}")
    try:
        data = _request("PUT", f"/tasks/{params[0]}/relations", json_data=body)
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({
        "task_id": int(params[0]),
        "other_task_id": body["other_task_id"],
        "relation_kind": body["relation_kind"],
        "created_by": data.get("created_by"),
    })

@directive("vikunja", "delete-relation",
            domain_alias="Vikunja", action_aliases={"delete-relation": "删除任务关系"})
def vikunja_delete_relation(params: list[str]) -> dict:
    """vikunja;delete-relation,<task_id>,<JSON>"""
    if len(params) < 2:
        return _error("Usage: vikunja;delete-relation,<task_id>,<JSON>")
    body = _parse_json(params, 1)
    if body is None or "relation_kind" not in body or "other_task_id" not in body:
        return _error("JSON must contain {relation_kind, other_task_id}")
    try:
        data = _request("DELETE", f"/tasks/{params[0]}/relations/{body['relation_kind']}/{body['other_task_id']}")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    return _ok({"task_id": int(params[0]), "relation_kind": body["relation_kind"], "other_task_id": body["other_task_id"], "deleted": True})

@directive("vikunja", "list-users",
            domain_alias="Vikunja", action_aliases={"list-users": "列出用户"})
def vikunja_list_users(params: list[str]) -> dict:
    """vikunja;list-users"""
    try:
        data = _request("GET", "/users")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    if data is None:
        return _ok({"users": [], "count": 0})

    users = data if isinstance(data, list) else data.get("data", data)
    if not isinstance(users, list):
        users = []
    reduced = [_reduce_user(u) for u in users]
    return _ok({"users": reduced, "count": len(reduced)})

@directive("vikunja", "get-user",
            domain_alias="Vikunja", action_aliases={"get-user": "获取用户"})
def vikunja_get_user(params: list[str]) -> dict:
    """vikunja;get-user,<user_id>"""
    if not params:
        return _error("Usage: vikunja;get-user,<user_id>")
    target_id = int(params[0])
    try:
        data = _request("GET", "/users")
    except RuntimeError as e:
        return _error(str(e))
    except requests.RequestException as e:
        return _error(f"vikunja not reachable: {e}")

    if isinstance(data, dict) and data.get("status") == "error":
        return data

    if data is None:
        return _error(f"user not found: {target_id}")

    users = data if isinstance(data, list) else []
    for u in users:
        if u.get("id") == target_id:
            return _ok(_reduce_user(u))
    return _error(f"user not found: {target_id}")

def _reduce_task(data: dict) -> dict:
    return {
        "id": data.get("id"),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "priority": data.get("priority", 0),
        "due_date": data.get("due_date"),
        "done": data.get("done", False),
        "project_id": data.get("project_id"),
        "labels": [l.get("id") if isinstance(l, dict) else l
                    for l in (data.get("labels") or [])],
    }

def _reduce_project(data: dict) -> dict:
    return {
        "id": data.get("id"),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "parent_project_id": data.get("parent_project_id"),
    }

def _reduce_label(data: dict) -> dict:
    return {
        "id": data.get("id"),
        "title": data.get("title", ""),
        "description": data.get("description", ""),
        "color": data.get("hex_color") or data.get("color", ""),
    }

def _reduce_relation(data: dict) -> dict:
    return {
        "id": data.get("id"),
        "other_task_id": data.get("other_task_id"),
        "relation_kind": data.get("relation_kind", ""),
        "created_by": {
            "id": data.get("created_by", {}).get("id"),
            "username": data.get("created_by", {}).get("username", ""),
        } if isinstance(data.get("created_by"), dict) else None,
    }

def _reduce_user(data: dict) -> dict:
    return {
        "id": data.get("id"),
        "username": data.get("username", ""),
        "name": data.get("name", ""),
        "email": data.get("email", ""),
    }

def _extract_tasks(data: dict | list) -> list[dict]:
    """Extract task list from Vikunja response (handles various shapes)."""
    if isinstance(data, list):
        return [_reduce_task(t) for t in data]
    tasks = data.get("data") or data.get("tasks") or []
    if isinstance(tasks, list):
        return [_reduce_task(t) for t in tasks]
    return []

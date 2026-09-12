from __future__ import annotations

import hashlib
import json
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

from .db import DATABASE_PATH, connect, init_db, row_dict
from .schemas import BackupRestoreRequest, BatchReportRequest, CandidateCreate, CandidatePatch, CriterionCreate, CriterionPatch, EvidenceCopyRequest, EvidenceCreate, EvidencePatch, ImportRequest, ReviewCreate, TaskCreate, TaskPatch, TaskTemplateCreate, TaskTemplateInstantiate
from .services.evaluator import evaluate
from .services.backup import BackupError, export_backup, restore_backup
from .services.evidence_files import copy_evidence_file
from .services.importer import ImportErrorMessage, parse_run, risk_level
from .services.link_checker import LinkCheckError, check_external_url
from .services.reports import render_html, render_markdown
from .services.audit import audit_row, record_audit
from .services.security import FixedWindowLimiter


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Task Evidence Lab API", version="0.1.0", lifespan=lifespan)
configured_origins = [item.strip() for item in os.getenv("TASK_EVIDENCE_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=configured_origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
request_limiter = FixedWindowLimiter(limit=120, window_seconds=60)


def _security_headers(response: JSONResponse | Any) -> Any:
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response


@app.middleware("http")
async def local_security_middleware(request, call_next):
    is_api = request.url.path.startswith("/api/") and request.url.path != "/api/health"
    if is_api:
        expected_key = os.getenv("TASK_EVIDENCE_API_KEY", "").strip()
        if expected_key and not secrets.compare_digest(request.headers.get("X-API-Key", ""), expected_key):
            return _security_headers(JSONResponse(status_code=401, content={"detail": "缺少或无效的 API Key"}))
        try:
            configured_limit = int(os.getenv("TASK_EVIDENCE_RATE_LIMIT", "0") or "0")
        except ValueError:
            configured_limit = 0
        if configured_limit > 0:
            request_limiter.limit = configured_limit
            client_host = request.client.host if request.client else "unknown"
            key = f"{client_host}:{request.url.path}"
            if not request_limiter.allow(key):
                response = JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后重试"})
                response.headers["Retry-After"] = str(request_limiter.retry_after(key))
                return _security_headers(response)
    return _security_headers(await call_next(request))


@app.exception_handler(RequestValidationError)
async def request_validation_handler(_, exc: RequestValidationError) -> JSONResponse:
    errors = [{"loc": list(error.get("loc", [])), "msg": error.get("msg", "请求参数不合法"), "type": error.get("type", "validation_error")} for error in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": "请求参数校验失败", "errors": errors})


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_task(connection: sqlite3.Connection, task_id: int) -> dict:
    task = row_dict(connection.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone())
    if not task:
        raise HTTPException(404, "任务不存在")
    return task


def task_payload(connection: sqlite3.Connection, task_id: int) -> dict:
    task = get_task(connection, task_id)
    task["criteria"] = [dict(row) for row in connection.execute("SELECT * FROM acceptance_criteria WHERE task_id = ? ORDER BY id", (task_id,))]
    task["evidence"] = [dict(row) for row in connection.execute("SELECT * FROM evidence WHERE task_id = ? ORDER BY id DESC", (task_id,))]
    task["runs"] = [dict(row) for row in connection.execute("SELECT id, executor, model, started_at, finished_at, status, created_at FROM runs WHERE task_id = ? ORDER BY id DESC", (task_id,))]
    task["reviews"] = [dict(row) for row in connection.execute("SELECT * FROM reviews WHERE task_id = ? ORDER BY id DESC", (task_id,))]
    latest = connection.execute("SELECT * FROM evaluations WHERE task_id = ? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
    task["evaluation"] = dict(latest) if latest else None
    if task["evaluation"]:
        task["evaluation"]["basis"] = json.loads(task["evaluation"].pop("basis_json"))
    return task


def template_payload(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["criteria"] = json.loads(item.pop("criteria_json") or "[]")
    item["evidence_types"] = json.loads(item.pop("evidence_types_json") or "[]")
    return item


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "task-evidence-lab", "ai_enabled": False}


@app.get("/api/templates")
def list_templates() -> list[dict]:
    with connect() as connection:
        return [template_payload(row) for row in connection.execute("SELECT * FROM task_templates ORDER BY updated_at DESC, id DESC")]


@app.post("/api/templates", status_code=201)
def create_template(payload: TaskTemplateCreate) -> dict:
    timestamp = now()
    criteria = [item.strip()[:300] for item in payload.criteria if item.strip()]
    evidence_types = [item.strip()[:50] for item in payload.evidence_types if item.strip()]
    with connect() as connection:
        row = connection.execute(
            "INSERT INTO task_templates(name, description, priority, completion_basis, criteria_json, evidence_types_json, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *",
            (payload.name, payload.description, payload.priority, payload.completion_basis, json.dumps(criteria, ensure_ascii=False), json.dumps(evidence_types, ensure_ascii=False), timestamp, timestamp),
        ).fetchone()
        record_audit(connection, action="template.created", entity_type="template", entity_id=row["id"], detail={"name": payload.name})
        return template_payload(row)


@app.delete("/api/templates/{template_id}")
def delete_template(template_id: int) -> dict:
    with connect() as connection:
        row = connection.execute("SELECT * FROM task_templates WHERE id = ?", (template_id,)).fetchone()
        if not row:
            raise HTTPException(404, "任务模板不存在")
        record_audit(connection, action="template.deleted", entity_type="template", entity_id=template_id, detail={"name": row["name"]})
        connection.execute("DELETE FROM task_templates WHERE id = ?", (template_id,))
        return {"deleted": True, "template_id": template_id}


@app.post("/api/templates/{template_id}/instantiate", status_code=201)
def instantiate_template(template_id: int, payload: TaskTemplateInstantiate) -> dict:
    timestamp = now()
    with connect() as connection:
        template = connection.execute("SELECT * FROM task_templates WHERE id = ?", (template_id,)).fetchone()
        if not template:
            raise HTTPException(404, "任务模板不存在")
        criteria = json.loads(template["criteria_json"] or "[]")
        evidence_types = json.loads(template["evidence_types_json"] or "[]")
        title = (payload.title or template["name"]).strip()
        description = payload.description if payload.description is not None else template["description"]
        if not title:
            raise HTTPException(422, "实例任务标题不能为空")
        task_cursor = connection.execute(
            "INSERT INTO tasks(title, description, priority, completion_basis, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (title, description, template["priority"], template["completion_basis"], timestamp, timestamp),
        )
        task_id = task_cursor.lastrowid
        for criterion in criteria:
            connection.execute("INSERT INTO acceptance_criteria(task_id, title, required, status) VALUES (?, ?, 1, 'pending')", (task_id, criterion))
        for evidence_type in evidence_types:
            connection.execute("INSERT INTO evidence(task_id, title, evidence_type, content, source, created_at) VALUES (?, ?, ?, ?, 'template', ?)", (task_id, f"待补充：{evidence_type}", evidence_type, "由任务模板创建，待补充真实证据", timestamp))
        record_audit(connection, action="task.created", entity_type="task", entity_id=task_id, task_id=task_id, detail={"title": title, "template_id": template_id}, created_at=timestamp)
        record_audit(connection, action="template.instantiated", entity_type="template", entity_id=template_id, task_id=task_id, detail={"task_id": task_id}, created_at=timestamp)
        return task_payload(connection, task_id)


@app.get("/api/backup/export")
def backup_export() -> dict:
    with connect() as connection:
        return export_backup(connection)


@app.post("/api/backup/restore")
def backup_restore(payload: BackupRestoreRequest) -> dict:
    if not payload.replace:
        raise HTTPException(422, "恢复会替换当前本地数据，请显式确认 replace=true")
    with connect() as connection:
        try:
            restore_backup(connection, payload.backup)
        except (BackupError, sqlite3.Error, TypeError, ValueError) as exc:
            raise HTTPException(422, f"备份恢复失败，当前数据未改变：{exc}") from exc
    with connect() as connection:
        record_audit(connection, action="backup.restored", entity_type="backup", detail={"schema_version": payload.backup.get("schema_version")})
    return {"restored": True, "schema_version": payload.backup.get("schema_version")}


@app.get("/api/audit-log")
def audit_log(limit: int = Query(default=200, ge=1, le=500), task_id: int | None = Query(default=None)) -> list[dict]:
    with connect() as connection:
        if task_id is None:
            rows = connection.execute("SELECT id, task_id, action, entity_type, entity_id, detail_json, created_at FROM audit_log ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        else:
            rows = connection.execute("SELECT id, task_id, action, entity_type, entity_id, detail_json, created_at FROM audit_log WHERE task_id = ? ORDER BY id DESC LIMIT ?", (task_id, limit)).fetchall()
        return [audit_row(row) for row in rows]


@app.post("/api/tasks", status_code=201)
def create_task(payload: TaskCreate) -> dict:
    timestamp = now()
    with connect() as connection:
        cursor = connection.execute("INSERT INTO tasks(title, description, priority, due_at, completion_basis, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)", (payload.title, payload.description, payload.priority, payload.due_at.isoformat() if payload.due_at else None, payload.completion_basis, timestamp, timestamp))
        task_id = cursor.lastrowid
        for tag in payload.tags:
            connection.execute("INSERT INTO acceptance_criteria(task_id, title, required, status) VALUES (?, ?, 0, 'pending')", (task_id, f"标签：{tag[:80]}"))
        record_audit(connection, action="task.created", entity_type="task", entity_id=task_id, task_id=task_id, detail={"title": payload.title, "priority": payload.priority}, created_at=timestamp)
        return task_payload(connection, task_id)


@app.get("/api/tasks")
def list_tasks(
    include_archived: bool = False,
    status: str | None = Query(default=None),
    q: str | None = Query(default=None, max_length=160),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[dict]:
    with connect() as connection:
        clauses, params = [], []
        if not include_archived:
            clauses.append("status != 'archived'")
        if status:
            clauses.append("status = ?"); params.append(status)
        if q and q.strip():
            search = q.strip()
            if search.isascii():
                terms = [term.replace('"', '""') for term in search.split() if term]
                if terms:
                    clauses.append("tasks.id IN (SELECT rowid FROM tasks_fts WHERE tasks_fts MATCH ?)")
                    params.append(" ".join(f'"{term}"' for term in terms))
            else:
                search_like = f"%{search}%"
                clauses.append("(title LIKE ? OR description LIKE ?)"); params.extend([search_like, search_like])
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        return [dict(row) for row in connection.execute(
            f"SELECT tasks.*, (SELECT COUNT(*) FROM acceptance_criteria WHERE task_id = tasks.id) AS criteria_count, (SELECT COUNT(*) FROM evidence WHERE task_id = tasks.id) AS evidence_count FROM tasks{where} ORDER BY updated_at DESC, id DESC LIMIT ? OFFSET ?",
            [*params, limit, offset],
        )]


@app.get("/api/tasks/{task_id}")
def read_task(task_id: int) -> dict:
    with connect() as connection:
        return task_payload(connection, task_id)


@app.patch("/api/tasks/{task_id}")
def patch_task(task_id: int, payload: TaskPatch) -> dict:
    values = payload.model_dump(exclude_unset=True)
    with connect() as connection:
        task = get_task(connection, task_id)
        if values.get("status") == "completed":
            required = connection.execute("SELECT status FROM acceptance_criteria WHERE task_id = ? AND required = 1", (task_id,)).fetchall()
            if not required or any(row["status"] not in ("verified", "not_applicable") for row in required):
                raise HTTPException(422, "不能标记为 completed：所有必需验收项必须为 verified 或 not_applicable")
            if not values.get("completion_basis", task["completion_basis"]).strip():
                raise HTTPException(422, "不能标记为 completed：必须填写完成依据")
        if values.get("status") == "archived":
            values["archived_at"] = now()
        elif "status" in values:
            values["archived_at"] = None
        values["updated_at"] = now()
        assignments = ", ".join(f"{key} = ?" for key in values)
        params = [values[key].isoformat() if isinstance(values[key], datetime) else values[key] for key in values] + [task_id]
        connection.execute(f"UPDATE tasks SET {assignments} WHERE id = ?", params)
        action = "task.archived" if values.get("status") == "archived" else "task.updated"
        record_audit(connection, action=action, entity_type="task", entity_id=task_id, task_id=task_id, detail={key: value.isoformat() if isinstance(value, datetime) else value for key, value in values.items()})
        return task_payload(connection, task_id)


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int) -> dict:
    with connect() as connection:
        task = get_task(connection, task_id)
        record_audit(connection, action="task.deleted", entity_type="task", entity_id=task_id, task_id=task_id, detail={"title": task["title"]})
        connection.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return {"deleted": True, "task_id": task_id}


@app.post("/api/tasks/{task_id}/criteria", status_code=201)
def create_criterion(task_id: int, payload: CriterionCreate) -> dict:
    with connect() as connection:
        get_task(connection, task_id)
        row = connection.execute("INSERT INTO acceptance_criteria(task_id, title, required) VALUES (?, ?, ?) RETURNING *", (task_id, payload.title, int(payload.required))).fetchone()
        record_audit(connection, action="criterion.created", entity_type="criterion", entity_id=row["id"], task_id=task_id, detail={"title": payload.title, "required": payload.required})
        return dict(row)


@app.patch("/api/criteria/{criterion_id}")
def patch_criterion(criterion_id: int, payload: CriterionPatch) -> dict:
    values = payload.model_dump(exclude_unset=True)
    if "required" in values: values["required"] = int(values["required"])
    with connect() as connection:
        existing = connection.execute("SELECT * FROM acceptance_criteria WHERE id = ?", (criterion_id,)).fetchone()
        if not existing: raise HTTPException(404, "验收项不存在")
        if not values: return dict(existing)
        assignments = ", ".join(f"{key} = ?" for key in values)
        connection.execute(f"UPDATE acceptance_criteria SET {assignments} WHERE id = ?", [*values.values(), criterion_id])
        record_audit(connection, action="criterion.updated", entity_type="criterion", entity_id=criterion_id, task_id=existing["task_id"], detail=values)
        return dict(connection.execute("SELECT * FROM acceptance_criteria WHERE id = ?", (criterion_id,)).fetchone())


@app.post("/api/tasks/{task_id}/evidence", status_code=201)
def create_evidence(task_id: int, payload: EvidenceCreate) -> dict:
    with connect() as connection:
        get_task(connection, task_id)
        row = connection.execute("INSERT INTO evidence(task_id, title, evidence_type, content, file_path, external_url, source, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) RETURNING *", (task_id, payload.title, payload.evidence_type, payload.content, payload.file_path, payload.external_url, payload.source, now())).fetchone()
        record_audit(connection, action="evidence.created", entity_type="evidence", entity_id=row["id"], task_id=task_id, detail={"title": payload.title, "evidence_type": payload.evidence_type})
        return dict(row)


@app.get("/api/tasks/{task_id}/evidence")
def list_evidence(task_id: int) -> list[dict]:
    with connect() as connection:
        get_task(connection, task_id)
        return [dict(row) for row in connection.execute("SELECT * FROM evidence WHERE task_id = ? ORDER BY id DESC", (task_id,))]


@app.patch("/api/evidence/{evidence_id}")
def patch_evidence(evidence_id: int, payload: EvidencePatch) -> dict:
    values = payload.model_dump(exclude_unset=True)
    with connect() as connection:
        existing = connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone()
        if not existing: raise HTTPException(404, "证据不存在")
        if values:
            assignments = ", ".join(f"{key} = ?" for key in values)
            connection.execute(f"UPDATE evidence SET {assignments} WHERE id = ?", [*values.values(), evidence_id])
            record_audit(connection, action="evidence.updated", entity_type="evidence", entity_id=evidence_id, task_id=existing["task_id"], detail=values)
        return dict(connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone())


@app.post("/api/evidence/{evidence_id}/check-link")
def check_evidence_link(evidence_id: int) -> dict:
    with connect() as connection:
        evidence = row_dict(connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone())
        if not evidence:
            raise HTTPException(404, "证据不存在")
        if not evidence.get("external_url"):
            raise HTTPException(422, "该证据没有 external_url")
        try:
            result = check_external_url(evidence["external_url"])
        except LinkCheckError as exc:
            raise HTTPException(422, str(exc)) from exc
        connection.execute(
            "UPDATE evidence SET link_check_status = ?, link_checked_at = ?, link_status_code = ?, link_final_url = ?, link_error = ? WHERE id = ?",
            (result["status"], now(), result["status_code"], result["final_url"], result["error"], evidence_id),
        )
        record_audit(connection, action="evidence.link_checked", entity_type="evidence", entity_id=evidence_id, task_id=evidence["task_id"], detail={"status": result["status"], "status_code": result["status_code"], "final_url": result["final_url"], "error": result["error"]})
        updated = dict(connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone())
        updated["link_check"] = result
        return updated


@app.post("/api/evidence/{evidence_id}/copy")
def copy_evidence(evidence_id: int, payload: EvidenceCopyRequest) -> dict:
    with connect() as connection:
        evidence = row_dict(connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone())
        if not evidence:
            raise HTTPException(404, "证据不存在")
        try:
            local_path, size_bytes, sha256 = copy_evidence_file(DATABASE_PATH.parent, evidence_id, evidence["title"], payload.source_path)
        except FileNotFoundError as exc:
            raise HTTPException(422, f"源文件不存在：{exc}") from exc
        except IsADirectoryError as exc:
            raise HTTPException(422, f"源路径不是文件：{exc}") from exc
        except PermissionError as exc:
            raise HTTPException(422, f"没有读取源文件的权限：{exc}") from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        connection.execute("UPDATE evidence SET local_path = ?, size_bytes = ?, sha256 = ? WHERE id = ?", (local_path, size_bytes, sha256, evidence_id))
        record_audit(connection, action="evidence.file_copied", entity_type="evidence", entity_id=evidence_id, task_id=evidence["task_id"], detail={"local_path": local_path, "size_bytes": size_bytes, "sha256": sha256})
        return dict(connection.execute("SELECT * FROM evidence WHERE id = ?", (evidence_id,)).fetchone())


@app.get("/api/tasks/{task_id}/evidence/files")
def list_local_evidence_files(task_id: int) -> list[dict]:
    with connect() as connection:
        get_task(connection, task_id)
        return [dict(row) for row in connection.execute("SELECT id, title, local_path, size_bytes, sha256, created_at FROM evidence WHERE task_id = ? AND local_path IS NOT NULL ORDER BY id DESC", (task_id,))]


@app.post("/api/runs/import", status_code=201)
def import_run(payload: ImportRequest) -> dict:
    try:
        parsed = parse_run(payload.content, payload.format)
    except ImportErrorMessage as exc:
        raise HTTPException(422, str(exc)) from exc
    source_hash = hashlib.sha256(payload.content.encode("utf-8")).hexdigest()
    timestamp = now()
    with connect() as connection:
        get_task(connection, payload.task_id)
        if connection.execute("SELECT 1 FROM runs WHERE task_id = ? AND source_hash = ?", (payload.task_id, source_hash)).fetchone():
            raise HTTPException(409, "该运行记录已导入，重复内容被拒绝")
        try:
            run = connection.execute("INSERT INTO runs(task_id, executor, model, started_at, finished_at, status, raw_source, source_hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) RETURNING *", (payload.task_id, parsed.executor, parsed.model, parsed.started_at, parsed.finished_at, parsed.status, payload.content, source_hash, timestamp)).fetchone()
            run_id = run["id"]
            for item in parsed.steps:
                connection.execute("INSERT INTO run_steps(run_id, step_index, step_type, content, status) VALUES (?, ?, ?, ?, ?)", (run_id, int(item.get("index", 0)), str(item.get("type", "unknown"))[:50], str(item.get("content", ""))[:10000], str(item.get("status", "unknown"))[:50]))
            for item in parsed.tool_calls:
                connection.execute("INSERT INTO tool_calls(run_id, step_index, tool_name, input_json, output_summary, status, duration_ms, risk_level) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (run_id, item.get("index"), str(item.get("tool", "unknown"))[:100], json.dumps(item.get("input", {}), ensure_ascii=False)[:10000], str(item.get("output_summary", ""))[:10000], str(item.get("status", "unknown"))[:50], item.get("duration_ms"), risk_level(json.dumps(item.get("input", {}), ensure_ascii=False))))
            for item in parsed.changed_files:
                path = str(item.get("path", "unknown"))[:1000]
                connection.execute("INSERT INTO changed_files(run_id, path, change_type, additions, deletions, risk_level) VALUES (?, ?, ?, ?, ?, ?)", (run_id, path, str(item.get("change_type", "modified"))[:50], int(item.get("additions", 0) or 0), int(item.get("deletions", 0) or 0), risk_level(path)))
            for item in parsed.tests:
                connection.execute("INSERT INTO test_results(run_id, name, status, duration_ms, output_summary) VALUES (?, ?, ?, ?, ?)", (run_id, str(item.get("name", "unnamed"))[:300], str(item.get("status", "unknown"))[:50], item.get("duration_ms"), str(item.get("output_summary", ""))[:10000]))
            record_audit(connection, action="run.imported", entity_type="run", entity_id=run_id, task_id=payload.task_id, detail={"executor": parsed.executor, "status": parsed.status, "steps": len(parsed.steps), "tool_calls": len(parsed.tool_calls), "changed_files": len(parsed.changed_files), "tests": len(parsed.tests)}, created_at=timestamp)
            return {"id": run_id, "task_id": payload.task_id, "executor": parsed.executor, "steps": len(parsed.steps), "tool_calls": len(parsed.tool_calls), "changed_files": len(parsed.changed_files), "tests": len(parsed.tests), "message": "已导入；所有命令和脚本仅作为文本保存，未执行"}
        except (sqlite3.Error, TypeError, ValueError) as exc:
            raise HTTPException(422, f"运行记录导入失败，事务已回滚：{exc}") from exc


@app.get("/api/tasks/{task_id}/runs")
def list_runs(task_id: int) -> list[dict]:
    with connect() as connection:
        get_task(connection, task_id)
        return [dict(row) for row in connection.execute("SELECT * FROM runs WHERE task_id = ? ORDER BY id DESC", (task_id,))]


@app.get("/api/tasks/{task_id}/timeline")
def task_timeline(task_id: int) -> list[dict]:
    with connect() as connection:
        get_task(connection, task_id)
        events: list[dict] = []
        for row in connection.execute("SELECT id, title, evidence_type, verification_status, created_at FROM evidence WHERE task_id = ?", (task_id,)):
            events.append({"kind": "evidence", "id": row["id"], "title": row["title"], "status": row["verification_status"], "detail": row["evidence_type"], "occurred_at": row["created_at"]})
        for row in connection.execute("SELECT id, executor, status, created_at FROM runs WHERE task_id = ?", (task_id,)):
            events.append({"kind": "run", "id": row["id"], "title": f"运行记录：{row['executor']}", "status": row["status"], "detail": "导入内容仅展示，未执行", "occurred_at": row["created_at"]})
        for row in connection.execute("SELECT id, overall_score, verified, summary, created_at FROM evaluations WHERE task_id = ?", (task_id,)):
            events.append({"kind": "evaluation", "id": row["id"], "title": f"确定性评测：{row['overall_score']} 分", "status": "verified" if row["verified"] else "unverified", "detail": row["summary"], "occurred_at": row["created_at"]})
        for row in connection.execute("SELECT id, reviewer, content, created_at FROM reviews WHERE task_id = ?", (task_id,)):
            events.append({"kind": "review", "id": row["id"], "title": f"人工复盘：{row['reviewer']}", "status": "human_confirmed", "detail": row["content"], "occurred_at": row["created_at"]})
        return sorted(events, key=lambda event: event["occurred_at"])


@app.get("/api/tasks/{task_id}/audit-log")
def task_audit_log(task_id: int) -> list[dict]:
    with connect() as connection:
        get_task(connection, task_id)
        rows = connection.execute("SELECT id, task_id, action, entity_type, entity_id, detail_json, created_at FROM audit_log WHERE task_id = ? ORDER BY id DESC LIMIT 200", (task_id,)).fetchall()
        return [audit_row(row) for row in rows]


@app.get("/api/runs/{run_id}")
def read_run(run_id: int) -> dict:
    with connect() as connection:
        run = row_dict(connection.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone())
        if not run: raise HTTPException(404, "运行记录不存在")
        run["steps"] = [dict(row) for row in connection.execute("SELECT * FROM run_steps WHERE run_id = ? ORDER BY step_index", (run_id,))]
        run["tool_calls"] = [dict(row) for row in connection.execute("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY id", (run_id,))]
        run["changed_files"] = [dict(row) for row in connection.execute("SELECT * FROM changed_files WHERE run_id = ? ORDER BY id", (run_id,))]
        run["tests"] = [dict(row) for row in connection.execute("SELECT * FROM test_results WHERE run_id = ? ORDER BY id", (run_id,))]
        return run


def report_runs(connection: sqlite3.Connection, task_id: int) -> list[dict]:
    runs = [dict(row) for row in connection.execute("SELECT * FROM runs WHERE task_id = ? ORDER BY id", (task_id,))]
    for run in runs:
        run_id = run["id"]
        run["steps"] = [dict(row) for row in connection.execute("SELECT * FROM run_steps WHERE run_id = ? ORDER BY step_index", (run_id,))]
        run["tool_calls"] = [dict(row) for row in connection.execute("SELECT * FROM tool_calls WHERE run_id = ? ORDER BY id", (run_id,))]
        run["changed_files"] = [dict(row) for row in connection.execute("SELECT * FROM changed_files WHERE run_id = ? ORDER BY id", (run_id,))]
        run["tests"] = [dict(row) for row in connection.execute("SELECT * FROM test_results WHERE run_id = ? ORDER BY id", (run_id,))]
    return runs


@app.post("/api/tasks/{task_id}/evaluate")
def evaluate_task(task_id: int) -> dict:
    with connect() as connection:
        task = get_task(connection, task_id)
        criteria = [dict(row) for row in connection.execute("SELECT * FROM acceptance_criteria WHERE task_id = ?", (task_id,))]
        evidence = [dict(row) for row in connection.execute("SELECT * FROM evidence WHERE task_id = ?", (task_id,))]
        runs = [dict(row) for row in connection.execute("SELECT * FROM runs WHERE task_id = ?", (task_id,))]
        run_ids = [item["id"] for item in runs]
        for run in runs:
            run["tool_calls"] = [dict(row) for row in connection.execute("SELECT * FROM tool_calls WHERE run_id = ?", (run["id"],))]
        changed_files = [dict(row) for row in connection.execute(f"SELECT * FROM changed_files WHERE run_id IN ({','.join('?' for _ in run_ids) or 'NULL'})", run_ids)] if run_ids else []
        tests = [dict(row) for row in connection.execute(f"SELECT * FROM test_results WHERE run_id IN ({','.join('?' for _ in run_ids) or 'NULL'})", run_ids)] if run_ids else []
        result = evaluate(task, criteria, evidence, runs, changed_files, tests)
        connection.execute("INSERT INTO evaluations(task_id, completion_score, evidence_score, verification_score, execution_score, risk_score, overall_score, verified, human_confirmed, summary, basis_json, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (task_id, result["completion_score"], result["evidence_score"], result["verification_score"], result["execution_score"], result["risk_score"], result["overall_score"], int(result["verified"]), int(result["human_confirmed"]), result["summary"], json.dumps(result["basis"], ensure_ascii=False), now()))
        record_audit(connection, action="evaluation.created", entity_type="evaluation", task_id=task_id, detail={"overall_score": result["overall_score"], "verified": result["verified"]})
        return result


@app.get("/api/tasks/{task_id}/evaluation")
def latest_evaluation(task_id: int) -> dict:
    with connect() as connection:
        get_task(connection, task_id)
        row = connection.execute("SELECT * FROM evaluations WHERE task_id = ? ORDER BY id DESC LIMIT 1", (task_id,)).fetchone()
        if not row: raise HTTPException(404, "尚未运行评测")
        result = dict(row); result["basis"] = json.loads(result.pop("basis_json")); return result


@app.post("/api/tasks/compare")
def compare_tasks(task_ids: list[int]) -> list[dict]:
    if len(task_ids) != 2: raise HTTPException(422, "一次只能比较两个任务")
    with connect() as connection:
        result = []
        for task_id in task_ids:
            task = task_payload(connection, task_id)
            evaluation = task["evaluation"] or {}
            runs = [dict(row) for row in connection.execute("SELECT * FROM runs WHERE task_id = ? ORDER BY id", (task_id,))]
            run_ids = [run["id"] for run in runs]
            tests = [dict(row) for row in connection.execute(f"SELECT * FROM test_results WHERE run_id IN ({','.join('?' for _ in run_ids) or 'NULL'})", run_ids)] if run_ids else []
            tool_calls = [dict(row) for row in connection.execute(f"SELECT * FROM tool_calls WHERE run_id IN ({','.join('?' for _ in run_ids) or 'NULL'})", run_ids)] if run_ids else []
            changed_files = [dict(row) for row in connection.execute(f"SELECT * FROM changed_files WHERE run_id IN ({','.join('?' for _ in run_ids) or 'NULL'})", run_ids)] if run_ids else []
            duration_seconds = 0
            run_breakdown = []
            for run in runs:
                run_tests = [dict(row) for row in connection.execute("SELECT * FROM test_results WHERE run_id = ?", (run["id"],))]
                run_tools = [dict(row) for row in connection.execute("SELECT * FROM tool_calls WHERE run_id = ?", (run["id"],))]
                run_files = [dict(row) for row in connection.execute("SELECT * FROM changed_files WHERE run_id = ?", (run["id"],))]
                run_duration = 0
                if run["started_at"] and run["finished_at"]:
                    try:
                        run_duration = round((datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["started_at"])).total_seconds())
                    except ValueError:
                        run_duration = 0
                run_passed = sum(item["status"].lower() in ("passed", "pass", "success") for item in run_tests)
                run_breakdown.append({
                    "id": run["id"], "executor": run["executor"], "model": run["model"], "status": run["status"],
                    "duration_seconds": run_duration, "tool_calls": len(run_tools),
                    "failed_tool_calls": sum(item["status"].lower() in ("failed", "error") for item in run_tools),
                    "tests": {"total": len(run_tests), "passed": run_passed, "skipped": sum(item["status"].lower() in ("skipped", "skip") for item in run_tests), "failed": sum(item["status"].lower() in ("failed", "fail", "error") for item in run_tests)},
                    "changed_files": len(run_files), "risk_flags": sorted({item["path"] for item in run_files if item["risk_level"] != "none"}),
                })
            for run in runs:
                if run["started_at"] and run["finished_at"]:
                    try:
                        duration_seconds += round((datetime.fromisoformat(run["finished_at"]) - datetime.fromisoformat(run["started_at"])).total_seconds())
                    except ValueError:
                        pass
            passed_tests = sum(item["status"].lower() in ("passed", "pass", "success") for item in tests)
            unfinished = [item["title"] for item in task["criteria"] if item["status"] not in ("verified", "not_applicable")]
            risk_flags = sorted({item["path"] for item in changed_files if item["risk_level"] != "none"})
            result.append({"id": task_id, "title": task["title"], "status": task["status"], "evidence_count": len(task["evidence"]), "confirmed_evidence": sum(item["verification_status"] == "confirmed" for item in task["evidence"]), "evaluation": evaluation, "runs": len(runs), "duration_seconds": duration_seconds, "tool_calls": len(tool_calls), "test_pass_rate": round(passed_tests / len(tests), 2) if tests else None, "risk_flags": risk_flags, "unfinished_criteria": unfinished, "run_breakdown": run_breakdown})
        return result


@app.post("/api/tasks/{task_id}/review", status_code=201)
def create_review(task_id: int, payload: ReviewCreate) -> dict:
    with connect() as connection:
        get_task(connection, task_id)
        row = connection.execute("INSERT INTO reviews(task_id, content, reviewer, created_at) VALUES (?, ?, ?, ?) RETURNING *", (task_id, payload.content, payload.reviewer, now())).fetchone()
        record_audit(connection, action="review.created", entity_type="review", entity_id=row["id"], task_id=task_id, detail={"reviewer": payload.reviewer})
        return dict(row)


@app.get("/api/tasks/{task_id}/report/markdown", response_class=PlainTextResponse)
def markdown_report(task_id: int) -> str:
    with connect() as connection:
        task = task_payload(connection, task_id)
        return render_markdown(task, task["criteria"], task["evidence"], task["evaluation"], task["reviews"], report_runs(connection, task_id))


@app.get("/api/tasks/{task_id}/report/html", response_class=HTMLResponse)
def html_report(task_id: int) -> str:
    with connect() as connection:
        task = task_payload(connection, task_id)
        return render_html(task, task["criteria"], task["evidence"], task["evaluation"], task["reviews"], report_runs(connection, task_id))


@app.get("/api/tasks/{task_id}/report/json")
def json_report(task_id: int) -> dict:
    with connect() as connection:
        return task_payload(connection, task_id)


@app.post("/api/reports/batch", response_class=PlainTextResponse)
def batch_markdown_report(payload: BatchReportRequest) -> str:
    if len(set(payload.task_ids)) != len(payload.task_ids):
        raise HTTPException(422, "批量报告中的任务不能重复")
    with connect() as connection:
        reports = []
        for task_id in payload.task_ids:
            task = task_payload(connection, task_id)
            reports.append(render_markdown(task, task["criteria"], task["evidence"], task["evaluation"], task["reviews"], report_runs(connection, task_id)))
    return PlainTextResponse("# Task Evidence Lab 批量复盘报告\n\n" + "\n\n---\n\n".join(reports), media_type="text/markdown")


@app.get("/api/memory-candidates")
def list_candidates(status: str | None = None) -> list[dict]:
    with connect() as connection:
        if status: return [dict(row) for row in connection.execute("SELECT * FROM memory_candidates WHERE status = ? ORDER BY id DESC", (status,))]
        return [dict(row) for row in connection.execute("SELECT * FROM memory_candidates ORDER BY id DESC")]


@app.post("/api/memory-candidates", status_code=201)
def create_candidate(payload: CandidateCreate) -> dict:
    with connect() as connection:
        if payload.task_id: get_task(connection, payload.task_id)
        row = connection.execute("INSERT INTO memory_candidates(task_id, title, content, source_evidence, target_type, created_at) VALUES (?, ?, ?, ?, ?, ?) RETURNING *", (payload.task_id, payload.title, payload.content, payload.source_evidence, payload.target_type, now())).fetchone()
        return dict(row)


@app.patch("/api/memory-candidates/{candidate_id}")
def patch_candidate(candidate_id: int, payload: CandidatePatch) -> dict:
    values = payload.model_dump(exclude_unset=True)
    with connect() as connection:
        existing = connection.execute("SELECT * FROM memory_candidates WHERE id = ?", (candidate_id,)).fetchone()
        if not existing: raise HTTPException(404, "经验候选不存在")
        if values:
            assignments = ", ".join(f"{key} = ?" for key in values)
            connection.execute(f"UPDATE memory_candidates SET {assignments} WHERE id = ?", [*values.values(), candidate_id])
        return dict(connection.execute("SELECT * FROM memory_candidates WHERE id = ?", (candidate_id,)).fetchone())


@app.post("/api/memory-candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: int) -> dict:
    return patch_candidate(candidate_id, CandidatePatch(status="approved"))


@app.post("/api/memory-candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: int) -> dict:
    return patch_candidate(candidate_id, CandidatePatch(status="rejected"))

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

TEST_DB = Path(tempfile.gettempdir()) / "task-evidence-lab-test.db"
if TEST_DB.exists():
    TEST_DB.unlink()
os.environ["DATABASE_PATH"] = str(TEST_DB)

from fastapi.testclient import TestClient

from app.main import app


def test_health_and_task_lifecycle() -> None:
    with TestClient(app) as client:
        assert client.get("/api/health").json()["status"] == "ok"
        task = client.post("/api/tasks", json={"title": "诊断报告接口", "description": "完成后端和前端链路", "completion_basis": "待人工填写"}).json()
        task_id = task["id"]
        criterion = client.post(f"/api/tasks/{task_id}/criteria", json={"title": "后端接口可用", "required": True}).json()
        assert criterion["status"] == "pending"
        blocked = client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
        assert blocked.status_code == 422
        assert client.patch(f"/api/criteria/{criterion['id']}", json={"status": "verified"}).status_code == 200
        evidence = client.post(f"/api/tasks/{task_id}/evidence", json={"title": "后端测试输出", "evidence_type": "测试输出", "content": "pytest passed"}).json()
        assert evidence["verification_status"] == "unreviewed"
        assert client.patch(f"/api/evidence/{evidence['id']}", json={"verification_status": "confirmed"}).status_code == 200
        completed = client.patch(f"/api/tasks/{task_id}", json={"status": "completed"})
        assert completed.status_code == 200
        assert completed.json()["status"] == "completed"


def test_import_is_parse_only_and_duplicate_is_rejected() -> None:
    content = json.dumps({
        "executor": "manual", "steps": [{"index": 1, "type": "command", "content": "Remove-Item -Recurse C:\\data", "status": "success"}],
        "tool_calls": [{"index": 1, "tool": "shell", "input": {"command": "do not run"}, "status": "success"}],
        "changed_files": [{"path": "../outside.txt", "change_type": "modified"}],
        "tests": [{"name": "test_safe", "status": "passed", "duration_ms": 3}],
    })
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "导入安全记录"}).json()["id"]
        imported = client.post("/api/runs/import", json={"task_id": task_id, "content": content, "format": "json"})
        assert imported.status_code == 201
        assert "未执行" in imported.json()["message"]
        run = client.get(f"/api/tasks/{task_id}/runs").json()[0]
        detail = client.get(f"/api/runs/{run['id']}").json()
        assert detail["steps"][0]["content"].startswith("Remove-Item")
        assert detail["changed_files"][0]["risk_level"] == "high"
        duplicate = client.post("/api/runs/import", json={"task_id": task_id, "content": content, "format": "json"})
        assert duplicate.status_code == 409


def test_invalid_import_rolls_back_and_evaluation_has_basis() -> None:
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "评测回滚任务"}).json()["id"]
        before = len(client.get(f"/api/tasks/{task_id}/runs").json())
        invalid = client.post("/api/runs/import", json={"task_id": task_id, "content": "{bad", "format": "json"})
        assert invalid.status_code == 422
        assert len(client.get(f"/api/tasks/{task_id}/runs").json()) == before
        result = client.post(f"/api/tasks/{task_id}/evaluate").json()
        assert "basis" in result
        assert "missing" in result["basis"]
        report = client.get(f"/api/tasks/{task_id}/report/markdown")
        assert report.status_code == 200
        assert "评测结果" in report.text


def test_compare_includes_run_metrics_and_unfinished_criteria() -> None:
    run_content = json.dumps({
        "executor": "manual",
        "started_at": "2026-09-12T10:00:00+08:00",
        "finished_at": "2026-09-12T10:02:00+08:00",
        "tool_calls": [{"index": 1, "tool": "powershell", "input": {"command": "npm run test"}, "status": "success", "duration_ms": 40}],
        "changed_files": [{"path": ".env.example", "change_type": "modified", "additions": 1, "deletions": 0}],
        "tests": [{"name": "test_one", "status": "passed", "duration_ms": 20}, {"name": "test_two", "status": "failed", "duration_ms": 30}],
    })
    with TestClient(app) as client:
        first = client.post("/api/tasks", json={"title": "对比任务 A", "description": "A"}).json()
        second = client.post("/api/tasks", json={"title": "对比任务 B", "description": "B"}).json()
        client.post(f"/api/tasks/{first['id']}/criteria", json={"title": "尚未完成的验收项", "required": True})
        client.post("/api/runs/import", json={"task_id": first["id"], "content": run_content, "format": "json"})
        response = client.post("/api/tasks/compare", json=[first["id"], second["id"]])
        assert response.status_code == 200
        compared = response.json()[0]
        assert compared["test_pass_rate"] == 0.5
        assert compared["tool_calls"] == 1
        assert compared["duration_seconds"] == 120
        assert compared["risk_flags"] == [".env.example"]
        assert compared["unfinished_criteria"] == ["尚未完成的验收项"]


def test_task_timeline_aggregates_evidence_runs_evaluation_and_review() -> None:
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "时间线任务", "description": "验证时间线"}).json()["id"]
        client.post(f"/api/tasks/{task_id}/evidence", json={"title": "截图", "evidence_type": "截图", "content": "manual"})
        client.post("/api/runs/import", json={"task_id": task_id, "content": json.dumps({"steps": [], "tests": []}), "format": "json"})
        client.post(f"/api/tasks/{task_id}/evaluate")
        client.post(f"/api/tasks/{task_id}/review", json={"content": "人工确认仍需补充端到端验证", "reviewer": "reviewer"})
        response = client.get(f"/api/tasks/{task_id}/timeline")
        assert response.status_code == 200
        events = response.json()
        assert {event["kind"] for event in events} == {"evidence", "run", "evaluation", "review"}
        assert all(events[index]["occurred_at"] <= events[index + 1]["occurred_at"] for index in range(len(events) - 1))


def test_archive_and_delete_are_explicit_single_task_operations() -> None:
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "可归档任务"}).json()["id"]
        archived = client.patch(f"/api/tasks/{task_id}", json={"status": "archived"})
        assert archived.status_code == 200
        assert archived.json()["status"] == "archived"
        assert archived.json()["archived_at"]
        assert all(task["id"] != task_id for task in client.get("/api/tasks").json())
        deleted = client.delete(f"/api/tasks/{task_id}")
        assert deleted.status_code == 200
        assert client.get(f"/api/tasks/{task_id}").status_code == 404


def test_compare_contains_per_run_breakdown() -> None:
    run_content = json.dumps({
        "executor": "codex", "started_at": "2026-09-12T10:00:00+08:00", "finished_at": "2026-09-12T10:01:30+08:00",
        "tool_calls": [{"index": 1, "tool": "read_file", "status": "success"}, {"index": 2, "tool": "shell", "status": "failed"}],
        "changed_files": [{"path": "src/a.py", "change_type": "modified", "additions": 4, "deletions": 1}],
        "tests": [{"name": "a", "status": "passed", "duration_ms": 12}, {"name": "b", "status": "skipped", "duration_ms": 0}],
    })
    with TestClient(app) as client:
        left = client.post("/api/tasks", json={"title": "运行明细 A"}).json()["id"]
        right = client.post("/api/tasks", json={"title": "运行明细 B"}).json()["id"]
        client.post("/api/runs/import", json={"task_id": left, "content": run_content, "format": "json"})
        response = client.post("/api/tasks/compare", json=[left, right])
        breakdown = response.json()[0]["run_breakdown"]
        assert breakdown[0]["executor"] == "codex"
        assert breakdown[0]["duration_seconds"] == 90
        assert breakdown[0]["tool_calls"] == 2
        assert breakdown[0]["failed_tool_calls"] == 1
        assert breakdown[0]["tests"] == {"total": 2, "passed": 1, "skipped": 1, "failed": 0}
        assert breakdown[0]["changed_files"] == 1


def test_copy_file_evidence_to_local_directory_records_hash(tmp_path: Path) -> None:
    source = tmp_path / "build-result.txt"
    source.write_text("verified build output\n", encoding="utf-8")
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "文件证据任务"}).json()["id"]
        evidence_id = client.post(f"/api/tasks/{task_id}/evidence", json={"title": "构建输出", "evidence_type": "测试输出"}).json()["id"]
        copied = client.post(f"/api/evidence/{evidence_id}/copy", json={"source_path": str(source)})
        assert copied.status_code == 200
        body = copied.json()
        assert body["local_path"]
        assert body["size_bytes"] == source.stat().st_size
        assert len(body["sha256"]) == 64
        local_path = Path(body["local_path"])
        assert local_path.is_file()
        assert local_path.read_text(encoding="utf-8") == source.read_text(encoding="utf-8")
        listed = client.get(f"/api/tasks/{task_id}/evidence/files").json()
        assert listed[0]["id"] == evidence_id


def test_backup_export_contains_version_and_related_tables() -> None:
    with TestClient(app) as client:
        task = client.post("/api/tasks", json={"title": "备份导出任务"}).json()
        client.post(f"/api/tasks/{task['id']}/criteria", json={"title": "可恢复"})
        response = client.get("/api/backup/export")

        assert response.status_code == 200
        backup = response.json()
        assert backup["schema_version"] == 1
        assert backup["tables"]["tasks"][-1]["title"] == "备份导出任务"
        assert backup["tables"]["acceptance_criteria"][-1]["task_id"] == task["id"]


def test_backup_restore_replaces_database_and_preserves_relationships() -> None:
    with TestClient(app) as client:
        source = client.post("/api/tasks", json={"title": "恢复源任务"}).json()
        criterion = client.post(f"/api/tasks/{source['id']}/criteria", json={"title": "恢复验收项"}).json()
        backup = client.get("/api/backup/export").json()
        transient = client.post("/api/tasks", json={"title": "恢复前临时任务"}).json()

        response = client.post("/api/backup/restore", json={"backup": backup, "replace": True})

        assert response.status_code == 200
        restored = client.get(f"/api/tasks/{source['id']}").json()
        assert restored["title"] == "恢复源任务"
        assert restored["criteria"][0]["id"] == criterion["id"]
        assert client.get(f"/api/tasks/{transient['id']}").status_code == 404


def test_link_check_rejects_private_destination_before_network_request() -> None:
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "链接安全任务"}).json()["id"]
        evidence_id = client.post(
            f"/api/tasks/{task_id}/evidence",
            json={"title": "本地链接", "evidence_type": "网页链接", "external_url": "http://127.0.0.1/api/health"},
        ).json()["id"]

        response = client.post(f"/api/evidence/{evidence_id}/check-link")

        assert response.status_code == 422
        assert "本机" in response.json()["detail"]


def test_schema_status_reports_current_version() -> None:
    from app.db import connect
    from app.migrations import schema_status

    with TestClient(app):
        with connect() as connection:
            status = schema_status(connection)

    assert status == {"current_version": 4, "latest_version": 4, "ready": True}


def test_audit_log_tracks_task_and_evidence_changes() -> None:
    with TestClient(app) as client:
        task = client.post("/api/tasks", json={"title": "审计任务"}).json()
        evidence = client.post(
            f"/api/tasks/{task['id']}/evidence",
            json={"title": "审计证据", "evidence_type": "人工说明"},
        ).json()
        client.patch(f"/api/evidence/{evidence['id']}", json={"verification_status": "confirmed"})

        response = client.get(f"/api/tasks/{task['id']}/audit-log")

        assert response.status_code == 200
        entries = response.json()
        assert {entry["action"] for entry in entries} >= {
            "task.created",
            "evidence.created",
            "evidence.updated",
        }
        updated = next(entry for entry in entries if entry["action"] == "evidence.updated")
        assert updated["detail"]["verification_status"] == "confirmed"


def test_global_audit_log_keeps_delete_history() -> None:
    with TestClient(app) as client:
        task = client.post("/api/tasks", json={"title": "待删除审计任务"}).json()
        task_id = task["id"]
        assert client.delete(f"/api/tasks/{task_id}").status_code == 200

        response = client.get("/api/audit-log?limit=20")

        assert response.status_code == 200
        deleted = next(entry for entry in response.json() if entry["action"] == "task.deleted" and entry["entity_id"] == task_id)
        assert deleted["task_id"] is None


def test_task_template_can_be_created_listed_and_instantiated() -> None:
    with TestClient(app) as client:
        template = client.post(
            "/api/templates",
            json={
                "name": "开发交付复盘",
                "description": "记录实现、验证与交付依据",
                "priority": "high",
                "completion_basis": "人工确认验收项和证据",
                "criteria": ["功能已实现", "自动化测试已通过"],
                "evidence_types": ["测试输出", "Git diff"],
            },
        )

        assert template.status_code == 201
        template_id = template.json()["id"]
        listed = client.get("/api/templates").json()
        assert listed[-1]["name"] == "开发交付复盘"

        instantiated = client.post(f"/api/templates/{template_id}/instantiate", json={"title": "本次功能交付"})

        assert instantiated.status_code == 201
        task = instantiated.json()
        assert task["title"] == "本次功能交付"
        assert [item["title"] for item in task["criteria"]] == ["功能已实现", "自动化测试已通过"]
        assert [item["evidence_type"] for item in task["evidence"]] == ["Git diff", "测试输出"]


def test_batch_report_contains_each_selected_task() -> None:
    with TestClient(app) as client:
        first = client.post("/api/tasks", json={"title": "批量报告任务 A"}).json()
        second = client.post("/api/tasks", json={"title": "批量报告任务 B"}).json()

        response = client.post("/api/reports/batch", json={"task_ids": [first["id"], second["id"]]})

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/markdown")
        assert "# Task Evidence Lab 批量复盘报告" in response.text
        assert "批量报告任务 A" in response.text
        assert "批量报告任务 B" in response.text


def test_task_list_supports_server_side_search() -> None:
    with TestClient(app) as client:
        client.post("/api/tasks", json={"title": "搜索命中任务", "description": "包含可检索关键词"})
        client.post("/api/tasks", json={"title": "其他任务", "description": "无关内容"})

        response = client.get("/api/tasks", params={"q": "可检索关键词"})

        assert response.status_code == 200
        assert [task["title"] for task in response.json()] == ["搜索命中任务"]


def test_sqlite_connection_enables_local_concurrency_pragmas() -> None:
    from app.db import connect

    with connect() as connection:
        journal_mode = connection.execute("PRAGMA journal_mode").fetchone()[0]
        busy_timeout = connection.execute("PRAGMA busy_timeout").fetchone()[0]
        synchronous = connection.execute("PRAGMA synchronous").fetchone()[0]

    assert journal_mode.lower() == "wal"
    assert busy_timeout >= 5000
    assert synchronous == 1


def test_validation_errors_have_stable_client_shape() -> None:
    with TestClient(app) as client:
        response = client.post("/api/tasks", json={"title": ""})

        assert response.status_code == 422
        payload = response.json()
        assert payload["detail"] == "请求参数校验失败"
        assert payload["errors"][0]["loc"][-1] == "title"


def test_optional_api_key_and_security_headers(monkeypatch) -> None:
    monkeypatch.setenv("TASK_EVIDENCE_API_KEY", "local-secret")
    with TestClient(app) as client:
        unauthorized = client.get("/api/tasks")
        assert unauthorized.status_code == 401
        assert client.get("/api/tasks", headers={"X-API-Key": "local-secret"}).status_code == 200
        response = client.get("/api/health")
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["x-frame-options"] == "DENY"
    monkeypatch.delenv("TASK_EVIDENCE_API_KEY")


def test_task_search_supports_fts_backed_pagination() -> None:
    from app.db import connect

    with TestClient(app) as client:
        for index in range(3):
            client.post("/api/tasks", json={"title": f"FTS 性能任务 {index}", "description": "可搜索内容"})

        response = client.get("/api/tasks", params={"q": "FTS", "limit": 2, "offset": 1})

        assert response.status_code == 200
        assert len(response.json()) == 2
        assert response.json()[0]["title"] == "FTS 性能任务 1"
        with connect() as connection:
            assert connection.execute("SELECT 1 FROM sqlite_master WHERE name = 'tasks_fts'").fetchone() is not None


def test_task_search_index_tracks_updates_deletes_and_quoted_input() -> None:
    with TestClient(app) as client:
        first = client.post("/api/tasks", json={"title": "可更新搜索目标"}).json()
        second = client.post("/api/tasks", json={"title": "待删除搜索目标"}).json()
        assert client.patch(f"/api/tasks/{first['id']}", json={"title": "更新后的索引目标"}).status_code == 200
        assert client.delete(f"/api/tasks/{second['id']}").status_code == 200

        assert [item["id"] for item in client.get("/api/tasks", params={"q": "更新后的"}).json()] == [first["id"]]
        assert client.get("/api/tasks", params={"q": '"'}).status_code == 200
        assert client.get("/api/tasks", params={"q": "待删除"}).json() == []


def test_markdown_report_contains_traceability_details() -> None:
    run_content = json.dumps({
        "executor": "reporter",
        "steps": [{"index": 1, "type": "test", "content": "运行 pytest", "status": "success"}],
        "tool_calls": [{"index": 1, "tool": "pytest", "input": {"command": "pytest -q"}, "status": "success"}],
        "changed_files": [{"path": "src/report.py", "change_type": "modified", "additions": 3, "deletions": 1}],
        "tests": [{"name": "report_test", "status": "passed", "duration_ms": 12}],
    })
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "增强报告任务", "description": "报告可回溯"}).json()["id"]
        client.post(f"/api/tasks/{task_id}/evidence", json={"title": "网页证据", "evidence_type": "网页链接", "external_url": "https://example.com", "content": "公开来源"})
        client.post("/api/runs/import", json={"task_id": task_id, "content": run_content, "format": "json"})
        report = client.get(f"/api/tasks/{task_id}/report/markdown")

        assert report.status_code == 200
        assert "## 证据核验" in report.text
        assert "## 运行明细" in report.text
        assert "pytest" in report.text
        assert "src/report.py" in report.text


def test_html_report_is_print_ready_and_escapes_task_text() -> None:
    with TestClient(app) as client:
        task_id = client.post("/api/tasks", json={"title": "HTML <报告>", "description": "<script>不执行</script>"}).json()["id"]
        response = client.get(f"/api/tasks/{task_id}/report/html")

        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/html")
        assert "@media print" in response.text
        assert "&lt;script&gt;不执行&lt;/script&gt;" in response.text

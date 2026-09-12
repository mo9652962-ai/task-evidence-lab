from __future__ import annotations

import json
import re
from dataclasses import dataclass


MAX_ITEMS = 2000
MAX_TEXT = 10000


@dataclass
class ParsedRun:
    executor: str
    model: str | None
    started_at: str | None
    finished_at: str | None
    status: str
    steps: list[dict]
    tool_calls: list[dict]
    changed_files: list[dict]
    tests: list[dict]


class ImportErrorMessage(ValueError):
    pass


def _text(value: object, limit: int = MAX_TEXT) -> str:
    if value is None:
        return ""
    text = str(value)
    if len(text) > limit:
        raise ImportErrorMessage(f"文本字段超过 {limit} 个字符")
    return text


def _list(value: object, name: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ImportErrorMessage(f"字段 {name} 必须是数组")
    if len(value) > MAX_ITEMS:
        raise ImportErrorMessage(f"字段 {name} 最多允许 {MAX_ITEMS} 项")
    return value


def _parse_json(content: str) -> dict:
    try:
        data = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ImportErrorMessage(f"JSON 格式错误：第 {exc.lineno} 行第 {exc.colno} 列") from exc
    if not isinstance(data, dict):
        raise ImportErrorMessage("JSON 根节点必须是对象")
    return data


def _parse_jsonl(content: str) -> dict:
    records = []
    for line_no, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ImportErrorMessage(f"JSONL 第 {line_no} 行格式错误：{exc.msg}") from exc
    if not records:
        raise ImportErrorMessage("JSONL 没有有效记录")
    if not all(isinstance(item, dict) for item in records):
        raise ImportErrorMessage("JSONL 每行必须是对象")
    base = records[0].copy()
    for key in ("steps", "tool_calls", "changed_files", "tests"):
        base[key] = [item for record in records for item in record.get(key, [])] if any(key in record for record in records) else []
    return base


def _parse_markdown(content: str) -> dict:
    def section(name: str) -> str:
        match = re.search(rf"^##\s+{re.escape(name)}\s*$([\s\S]*?)(?=^##\s+|\Z)", content, re.MULTILINE)
        return match.group(1).strip() if match else ""

    return {
        "executor": "markdown",
        "status": "imported",
        "steps": [{"index": 1, "type": "markdown", "content": section("执行过程") or content[:MAX_TEXT], "status": "imported"}],
        "tests": [], "tool_calls": [], "changed_files": [],
        "final_output": section("最终结论") or section("结论"),
    }


def parse_run(content: str, file_format: str = "auto") -> ParsedRun:
    if len(content.encode("utf-8")) > 1_000_000:
        raise ImportErrorMessage("导入内容超过 1 MB 限制")
    stripped = content.lstrip()
    if file_format == "markdown" or (file_format == "auto" and stripped.startswith("#") and not stripped.startswith("#{")):
        data = _parse_markdown(content)
    elif file_format == "jsonl" or (file_format == "auto" and "\n" in content and all(not line.strip() or line.lstrip().startswith(("{", "[")) for line in content.splitlines())):
        data = _parse_jsonl(content)
    else:
        data = _parse_json(content)

    def records(name: str) -> list[dict]:
        values = _list(data.get(name), name)
        if not all(isinstance(item, dict) for item in values):
            raise ImportErrorMessage(f"字段 {name} 的每一项必须是对象")
        return values

    return ParsedRun(
        executor=_text(data.get("executor", "imported"), 100), model=_text(data.get("model"), 100) or None,
        started_at=_text(data.get("started_at"), 100) or None, finished_at=_text(data.get("finished_at"), 100) or None,
        status=_text(data.get("status", "imported"), 50), steps=records("steps"), tool_calls=records("tool_calls"),
        changed_files=records("changed_files"), tests=records("tests"),
    )


def risk_level(path: str) -> str:
    lowered = path.lower().replace("\\", "/")
    if any(token in lowered for token in (".env", "secret", "credential", "password", "token", ".ssh/")):
        return "high"
    if lowered.startswith("../") or lowered.startswith("/") or ":/" in lowered:
        return "high"
    if any(token in lowered for token in ("delete", "remove-item", "powershell", "cmd ", "python ", "npm run", "curl ", "http://", "https://", "reset --hard", "git reflog", "shell")):
        return "medium"
    return "none"

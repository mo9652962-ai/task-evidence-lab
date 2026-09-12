from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


TaskStatus = Literal["draft", "in_progress", "blocked", "partially_verified", "completed", "archived"]
CriterionStatus = Literal["pending", "in_progress", "verified", "failed", "not_applicable"]
EvidenceStatus = Literal["unreviewed", "confirmed", "rejected", "outdated"]


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=6000)
    priority: Literal["low", "medium", "high"] = "medium"
    due_at: datetime | None = None
    completion_basis: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=6000)
    status: TaskStatus | None = None
    priority: Literal["low", "medium", "high"] | None = None
    due_at: datetime | None = None
    completion_basis: str | None = Field(default=None, max_length=4000)


class TaskTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=6000)
    priority: Literal["low", "medium", "high"] = "medium"
    completion_basis: str = Field(default="", max_length=4000)
    criteria: list[str] = Field(default_factory=list, max_length=30)
    evidence_types: list[str] = Field(default_factory=list, max_length=20)


class TaskTemplateInstantiate(BaseModel):
    title: str | None = Field(default=None, max_length=160)
    description: str | None = Field(default=None, max_length=6000)


class CriterionCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    required: bool = True


class CriterionPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    required: bool | None = None
    status: CriterionStatus | None = None
    note: str | None = Field(default=None, max_length=2000)


class EvidenceCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    evidence_type: str = Field(min_length=1, max_length=50)
    content: str = Field(default="", max_length=10000)
    file_path: str | None = Field(default=None, max_length=1000)
    external_url: str | None = Field(default=None, max_length=2000)
    source: str = Field(default="manual", max_length=100)


class EvidencePatch(BaseModel):
    verification_status: EvidenceStatus | None = None
    review_note: str | None = Field(default=None, max_length=2000)
    content: str | None = Field(default=None, max_length=10000)


class EvidenceCopyRequest(BaseModel):
    source_path: str = Field(min_length=1, max_length=1000)


class ImportRequest(BaseModel):
    task_id: int
    content: str = Field(min_length=1, max_length=1_000_000)
    format: Literal["json", "jsonl", "markdown", "auto"] = "auto"


class BackupRestoreRequest(BaseModel):
    backup: dict
    replace: bool = False


class BatchReportRequest(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=20)


class ReviewCreate(BaseModel):
    content: str = Field(min_length=1, max_length=10000)
    reviewer: str = Field(default="manual", max_length=100)


class CandidateCreate(BaseModel):
    task_id: int | None = None
    title: str = Field(min_length=1, max_length=300)
    content: str = Field(min_length=1, max_length=10000)
    source_evidence: str = Field(default="", max_length=4000)
    target_type: str = Field(default="manual", max_length=100)


class CandidatePatch(BaseModel):
    status: Literal["pending", "approved", "rejected"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=300)
    content: str | None = Field(default=None, min_length=1, max_length=10000)
    reviewer_note: str | None = Field(default=None, max_length=2000)

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobStatus(str, Enum):
    submitted = "submitted"
    running = "running"
    completed = "completed"
    failed = "failed"
    timed_out = "timed_out"


class JobDurations(BaseModel):
    submit_ms: int = 0
    poll_ms: int = 0
    process_ms: int = 0
    total_ms: int = 0


class JobRecord(BaseModel):
    job_id: str
    status: JobStatus = JobStatus.submitted
    message: str = ""

    created_at: str = Field(default_factory=utcnow_iso)
    updated_at: str = Field(default_factory=utcnow_iso)
    completed_at: str | None = None

    filename: str | None = None
    input_path: str | None = None
    output_md_path: str | None = None
    raw_result_path: str | None = None
    metadata_path: str | None = None

    docling_task_id: str | None = None
    docling_status: str | None = None

    images_count: int = 0
    image_paths: list[str] = Field(default_factory=list)

    durations: JobDurations = Field(default_factory=JobDurations)
    error: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ProcessResponse(BaseModel):
    job_id: str
    status: JobStatus
    docling_task_id: str | None = None
    created_at: str


class JobStatusResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str = ""
    docling_task_id: str | None = None
    docling_status: str | None = None
    durations: JobDurations
    created_at: str
    updated_at: str
    completed_at: str | None = None
    error: str | None = None


class JobResultResponse(BaseModel):
    job_id: str
    status: JobStatus
    output_md_path: str | None = None
    raw_result_path: str | None = None
    metadata_path: str | None = None
    images_count: int = 0
    image_paths: list[str] = Field(default_factory=list)
    durations: JobDurations
    message: str = ""

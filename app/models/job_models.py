from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


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


class ConversionOptions(BaseModel):
    """All conversion parameters for Docling processing."""
    
    # Table processing
    table_mode: Literal["fast", "accurate"] = "accurate"
    
    # OCR settings
    do_ocr: bool = False
    ocr_engine: Literal["auto", "easyocr", "rapidocr", "tesseract"] = "easyocr"
    
    # Image handling
    image_export_mode: Literal["placeholder", "embedded", "referenced"] = "embedded"
    images_scale: float = 2.0
    include_images: bool = True
    
    # Picture description (Azure OpenAI)
    do_picture_description: bool = False
    picture_description_prompt: str | None = None
    
    # Page range
    page_range_start: int | None = None
    page_range_end: int | None = None
    
    # PDF backend
    pdf_backend: Literal["pypdfium2", "docling_parse", "dlparse_v1", "dlparse_v2", "dlparse_v4"] = "docling_parse"
    
    # Timeout
    document_timeout: float | None = None
    
    # Error handling
    abort_on_error: bool = False
    
    @field_validator("images_scale")
    @classmethod
    def validate_images_scale(cls, v: float) -> float:
        """Validate images_scale is positive."""
        if v <= 0:
            raise ValueError("images_scale must be positive")
        return v
    
    @field_validator("page_range_start", "page_range_end")
    @classmethod
    def validate_page_range(cls, v: int | None) -> int | None:
        """Validate page numbers are positive."""
        if v is not None and v <= 0:
            raise ValueError("Page numbers must be positive")
        return v


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
    
    # Conversion options (for audit/tracking)
    conversion_options: ConversionOptions | None = None


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
    conversion_options: ConversionOptions | None = None

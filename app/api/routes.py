from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app.models.job_models import JobResultResponse, JobStatusResponse, ProcessResponse
from app.services.job_service import JobService
from app.services.job_store import JobStore


router = APIRouter()


def get_job_store() -> JobStore:
    from app.main import job_store

    return job_store


def get_job_service() -> JobService:
    from app.main import job_service

    return job_service


@router.post("/process-document", response_model=ProcessResponse, status_code=status.HTTP_202_ACCEPTED)
async def process_document(
    file: UploadFile = File(...),
    tenant_id: str | None = Form(default=None),
    to_formats: str = Form(default="md"),
    convert_include_images: bool = Form(default=True),
    convert_do_ocr: bool = Form(default=False),
    store: JobStore = Depends(get_job_store),
    service: JobService = Depends(get_job_service),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    from app.core.config import settings

    if len(data) > settings.max_file_size_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds max size limit ({settings.max_file_size_bytes} bytes).",
        )

    job = await service.create_job(filename=file.filename or "input.bin", file_bytes=data)
    asyncio.create_task(
        service.run_job(
            job_id=job.job_id,
            tenant_id=tenant_id,
            to_formats=to_formats,
            convert_include_images=convert_include_images,
            convert_do_ocr=convert_do_ocr,
        )
    )

    return ProcessResponse(
        job_id=job.job_id,
        status=job.status,
        docling_task_id=job.docling_task_id,
        created_at=job.created_at,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: str, store: JobStore = Depends(get_job_store)):
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        message=job.message,
        docling_task_id=job.docling_task_id,
        docling_status=job.docling_status,
        durations=job.durations,
        created_at=job.created_at,
        updated_at=job.updated_at,
        completed_at=job.completed_at,
        error=job.error,
    )


@router.get("/jobs/{job_id}/result", response_model=JobResultResponse)
async def get_job_result(job_id: str, store: JobStore = Depends(get_job_store)):
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    return JobResultResponse(
        job_id=job.job_id,
        status=job.status,
        output_md_path=job.output_md_path,
        raw_result_path=job.raw_result_path,
        metadata_path=job.metadata_path,
        images_count=job.images_count,
        image_paths=job.image_paths,
        durations=job.durations,
        message=job.message,
    )


@router.get(
    "/jobs/{job_id}/markdown",
    response_class=FileResponse,
    responses={
        200: {
            "description": "Markdown file response",
            "content": {"text/markdown": {}},
        },
        404: {"description": "Job or markdown file not found"},
        409: {"description": "Markdown output not available yet"},
    },
)
async def get_job_markdown(job_id: str, store: JobStore = Depends(get_job_store)):
    job = await store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not job.output_md_path:
        raise HTTPException(status_code=409, detail="Markdown output not available yet.")

    path = Path(job.output_md_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Markdown file not found on disk.")
    return FileResponse(path=str(path), media_type="text/markdown", filename=f"{job.job_id}.md")

from __future__ import annotations

import asyncio
import json
from pathlib import Path

from app.models.job_models import JobRecord, JobStatus, utcnow_iso


class JobStore:
    def __init__(self, output_root: str) -> None:
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()
        self._output_root = Path(output_root)
        self._output_root.mkdir(parents=True, exist_ok=True)

    async def create(self, record: JobRecord) -> JobRecord:
        async with self._lock:
            self._jobs[record.job_id] = record
            await self._persist_metadata(record)
            return record

    async def get(self, job_id: str) -> JobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def update(self, job_id: str, **kwargs) -> JobRecord | None:
        async with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None

            for k, v in kwargs.items():
                setattr(job, k, v)

            job.updated_at = utcnow_iso()
            if job.status in {JobStatus.completed, JobStatus.failed, JobStatus.timed_out} and not job.completed_at:
                job.completed_at = utcnow_iso()

            self._jobs[job_id] = job
            await self._persist_metadata(job)
            return job

    async def _persist_metadata(self, record: JobRecord) -> None:
        job_dir = self._output_root / record.job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        metadata_path = job_dir / "metadata.json"
        metadata_path.write_text(json.dumps(record.model_dump(), indent=2), encoding="utf-8")
        record.metadata_path = str(metadata_path.resolve())

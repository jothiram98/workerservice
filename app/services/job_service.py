from __future__ import annotations

import json
import uuid
from pathlib import Path
from time import perf_counter
from typing import Any

from app.core.config import settings
from app.models.job_models import JobRecord, JobStatus
from app.services.docling_client import DoclingClient
from app.services.job_store import JobStore
from app.services.markdown_image_processor import extract_and_rewrite_markdown_images


class JobService:
    def __init__(self, store: JobStore, docling_client: DoclingClient) -> None:
        self.store = store
        self.docling_client = docling_client
        self.output_root = Path(settings.output_root)
        self.output_root.mkdir(parents=True, exist_ok=True)

    async def create_job(self, filename: str, file_bytes: bytes) -> JobRecord:
        job_id = str(uuid.uuid4())
        job_dir = self.output_root / job_id
        input_dir = job_dir / "input"
        input_dir.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name or "input.bin"
        input_path = input_dir / safe_name
        input_path.write_bytes(file_bytes)

        record = JobRecord(
            job_id=job_id,
            status=JobStatus.submitted,
            filename=safe_name,
            input_path=str(input_path.resolve()),
        )
        await self.store.create(record)
        return record

    async def run_job(
        self,
        job_id: str,
        tenant_id: str | None = None,
        to_formats: str = "md",
        convert_include_images: bool = True,
        convert_do_ocr: bool = False,
    ) -> None:
        record = await self.store.get(job_id)
        if record is None:
            return

        started = perf_counter()
        await self.store.update(job_id, status=JobStatus.running, message="Submitting to Docling async API")

        try:
            task_id, submit_ms = await self.docling_client.submit_file_async(
                file_path=record.input_path or "",
                filename=record.filename or "input.bin",
                tenant_id=tenant_id,
                to_formats=to_formats,
                convert_include_images=convert_include_images,
                convert_do_ocr=convert_do_ocr,
            )

            await self.store.update(
                job_id,
                docling_task_id=task_id,
                docling_status="pending",
                message="Docling task submitted. Polling status.",
            )

            status_payload, poll_ms = await self.docling_client.poll_until_terminal(task_id=task_id)
            docling_status = str(status_payload.get("task_status", ""))
            await self.store.update(job_id, docling_status=docling_status)

            if docling_status.lower() not in {"success", "completed", "done"}:
                err = status_payload.get("error_message") or f"Docling task ended in status={docling_status}"
                await self.store.update(
                    job_id,
                    status=JobStatus.failed,
                    error=str(err),
                    message="Docling task failed.",
                )
                return

            result_payload = await self.docling_client.fetch_result(task_id=task_id)
            job_dir = self.output_root / job_id
            raw_path = job_dir / "raw_docling_result.json"
            raw_path.write_text(json.dumps(result_payload, indent=2), encoding="utf-8")

            md_content = self._extract_md(result_payload)
            images_dir = job_dir / "images"
            rewritten_md, image_paths = extract_and_rewrite_markdown_images(
                md_content=md_content,
                images_dir=str(images_dir),
                image_prefix="img",
            )

            final_md_path = job_dir / "final.md"
            final_md_path.write_text(rewritten_md, encoding="utf-8")

            total_ms = int((perf_counter() - started) * 1000)
            process_ms = max(total_ms - submit_ms - poll_ms, 0)

            current = await self.store.get(job_id)
            if current is None:
                return
            current.durations.submit_ms = submit_ms
            current.durations.poll_ms = poll_ms
            current.durations.process_ms = process_ms
            current.durations.total_ms = total_ms

            await self.store.update(
                job_id,
                status=JobStatus.completed,
                message="Completed successfully.",
                output_md_path=str(final_md_path.resolve()),
                raw_result_path=str(raw_path.resolve()),
                images_count=len(image_paths),
                image_paths=image_paths,
                durations=current.durations,
            )
        except TimeoutError as exc:
            await self.store.update(
                job_id,
                status=JobStatus.timed_out,
                error=str(exc),
                message="Job timed out while polling Docling.",
            )
        except Exception as exc:
            await self.store.update(
                job_id,
                status=JobStatus.failed,
                error=str(exc),
                message="Unhandled error while processing job.",
            )

    @staticmethod
    def _extract_md(payload: dict[str, Any]) -> str:
        # Observed contract in this setup:
        # payload["document"]["md_content"]
        doc = payload.get("document")
        if isinstance(doc, dict):
            md = doc.get("md_content")
            if isinstance(md, str):
                return md

        # Fall back for compatibility with other possible response shapes.
        docs = payload.get("documents")
        if isinstance(docs, list) and docs:
            first = docs[0]
            if isinstance(first, dict):
                content = first.get("content") or first.get("md_content")
                if isinstance(content, str):
                    return content

        raise ValueError("Could not find markdown content in Docling result payload.")

from __future__ import annotations

import asyncio
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from app.core.config import settings
from app.models.job_models import ConversionOptions


class DoclingClient:
    def __init__(self) -> None:
        self.base_url = settings.docling_base_url.rstrip("/")
        self.max_attempts = settings.retry_max_attempts
        self.base_delay_ms = settings.retry_base_delay_ms
        self.timeout = settings.request_timeout_seconds

    def _headers(self, tenant_id: str | None = None) -> dict[str, str]:
        headers: dict[str, str] = {}
        if settings.docling_api_key:
            headers["X-Api-Key"] = settings.docling_api_key
        if tenant_id:
            headers["X-Tenant-Id"] = tenant_id
        elif settings.docling_tenant_id:
            headers["X-Tenant-Id"] = settings.docling_tenant_id
        return headers

    async def _request_with_retry(self, request_func):
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return await request_func()
            except (httpx.RequestError, httpx.TimeoutException) as exc:
                last_error = exc
                if attempt == self.max_attempts:
                    break
                delay = (self.base_delay_ms * (2 ** (attempt - 1))) / 1000.0
                await asyncio.sleep(delay)
        if last_error:
            raise last_error
        raise RuntimeError("Request failed unexpectedly.")

    async def submit_file_async(
        self,
        file_path: str,
        filename: str,
        tenant_id: str | None = None,
        to_formats: str = "md",
        conversion_options: ConversionOptions | None = None,
        picture_description_api: dict[str, Any] | None = None,
    ) -> tuple[str, int]:
        headers = self._headers(tenant_id=tenant_id)
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {file_path}")

        # Use defaults if no conversion_options provided
        if conversion_options is None:
            conversion_options = ConversionOptions()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            started = perf_counter()

            async def do_request():
                with path.open("rb") as fh:
                    files = {"files": (filename, fh, "application/octet-stream")}
                    
                    # Build data payload from conversion_options
                    data = {
                        "to_formats": to_formats,
                        "table_mode": conversion_options.table_mode,
                        "do_ocr": str(conversion_options.do_ocr).lower(),
                        "ocr_engine": conversion_options.ocr_engine,
                        "image_export_mode": conversion_options.image_export_mode,
                        "images_scale": str(conversion_options.images_scale),
                        "include_images": str(conversion_options.include_images).lower(),
                        "do_picture_description": str(conversion_options.do_picture_description).lower(),
                        "pdf_backend": conversion_options.pdf_backend,
                        "abort_on_error": str(conversion_options.abort_on_error).lower(),
                    }
                    
                    # Add page_range if both start and end are provided
                    if conversion_options.page_range_start is not None and conversion_options.page_range_end is not None:
                        data["page_range"] = f"({conversion_options.page_range_start}, {conversion_options.page_range_end})"
                    
                    # Add document_timeout if provided
                    if conversion_options.document_timeout is not None:
                        data["document_timeout"] = str(conversion_options.document_timeout)
                    
                    # Add picture_description_api if provided
                    if picture_description_api is not None:
                        # Picture description API config needs special handling
                        import json
                        data["picture_description_api"] = json.dumps(picture_description_api)
                    
                    # Add picture_description_prompt if provided and not already included
                    if conversion_options.picture_description_prompt is not None:
                        data["picture_description_prompt"] = conversion_options.picture_description_prompt
                    
                    response = await client.post(
                        f"{self.base_url}/v1/convert/file/async",
                        headers=headers,
                        files=files,
                        data=data,
                    )
                    response.raise_for_status()
                    return response

            response = await self._request_with_retry(do_request)
            elapsed = int((perf_counter() - started) * 1000)
            payload = response.json()
            task_id = payload.get("task_id")
            if not task_id:
                raise ValueError(f"Docling async submit did not return task_id. Payload: {payload}")
            return task_id, elapsed

    async def poll_until_terminal(
        self,
        task_id: str,
    ) -> tuple[dict[str, Any], int]:
        terminal_statuses = {"success", "completed", "done", "failed", "error", "cancelled"}
        wait = settings.poll_wait_seconds
        started = perf_counter()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            while True:
                url = f"{self.base_url}/v1/status/poll/{task_id}"
                headers = self._headers()
                response = await client.get(url, headers=headers, params={"wait": wait})

                if response.status_code == 404:
                    raise ValueError(f"Docling task not found for task_id={task_id}")
                response.raise_for_status()

                payload = response.json()
                status = str(payload.get("task_status", "")).lower()
                if status in terminal_statuses:
                    elapsed = int((perf_counter() - started) * 1000)
                    return payload, elapsed

                elapsed_s = perf_counter() - started
                if elapsed_s > settings.max_wait_seconds:
                    raise TimeoutError(
                        f"Polling timeout for task_id={task_id} after {settings.max_wait_seconds}s"
                    )

                await asyncio.sleep(settings.poll_interval_seconds)

    async def fetch_result(self, task_id: str) -> dict[str, Any]:
        headers = self._headers()
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/v1/result/{task_id}", headers=headers)
            if response.status_code == 404:
                raise ValueError(f"Result not found for task_id={task_id}")
            response.raise_for_status()
            return response.json()

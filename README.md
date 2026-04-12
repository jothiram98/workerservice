# Phase 1.5 Document Pipeline (FastAPI + Docling Async)

## Overview
This repository is the Phase 1.5 baseline for a production-minded document processing pipeline:

- FastAPI acts as the orchestration layer.
- Docling Serve acts as the async conversion engine.
- Output is Markdown (`.md`) with extracted image files (no base64 in final markdown).
- Pipeline is queue-less at app level (uses Docling built-in async task system).

This phase is focused on correctness, reliability, and clean contracts before external queues/workers are introduced.

---

## Current Context
- Docling OpenAPI source: [openapi.json](C:\Users\niveb\Documents\Personal_Jothiram\Dockling Microservice\openapi.json)
- Local API understanding: [dockerengine.md](C:\Users\niveb\Documents\Personal_Jothiram\Dockling Microservice\dockerengine.md)
- Verified local Docling endpoint: `http://localhost:5001`
- Verified async conversion example output: [sample_converted_async.md](C:\Users\niveb\Documents\Personal_Jothiram\Dockling Microservice\sample_converted_async.md)

Important contract note observed in this environment:
- Result payload shape is `result["document"]["md_content"]` (singular `document`), not `documents[0]`.

---

## Phase 1.5 Goals
- Keep architecture simple and shippable.
- Use Docling async API end-to-end.
- Produce clean markdown without embedded base64 image data.
- Preserve image placement by replacing data URLs with local/served image paths in-place.
- Add reliability safeguards: retries, timeout, status model, structured errors, and artifact persistence.

---

## High-Level Architecture
```text
Client
  -> FastAPI (/process-document)
  -> Docling (/v1/convert/file/async)
  -> Poll Docling (/v1/status/poll/{task_id}?wait=2)
  -> Fetch result (/v1/result/{task_id})
  -> Post-process markdown (extract base64 images, rewrite links)
  -> Persist artifacts (.md + images + metadata)
  -> Return job status/result
```

---

## Recommended API Design (FastAPI)

### 1) Submit document
`POST /process-document`

Input:
- multipart file upload (`file`)
- optional `tenant_id`
- optional conversion flags (safe defaults)

Output (`202 Accepted`):
```json
{
  "job_id": "uuid",
  "status": "submitted",
  "docling_task_id": "uuid",
  "created_at": "timestamp"
}
```

### 2) Check job status
`GET /jobs/{job_id}`

Output:
```json
{
  "job_id": "uuid",
  "status": "submitted|running|completed|failed|timed_out",
  "docling_task_id": "uuid",
  "message": "optional",
  "durations": {
    "submit_ms": 0,
    "poll_ms": 0,
    "total_ms": 0
  }
}
```

### 3) Get final result
`GET /jobs/{job_id}/result`

Output:
- JSON containing metadata and file paths
- or direct markdown response (optional mode)

---

## Docling Interaction Contract

### Submit async conversion
`POST {DOCLING_BASE_URL}/v1/convert/file/async`

Recommended options for this phase:
- `to_formats=md`
- `convert_include_images=true`
- `convert_do_ocr=false` (enable only where needed)

### Poll status
`GET {DOCLING_BASE_URL}/v1/status/poll/{task_id}?wait=2`

Use bounded retry + timeout:
- `POLL_INTERVAL_SECONDS=1..2`
- `MAX_WAIT_SECONDS=300` (adjust by file size profile)

### Fetch result
`GET {DOCLING_BASE_URL}/v1/result/{task_id}`

Expect:
- markdown at `document.md_content`
- status should be success before result fetch

---

## Markdown + Image Post-Processing

### Problem
Docling can return markdown image tags with base64 `data:image/...` URLs.

### Phase 1.5 behavior
1. Parse markdown image links.
2. Detect links that start with `data:image/`.
3. Decode and save image bytes to deterministic paths.
4. Replace original image URLs in markdown with saved file paths.
5. Persist rewritten markdown as final output.

### Deterministic naming
Recommended:
- `outputs/{job_id}/images/img_0001.png`
- `outputs/{job_id}/final.md`
- `outputs/{job_id}/raw_docling_result.json`
- `outputs/{job_id}/metadata.json`

### Placement guarantee
Since replacement happens in-place at each original markdown image tag, image ordering and position remain aligned with original document flow.

---

## Reliability Controls (Phase 1.5)
- Use `httpx.AsyncClient` (avoid blocking `requests` in `async def`).
- Retry transient HTTP failures with exponential backoff.
- Mark explicit terminal job states (`completed`, `failed`, `timed_out`).
- Store raw Docling payload before transformations.
- Capture and persist timing metrics.
- Handle edge cases:
  - `Task not found`
  - partial/malformed result payload
  - image decode failure
  - markdown exists but image extraction fails

---

## Configuration

Use environment variables:

```env
DOCLING_BASE_URL=http://localhost:5001
DOCLING_API_KEY=
DOCLING_TENANT_ID=
POLL_WAIT_SECONDS=2
MAX_WAIT_SECONDS=300
RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY_MS=500
OUTPUT_ROOT=./outputs
LOG_LEVEL=INFO
```

Notes:
- If your Docling instance enforces API key, send `X-Api-Key`.
- If multi-tenant behavior is needed, send `X-Tenant-Id`.

---

## Suggested Project Layout
```text
.
├── app/
│   ├── main.py
│   ├── api/routes.py
│   ├── services/docling_client.py
│   ├── services/job_service.py
│   ├── services/markdown_image_processor.py
│   ├── models/job_models.py
│   └── core/config.py
├── outputs/
├── openapi.json
├── dockerengine.md
└── README.md
```

---

## Local Run (when implementation files are added)
```bash
uvicorn app.main:app --reload --port 7001
```

Example call:
```bash
curl -X POST "http://localhost:7001/process-document" ^
  -F "file=@sample.pdf"
```

Then:
```bash
curl "http://localhost:7001/jobs/<job_id>"
curl "http://localhost:7001/jobs/<job_id>/result"
```

---

## Acceptance Criteria (Phase 1.5)
- Async conversion works for `sample.pdf`.
- Job state transitions are consistent and queryable.
- Final markdown file is generated.
- All base64 markdown images are extracted to files and rewritten as file paths.
- Raw payload + metadata + timings are persisted per job.
- Failure modes return actionable error messages.

---

## Operational Notes
- CPU-only Docling is slower for large PDFs; prefer async flow always.
- Use bounded page ranges and OCR only when needed for performance.
- Poll with `wait` query to reduce unnecessary request churn.

---

## Security Notes
- Do not log API keys or raw secrets.
- Validate upload MIME type and file size limits.
- Sanitize output file names and paths.
- Consider malware scanning before processing in later phases.

---

## Roadmap

### Phase 2
- Blob/object storage for artifacts.
- Vision enrichment for extracted images.
- Better document chunking and indexing hooks.

### Phase 3
- External queue + worker pool (RabbitMQ/Service Bus/Kafka).
- Horizontal scaling and backpressure controls.
- Full observability dashboards and SLOs.

---

## Summary
This Phase 1.5 design keeps your architecture simple but robust:
- Async-first with Docling.
- Reliable orchestration via FastAPI.
- Clean markdown outputs with extracted image assets.
- Production-minded safeguards without over-engineering.


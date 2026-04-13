# Phase 1.5 Document Pipeline (FastAPI + Docling Async)

## Overview
This repo contains a Phase 1.5 document processing pipeline:

- FastAPI is the orchestrator (job tracking + post-processing).
- Docling Serve is the conversion engine (async tasks).
- Output is Markdown (`final.md`) with optional extracted images (no base64 in the final markdown if image extraction is enabled).

Phase 1.5 focuses on correctness, reliability, and clean contracts before adding external queues/workers and cloud storage.

---

## Current Context
- Docling Serve endpoint: `http://localhost:5001`
- FastAPI orchestrator endpoint (local): `http://127.0.0.1:7001`
- Docling result contract (observed here): `result["document"]["md_content"]`

---

## High-Level Architecture
```text
Client
  -> FastAPI: POST /process-document (multipart upload)
  -> Docling: POST /v1/convert/file/async
  -> FastAPI polls: GET /v1/status/poll/{task_id}?wait=2
  -> FastAPI fetches: GET /v1/result/{task_id}
  -> FastAPI post-processes markdown (optional image extraction + link rewrite)
  -> FastAPI persists artifacts under outputs/<job_id>/
  -> Client polls: GET /jobs/{job_id}, fetches result/markdown
```

---

## FastAPI API (Phase 1.5)

### 1) Submit document
`POST /process-document`

Form fields:
- `file` (required)
- `tenant_id` (optional)
- `to_formats` (default `md`)
- `convert_include_images` (default `true`)
- `convert_do_ocr` (default `false`)
- `max_wait_seconds` (optional override for large docs; seconds)

Response (`202 Accepted`):
```json
{
  "job_id": "uuid",
  "status": "submitted",
  "docling_task_id": null,
  "created_at": "timestamp"
}
```

### 2) Job status
`GET /jobs/{job_id}`

Status values:
- `submitted`, `running`, `completed`, `failed`, `timed_out`

### 3) Job result metadata
`GET /jobs/{job_id}/result`

Returns paths for:
- `outputs/<job_id>/final.md`
- `outputs/<job_id>/raw_docling_result.json`
- `outputs/<job_id>/metadata.json`
- extracted image paths (if any)

### 4) Download markdown
`GET /jobs/{job_id}/markdown`

Returns:
- `text/markdown` file response

### 5) Resume polling for timed-out jobs
If a job hits `timed_out`, Docling may still be processing. Resume without resubmitting the file:

`POST /jobs/{job_id}/resume`

Form fields:
- `max_wait_seconds` (optional; extra polling window in seconds)

---

## Artifact Persistence
Artifacts are written to disk:

```text
outputs/<job_id>/
  input/<original_filename>
  final.md
  raw_docling_result.json
  metadata.json
  images/ (only if extracted)
```

Important: Phase 1.5 job state is stored in-memory while FastAPI is running (for quick queries), and also written to `outputs/<job_id>/metadata.json`.
After a FastAPI restart, old job IDs are not queryable via API unless you implement a disk/DB-backed index (recommended for Phase 2).

---

## Docling Serve Notes (Important Defaults)
Docling Serve can clear results after completion depending on its configuration:

- `DOCLING_SERVE_SINGLE_USE_RESULTS=true` (default)
- `DOCLING_SERVE_RESULT_REMOVAL_DELAY=300` (default, seconds)

This means `/v1/result/{task_id}` may stop working after some time; the orchestrator should fetch results promptly.

Management endpoints (`/v1/memory/*`) return `403` unless enabled:
- `DOCLING_SERVE_ENABLE_MANAGEMENT_ENDPOINTS=true`

---

## Configuration (FastAPI)
Use a `.env` file (see `.env.example`) or environment variables:

```env
DOCLING_BASE_URL=http://localhost:5001
DOCLING_API_KEY=
DOCLING_TENANT_ID=

POLL_WAIT_SECONDS=2
POLL_INTERVAL_SECONDS=1
MAX_WAIT_SECONDS=300

RETRY_MAX_ATTEMPTS=3
RETRY_BASE_DELAY_MS=500
REQUEST_TIMEOUT_SECONDS=60

OUTPUT_ROOT=./outputs
SERVE_ARTIFACTS=true
MAX_FILE_SIZE_BYTES=52428800
LOG_LEVEL=INFO
```

---

## Project Layout
```text
.
|-- app/
|   |-- main.py
|   |-- api/routes.py
|   |-- core/config.py
|   |-- models/job_models.py
|   `-- services/
|       |-- docling_client.py
|       |-- job_service.py
|       |-- job_store.py
|       `-- markdown_image_processor.py
|-- outputs/
|-- openapi.json
|-- dockerengine.md
|-- requirements.txt
|-- .env.example
`-- README.md
```

---

## Local Run
Install dependencies:
```bash
python -m pip install -r requirements.txt
```

Run:
```bash
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 7001
```

Example submit (increase polling window to 20 minutes):
```bash
curl -X POST "http://127.0.0.1:7001/process-document" ^
  -F "file=@sample.pdf" ^
  -F "max_wait_seconds=1200"
```

Poll:
```bash
curl "http://127.0.0.1:7001/jobs/<job_id>"
```

Download markdown:
```bash
curl "http://127.0.0.1:7001/jobs/<job_id>/markdown" -o final.md
```

Resume (if timed out):
```bash
curl -X POST "http://127.0.0.1:7001/jobs/<job_id>/resume" ^
  -F "max_wait_seconds=1200"
```

---

## Roadmap
- Phase 2: disk-backed index or SQLite/Cosmos DB for job persistence; move artifacts to blob storage.
- Phase 3: external queue + worker pool if throughput/concurrency requires it.


# Docker Engine Context (Docling Serve CPU-Only)

## 1) Scope and Objective

This document captures the current API and runtime context for your Docling-based file processing engine, running as a **CPU-only container** with **PyTorch from the CPU index**.

It is meant to be the baseline for the upcoming action plan.

---

## 2) Source of Truth

- Local API schema: `openapi.json` (OpenAPI `3.1.0`)
- Service title/version from schema:
  - `title`: `Docling Serve`
  - `version`: `1.16.1`
- Upstream project reference:
  - `https://github.com/docling-project/docling-serve/tree/main`

---

## 3) Runtime Context (Current Setup)

- Deployment style: containerized microservice
- Compute profile: CPU-only
- Torch installation strategy: PyTorch CPU wheels from the CPU index
- Main responsibility: document/file processing engine (conversion + chunking + async task workflow)

Assumption used here:
- You intend this engine to be called by another service/application rather than used only manually.

---

## 4) Security and Multi-Tenant Model

### Authentication

- Security scheme in schema: `APIKeyAuth`
- Header name: `X-Api-Key`
- Most `/v1/*` processing/task/clear endpoints require this header.

### Optional tenancy header

- Optional header on processing endpoints: `X-Tenant-Id`
- Use this to partition workloads logically by tenant/customer when needed.

---

## 5) API Surface Overview

Total paths in schema: `22`

### Health and metadata

- `GET /health` (no auth)
- `GET /ready` (no auth)
- `GET /version` (no auth)
- `GET /openapi-3.0.json` (no auth)

### Convert endpoints

- `POST /v1/convert/source` (auth)
- `POST /v1/convert/file` (auth)
- `POST /v1/convert/source/async` (auth)
- `POST /v1/convert/file/async` (auth)

### Chunk endpoints (Hybrid chunker)

- `POST /v1/chunk/hybrid/source` (auth)
- `POST /v1/chunk/hybrid/file` (auth)
- `POST /v1/chunk/hybrid/source/async` (auth)
- `POST /v1/chunk/hybrid/file/async` (auth)

### Chunk endpoints (Hierarchical chunker)

- `POST /v1/chunk/hierarchical/source` (auth)
- `POST /v1/chunk/hierarchical/file` (auth)
- `POST /v1/chunk/hierarchical/source/async` (auth)
- `POST /v1/chunk/hierarchical/file/async` (auth)

### Async task lifecycle

- `GET /v1/status/poll/{task_id}` (auth)
- `GET /v1/result/{task_id}` (auth)

### Management / cleanup

- `GET /v1/clear/converters` (auth)
- `GET /v1/clear/results` (auth)
- `GET /v1/memory/stats` (no auth in current schema)
- `GET /v1/memory/counts` (no auth in current schema)

---

## 6) Processing Modes and I/O Patterns

### Source vs file input

- `.../source` endpoints accept structured JSON request bodies for external sources (URL/cloud-style sources depending on schema request models).
- `.../file` endpoints accept multipart uploads (`multipart/form-data`), useful for direct local file ingestion.

### Sync vs async

- Sync endpoints return processed payload immediately (or zip when requested).
- Async endpoints return a task payload (`TaskStatusResponse`) and require polling/result retrieval.

### Output targeting

Common target behavior in request models:
- `target_type = inbody` to return content inline JSON
- `target_type = zip` to return zip output stream (`application/zip`)

---

## 7) Core Request Options (Important Knobs from Schema)

These options are central for quality/performance behavior:

- `convert_from_formats`: restrict accepted source formats
- `convert_do_ocr`: OCR enabled/disabled
- `convert_force_ocr`: force OCR over existing text layers
- `convert_ocr_engine`: enum includes `auto`, `easyocr`, `rapidocr`, `tesseract`, etc.
- `convert_ocr_lang`: OCR language list
- `convert_pdf_backend`: enum includes `pypdfium2`, `docling_parse`, `dlparse_*`
- `convert_table_mode`: `fast` or `accurate`
- `convert_table_cell_matching`: table mapping behavior
- `convert_pipeline`: processing pipeline enum includes `legacy`, `standard`, `vlm`, `asr`
- `convert_page_range`: partial page processing
- `convert_document_timeout`: per-document processing timeout
- `convert_abort_on_error`: fail-fast behavior for batch jobs

For chunking workflows:
- supports both Hybrid and Hierarchical chunkers
- optional inclusion of converted document with chunks (`include_converted_doc`)

---

## 8) Response Model Summary

Main response families observed:

- `ConvertDocumentResponse`
- `PresignedUrlConvertDocumentResponse`
- `ChunkDocumentResponse`
- `TaskStatusResponse`
- `ClearResponse`
- validation errors via `HTTPValidationError`

For async jobs:
- status endpoint returns task progress + meta (`num_docs`, `num_processed`, `num_succeeded`, `num_failed`)
- result endpoint returns final converted/chunked output (JSON or zip based on target)

---

## 9) Async Lifecycle (Recommended Client Pattern)

1. Submit to an async endpoint (`/v1/convert/*/async` or `/v1/chunk/*/async`).
2. Store returned `task_id`.
3. Poll `GET /v1/status/poll/{task_id}` until terminal status.
4. Fetch payload from `GET /v1/result/{task_id}`.
5. Optionally call clear endpoints for retention management.

Notes:
- `wait` query parameter in poll API can reduce tight polling loops.
- Build retries/backoff around status polling to avoid pressure on the service.

---

## 10) CPU-Only Container Guidance

### Build intent

This engine should avoid GPU/CUDA dependencies and run predictably on commodity CPU hosts.

### Torch install approach

Use PyTorch CPU index for deterministic CPU builds. Typical pattern:

```dockerfile
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch torchvision torchaudio
```

### Operational implications on CPU

- Throughput will be lower than GPU variants; prefer async APIs for larger files.
- Use page ranges and format restrictions to reduce processing time.
- Select `table_mode=fast` when latency is more important than table fidelity.
- Keep OCR enabled only when needed to save CPU cycles on text-based PDFs.

---

## 11) Integration Contract for Upstream Services

When using this as a backend engine from another service:

- Always send `X-Api-Key` for `/v1/*` protected routes.
- Optionally send `X-Tenant-Id` for tenant isolation and traceability.
- Choose endpoint family by workload:
  - low-latency single-file: sync
  - bulk/long-running: async
- Normalize handling for dual content types (`application/json` and `application/zip`).
- Implement shared error handling for:
  - `422` validation errors
  - task failures surfaced in `TaskStatusResponse.error_message`

---

## 12) Minimal cURL Examples

### Health check

```bash
curl -s http://localhost:8000/health
```

### Convert file (sync)

```bash
curl -X POST "http://localhost:8000/v1/convert/file" \
  -H "X-Api-Key: <API_KEY>" \
  -H "X-Tenant-Id: <TENANT_ID>" \
  -F "files=@sample.pdf"
```

### Convert file (async) + poll

```bash
curl -X POST "http://localhost:8000/v1/convert/file/async" \
  -H "X-Api-Key: <API_KEY>" \
  -F "files=@sample.pdf"

curl -X GET "http://localhost:8000/v1/status/poll/<TASK_ID>?wait=2" \
  -H "X-Api-Key: <API_KEY>"
```

---

## 13) Ready State for Action Plan

The API is understood at contract level and is ready for requirement-driven planning.  
Next step is to map your specific business requirement onto:

- exact endpoint choice (`source` vs `file`, `sync` vs `async`)
- required output format (`inbody` vs `zip`)
- processing option profile (OCR/table/pipeline/timeouts)
- retention and cleanup policy (`clear/results`, polling cadence)

---

## 14) Open Items to Lock During Planning

- final auth and key rotation approach for production
- expected max file size and concurrency targets
- timeout/retry policy between caller service and docling engine
- desired default conversion/chunking presets per document type
- observability: request IDs, task tracking, and failure metrics


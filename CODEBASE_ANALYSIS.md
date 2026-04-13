# Dockling Microservice - Codebase Analysis

## Executive Summary

You've built a **FastAPI-based document processing orchestrator** that acts as a middleware layer between client applications and the Docling Serve document conversion engine. The system handles async job submission, polling, result retrieval, and post-processing of Markdown content with image extraction.

---

## Architecture Overview

### Three-Tier Design

```
┌─────────────────────────────────────────────────────────────┐
│ CLIENT (Postman / UI / Service)                             │
│ POST /process-document → GET /jobs/{job_id} → GET /result   │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ FASTAPI ORCHESTRATOR (Port 7001)                            │
│ • Job Store (In-Memory + JSON Persistence)                  │
│ • Job Service (Async Workflow Executor)                     │
│ • Markdown Image Processor (Extract & Rewrite Links)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ DOCLING SERVE ENGINE (Port 5001 - CPU-Only)                │
│ • Async Convert Endpoints: POST /v1/convert/file/async      │
│ • Status Polling: GET /v1/status/poll/{task_id}             │
│ • Result Retrieval: GET /v1/result/{task_id}                │
└─────────────────────────────────────────────────────────────┘
```

---

## Key Components

### 1. **Entry Point** (`app/main.py`)
- **Purpose**: FastAPI application initialization
- **Responsibilities**:
  - Creates FastAPI app with title "Doc Pipeline Phase 1.5"
  - Instantiates core service dependencies:
    - `JobStore`: In-memory job registry + JSON persistence
    - `DoclingClient`: HTTP client for Docling Serve API
    - `JobService`: Orchestration logic
  - Mounts `/artifacts` static file server for serving output files
  - Exposes `GET /health` endpoint for liveness checks

### 2. **Configuration** (`app/core/config.py`)
- **Type**: Pydantic BaseSettings (environment-driven)
- **Key Settings**:
  - `docling_base_url`: Docling Serve endpoint (default: `http://localhost:5001`)
  - `docling_api_key`: Authentication header value
  - `poll_wait_seconds`: Long-poll wait duration (default: 2s)
  - `poll_interval_seconds`: Re-check interval during polling (default: 1s)
  - `max_wait_seconds`: Max total polling time (default: 1200s = 20 min)
  - `retry_max_attempts`: Network retry count (default: 3)
  - `output_root`: Job artifacts storage directory (default: `./outputs`)
  - `max_file_size_bytes`: Client upload limit (default: 50 MB)

### 3. **Data Models** (`app/models/job_models.py`)
Defines the job lifecycle and API contracts:

**Job States**:
```
submitted → running → completed
                  ↘ failed / timed_out
```

**JobRecord** (Single source of truth for job state):
- `job_id`: UUID identifier
- `status`: Current job state enum
- `filename`: Original uploaded filename
- `input_path`: Path to uploaded file on disk
- `docling_task_id`: ID returned by Docling async API
- `docling_status`: Status from Docling polling
- `output_md_path`: Path to `final.md`
- `raw_result_path`: Path to raw JSON response from Docling
- `metadata_path`: Path to job metadata JSON
- `image_paths`: List of extracted image file paths
- `durations`: Timing breakdown (submit, poll, process, total in ms)
- `error`: Error message if failed

**API Response Models**:
- `ProcessResponse`: Returned on submission (202 Accepted)
- `JobStatusResponse`: Current job status
- `JobResultResponse`: Links to output artifacts

### 4. **API Routes** (`app/api/routes.py`)
**Endpoint: POST /process-document** (202 Accepted)
- Accepts multipart file upload
- Form parameters:
  - `file`: PDF/document to process
  - `tenant_id` (optional): For multi-tenant isolation
  - `to_formats`: Output format (default: `"md"`)
  - `convert_include_images`: Extract images (default: `true`)
  - `convert_do_ocr`: Enable OCR (default: `false`)
- Flow:
  1. Validates file not empty and under size limit
  2. Creates job record in `JobStore`
  3. Saves file to `outputs/{job_id}/input/`
  4. Launches background async task via `service.run_job()`
  5. Returns `ProcessResponse` immediately

**Endpoint: GET /jobs/{job_id}** (200 OK)
- Returns `JobStatusResponse` with current state
- Polling this endpoint allows clients to track progress

**Endpoint: GET /jobs/{job_id}/result** (200 OK)
- Returns `JobResultResponse` with artifact paths
- Available once job reaches terminal state

### 5. **Job Store** (`app/services/job_store.py`)
**Pattern**: In-memory registry with JSON file persistence

- **Responsibilities**:
  - Thread-safe job CRUD (uses `asyncio.Lock`)
  - Persists metadata to `outputs/{job_id}/metadata.json` on every update
  - Maintains job records in `_jobs` dict during session

- **Key Methods**:
  ```python
  async def create(record: JobRecord) -> JobRecord
  async def get(job_id: str) -> JobRecord | None
  async def update(job_id: str, **kwargs) -> JobRecord | None
  ```

- **Auto-completion tracking**: When status becomes `completed|failed|timed_out`, sets `completed_at` timestamp

### 6. **Docling Client** (`app/services/docling_client.py`)
**Pattern**: Async HTTP client with retry logic and long-polling

- **Authentication**:
  - `X-Api-Key`: From `settings.docling_api_key` (if set)
  - `X-Tenant-Id`: From parameter or `settings.docling_tenant_id`

- **Retry Strategy**:
  - Exponential backoff: delay = `base_delay_ms * 2^(attempt-1)`
  - Max attempts: 3
  - Catches: `httpx.RequestError`, `httpx.TimeoutException`

- **Key Methods**:

  **`submit_file_async(file_path, filename, tenant_id, to_formats, include_images, do_ocr)`**
  - Opens file and POSTs to `POST /v1/convert/file/async`
  - Returns: `(task_id: str, submit_ms: int)`

  **`poll_until_terminal(task_id)`**
  - Continuously polls `GET /v1/status/poll/{task_id}?wait=2`
  - Terminal statuses: `{success, completed, done, failed, error, cancelled}`
  - Timeout: `max_wait_seconds` (default 1200s)
  - Returns: `(status_payload: dict, poll_ms: int)`

  **`fetch_result(task_id)`**
  - GETs `GET /v1/result/{task_id}`
  - Returns full JSON payload (expected structure: `result["document"]["md_content"]`)

### 7. **Job Service** (`app/services/job_service.py`)
**Pattern**: High-level orchestration orchestrator; runs async background tasks

- **Workflow** (`run_job()` method):

  1. **State: submitted → running**
     - Calls `docling_client.submit_file_async()`
     - Stores `docling_task_id` + `docling_status: pending`

  2. **State: running**
     - Polls `poll_until_terminal()` until terminal status
     - Checks if result indicates success or failure

  3. **State: completed (success)**
     - Fetches full result via `fetch_result()`
     - Saves raw JSON to `raw_docling_result.json`
     - Extracts markdown content via `_extract_md()`
     - Processes images: calls `extract_and_rewrite_markdown_images()`
     - Writes final markdown to `final.md`
     - Records timing breakdown and artifact paths

  4. **Error Handling**:
     - `TimeoutError` → status: `timed_out`
     - Docling failure → status: `failed`, stores error message
     - Other exceptions → status: `failed`, logs error

- **Timing Breakdown**:
  - `submit_ms`: Time to submit async job
  - `poll_ms`: Time spent polling Docling
  - `process_ms`: Time for post-processing (image extraction, etc.)
  - `total_ms`: End-to-end time

### 8. **Markdown Image Processor** (`app/services/markdown_image_processor.py`)
**Pattern**: Regex-based extraction of base64-encoded images

- **Function**: `extract_and_rewrite_markdown_images(md_content, images_dir, image_prefix)`

- **Flow**:
  1. Regex pattern: `![alt](data:image/FORMAT;base64,BASE64DATA)`
  2. For each match:
     - Decode base64 to binary
     - Write to file: `{images_dir}/{image_prefix}_{counter}.{ext}`
     - Rewrite markdown link to file path (POSIX-style)
  3. Return: `(rewritten_md: str, image_paths: list[str])`

- **Extension Normalization**: `jpeg` → `jpg`

---

## Data Flow: Complete Request Lifecycle

### Example: Upload a PDF → Poll → Retrieve Result

```
1. CLIENT
   POST /process-document (multipart: file=sample.pdf)
   ↓
2. FASTAPI ROUTE (routes.py::process_document)
   - Validate file size
   - Create JobStore entry (status: submitted)
   - Save to outputs/{job_id}/input/sample.pdf
   - Launch async task: service.run_job(job_id, tenant_id, ...)
   - Return 202: {job_id, status: submitted, created_at: timestamp}
   ↓
3. BACKGROUND TASK (job_service.py::run_job) [Async]
   a) Update JobStore: status = running
   b) Call docling_client.submit_file_async()
      → POST /v1/convert/file/async to Docling
      ← Returns task_id (e.g., "abc123")
   c) Call docling_client.poll_until_terminal(task_id)
      → GET /v1/status/poll/abc123?wait=2
      → Loop until status in {success, completed, failed}
   d) If success:
      - fetch_result(task_id)
      - Save to outputs/{job_id}/raw_docling_result.json
      - Extract md_content
      - Extract images (base64 → files)
      - Save to outputs/{job_id}/final.md
      - Update JobStore: status = completed, output paths, image count
   e) Else if timed out:
      - Update JobStore: status = timed_out
   f) Else if error:
      - Update JobStore: status = failed, error message
   ↓
4. CLIENT POLLING
   GET /jobs/{job_id}
   ← Returns JobStatusResponse with current state
   
5. CLIENT FETCHES RESULT (when status = completed)
   GET /jobs/{job_id}/result
   ← Returns paths:
      {
        job_id,
        status: completed,
        output_md_path: "/absolute/path/final.md",
        raw_result_path: "/absolute/path/raw_docling_result.json",
        metadata_path: "/absolute/path/metadata.json"
      }
   
6. CLIENT DOWNLOADS MARKDOWN
   GET /artifacts/{job_id}/final.md
   ← Served by FastAPI static file server
```

---

## Directory Structure: Outputs

```
outputs/
├── {job_id_1}/
│   ├── metadata.json          ← Job record (Pydantic model dump)
│   ├── input/
│   │   └── sample.pdf         ← Original uploaded file
│   ├── raw_docling_result.json ← Full JSON response from Docling
│   ├── final.md               ← Processed markdown (images rewritten)
│   └── images/
│       ├── img_0001.jpg       ← Extracted image 1
│       ├── img_0002.png       ← Extracted image 2
│       └── ...
├── {job_id_2}/
│   └── ...
```

---

## Security & Multi-Tenancy

### Authentication
- **X-Api-Key Header**: Optional; required if `DOCLING_SERVE_API_KEY` is set on Docling Serve
- **X-Tenant-Id Header**: Optional; allows logical workload isolation
- Both headers forwarded from your FastAPI to Docling Serve

### Client-Side Validation
- File upload size check (50 MB default, configurable)
- File emptiness check

### No Built-In Rate Limiting
- Current implementation: No rate limiting or quota per tenant
- Production consideration: Add middleware for quota enforcement

---

## Configuration (Environment Variables)

### Docling Integration
```bash
DOCLING_BASE_URL=http://localhost:5001
DOCLING_API_KEY=<your-api-key>        # Leave blank if Docling has no auth
DOCLING_TENANT_ID=<default-tenant>    # Default tenant for all jobs
```

### Polling Behavior
```bash
POLL_WAIT_SECONDS=2.0                 # Long-poll duration
POLL_INTERVAL_SECONDS=1.0             # Retry interval
MAX_WAIT_SECONDS=1200.0               # Max polling time (20 min)
```

### Network Resilience
```bash
RETRY_MAX_ATTEMPTS=3                  # Max retries on network error
RETRY_BASE_DELAY_MS=500               # Exponential backoff base
REQUEST_TIMEOUT_SECONDS=60.0          # HTTP timeout
```

### Storage & Limits
```bash
OUTPUT_ROOT=./outputs                 # Job artifacts directory
SERVE_ARTIFACTS=true                  # Mount /artifacts endpoint
MAX_FILE_SIZE_BYTES=52428800          # 50 MB (configurable)
```

### Application
```bash
APP_NAME="Doc Pipeline Phase 1.5"
APP_ENV=dev                           # dev|prod|staging
LOG_LEVEL=INFO                        # INFO|DEBUG|WARNING
```

---

## Error Handling Strategy

### Client Upload Errors
- **413 Payload Too Large**: File exceeds `max_file_size_bytes`
- **400 Bad Request**: Empty file or missing required fields
- **422 Validation Error**: Invalid form parameters

### Docling API Errors
- **TimeoutError**: Polling exceeded `max_wait_seconds`
- **ValueError** (task not found): Docling task_id invalid
- **RequestError/TimeoutException**: Network issues (retried with exponential backoff)

### Job State on Error
- All errors set `status: failed` or `timed_out`
- Error message stored in `JobRecord.error`
- Metadata persisted to JSON for post-mortem analysis

---

## Dependencies

```
fastapi>=0.115.0           # Web framework
uvicorn[standard]>=0.30.0  # ASGI server
httpx>=0.27.0              # Async HTTP client
pydantic>=2.8.0            # Data validation
pydantic-settings>=2.4.0   # Environment config
python-multipart>=0.0.9    # Multipart form parsing
```

---

## Known Limitations & Future Enhancements

### Phase 1.5 Scope (Current)
- ✅ Single-node in-memory job store
- ✅ Async task handling with polling
- ✅ Image extraction and link rewriting
- ✅ JSON metadata persistence
- ❌ No external queue (Redis/RQ/Celery)
- ❌ No cloud storage (S3/GCS)
- ❌ No rate limiting or quota
- ❌ No request ID tracking across services

### Production Considerations
1. **Persistence**: Replace in-memory store with database (PostgreSQL/MongoDB)
2. **Scalability**: Add message queue (Redis/RQ) for distributed workers
3. **Storage**: Move outputs to cloud storage (S3) instead of local disk
4. **Observability**: Add request IDs, structured logging, tracing
5. **Resilience**: Circuit breaker for Docling API calls, retry queues
6. **Security**: Add rate limiting, quota enforcement, audit logging

---

## Testing Your API Locally

### Start Docling Serve (CPU-only)
```bash
docker run -p 5001:5001 \
  -e DOCLING_SERVE_LOG_LEVEL=INFO \
  docling-serve:cpu
```

### Start FastAPI Orchestrator
```bash
cd "c:\Users\niveb\Documents\Personal_Jothiram\Dockling Microservice"
python -m uvicorn app.main:app --host 127.0.0.1 --port 7001 --reload
```

### Submit Document
```bash
curl -X POST "http://127.0.0.1:7001/process-document" \
  -F "file=@sample.pdf" \
  -F "tenant_id=customer-1" \
  -F "to_formats=md" \
  -F "convert_include_images=true" \
  -F "convert_do_ocr=false"
```

### Poll Job Status
```bash
curl "http://127.0.0.1:7001/jobs/{job_id}"
```

### Fetch Result Paths
```bash
curl "http://127.0.0.1:7001/jobs/{job_id}/result"
```

### Download Markdown
```bash
curl "http://127.0.0.1:7001/artifacts/{job_id}/final.md"
```

---

## Summary

Your codebase implements a **robust async orchestration layer** between FastAPI and Docling Serve:

1. **Clean Separation of Concerns**: Routes → JobService → DoclingClient
2. **Async by Design**: Uses Python `asyncio` for non-blocking operations
3. **Reliable Polling**: Exponential backoff + long-polling for efficient status checks
4. **Post-Processing**: Extracts images from base64 and rewrites Markdown links
5. **State Persistence**: JSON metadata enables job recovery and audit trails
6. **Extensible Config**: Environment-driven settings for different deployments

This is a solid foundation for a production document processing pipeline. Phase 1.5 succeeds in creating a clean contract layer before adding distributed queues and cloud storage.

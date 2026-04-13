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


Other details about the API

# Configuration

The `docling-serve` executable allows to configure the server via command line
options as well as environment variables.
Configurations are divided between the settings used for the `uvicorn` asgi
server and the actual app-specific configurations.

 > [!WARNING]
> When the server is running with `reload` or with multiple `workers`, uvicorn
> will spawn multiple subprocesses. This invalidates all the values configured
> via the CLI command line options. Please use environment variables in this
> type of deployments.

## Webserver configuration

The following table shows the options which are propagated directly to the
`uvicorn` webserver runtime.

| CLI option | ENV | Default | Description |
| -----------|-----|---------|-------------|
| `--host` | `UVICORN_HOST` | `0.0.0.0` for `run`, `localhost` for `dev` | THe host to serve on. |
| `--port` | `UVICORN_PORT` | `5001` | The port to serve on. |
| `--reload` | `UVICORN_RELOAD` | `false` for `run`, `true` for `dev` | Enable auto-reload of the server when (code) files change. |
| `--workers` | `UVICORN_WORKERS` | `1` | Use multiple worker processes. |
| `--root-path` | `UVICORN_ROOT_PATH` | `""` | The root path is used to tell your app that it is being served to the outside world with some |
| `--proxy-headers` | `UVICORN_PROXY_HEADERS` | `true` | Enable/Disable X-Forwarded-Proto, X-Forwarded-For, X-Forwarded-Port to populate remote address info. |
| `--timeout-keep-alive` | `UVICORN_TIMEOUT_KEEP_ALIVE` | `60` | Timeout for the server response. |
| `--ssl-certfile` | `UVICORN_SSL_CERTFILE` |  | SSL certificate file. |
| `--ssl-keyfile` | `UVICORN_SSL_KEYFILE` |  | SSL key file. |
| `--ssl-keyfile-password` | `UVICORN_SSL_KEYFILE_PASSWORD` |  | SSL keyfile password. |

## Docling Serve configuration

THe following table describes the options to configure the Docling Serve app.

| CLI option | ENV | Default | Description |
| -----------|-----|---------|-------------|
| `-v, --verbose` | `DOCLING_SERVE_LOG_LEVEL` | `WARNING` | Set the verbosity level. CLI: `-v` for INFO, `-vv` for DEBUG. ENV: `WARNING`, `INFO`, or `DEBUG` (case-insensitive). CLI flag takes precedence over ENV. |
| `--artifacts-path` | `DOCLING_SERVE_ARTIFACTS_PATH` | unset | If set to a valid directory, the model weights will be loaded from this path |
|  | `DOCLING_SERVE_STATIC_PATH` | unset | If set to a valid directory, the static assets for the docs and UI will be loaded from this path |
|  | `DOCLING_SERVE_SCRATCH_PATH` |  | If set, this directory will be used as scratch workspace, e.g. storing the results before they get requested. If unset, a temporary created is created for this purpose. |
| `--enable-ui` | `DOCLING_SERVE_ENABLE_UI` | `false` | Enable the demonstrator UI. |
|  | `DOCLING_SERVE_ENABLE_MANAGEMENT_ENDPOINTS` | `false` | If enabled, the `/v1/memory` endpoints will provide memory statistics, otherwise it will return a forbidden 403 error. |
|  | `DOCLING_SERVE_SHOW_VERSION_INFO` | `true` | If enabled, the `/version` endpoint will provide the Docling package versions, otherwise it will return a forbidden 403 error. |
|  | `DOCLING_SERVE_ENABLE_REMOTE_SERVICES` | `false` | Allow pipeline components making remote connections. For example, this is needed when using a vision-language model via APIs. |
|  | `DOCLING_SERVE_ALLOW_EXTERNAL_PLUGINS` | `false` | Allow the selection of third-party plugins. |
|  | `DOCLING_SERVE_ALLOW_CUSTOM_VLM_CONFIG` | `false` | Allow users to specify a fully custom VLM pipeline configuration (`vlm_pipeline_custom_config`). When `false`, only presets are accepted. |
|  | `DOCLING_SERVE_ALLOW_CUSTOM_PICTURE_DESCRIPTION_CONFIG` | `false` | Allow users to specify a fully custom picture description configuration. When `false`, only presets are accepted. |
|  | `DOCLING_SERVE_ALLOW_CUSTOM_CODE_FORMULA_CONFIG` | `false` | Allow users to specify a fully custom code/formula configuration. When `false`, only presets are accepted. |
|  | `DOCLING_SERVE_SINGLE_USE_RESULTS` | `true` | If true, results can be accessed only once. If false, the results accumulate in the scratch directory. |
|  | `DOCLING_SERVE_RESULT_REMOVAL_DELAY` | `300` | When `DOCLING_SERVE_SINGLE_USE_RESULTS` is active, this is the delay before results are removed from the task registry. |
|  | `DOCLING_SERVE_MAX_DOCUMENT_TIMEOUT` | `604800` (7 days) | The maximum time for processing a document. |
|  | `DOCLING_SERVE_MAX_NUM_PAGES` |  | The maximum number of pages for a document to be processed. |
|  | `DOCLING_SERVE_MAX_FILE_SIZE` |  | The maximum file size for a document to be processed. |
|  | `DOCLING_SERVE_SYNC_POLL_INTERVAL` | `2` | Number of seconds to sleep between polling the task status in the sync endpoints. |
|  | `DOCLING_SERVE_MAX_SYNC_WAIT` | `120` | Max number of seconds a synchronous endpoint is waiting for the task completion. |
|  | `DOCLING_SERVE_LOAD_MODELS_AT_BOOT` | `True` | If enabled, the models for the default options will be loaded at boot. |
|  | `DOCLING_SERVE_OPTIONS_CACHE_SIZE` | `2` | How many DocumentConveter objects (including their loaded models) to keep in the cache. |
|  | `DOCLING_SERVE_QUEUE_MAX_SIZE` | | Size of the pages queue. Potentially so many pages opened at the same time. |
|  | `DOCLING_SERVE_OCR_BATCH_SIZE` | | Batch size for the OCR stage. |
|  | `DOCLING_SERVE_LAYOUT_BATCH_SIZE` | | Batch size for the layout detection stage. |
|  | `DOCLING_SERVE_TABLE_BATCH_SIZE` | | Batch size for the table structure stage. |
|  | `DOCLING_SERVE_BATCH_POLLING_INTERVAL_SECONDS` | | Wait time for gathering pages before starting a stage processing. |
|  | `DOCLING_SERVE_CORS_ORIGINS` | `["*"]` | A list of origins that should be permitted to make cross-origin requests. |
|  | `DOCLING_SERVE_CORS_METHODS` | `["*"]` | A list of HTTP methods that should be allowed for cross-origin requests. |
|  | `DOCLING_SERVE_CORS_HEADERS` | `["*"]` | A list of HTTP request headers that should be supported for cross-origin requests. |
|  | `DOCLING_SERVE_API_KEY` | | If specified, all the API requests must contain the header `X-Api-Key` with this value. |
|  | `DOCLING_SERVE_ENG_KIND` | `local` | The compute engine to use for the async tasks. Possible values are `local`, `rq` and `kfp`. See below for more configurations of the engines. |

### Configuration File Support

Docling Serve supports loading configuration from YAML or JSON files. This is useful for complex configurations with nested structures.

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_SERVE_CONFIG_FILE` | | Path to a YAML or JSON configuration file. Environment variables take precedence over config file values. See [examples/config.yaml](../examples/config.yaml) and [examples/config.json](../examples/config.json) for examples. |

**Priority Order:** Environment variables > Config file > Defaults

### DoclingConverterManager Configuration

The following options control the behavior of the Docling converter, including preset management and engine restrictions.

#### VLM Pipeline Control

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_SERVE_DEFAULT_VLM_PRESET` | `granite_docling` | Default VLM preset to use when user specifies "default". |
| `DOCLING_SERVE_ALLOWED_VLM_PRESETS` | `null` (all allowed) | List of allowed VLM preset IDs. Accepts JSON array (`'["preset1", "preset2"]'`) or comma-separated string (`preset1,preset2`). When set, only these presets can be used. |
| `DOCLING_SERVE_CUSTOM_VLM_PRESETS` | `{}` | Custom VLM presets defined by admin. Must be a JSON object mapping preset IDs to VlmConvertOptions. Example: `'{"my_preset": {"engine": "openai", "model": "gpt-4-vision"}}'` |
| `DOCLING_SERVE_ALLOWED_VLM_ENGINES` | `null` (all allowed) | List of allowed VLM engine types. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_ALLOW_CUSTOM_VLM_CONFIG` | `false` | Whether users can specify fully custom VLM engine configurations. |

#### Picture Description Control

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_SERVE_DEFAULT_PICTURE_DESCRIPTION_PRESET` | `smolvlm` | Default picture description preset. |
| `DOCLING_SERVE_ALLOWED_PICTURE_DESCRIPTION_PRESETS` | `null` (all allowed) | List of allowed picture description preset IDs. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_CUSTOM_PICTURE_DESCRIPTION_PRESETS` | `{}` | Custom picture description presets. Must be a JSON object. |
| `DOCLING_SERVE_ALLOWED_PICTURE_DESCRIPTION_ENGINES` | `null` (all allowed) | List of allowed picture description engine types. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_ALLOW_CUSTOM_PICTURE_DESCRIPTION_CONFIG` | `false` | Whether users can specify custom picture description configurations. |

#### Code/Formula Control

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_SERVE_DEFAULT_CODE_FORMULA_PRESET` | `default` | Default code/formula preset. |
| `DOCLING_SERVE_ALLOWED_CODE_FORMULA_PRESETS` | `null` (all allowed) | List of allowed code/formula preset IDs. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_CUSTOM_CODE_FORMULA_PRESETS` | `{}` | Custom code/formula presets. Must be a JSON object. |
| `DOCLING_SERVE_ALLOWED_CODE_FORMULA_ENGINES` | `null` (all allowed) | List of allowed code/formula engine types. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_ALLOW_CUSTOM_CODE_FORMULA_CONFIG` | `false` | Whether users can specify custom code/formula configurations. |

#### Table Structure Control

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_SERVE_DEFAULT_TABLE_STRUCTURE_KIND` | `docling_tableformer` | Default table structure kind used when user doesn't provide custom config. |
| `DOCLING_SERVE_ALLOWED_TABLE_STRUCTURE_KINDS` | `null` (all allowed) | List of allowed table structure kinds. The default kind is always implicitly allowed. Accepts JSON array or comma-separated string. Use this to block specific plugin kinds for security or policy reasons. |
| `DOCLING_SERVE_DEFAULT_TABLE_STRUCTURE_PRESET` | `tableformer_v1_accurate` | Default table structure preset to use when user specifies "default". |
| `DOCLING_SERVE_ALLOWED_TABLE_STRUCTURE_PRESETS` | `null` (all allowed) | List of allowed table structure preset IDs. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_CUSTOM_TABLE_STRUCTURE_PRESETS` | `{}` | Custom table structure presets. Must be a JSON object mapping preset IDs to table structure options with 'kind' field. |

#### Layout Control

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_SERVE_DEFAULT_LAYOUT_KIND` | `docling_layout_default` | Default layout kind used when user doesn't provide custom config. |
| `DOCLING_SERVE_ALLOWED_LAYOUT_KINDS` | `null` (all allowed) | List of allowed layout kinds. The default kind is always implicitly allowed. Accepts JSON array or comma-separated string. Use this to block specific plugin kinds for security or policy reasons. |
| `DOCLING_SERVE_DEFAULT_LAYOUT_PRESET` | `docling_layout_default` | Default layout preset to use when user specifies "default". |
| `DOCLING_SERVE_ALLOWED_LAYOUT_PRESETS` | `null` (all allowed) | List of allowed layout preset IDs. Accepts JSON array or comma-separated string. |
| `DOCLING_SERVE_CUSTOM_LAYOUT_PRESETS` | `{}` | Custom layout presets. Must be a JSON object mapping preset IDs to layout options with 'kind' field. |

**Configuration Examples:**

Using JSON arrays in environment variables:
```bash
export DOCLING_SERVE_ALLOWED_VLM_PRESETS='["granite_docling", "custom_preset"]'
export DOCLING_SERVE_CUSTOM_VLM_PRESETS='{"my_preset": {"engine": "openai"}}'
```

Using comma-separated strings (for lists only):
```bash
export DOCLING_SERVE_ALLOWED_VLM_PRESETS="granite_docling,custom_preset"
export DOCLING_SERVE_ALLOWED_LAYOUT_KINDS="docling_layout_default,layout_object_detection"
```

Using a configuration file (recommended for complex setups):
```bash
export DOCLING_SERVE_CONFIG_FILE=config.yaml
```

See [examples/config.yaml](../examples/config.yaml) for a complete configuration file example.

### Docling configuration

Some Docling settings, mostly about performance, are exposed as environment variable which can be used also when running Docling Serve.

| ENV | Default | Description |
| ----|---------|-------------|
| `DOCLING_NUM_THREADS` | `4` | Number of concurrent threads used for the `torch` CPU execution. |
| `DOCLING_DEVICE` | | Device used for the model execution. Valid values are `cpu`, `cuda`, `mps`. When unset, the best device is chosen. For CUDA-enabled environments, you can choose which GPU using the syntax `cuda:0`, `cuda:1`, ... |
| `DOCLING_PERF_PAGE_BATCH_SIZE` | `4` | Number of pages processed in the same batch. |
| `DOCLING_PERF_ELEMENTS_BATCH_SIZE` | `8` | Number of document items/elements processed in the same batch during enrichment. |
| `DOCLING_DEBUG_PROFILE_PIPELINE_TIMINGS` | `false` | When enabled, Docling will provide detailed timings information. |


### Compute engine

Docling Serve can be deployed with several possible of compute engine.
The selected compute engine will be running all the async jobs.

#### Local engine

The following table describes the options to configure the Docling Serve local engine.

| ENV | Default | Description |
|-----|---------|-------------|
| `DOCLING_SERVE_ENG_LOC_NUM_WORKERS` | 2 | Number of workers/threads processing the incoming tasks. |
| `DOCLING_SERVE_ENG_LOC_SHARE_MODELS` | False | If true, each process will share the same models among all thread workers. Otherwise, one instance of the models is allocated for each worker thread. |

#### RQ engine

The following table describes the options to configure the Docling Serve RQ engine.

| ENV | Default | Description |
|-----|---------|-------------|
| `DOCLING_SERVE_ENG_RQ_REDIS_URL` | (required) | The connection Redis url, e.g. `redis://localhost:6373/` |
| `DOCLING_SERVE_ENG_RQ_RESULTS_PREFIX` | `docling:results` | The prefix used for storing the results in Redis. |
| `DOCLING_SERVE_ENG_RQ_SUB_CHANNEL` | `docling:updates` | The channel key name used for storing communicating updates between the workers and the orchestrator. |
| `DOCLING_SERVE_ENG_RQ_RESULTS_TTL` | `14400` (4 hours) | Time To Live (in seconds) for RQ job results in Redis. This controls how long job results are kept before being automatically deleted. |
| `DOCLING_SERVE_ENG_RQ_REDIS_MAX_CONNECTIONS` | `50` | Maximum number of connections in the Redis connection pool. Increase this value when scaling to many RQ workers (e.g., 100 for 10+ workers). |
| `DOCLING_SERVE_ENG_RQ_REDIS_SOCKET_TIMEOUT` | `None` | Socket timeout in seconds for Redis operations. If not set, uses Redis client default. Set to a value (e.g., 5.0) if you experience timeout issues. |
| `DOCLING_SERVE_ENG_RQ_REDIS_SOCKET_CONNECT_TIMEOUT` | `None` | Socket connect timeout in seconds for establishing Redis connections. If not set, uses Redis client default. Set to a value (e.g., 5.0) for slow networks. |

**Scaling Recommendations for RQ Engine:**

- **Small deployments (1-4 workers):** Default settings (50 connections) are sufficient
- **Medium deployments (5-10 workers):** Set `DOCLING_SERVE_ENG_RQ_REDIS_MAX_CONNECTIONS=100`
- **Large deployments (10+ workers):** Set `DOCLING_SERVE_ENG_RQ_REDIS_MAX_CONNECTIONS=150-200`
- **Timeout settings:** Only set if experiencing connection issues. Start with 5.0 seconds for both timeouts.
- Ensure your Redis server's `maxclients` setting can accommodate all connections from all docling-serve instances and RQ workers

#### KFP engine

The following table describes the options to configure the Docling Serve KFP engine.

| ENV | Default | Description |
|-----|---------|-------------|
| `DOCLING_SERVE_ENG_KFP_ENDPOINT` |  | Must be set to the Kubeflow Pipeline endpoint. When using the in-cluster deployment, make sure to use the cluster endpoint, e.g. `https://NAME.NAMESPACE.svc.cluster.local:8888`  |
| `DOCLING_SERVE_ENG_KFP_TOKEN` |  | The authentication token for KFP. For in-cluster deployment, the app will load automatically the token of the ServiceAccount. |
| `DOCLING_SERVE_ENG_KFP_CA_CERT_PATH` |  | Path to the CA certificates for the KFP endpoint. For in-cluster deployment, the app will load automatically the internal CA. |
| `DOCLING_SERVE_ENG_KFP_SELF_CALLBACK_ENDPOINT` |  | If set, it enables internal callbacks providing status update of the KFP job. Usually something like `https://NAME.NAMESPACE.svc.cluster.local:5001/v1/callback/task/progress`. |
| `DOCLING_SERVE_ENG_KFP_SELF_CALLBACK_TOKEN_PATH` |  | The token used for authenticating the progress callback. For cluster-internal workloads, use `/run/secrets/kubernetes.io/serviceaccount/token`. |
| `DOCLING_SERVE_ENG_KFP_SELF_CALLBACK_CA_CERT_PATH` |  | The CA certificate for the progress callback. For cluster-inetrnal workloads, use `/var/run/secrets/kubernetes.io/serviceaccount/service-ca.crt`. |

### Gradio UI

When using Gradio UI and using the option to output conversion as file, Gradio uses cache to prevent files to be overwritten ([more info here](https://www.gradio.app/guides/file-access#the-gradio-cache)), and we defined the cache clean frequency of one hour to clean files older than 10hours. For situations that files need to be available to download from UI older than 10 hours, there is two options:

- Increase the older age of files to clean [here](https://github.com/docling-project/docling-serve/blob/main/docling_serve/gradio_ui.py#L483) to suffice the age desired;
- Or set the clean up manually by defining the temporary dir of Gradio to use the same as `DOCLING_SERVE_SCRATCH_PATH` absolute path. This can be achieved by setting the environment variable `GRADIO_TEMP_DIR`, that can be done via command line `export GRADIO_TEMP_DIR="<same_path_as_scratch>"` or in `Dockerfile` using `ENV GRADIO_TEMP_DIR="<same_path_as_scratch>"`. After this, set the clean of cache to `None` [here](https://github.com/docling-project/docling-serve/blob/main/docling_serve/gradio_ui.py#L483). Now, the clean up of `DOCLING_SERVE_SCRATCH_PATH` will also clean the Gradio temporary dir. (If you use this option, please remember when reversing changes to remove the environment variable `GRADIO_TEMP_DIR`, otherwise may lead to files not be available to download).

### Telemetry

THe following table describes the telemetry options for the Docling Serve app. Some deployment examples are available in [examples/OTEL.md](../examples/OTEL.md).

ENV | Default | Description |
|-----|---------|-------------|
| `DOCLING_SERVE_OTEL_ENABLE_METRICS` | true | Enable metrics collection. |
| `DOCLING_SERVE_OTEL_ENABLE_TRACES` | false | Enable trace collection. Requires a valid value for `OTEL_EXPORTER_OTLP_ENDPOINT`. |
| `DOCLING_SERVE_OTEL_ENABLE_PROMETHEUS` | true | Enable Prometheus /metrics endpoint. |
| `DOCLING_SERVE_OTEL_ENABLE_OTLP_METRICS` | `false` | Enable OTLP metrics export. |
| `DOCLING_SERVE_OTEL_SERVICE_NAME` | docling-serve | Service identification. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` |  | OTLP endpoint (for traces and optional metrics). |
| `DOCLING_SERVE_METRICS_PORT` | `None` | Enable serving /metrics endpoint on a separate port. |



# Usage

The API provides two endpoints: one for urls, one for files. This is necessary to send files directly in binary format instead of base64-encoded strings.

## Common parameters

On top of the source of file (see below), both endpoints support the same parameters.

<!-- begin: parameters-docs -->
<h4>ConvertDocumentsRequestOptions</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `from_formats` | List[InputFormat] | Input format(s) to convert from. String or list of strings. Allowed values: `docx`, `pptx`, `html`, `image`, `pdf`, `asciidoc`, `md`, `csv`, `xlsx`, `xml_uspto`, `xml_jats`, `xml_xbrl`, `mets_gbs`, `json_docling`, `audio`, `vtt`, `latex`. Optional, defaults to all formats. |
| `to_formats` | List[OutputFormat] | Output format(s) to convert to. String or list of strings. Allowed values: `md`, `json`, `yaml`, `html`, `html_split_page`, `text`, `doctags`, `vtt`. Optional, defaults to Markdown. |
| `image_export_mode` | ImageRefMode | Image export mode for the document (in case of JSON, Markdown or HTML). Allowed values: `placeholder`, `embedded`, `referenced`. Optional, defaults to Embedded. |
| `do_ocr` | bool | If enabled, the bitmap content will be processed using OCR. Boolean. Optional, defaults to true |
| `force_ocr` | bool | If enabled, replace existing text with OCR-generated text over content. Boolean. Optional, defaults to false. |
| `ocr_engine` | `ocr_engines_enum` | The OCR engine to use. String. Allowed values: `auto`, `easyocr`, `kserve_v2_ocr`, `ocrmac`, `rapidocr`, `tesserocr`, `tesseract`. Optional, defaults to `easyocr`. |
| `ocr_lang` | List[str] or NoneType | List of languages used by the OCR engine. Note that each OCR engine has different values for the language names. String or list of strings. Optional, defaults to empty. |
| `ocr_preset` | str | Preset ID for OCR engine. |
| `ocr_custom_config` | Dict[str, Any] or NoneType | Custom configuration for OCR engine. Use this to specify engine-specific options beyond `ocr_lang`. Each OCR engine kind has its own configuration schema. |
| `pdf_backend` | PdfBackend | The PDF backend to use. String. Allowed values: `pypdfium2`, `docling_parse`, `dlparse_v1`, `dlparse_v2`, `dlparse_v4`. Optional, defaults to `docling_parse`. |
| `table_mode` | TableFormerMode | Mode to use for table structure, String. Allowed values: `fast`, `accurate`. Optional, defaults to accurate. |
| `table_cell_matching` | bool | If true, matches table cells predictions back to PDF cells. Can break table output if PDF cells are merged across table columns. If false, let table structure model define the text cells, ignore PDF cells. |
| `pipeline` | ProcessingPipeline | Choose the pipeline to process PDF or image files. |
| `page_range` | Tuple | Only convert a range of pages. The page number starts at 1. |
| `document_timeout` | float | The timeout for processing each document, in seconds. |
| `abort_on_error` | bool | Abort on error if enabled. Boolean. Optional, defaults to false. |
| `do_table_structure` | bool | If enabled, the table structure will be extracted. Boolean. Optional, defaults to true. |
| `include_images` | bool | If enabled, images will be extracted from the document. Boolean. Optional, defaults to true. |
| `images_scale` | float | Scale factor for images. Float. Optional, defaults to 2.0. |
| `md_page_break_placeholder` | str | Add this placeholder between pages in the markdown output. |
| `do_code_enrichment` | bool | If enabled, perform OCR code enrichment. Boolean. Optional, defaults to false. |
| `do_formula_enrichment` | bool | If enabled, perform formula OCR, return LaTeX code. Boolean. Optional, defaults to false. |
| `do_picture_classification` | bool | If enabled, classify pictures in documents. Boolean. Optional, defaults to false. |
| `do_chart_extraction` | bool | If enabled, extract numeric data from charts. Boolean. Optional, defaults to false. |
| `do_picture_description` | bool | If enabled, describe pictures in documents. Boolean. Optional, defaults to false. |
| `picture_description_area_threshold` | float | Minimum percentage of the area for a picture to be processed with the models. |
| `picture_description_local` | PictureDescriptionLocal or NoneType | DEPRECATED: Options for running a local vision-language model in the picture description. The parameters refer to a model hosted on Hugging Face. This parameter is mutually exclusive with `picture_description_api`. Please migrate to `picture_description_preset` or `picture_description_custom_config`. |
| `picture_description_api` | PictureDescriptionApi or NoneType | DEPRECATED: API details for using a vision-language model in the picture description. This parameter is mutually exclusive with `picture_description_local`. Please migrate to `picture_description_preset` or `picture_description_custom_config`. |
| `vlm_pipeline_model` | VlmModelType or NoneType | DEPRECATED: Preset of local and API models for the `vlm` pipeline. This parameter is mutually exclusive with `vlm_pipeline_model_local` and `vlm_pipeline_model_api`. Use the other options for more parameters. Please migrate to `vlm_pipeline_preset` or `vlm_pipeline_custom_config`. |
| `vlm_pipeline_model_local` | VlmModelLocal or NoneType | DEPRECATED: Options for running a local vision-language model for the `vlm` pipeline. The parameters refer to a model hosted on Hugging Face. This parameter is mutually exclusive with `vlm_pipeline_model_api` and `vlm_pipeline_model`. Please migrate to `vlm_pipeline_preset` or `vlm_pipeline_custom_config`. |
| `vlm_pipeline_model_api` | VlmModelApi or NoneType | DEPRECATED: API details for using a vision-language model for the `vlm` pipeline. This parameter is mutually exclusive with `vlm_pipeline_model_local` and `vlm_pipeline_model`. Please migrate to `vlm_pipeline_preset` or `vlm_pipeline_custom_config`. |
| `vlm_pipeline_preset` | str or NoneType | Preset ID to use (e.g., "default", "`granite_docling`"). Use "default" for stable, admin-controlled configuration. |
| `picture_description_preset` | str or NoneType | Preset ID for picture description. |
| `code_formula_preset` | str or NoneType | Preset ID for code/formula extraction. |
| `vlm_pipeline_custom_config` | VlmConvertOptions or dict or NoneType | Custom VLM configuration including model spec and engine options. Only available if admin allows it. Must include '`model_spec`' and '`engine_options`'. |
| `picture_description_custom_config` | PictureDescriptionVlmEngineOptions or dict or NoneType | Custom picture description configuration including model spec and engine options. |
| `code_formula_custom_config` | CodeFormulaVlmOptions or dict or NoneType | Custom code/formula extraction configuration including model spec and engine options. |
| `table_structure_preset` | str or NoneType | Preset ID for table structure detection. |
| `table_structure_custom_config` | Dict[str, Any] or NoneType | Custom configuration for table structure model. Use this to specify a non-default kind with its options. The 'kind' field in the config dict determines which table structure implementation to use. If not specified, uses the default kind with preset configuration. |
| `layout_custom_config` | Dict[str, Any] or NoneType | Custom configuration for layout model. Use this to specify a non-default kind with its options. The 'kind' field in the config dict determines which layout implementation to use. If not specified, uses the default kind with preset configuration. |
| `layout_preset` | str or NoneType | Preset ID for layout detection. |
| `picture_classification_preset` | str or NoneType | Preset ID for picture classification. |
| `picture_classification_custom_config` | Dict[str, Any] or NoneType | Custom configuration for picture classification. Use this to specify custom options for the picture classifier. The configuration should match DocumentPictureClassifierOptions schema. |

<h4>CodeFormulaVlmOptions</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `engine_options` | BaseVlmEngineOptions | Runtime configuration (transformers, mlx, api, etc.) |
| `model_spec` | VlmModelSpec | Model specification with runtime-specific overrides |
| `scale` | float | Image scaling factor for preprocessing |
| `max_size` | int or NoneType | Maximum image dimension (width or height) |
| `extract_code` | bool | Extract code blocks |
| `extract_formulas` | bool | Extract mathematical formulas |

<h4>VlmModelSpec</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `name` | str | Human-readable model name |
| `default_repo_id` | str | Default HuggingFace repository ID |
| `revision` | str | Default model revision |
| `prompt` | str | Prompt template for this model |
| `response_format` | ResponseFormat | Expected response format from the model |
| `supported_engines` | Set or NoneType | Set of supported engines (None = all supported) |
| `engine_overrides` | Dict[VlmEngineType, EngineModelConfig] | Engine-specific configuration overrides |
| `api_overrides` | Dict[VlmEngineType, ApiModelConfig] | API-specific configuration overrides |
| `trust_remote_code` | bool | Whether to trust remote code for this model |
| `stop_strings` | List[str] | Stop strings for generation |
| `max_new_tokens` | int | Maximum number of new tokens to generate |

<h4>BaseVlmEngineOptions</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `engine_type` | VlmEngineType | Type of inference engine to use |

<h4>PictureDescriptionVlmEngineOptions</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `batch_size` | int | Number of images to process in a single batch during picture description. Higher values improve throughput but increase memory usage. Adjust based on available GPU/CPU memory. |
| `scale` | float | Scaling factor for image resolution before processing. Higher values (e.g., 2.0) provide more detail for the vision model but increase processing time and memory. Range: 0.5-4.0 typical. |
| `picture_area_threshold` | float | Minimum picture area as fraction of page area (0.0-1.0) to trigger description. Pictures smaller than this threshold are skipped. Use lower values (e.g., 0.01) to describe small images. |
| `classification_allow` | List[PictureClassificationLabel] or NoneType | List of picture classification labels to allow for description. Only pictures classified with these labels will be processed. If None, all picture types are allowed unless explicitly denied. Use to focus description on specific image types (e.g., diagrams, charts). |
| `classification_deny` | List[PictureClassificationLabel] or NoneType | List of picture classification labels to exclude from description. Pictures classified with these labels will be skipped. If None, no picture types are denied unless not in allow list. Use to exclude unwanted image types (e.g., decorative images, logos). |
| `classification_min_confidence` | float | Minimum classification confidence score (0.0-1.0) required for a picture to be processed. Pictures with classification confidence below this threshold are skipped. Higher values ensure only confidently classified images are described. Range: 0.0 (no filtering) to 1.0 (maximum confidence). |
| `engine_options` | BaseVlmEngineOptions | Runtime configuration (transformers, mlx, api, etc.) |
| `model_spec` | VlmModelSpec | Model specification with runtime-specific overrides |
| `prompt` | str | Prompt template for the vision model. Customize to control description style, detail level, or focus. |
| `generation_config` | Dict[str, Any] | Generation configuration for text generation. Controls output length, sampling strategy, temperature, etc. |

<h4>VlmConvertOptions</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `engine_options` | BaseVlmEngineOptions | Runtime configuration (transformers, mlx, api, etc.) |
| `model_spec` | VlmModelSpec | Model specification with runtime-specific overrides |
| `scale` | float | Image scaling factor for preprocessing |
| `max_size` | int or NoneType | Maximum image dimension (width or height) |
| `batch_size` | int | Batch size for processing multiple pages |
| `force_backend_text` | bool | Force use of backend text extraction instead of VLM |

<h4>VlmModelApi</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `url` | AnyUrl | Endpoint which accepts openai-api compatible requests. |
| `headers` | Dict[str, str] | Headers used for calling the API endpoint. For example, it could include authentication headers. |
| `params` | Dict[str, Any] | Model parameters. |
| `timeout` | float | Timeout for the API request. |
| `concurrency` | int | Maximum number of concurrent requests to the API. |
| `prompt` | str | Prompt used when calling the vision-language model. |
| `scale` | float | Scale factor of the images used. |
| `response_format` | ResponseFormat | Type of response generated by the model. |
| `temperature` | float | Temperature parameter controlling the reproducibility of the result. |

<h4>VlmModelLocal</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `repo_id` | str | Repository id from the Hugging Face Hub. |
| `prompt` | str | Prompt used when calling the vision-language model. |
| `scale` | float | Scale factor of the images used. |
| `response_format` | ResponseFormat | Type of response generated by the model. |
| `inference_framework` | InferenceFramework | Inference framework to use. |
| `transformers_model_type` | TransformersModelType | Type of transformers auto-model to use. |
| `extra_generation_config` | Dict[str, Any] | Config from https://huggingface.co/docs/transformers/en/main_classes/text_generation#transformers.GenerationConfig |
| `temperature` | float | Temperature parameter controlling the reproducibility of the result. |

<h4>PictureDescriptionApi</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `url` | AnyUrl | Endpoint which accepts openai-api compatible requests. |
| `headers` | Dict[str, str] | Headers used for calling the API endpoint. For example, it could include authentication headers. |
| `params` | Dict[str, Any] | Model parameters. |
| `timeout` | float | Timeout for the API request. |
| `concurrency` | int | Maximum number of concurrent requests to the API. |
| `prompt` | str | Prompt used when calling the vision-language model. |
| `classification_allow` | List[PictureClassificationLabel] or NoneType | Only describe pictures whose predicted class is in this allow-list. |
| `classification_deny` | List[PictureClassificationLabel] or NoneType | Do not describe pictures whose predicted class is in this deny-list. |
| `classification_min_confidence` | float | Minimum classification confidence required before a picture can be described. |

<h4>PictureDescriptionLocal</h4>

| Field Name | Type | Description |
|------------|------|-------------|
| `repo_id` | str | Repository id from the Hugging Face Hub. |
| `prompt` | str | Prompt used when calling the vision-language model. |
| `generation_config` | Dict[str, Any] | Config from https://huggingface.co/docs/transformers/en/main_classes/text_generation#transformers.GenerationConfig |
| `classification_allow` | List[PictureClassificationLabel] or NoneType | Only describe pictures whose predicted class is in this allow-list. |
| `classification_deny` | List[PictureClassificationLabel] or NoneType | Do not describe pictures whose predicted class is in this deny-list. |
| `classification_min_confidence` | float | Minimum classification confidence required before a picture can be described. |

<!-- end: parameters-docs -->

### Authentication

When authentication is activated (see the parameter `DOCLING_SERVE_API_KEY` in [configuration.md](./configuration.md)), all the API requests **must** provide the header `X-Api-Key` with the correct secret key.

## Convert endpoints

### Source endpoint

The endpoint is `/v1/convert/source`, listening for POST requests of JSON payloads.

On top of the above parameters, you must send the URL(s) of the document you want process with either the `http_sources` or `file_sources` fields.
The first is fetching URL(s) (optionally using with extra headers), the second allows to provide documents as base64-encoded strings.
No `options` is required, they can be partially or completely omitted.

Simple payload example:

```json
{
  "http_sources": [{"url": "https://arxiv.org/pdf/2206.01062"}]
}
```

<details>

<summary>Complete payload example:</summary>

```json
{
  "options": {
    "from_formats": ["docx", "pptx", "html", "image", "pdf", "asciidoc", "md", "xlsx"],
    "to_formats": ["md", "json", "html", "text", "doctags"],
    "image_export_mode": "placeholder",
    "do_ocr": true,
    "force_ocr": false,
    "ocr_engine": "easyocr",
    "ocr_lang": ["en"],
    "pdf_backend": "dlparse_v2",
    "table_mode": "fast",
    "abort_on_error": false,
  },
  "http_sources": [{"url": "https://arxiv.org/pdf/2206.01062"}]
}
```

</details>

<details>

<summary>CURL example:</summary>

```sh
curl -X 'POST' \
  'http://localhost:5001/v1/convert/source' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "options": {
    "from_formats": [
      "docx",
      "pptx",
      "html",
      "image",
      "pdf",
      "asciidoc",
      "md",
      "xlsx"
    ],
    "to_formats": ["md", "json", "html", "text", "doctags"],
    "image_export_mode": "placeholder",
    "do_ocr": true,
    "force_ocr": false,
    "ocr_engine": "easyocr",
    "ocr_lang": [
      "fr",
      "de",
      "es",
      "en"
    ],
    "pdf_backend": "dlparse_v2",
    "table_mode": "fast",
    "abort_on_error": false,
    "do_table_structure": true,
    "include_images": true,
    "images_scale": 2
  },
  "http_sources": [{"url": "https://arxiv.org/pdf/2206.01062"}]
}'
```

</details>

<details>
<summary>Python example:</summary>

```python
import httpx

async_client = httpx.AsyncClient(timeout=60.0)
url = "http://localhost:5001/v1/convert/source"
payload = {
  "options": {
    "from_formats": ["docx", "pptx", "html", "image", "pdf", "asciidoc", "md", "xlsx"],
    "to_formats": ["md", "json", "html", "text", "doctags"],
    "image_export_mode": "placeholder",
    "do_ocr": True,
    "force_ocr": False,
    "ocr_engine": "easyocr",
    "ocr_lang": "en",
    "pdf_backend": "dlparse_v2",
    "table_mode": "fast",
    "abort_on_error": False,
  },
  "http_sources": [{"url": "https://arxiv.org/pdf/2206.01062"}]
}

response = await async_client_client.post(url, json=payload)

data = response.json()
```

</details>

#### File as base64

The `file_sources` argument in the endpoint allows to send files as base64-encoded strings.
When your PDF or other file type is too large, encoding it and passing it inline to curl
can lead to an “Argument list too long” error on some systems. To avoid this, we write
the JSON request body to a file and have curl read from that file.

<details>
<summary>CURL steps:</summary>

```sh
# 1. Base64-encode the file
B64_DATA=$(base64 -w 0 /path/to/file/pdf-to-convert.pdf)

# 2. Build the JSON with your options
cat <<EOF > /tmp/request_body.json
{
  "options": {
  },
  "file_sources": [{
    "base64_string": "${B64_DATA}",
    "filename": "pdf-to-convert.pdf"
  }]
}
EOF

# 3. POST the request to the docling service
curl -X POST "localhost:5001/v1/convert/source" \
     -H "Content-Type: application/json" \
     -d @/tmp/request_body.json
```

</details>

### File endpoint

The endpoint is: `/v1/convert/file`, listening for POST requests of Form payloads (necessary as the files are sent as multipart/form data). You can send one or multiple files.

<details>
<summary>CURL example:</summary>

```sh
curl -X 'POST' \
  'http://127.0.0.1:5001/v1/convert/file' \
  -H 'accept: application/json' \
  -H 'Content-Type: multipart/form-data' \
  -F 'ocr_engine=easyocr' \
  -F 'pdf_backend=dlparse_v2' \
  -F 'from_formats=pdf' \
  -F 'from_formats=docx' \
  -F 'force_ocr=false' \
  -F 'image_export_mode=embedded' \
  -F 'ocr_lang=en' \
  -F 'ocr_lang=pl' \
  -F 'table_mode=fast' \
  -F 'files=@2206.01062v1.pdf;type=application/pdf' \
  -F 'abort_on_error=false' \
  -F 'to_formats=md' \
  -F 'to_formats=text' \
  -F 'do_ocr=true'
```

</details>

<details>
<summary>Python example:</summary>

```python
import httpx

async_client = httpx.AsyncClient(timeout=60.0)
url = "http://localhost:5001/v1/convert/file"
parameters = {
"from_formats": ["docx", "pptx", "html", "image", "pdf", "asciidoc", "md", "xlsx"],
"to_formats": ["md", "json", "html", "text", "doctags"],
"image_export_mode": "placeholder",
"do_ocr": True,
"force_ocr": False,
"ocr_engine": "easyocr",
"ocr_lang": ["en"],
"pdf_backend": "dlparse_v2",
"table_mode": "fast",
"abort_on_error": False,
}

current_dir = os.path.dirname(__file__)
file_path = os.path.join(current_dir, '2206.01062v1.pdf')

files = {
    'files': ('2206.01062v1.pdf', open(file_path, 'rb'), 'application/pdf'),
}

response = await async_client.post(url, files=files, data=parameters)
assert response.status_code == 200, "Response should be 200 OK"

data = response.json()
```

</details>

### Picture description options

When the picture description enrichment is activated, users may specify which model and which execution mode to use for this task. There are two choices for the execution mode: _local_ will run the vision-language model directly, _api_ will invoke an external API endpoint.

The local option is specified with:

```jsonc
{
  "picture_description_local": {
    "repo_id": "",  // Repository id from the Hugging Face Hub.
    "generation_config": {"max_new_tokens": 200, "do_sample": false},  // HF generation config.
    "prompt": "Describe this image in a few sentences. ",  // Prompt used when calling the vision-language model.
  }
}
```

The possible values for `generation_config` are documented in the [Hugging Face text generation docs](https://huggingface.co/docs/transformers/en/main_classes/text_generation#transformers.GenerationConfig).

The api option is specified with:

```jsonc
{
  "picture_description_api": {
    "url": "",  // Endpoint which accepts openai-api compatible requests.
    "headers": {},  // Headers used for calling the API endpoint. For example, it could include authentication headers.
    "params": {},  // Model parameters.
    "timeout": 20,  // Timeout for the API request.
    "prompt": "Describe this image in a few sentences. ",  // Prompt used when calling the vision-language model.
  }
}
```

Example URLs are:

- `http://localhost:8000/v1/chat/completions` for the local vllm api, with example `picture_description_api`:
  - the `HuggingFaceTB/SmolVLM-256M-Instruct` model

    ```json
    {
      "url": "http://localhost:8000/v1/chat/completions",
      "params": {
        "model": "HuggingFaceTB/SmolVLM-256M-Instruct",
        "max_completion_tokens": 200,
      }
    }
    ```

  - the `ibm-granite/granite-vision-3.2-2b` model

    ```json
    {
      "url": "http://localhost:8000/v1/chat/completions",
      "params": {
        "model": "ibm-granite/granite-vision-3.2-2b",
        "max_completion_tokens": 200,
      }
    }
    ```

- `http://localhost:11434/v1/chat/completions` for the local Ollama api, with example `picture_description_api`:
  - the `granite3.2-vision:2b` model

    ```json
    {
      "url": "http://localhost:11434/v1/chat/completions",
      "params": {
        "model": "granite3.2-vision:2b"
      }
    }
    ```

Note that when using `picture_description_api`, the server must be launched with `DOCLING_SERVE_ENABLE_REMOTE_SERVICES=true`.

## Response format

The response can be a JSON Document or a File.

- If you process only one file, the response will be a JSON document with the following format:

  ```jsonc
  {
    "document": {
      "md_content": "",
      "json_content": {},
      "html_content": "",
      "text_content": "",
      "doctags_content": ""
      },
    "status": "<success|partial_success|skipped|failure>",
    "processing_time": 0.0,
    "timings": {},
    "errors": []
  }
  ```

  Depending on the value you set in `output_formats`, the different items will be populated with their respective results or empty.

  `processing_time` is the Docling processing time in seconds, and `timings` (when enabled in the backend) provides the detailed
  timing of all the internal Docling components.

- If you set the parameter `target` to the zip mode, the response will be a zip file.
- If multiple files are generated (multiple inputs, or one input but multiple outputs with the zip target mode), the response will be a zip file.

## Asynchronous API

Both `/v1/convert/source` and `/v1/convert/file` endpoints are available as asynchronous variants.
The advantage of the asynchronous endpoints is the possible to interrupt the connection, check for the progress update and fetch the result.
This approach is more resilient against network instabilities and allows the client application logic to easily interleave conversion with other tasks.

Launch an asynchronous conversion with:

- `POST /v1/convert/source/async` when providing the input as sources.
- `POST /v1/convert/file/async` when providing the input as multipart-form files.

The response format is a task detail:

```jsonc
{
  "task_id": "<task_id>",  // the task_id which can be used for the next operations
  "task_status": "pending|started|success|failure",  // the task status
  "task_position": 1,  // the position in the queue
  "task_meta": null,  // metadata e.g. how many documents are in the total job and how many have been converted
}
```

### Polling status

For checking the progress of the conversion task and wait for its completion, use the endpoint:

- `GET /v1/status/poll/{task_id}`

<details>
<summary>Example waiting loop:</summary>

```python
import time
import httpx

# ...
# response from the async task submission
task = response.json()

while task["task_status"] not in ("success", "failure"):
    response = httpx.get(f"{base_url}/status/poll/{task['task_id']}")
    task = response.json()

    time.sleep(5)
```

<details>

### Subscribe with websockets

Using websocket you can get the client application being notified about updates of the conversion task.
To start the websocket connection, use the endpoint:

- `/v1/status/ws/{task_id}`

Websocket messages are JSON object with the following structure:

```jsonc
{
  "message": "connection|update|error",  // type of message being sent
  "task": {},  // the same content of the task description
  "error": "",  // description of the error
}
```

<details>
<summary>Example websocket usage:</summary>

```python
from websockets.sync.client import connect

uri = f"ws://{base_url}/v1/status/ws/{task['task_id']}"
with connect(uri) as websocket:
    for message in websocket:
        try:
            payload = json.loads(message)
            if payload["message"] == "error":
                break
            if payload["message"] == "update" and payload["task"]["task_status"] in ("success", "failure"):
                break
        except:
          break
```

</details>

### Fetch results

When the task is completed, the result can be fetched with the endpoint:

- `GET /v1/result/{task_id}`


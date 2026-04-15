# Conversion Parameters Implementation Guide

## Overview

This implementation provides a complete three-tier architecture for exposing Docling conversion parameters with optional Azure OpenAI image description integration. Users can now fine-tune document processing with 10+ configurable parameters.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ TIER 1: API Routes (routes.py)                              │
│ • Accept all parameters as form fields                      │
│ • Validate form input                                        │
│ • Create ConversionOptions Pydantic model                   │
│ • Pass to JobService                                        │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ TIER 2: Job Service (job_service.py)                        │
│ • Receive ConversionOptions from routes                     │
│ • Store options in JobRecord for audit trail                │
│ • Build Azure OpenAI config if do_picture_description=true  │
│ • Pass both to DoclingClient                                │
└────────────────────────┬────────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────────┐
│ TIER 3: Docling Client (docling_client.py)                  │
│ • Receive ConversionOptions from JobService                 │
│ • Build complete data payload with all parameters           │
│ • Convert booleans to lowercase strings for Docling API     │
│ • Include picture_description_api config if provided        │
│ • Submit to Docling Serve at /v1/convert/file/async         │
└─────────────────────────────────────────────────────────────┘
```

## Parameter Categories

### Tier 1: Essential Parameters (Performance/Quality Trade-offs)
These parameters control the fundamental conversion behavior:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `table_mode` | Literal["fast", "accurate"] | "accurate" | Table processing strategy - fast mode is quicker, accurate mode is thorough |
| `do_ocr` | bool | False | Enable Optical Character Recognition for scanned documents |
| `ocr_engine` | Literal["auto", "easyocr", "rapidocr", "tesseract"] | "easyocr" | OCR engine selection - affects speed/accuracy trade-off |
| `image_export_mode` | Literal["placeholder", "embedded", "referenced"] | "embedded" | How images are handled in output |

### Tier 2: Important Parameters (Output Customization)
These parameters control output quality and features:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `images_scale` | float > 0 | 2.0 | Scale factor for image processing |
| `include_images` | bool | True | Whether to include images in output |
| `do_picture_description` | bool | False | Enable Azure OpenAI image descriptions |
| `picture_description_prompt` | str \| None | None | Custom prompt for image descriptions |

### Tier 3: Advanced Parameters (Expert Settings)
These parameters are for advanced use cases:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `page_range_start` | int > 0 \| None | None | First page to process (1-indexed) |
| `page_range_end` | int > 0 \| None | None | Last page to process (inclusive) |
| `pdf_backend` | Literal["pypdfium2", "docling_parse", "dlparse_v1", "dlparse_v2", "dlparse_v4"] | "docling_parse" | PDF parsing backend |
| `document_timeout` | float \| None | None | Processing timeout in seconds |
| `abort_on_error` | bool | False | Stop processing on first error |

## API Usage Examples

### Basic Usage (All Defaults)
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@document.pdf"
```

### Enable OCR with Accurate Table Mode
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@document.pdf" \
  -F "do_ocr=true" \
  -F "ocr_engine=easyocr" \
  -F "table_mode=accurate"
```

### Enable Azure OpenAI Picture Description
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@document.pdf" \
  -F "do_picture_description=true" \
  -F "picture_description_prompt=Describe this technical diagram"
```

### Process Only Pages 5-10 with Fast Table Mode
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@document.pdf" \
  -F "page_range_start=5" \
  -F "page_range_end=10" \
  -F "table_mode=fast"
```

### Comprehensive Configuration
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@document.pdf" \
  -F "table_mode=accurate" \
  -F "do_ocr=true" \
  -F "ocr_engine=easyocr" \
  -F "image_export_mode=embedded" \
  -F "images_scale=2.5" \
  -F "include_images=true" \
  -F "do_picture_description=true" \
  -F "picture_description_prompt=Analyze this business chart" \
  -F "page_range_start=1" \
  -F "page_range_end=50" \
  -F "pdf_backend=docling_parse" \
  -F "document_timeout=120" \
  -F "abort_on_error=false"
```

## Azure OpenAI Configuration

### Setup Steps

1. **Get Azure Credentials**
   - Log in to Azure Portal
   - Navigate to your OpenAI resource
   - Get: Resource name, API key, Deployment name

2. **Set Environment Variables**
   - Copy `.env.example` to `.env`
   - Fill in the Azure OpenAI settings:
     ```env
     AZURE_OPENAI_API_KEY=your-api-key
     AZURE_OPENAI_RESOURCE=your-resource-name
     AZURE_OPENAI_DEPLOYMENT=your-deployment-name
     AZURE_OPENAI_API_VERSION=2024-02-15-preview
     ```

3. **Test the Configuration**
   ```bash
   curl -X POST http://localhost:7001/api/v1/process-document \
     -F "file=@test.pdf" \
     -F "do_picture_description=true"
   ```

### Azure OpenAI Request Format

The implementation automatically builds the correct Azure OpenAI request format:

```json
{
  "url": "https://{resource}.openai.azure.com/deployments/{deployment}/chat/completions?api-version={api_version}",
  "headers": {
    "api-key": "{api_key}",
    "Content-Type": "application/json"
  },
  "params": {
    "model": "{deployment}"
  },
  "prompt": "Describe this image in detail.",
  "timeout": 30,
  "concurrency": 3
}
```

**Note:** Azure OpenAI uses `api-key` header, not `Authorization: Bearer` like standard OpenAI.

## Implementation Details

### ConversionOptions Model (job_models.py)
```python
class ConversionOptions(BaseModel):
    table_mode: Literal["fast", "accurate"] = "accurate"
    do_ocr: bool = False
    ocr_engine: Literal["auto", "easyocr", "rapidocr", "tesseract"] = "easyocr"
    image_export_mode: Literal["placeholder", "embedded", "referenced"] = "embedded"
    images_scale: float = 2.0  # validated > 0
    include_images: bool = True
    do_picture_description: bool = False
    picture_description_prompt: str | None = None
    page_range_start: int | None = None  # validated > 0
    page_range_end: int | None = None    # validated > 0
    pdf_backend: Literal["pypdfium2", "docling_parse", "dlparse_v1", "dlparse_v2", "dlparse_v4"] = "docling_parse"
    document_timeout: float | None = None
    abort_on_error: bool = False
```

### JobService Azure Config Builder (job_service.py)
```python
def _build_azure_openai_config(self, prompt: str | None = None) -> dict[str, Any]:
    """Build Azure OpenAI picture description config."""
    # Validates all 4 required settings are present
    # Returns properly formatted config dict with api-key header
    # Includes timeout and concurrency settings
```

### DoclingClient Submit with Options (docling_client.py)
```python
async def submit_file_async(
    self,
    file_path: str,
    filename: str,
    tenant_id: str | None = None,
    to_formats: str = "md",
    conversion_options: ConversionOptions | None = None,
    picture_description_api: dict[str, Any] | None = None,
) -> tuple[str, int]:
    # Builds complete data payload from ConversionOptions
    # Converts booleans to lowercase strings for Docling API
    # Handles page_range tuple creation
    # Includes picture_description_api JSON if provided
```

## Data Flow Example

For this API call:
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@doc.pdf" \
  -F "do_ocr=true" \
  -F "do_picture_description=true" \
  -F "table_mode=fast"
```

**Step 1: Routes Layer** (`routes.py`)
- Receives form parameters
- Creates `ConversionOptions(do_ocr=True, do_picture_description=True, table_mode="fast", ...)`
- Validates all parameters
- Creates job and calls `service.run_job(job_id, tenant_id, "md", conversion_options)`

**Step 2: Service Layer** (`job_service.py`)
- Receives `ConversionOptions` with do_picture_description=True
- Calls `_build_azure_openai_config()` to build Azure config
- Updates JobRecord with conversion_options for audit trail
- Calls `docling_client.submit_file_async(..., conversion_options, picture_description_api)`

**Step 3: Client Layer** (`docling_client.py`)
- Receives both `ConversionOptions` and `picture_description_api`
- Builds POST data:
  ```python
  data = {
      "to_formats": "md",
      "table_mode": "fast",
      "do_ocr": "true",  # converted from boolean
      "do_picture_description": "true",
      "picture_description_api": "{...json...}",
      # ... other parameters ...
  }
  ```
- POSTs to Docling Serve at `/v1/convert/file/async`

## Validation

All parameters are validated at multiple layers:

### Pydantic Validation (job_models.py)
- Literal types enforce enum constraints
- Field validators check numeric ranges
- page_range_start and page_range_end validated to be > 0
- images_scale validated to be > 0

### FastAPI Route Validation (routes.py)
- Form field types validated automatically
- Try-catch block around ConversionOptions instantiation
- Returns 422 (Unprocessable Entity) on validation errors

### Azure Config Validation (job_service.py)
- All 4 required fields checked before building config
- Returns ValueError with specific missing field information
- Caught in run_job() and stored as job error

## Result Storage

All conversion options are stored in the JobRecord and returned via the result endpoint:

```json
{
  "job_id": "uuid",
  "status": "completed",
  "conversion_options": {
    "table_mode": "fast",
    "do_ocr": true,
    "ocr_engine": "easyocr",
    "do_picture_description": true,
    // ... all other parameters ...
  },
  "output_md_path": "/path/to/final.md",
  "images_count": 5,
  // ... other fields ...
}
```

This enables:
- **Audit trails**: Track what conversion settings were used for each job
- **Reproducibility**: Re-run jobs with identical settings
- **Debugging**: Understand which options led to specific outputs

## Error Handling

### Invalid Parameter Values
```
POST /process-document with invalid table_mode="invalid"
Response: 422 Unprocessable Entity
{
  "detail": "Invalid conversion options: 2 validation errors..."
}
```

### Missing Azure Configuration
```
POST /process-document with do_picture_description=true but AZURE_OPENAI_API_KEY not set
Response: Job fails with message: "Azure OpenAI configuration error: AZURE_OPENAI_API_KEY not configured"
```

### Parameter Validation Errors
- `images_scale <= 0`: Rejected by Pydantic validator
- `page_range_start > page_range_end`: No explicit validation (Docling handles)
- `document_timeout < 0`: No explicit validation (treated as valid)

## Performance Considerations

### Parameter Trade-offs
| Setting | Performance Impact | Quality Impact |
|---------|-------------------|----------------|
| `table_mode=fast` | ↑ Faster | ↓ Less accurate tables |
| `do_ocr=true` | ↓ Slower | ↑ Better scanned doc support |
| `images_scale=1.0` | ↑ Faster | ↓ Lower image quality |
| `do_picture_description=true` | ↓ Much slower | ↑ Enhanced image metadata |

### Recommended Configurations

**Fast Processing** (scanned PDFs, real-time needs)
```
table_mode=fast
do_ocr=false
images_scale=1.0
do_picture_description=false
```

**Balanced** (most documents)
```
table_mode=accurate
do_ocr=true
ocr_engine=easyocr
images_scale=2.0
do_picture_description=false
```

**High Quality** (legal/financial documents)
```
table_mode=accurate
do_ocr=true
ocr_engine=easyocr
images_scale=2.5
do_picture_description=true
abort_on_error=true
```

## Testing

### Unit Tests for ConversionOptions Validation
```python
# Valid: All defaults
opts = ConversionOptions()
assert opts.table_mode == "accurate"

# Valid: Custom values
opts = ConversionOptions(table_mode="fast", do_ocr=True)

# Invalid: Bad enum value
with pytest.raises(ValueError):
    ConversionOptions(table_mode="invalid")

# Invalid: Negative scale
with pytest.raises(ValueError):
    ConversionOptions(images_scale=-1.0)
```

### Integration Tests
```bash
# Test basic flow
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@test.pdf" > response.json
job_id=$(jq -r '.job_id' response.json)

# Poll for completion
curl http://localhost:7001/api/v1/jobs/$job_id

# Get results with conversion_options
curl http://localhost:7001/api/v1/jobs/$job_id/result | jq '.conversion_options'
```

## Files Modified

1. **app/models/job_models.py**
   - Added `ConversionOptions` model with validators
   - Extended `JobRecord` with `conversion_options` field
   - Extended `JobResultResponse` to include `conversion_options`

2. **app/core/config.py**
   - Added 4 Azure OpenAI environment variables

3. **app/api/routes.py**
   - Expanded `/process-document` endpoint with all 10 parameters
   - Added ConversionOptions instantiation and validation
   - Updated `/jobs/{job_id}/result` to return conversion_options

4. **app/services/job_service.py**
   - Added `_build_azure_openai_config()` method
   - Updated `run_job()` signature to accept `ConversionOptions`
   - Added Azure config building logic

5. **app/services/docling_client.py**
   - Updated `submit_file_async()` to accept `ConversionOptions` and `picture_description_api`
   - Added complete parameter payload construction

6. **.env.example**
   - Added Azure OpenAI configuration examples

## Migration from Old API

**Old API (still works with defaults):**
```python
await service.run_job(job_id, tenant_id, "md")
```

**New API (recommended):**
```python
conversion_options = ConversionOptions(
    table_mode="accurate",
    do_ocr=True,
    do_picture_description=True,
)
await service.run_job(job_id, tenant_id, "md", conversion_options)
```

The implementation is backward compatible - if `conversion_options` is None, defaults are used.

## Future Enhancements

1. **Parameter Presets**: Save and load common configuration profiles
2. **Cost Estimation**: Calculate Azure OpenAI costs before processing
3. **Batch Operations**: Process multiple documents with same parameters
4. **Parameter Recommendation**: ML-based suggestions based on document type
5. **A/B Testing**: Compare results with different parameter combinations

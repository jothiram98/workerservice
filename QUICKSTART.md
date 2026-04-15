# Quick Start Guide - Conversion Parameters

## 5-Minute Setup

### 1. Basic Configuration
Your microservice is ready to use! No additional setup needed for basic functionality.

```bash
# Start your microservice
python -m app.main
```

### 2. Test Basic Document Processing
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@sample.pdf"
```

This uses all default parameters:
- Table mode: accurate
- OCR: disabled
- Images: embedded at 2.0x scale
- No picture descriptions

### 3. Get Job Status
```bash
# Replace {job_id} with the ID from the response above
curl http://localhost:7001/api/v1/jobs/{job_id}
```

### 4. Get Results
```bash
curl http://localhost:7001/api/v1/jobs/{job_id}/result | jq
```

Response includes `conversion_options` showing what parameters were used.

---

## Common Use Cases

### Use Case 1: Fast Processing (Scanned Documents)
OCR is disabled by default. For scanned PDFs with fast processing:

```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@scanned.pdf" \
  -F "do_ocr=true" \
  -F "table_mode=fast"
```

### Use Case 2: Accurate Table Extraction
For documents with complex tables (financial reports, spreadsheets):

```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@financials.pdf" \
  -F "table_mode=accurate" \
  -F "do_ocr=true" \
  -F "images_scale=2.5"
```

### Use Case 3: High-Quality with Image Descriptions
For business documents where image context matters:

```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@presentation.pdf" \
  -F "do_picture_description=true" \
  -F "picture_description_prompt=Describe what you see in detail"
```

**Requires**: Azure OpenAI configured (see section below)

### Use Case 4: Partial Document Processing
Process only pages 1-10 of a 100-page document:

```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@large.pdf" \
  -F "page_range_start=1" \
  -F "page_range_end=10"
```

---

## Azure OpenAI Setup (For Picture Descriptions)

### Step 1: Get Azure Credentials
1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to your OpenAI resource
3. Under "Keys and Endpoint":
   - Copy **API Key 1** (or Key 2)
   - Note your **Resource Name** (e.g., "my-openai-resource")
   - Note your **Deployment Name** (e.g., "gpt-4-vision")

### Step 2: Update .env File
```bash
# Copy .env.example to .env
cp .env.example .env

# Edit .env and add:
AZURE_OPENAI_API_KEY=your-api-key-here
AZURE_OPENAI_RESOURCE=your-resource-name
AZURE_OPENAI_DEPLOYMENT=your-deployment-name
AZURE_OPENAI_API_VERSION=2024-02-15-preview
```

### Step 3: Test the Configuration
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@test.pdf" \
  -F "do_picture_description=true"
```

If successful, job will complete with image descriptions. If you get an error about Azure settings, check:
- All 4 settings are in `.env`
- Microservice was restarted after updating `.env`
- Credentials are correct (check Azure Portal)

---

## Parameter Reference

### Essential Parameters (Tier 1)

| Parameter | Options | Default | When to Use |
|-----------|---------|---------|------------|
| `table_mode` | `fast`, `accurate` | `accurate` | Use `fast` for speed, `accurate` for correctness |
| `do_ocr` | `true`, `false` | `false` | Set to `true` for scanned/image-based PDFs |
| `ocr_engine` | `auto`, `easyocr`, `rapidocr`, `tesseract` | `easyocr` | Change for different OCR accuracy/speed trade-offs |
| `image_export_mode` | `placeholder`, `embedded`, `referenced` | `embedded` | `embedded` keeps everything in markdown file |

### Important Parameters (Tier 2)

| Parameter | Type | Default | When to Use |
|-----------|------|---------|------------|
| `images_scale` | Float (1.0-5.0) | `2.0` | Increase for high-quality images, decrease for speed |
| `include_images` | `true`, `false` | `true` | Set to `false` to skip image processing |
| `do_picture_description` | `true`, `false` | `false` | Set to `true` for AI-generated image descriptions |
| `picture_description_prompt` | String | `null` | Custom prompt for image descriptions (e.g., "Focus on technical details") |

### Advanced Parameters (Tier 3)

| Parameter | Type | Default | When to Use |
|-----------|------|---------|------------|
| `page_range_start` | Integer > 0 | `null` | First page to process (1-indexed) |
| `page_range_end` | Integer > 0 | `null` | Last page to process (inclusive) |
| `pdf_backend` | `docling_parse`, `pypdfium2`, ... | `docling_parse` | Advanced: choose PDF parser backend |
| `document_timeout` | Float (seconds) | `null` | Maximum processing time per document |
| `abort_on_error` | `true`, `false` | `false` | Set to `true` to stop on first error |

---

## Real-World Examples

### Example 1: Legal Document with Tables
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@contract.pdf" \
  -F "table_mode=accurate" \
  -F "do_ocr=false" \
  -F "images_scale=2.0" \
  -F "abort_on_error=true"
```

### Example 2: Scanned Handwritten Notes
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@notes.pdf" \
  -F "do_ocr=true" \
  -F "ocr_engine=easyocr" \
  -F "table_mode=fast" \
  -F "images_scale=1.0"
```

### Example 3: Business Presentation with Detailed Image Analysis
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@presentation.pdf" \
  -F "do_picture_description=true" \
  -F "picture_description_prompt=Analyze this business chart and describe key metrics" \
  -F "images_scale=2.5" \
  -F "page_range_start=1" \
  -F "page_range_end=20"
```

### Example 4: Quick Summary (Executive Pages Only)
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@report.pdf" \
  -F "table_mode=fast" \
  -F "page_range_start=1" \
  -F "page_range_end=5"
```

---

## Monitoring & Debugging

### Check Job Status
```bash
curl http://localhost:7001/api/v1/jobs/{job_id}
```

Response shows: current status, processing time, any errors

### View Results with Parameters
```bash
curl http://localhost:7001/api/v1/jobs/{job_id}/result | jq '.conversion_options'
```

Shows exactly what parameters were used for this job.

### Download Markdown Output
```bash
curl http://localhost:7001/api/v1/jobs/{job_id}/markdown > output.md
```

---

## Performance Tips

| Goal | Settings |
|------|----------|
| **Fastest** | `table_mode=fast`, `do_ocr=false`, `images_scale=1.0` |
| **Balanced** | Default settings (table_mode=accurate, do_ocr=false, images_scale=2.0) |
| **Highest Quality** | `table_mode=accurate`, `do_ocr=true`, `images_scale=2.5`, `do_picture_description=true` |

### Speed vs Quality Trade-offs
- **table_mode**: fast is ~3-5x faster but less accurate
- **do_ocr**: adds 2-3x time but handles scanned PDFs
- **images_scale**: 1.0 is fastest, 3.0+ is slowest
- **do_picture_description**: adds 5-30s per image (Azure API calls)

---

## Troubleshooting

### Job Fails with "Azure OpenAI configuration error"
**Problem**: `do_picture_description=true` but Azure settings not configured
**Solution**: 
```bash
# Check .env file has these 4 settings:
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_RESOURCE=...
AZURE_OPENAI_DEPLOYMENT=...
AZURE_OPENAI_API_VERSION=...

# Restart microservice after updating .env
```

### Parameters Ignored (Using Defaults)
**Problem**: You send `do_ocr=true` but job processes without OCR
**Possible Causes**:
1. Check spelling: Is it `do_ocr` or `docr`?
2. Value format: Send as `true` or `false` (lowercase)
3. Check job result to verify parameters were received:
   ```bash
   curl http://localhost:7001/api/v1/jobs/{job_id}/result | jq '.conversion_options'
   ```

### 422 Validation Error
**Problem**: Response says "Invalid conversion options"
**Solution**: 
- Check parameter values are valid (e.g., `table_mode` must be "fast" or "accurate")
- Ensure numeric values are actually numbers: `images_scale=2.0` not `images_scale=2.0abc`
- Use exact parameter names from this guide

### Processing Timeout
**Problem**: Job status stuck on "running" for hours
**Solution**: Set a timeout:
```bash
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@document.pdf" \
  -F "document_timeout=120"
```

---

## API Reference

### POST /process-document
Upload and process a document.

**Request**:
```
POST /api/v1/process-document
Content-Type: multipart/form-data

file: [binary PDF/document]
tenant_id: [optional string]
to_formats: [default: "md"]
[+ all 10 conversion parameters]
```

**Response (202 Accepted)**:
```json
{
  "job_id": "uuid-here",
  "status": "submitted",
  "docling_task_id": "task-id-here",
  "created_at": "2024-01-15T10:30:00Z"
}
```

### GET /jobs/{job_id}
Get job status.

**Response**:
```json
{
  "job_id": "uuid",
  "status": "running",
  "message": "Docling task submitted. Polling status.",
  "docling_task_id": "task-id",
  "docling_status": "pending",
  "error": null,
  "created_at": "2024-01-15T10:30:00Z",
  "updated_at": "2024-01-15T10:35:00Z",
  "completed_at": null
}
```

### GET /jobs/{job_id}/result
Get processed document results.

**Response (when completed)**:
```json
{
  "job_id": "uuid",
  "status": "completed",
  "output_md_path": "/path/to/final.md",
  "raw_result_path": "/path/to/raw_result.json",
  "images_count": 5,
  "image_paths": ["img_001.png", "img_002.png", ...],
  "conversion_options": {
    "table_mode": "accurate",
    "do_ocr": true,
    "images_scale": 2.0,
    ...
  }
}
```

### GET /jobs/{job_id}/markdown
Download the markdown file.

**Response**: `text/markdown` with the converted markdown content

---

## Next Steps

1. **Try basic processing**: Upload a test PDF
2. **Explore parameters**: Test different table_mode, do_ocr values
3. **Configure Azure**: Set up picture descriptions
4. **Monitor results**: Check conversion_options in responses
5. **Optimize**: Use performance tips for your document types

For detailed documentation, see [CONVERSION_PARAMETERS.md](CONVERSION_PARAMETERS.md)

Good luck! 🚀

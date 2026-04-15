# Parameter Reference Card

## All 10+ Configurable Parameters at a Glance

### Form Field Names for API Calls

```
file                          # Required: PDF document
tenant_id                     # Optional: tenant identifier
to_formats                    # Optional: output format (default: "md")

# TIER 1: ESSENTIAL (Performance/Quality)
table_mode                    # "fast" | "accurate" (default: "accurate")
do_ocr                        # true | false (default: false)
ocr_engine                    # "auto" | "easyocr" | "rapidocr" | "tesseract"
image_export_mode             # "placeholder" | "embedded" | "referenced"

# TIER 2: IMPORTANT (Features)
images_scale                  # Float 1.0-5.0 (default: 2.0)
include_images                # true | false (default: true)
do_picture_description        # true | false (default: false)
picture_description_prompt    # String or null (default: null)

# TIER 3: ADVANCED (Expert)
page_range_start              # Integer > 0 or null (default: null)
page_range_end                # Integer > 0 or null (default: null)
pdf_backend                   # Parser backend selection
document_timeout              # Float seconds or null (default: null)
abort_on_error                # true | false (default: false)
```

---

## Decision Matrix

```
Choose TIER 1 (Essential):
  ├─ table_mode=fast         IF: Speed > Quality
  ├─ do_ocr=true             IF: Document is scanned/image-based
  ├─ ocr_engine=easyocr      IF: Need good accuracy-speed balance
  └─ image_export_mode       IF: Want to control image handling

Choose TIER 2 (Important):
  ├─ images_scale=2.5        IF: Want higher quality images
  ├─ do_picture_description  IF: Need AI-generated image descriptions
  └─ picture_description_prompt IF: Have specific image analysis needs

Choose TIER 3 (Advanced):
  ├─ page_range_start/end    IF: Only need certain pages
  ├─ pdf_backend             IF: Default parser doesn't work well
  ├─ document_timeout        IF: Need to limit processing time
  └─ abort_on_error          IF: Want strict error handling
```

---

## One-Liner Examples

```bash
# Default (use everything as-is)
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf"

# Fast processing
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "table_mode=fast"

# With OCR
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "do_ocr=true"

# High quality images
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "images_scale=3.0"

# With picture descriptions
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "do_picture_description=true"

# Pages 1-10 only
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "page_range_start=1" -F "page_range_end=10"

# Multiple parameters
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "do_ocr=true" -F "table_mode=accurate" -F "images_scale=2.5"
```

---

## Boolean Parameters

These accept: `true` or `false` (lowercase strings)

- `do_ocr`: Enable Optical Character Recognition
- `include_images`: Include images in output
- `do_picture_description`: Enable AI image descriptions
- `abort_on_error`: Stop on first error

**Note**: In curl, boolean form values must be strings: `-F "do_ocr=true"` not `-F "do_ocr=1"`

---

## Enum Parameters

These accept only specific values:

**table_mode**:
- `fast` - Quick processing, less accurate
- `accurate` - Thorough processing, high quality (default)

**do_ocr**:
- `true` - Enable OCR for scanned documents
- `false` - Skip OCR (default)

**ocr_engine**:
- `auto` - Automatic selection
- `easyocr` - Balanced speed/accuracy (recommended)
- `rapidocr` - Fast OCR
- `tesseract` - Accurate OCR

**image_export_mode**:
- `placeholder` - Replace with text placeholders
- `embedded` - Include in markdown (default)
- `referenced` - Link to external files

**pdf_backend**:
- `docling_parse` - Default
- `pypdfium2` - Alternative parser
- `dlparse_v1`, `dlparse_v2`, `dlparse_v4` - Docling versions

---

## Numeric Parameters

**images_scale**: Float between 1.0 and 5.0
- `1.0` - Smallest (fast, low quality)
- `2.0` - Default (balanced)
- `2.5` - High quality
- `3.0+` - Highest quality (slowest)

**page_range_start**: Integer > 0
- First page to process (1-indexed)
- Must be ≤ page_range_end if both specified

**page_range_end**: Integer > 0
- Last page to process (inclusive)
- Must be ≥ page_range_start if both specified

**document_timeout**: Float (seconds)
- Maximum time allowed for processing
- Set to handle large/slow documents
- Example: `120` for 2 minutes

---

## String Parameters

**tenant_id**: Optional tenant identifier
- Example: `-F "tenant_id=customer-123"`
- Used for multi-tenant systems

**to_formats**: Output format
- Default: `"md"` (markdown)
- Other values: Depends on Docling Serve config

**picture_description_prompt**: Custom prompt for image analysis
- Example: `-F "picture_description_prompt=Analyze this technical diagram"`
- Only used if `do_picture_description=true`
- If not provided, uses default: "Describe this image in detail."

---

## Response Metadata

When you retrieve results, conversion_options are included:

```json
{
  "conversion_options": {
    "table_mode": "accurate",
    "do_ocr": false,
    "ocr_engine": "easyocr",
    "image_export_mode": "embedded",
    "images_scale": 2.0,
    "include_images": true,
    "do_picture_description": false,
    "picture_description_prompt": null,
    "page_range_start": null,
    "page_range_end": null,
    "pdf_backend": "docling_parse",
    "document_timeout": null,
    "abort_on_error": false
  }
}
```

This shows exactly what parameters were used for each job.

---

## Common Combinations

```
FAST SCANNED DOCUMENTS:
  table_mode=fast
  do_ocr=true
  ocr_engine=easyocr
  images_scale=1.0

BALANCED DIGITAL PDFs:
  table_mode=accurate
  do_ocr=false
  images_scale=2.0
  (use defaults for rest)

HIGH QUALITY WITH ANALYSIS:
  table_mode=accurate
  do_ocr=true
  ocr_engine=easyocr
  images_scale=2.5
  do_picture_description=true

LARGE DOCUMENTS - FIRST SECTION:
  page_range_start=1
  page_range_end=50
  document_timeout=120

STRICT PROCESSING:
  abort_on_error=true
  table_mode=accurate
  do_ocr=true
```

---

## Validation Rules

**All parameters are validated**:

✓ table_mode must be "fast" or "accurate"
✓ do_ocr must be true or false
✓ images_scale must be > 0
✓ page_range_start must be > 0 if provided
✓ page_range_end must be > 0 if provided
✓ ocr_engine must be valid engine name
✓ image_export_mode must be valid mode

**Azure settings required if do_picture_description=true**:
✓ AZURE_OPENAI_API_KEY in .env
✓ AZURE_OPENAI_RESOURCE in .env
✓ AZURE_OPENAI_DEPLOYMENT in .env
✓ AZURE_OPENAI_API_VERSION in .env

---

## HTTP Status Codes

```
202 Accepted       - Job submitted successfully
400 Bad Request    - Empty file or file too large
404 Not Found      - Job ID doesn't exist
409 Conflict       - Results not available yet
422 Unprocessable  - Invalid parameter values
500 Server Error   - Internal server error
```

**Example 422 response**:
```json
{
  "detail": "Invalid conversion options: 1 validation error for ConversionOptions\ntable_mode\n  Input should be 'fast' or 'accurate' [type=enum, input_value='invalid', input_type=str]"
}
```

---

## Tips & Tricks

### Tip 1: Check What Parameters Were Used
```bash
curl http://localhost:7001/api/v1/jobs/{job_id}/result | jq '.conversion_options'
```

### Tip 2: Fast Initial Test
```bash
# Default settings = fastest
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf"
```

### Tip 3: Reproduce Exact Results
```bash
# Save the conversion_options from result
# Then use same parameters again with another document
curl -X POST http://localhost:7001/api/v1/process-document \
  -F "file=@new.pdf" \
  -F "table_mode=accurate" \
  -F "do_ocr=true" \
  -F "images_scale=2.5"
```

### Tip 4: Debug Parameter Issues
```bash
# Send minimal request
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf"

# If it works, add parameters one by one
curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf" -F "do_ocr=true"

# If it fails, the error will tell you which parameter is wrong
```

### Tip 5: Large Document Strategy
```bash
# Instead of processing all 500 pages at once:
# 1. Process page ranges separately
for start in 1 51 101 151; do
  end=$((start + 49))
  curl -X POST http://localhost:7001/api/v1/process-document \
    -F "file=@large.pdf" \
    -F "page_range_start=$start" \
    -F "page_range_end=$end"
done
```

---

## Parameter Defaults Table

| Parameter | Default Value |
|-----------|---------------|
| table_mode | "accurate" |
| do_ocr | false |
| ocr_engine | "easyocr" |
| image_export_mode | "embedded" |
| images_scale | 2.0 |
| include_images | true |
| do_picture_description | false |
| picture_description_prompt | null |
| page_range_start | null |
| page_range_end | null |
| pdf_backend | "docling_parse" |
| document_timeout | null |
| abort_on_error | false |

**Using defaults**: Just send file, no other parameters needed!

---

## Quick Decision Tree

```
START: curl -X POST http://localhost:7001/api/v1/process-document -F "file=@doc.pdf"
  │
  ├─ Too slow?
  │  └─ Add: -F "table_mode=fast"
  │
  ├─ Bad OCR results?
  │  └─ Add: -F "do_ocr=true"
  │
  ├─ Poor image quality?
  │  └─ Add: -F "images_scale=2.5"
  │
  ├─ Need image descriptions?
  │  └─ Add: -F "do_picture_description=true"
  │
  ├─ Only need some pages?
  │  └─ Add: -F "page_range_start=1" -F "page_range_end=50"
  │
  └─ Need multiple changes?
      └─ Combine: -F "table_mode=fast" -F "do_ocr=true" -F "images_scale=2.0"
```

---

## Troubleshooting Quick Reference

```
Problem: "422 Unprocessable Entity"
Fix: Check parameter values are valid (see Validation Rules above)

Problem: "Azure OpenAI configuration error"
Fix: Set all 4 AZURE_OPENAI_* settings in .env

Problem: Processing takes forever
Fix: Add -F "table_mode=fast" or -F "page_range_end=10"

Problem: Poor OCR quality
Fix: Try -F "ocr_engine=easyocr" or "tesseract"

Problem: Images look fuzzy
Fix: Increase -F "images_scale=3.0"

Problem: Parameters seem to be ignored
Fix: Verify parameter names spelling exactly
```

---

**Keep this card handy for quick reference!**

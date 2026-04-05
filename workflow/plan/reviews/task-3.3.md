# Task 3.3 Review: AI-Multimodal Pipeline Lambda (Bedrock Extract)

**Date:** 2026-04-04
**Status:** complete
**Branch:** task/3.3-bedrock-extract

## Files Created

- `backend/src/novascan/pipeline/bedrock_extract.py` -- shadow pipeline Lambda that sends receipt images directly to Bedrock Nova multimodal for extraction

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| Lambda handler receives image S3 ref + custom categories | PASS |
| Reads image from S3 | PASS |
| Constructs multimodal Bedrock prompt with image + taxonomy | PASS |
| Calls invoke_model with Nova | PASS |
| Parses response into ExtractionResult schema | PASS |
| Uses same prompt template from prompts.py (build_extraction_prompt) | PASS |
| Uses Lambda Powertools Logger and Tracer | PASS |
| Error handling: exceptions caught and returned as error payload | PASS |
| ruff check passes | PASS |
| Import verification passes | PASS |

## Test Command Output

```
cd backend && uv run ruff check src/  --> All checks passed!
cd backend && uv run python -c "from novascan.pipeline.bedrock_extract import handler; print('PASS')"  --> PASS
```

## Design Decisions

- **Prompt reuse:** Calls `build_extraction_prompt(custom_categories=...)` without `textract_output`, which triggers the image-only extraction instructions path in the shared prompt template
- **No code duplication:** Helper functions `_read_image_from_s3`, `_infer_media_type`, `_call_bedrock`, and `_parse_response` follow the same patterns as nova_structure.py but are independent (no shared mutable state)
- **Event shape:** Simpler than nova_structure -- receives `{bucket, key, customCategories}` directly from Step Functions (no textractResult nesting)
- **Required fields:** `bucket` and `key` are accessed via `event["bucket"]` (KeyError) rather than `.get()` with empty defaults, since these are required inputs from Step Functions and a missing field should surface as an error
- **Model ID:** Same `amazon.nova-lite-v1:0` default, configurable via `NOVA_MODEL_ID` env var

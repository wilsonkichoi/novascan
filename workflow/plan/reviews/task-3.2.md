# Task 3.2 Review: OCR-AI Pipeline Lambdas (Textract + Nova)

**Date:** 2026-04-04
**Status:** complete
**Branch:** task/3.2-ocr-ai-lambdas

## Files Created

- `backend/src/novascan/pipeline/prompts.py` -- extraction prompt template with full category taxonomy
- `backend/src/novascan/pipeline/textract_extract.py` -- Textract AnalyzeExpense sync Lambda handler
- `backend/src/novascan/pipeline/nova_structure.py` -- Bedrock Nova structuring Lambda handler

## Acceptance Criteria Verification

| Criterion | Status |
|-----------|--------|
| textract_extract receives S3 bucket/key, calls analyze_expense sync, returns raw ExpenseDocuments | PASS |
| nova_structure receives Textract output + image S3 ref + taxonomy + custom categories | PASS |
| nova_structure constructs Bedrock prompt, calls invoke_model with Nova | PASS |
| nova_structure parses response into ExtractionResult schema | PASS |
| Prompt template includes full category taxonomy | PASS |
| Prompt template includes custom categories (if any) | PASS |
| Prompt template includes extraction instructions and output schema | PASS |
| Both handlers use Lambda Powertools Logger and Tracer | PASS |
| Error handling: exceptions caught and returned as error payload | PASS |
| ruff check passes | PASS |
| Import verification passes | PASS |

## Test Command Output

```
cd backend && uv run ruff check src/  --> All checks passed!
cd backend && uv run python -c "from novascan.pipeline.textract_extract import handler; from novascan.pipeline.nova_structure import handler; print('PASS')"  --> PASS
```

## Design Decisions

- **Model ID:** `amazon.nova-lite-v1:0` as the cost-effective default, configurable via `NOVA_MODEL_ID` env var
- **Textract output formatting:** Converts raw ExpenseDocuments into a structured text summary (summary fields + line item groups) that Nova can reason over
- **Image included in Nova call:** The receipt image is read from S3 and sent alongside the Textract text to allow cross-referencing
- **Markdown fence stripping:** _parse_response handles cases where the model wraps JSON in code blocks
- **Error payloads:** Both handlers return `{"error": ..., "errorType": ...}` instead of raising, compatible with Step Functions Catch blocks
- **Prompt reuse:** `build_extraction_prompt` function is designed to be reused by the shadow pipeline (task 3.3) via the `textract_output` parameter toggle

# Task 3.6 Review: Pipeline Lambda Unit Tests

**Date:** 2026-04-04
**Role:** qa-engineer
**Branch:** `task/3.6-pipeline-unit-tests` (from `feature/m3-wave4-pipeline-tests`)

## Summary

Created 5 test files with 92 total tests covering all OCR pipeline Lambda handlers and the ranking algorithm. Tests verify behavioral contracts from SPEC.md Sections 3 and 7.

## Test Files

| File | Tests | Coverage |
|------|-------|----------|
| `test_textract_extract.py` | 10 | Success extraction, API error payloads, S3 ref passthrough |
| `test_nova_structure.py` | 12 | Valid Textract -> ExtractionResult, Bedrock errors, markdown handling |
| `test_bedrock_extract.py` | 15 | Valid image -> ExtractionResult, error payloads, minimal extraction |
| `test_finalize.py` | 37 | Main/shadow selection, fallback, both-fail, DynamoDB records, S3 metadata, ranking |
| `test_ranking.py` | 18 | Perfect/minimal/inconsistent scores, component influences, edge cases |

## Acceptance Criteria

- [x] Textract extract: successful extraction, Textract API error returns error payload
- [x] Nova structure: valid Textract output -> valid ExtractionResult, Bedrock error returns error payload
- [x] Bedrock extract: valid image -> valid ExtractionResult, Bedrock error returns error payload
- [x] Finalize: main success uses main, main fail + shadow success uses shadow with fallback flag, both fail -> status failed, ranking scores computed, DynamoDB records created (receipt update, pipeline results, line items), S3 metadata updated
- [x] Ranking: perfect result scores near 1.0, empty result scores near 0.0, inconsistent totals reduce score
- [x] All tests pass via both test commands

## Bug Found

**SEVERITY:** Critical
**TEST:** `TestFinalizeMainSuccess::test_status_confirmed` (and all finalize tests with successful extraction)
**EXPECTED:** Finalize Lambda should update receipt record in DynamoDB with extracted data
**ACTUAL:** `UpdateItem` failed with `ValidationException: Attribute name is a reserved keyword; reserved keyword: total`
**SPEC REF:** SPEC.md Section 3 (Processing Flow) -- receipt record updated with extracted data
**ROOT CAUSE:** `finalize.py::_update_receipt()` used DynamoDB reserved keywords (`total`, `category`, `subtotal`, `currency`) directly in the UpdateExpression without expression attribute name aliases (`#total`, `#category`, etc.)
**FIX:** Added `ExpressionAttributeNames` entries: `#total`, `#category`, `#subtotal`, `#currency`
**IMPACT:** Every receipt finalization would fail in production -- no receipts could ever transition from `processing` to `confirmed`

## Test Methodology

- Tests written against SPEC contract (Section 3 processing flow, Section 7 extraction schema)
- External AWS services (Textract, Bedrock) mocked with `unittest.mock.patch`
- DynamoDB and S3 mocked with moto (`mock_aws`)
- Each test is independent -- no shared state between tests
- Tests verify behavior, not implementation details

## Commands

```bash
# Specific files
cd backend && uv run pytest tests/unit/test_textract_extract.py tests/unit/test_nova_structure.py tests/unit/test_bedrock_extract.py tests/unit/test_finalize.py tests/unit/test_ranking.py -v

# Filter command
cd backend && uv run pytest tests/unit/ -v -k "pipeline or textract or nova or bedrock or finalize or ranking"

# Full suite
cd backend && uv run pytest -v
```

All 236 tests pass (92 new + 144 existing).

# Task 3.8 Review: Sanitize Custom Category Inputs in Extraction Prompt [C1]

## Summary
Added input validation and sanitization for custom category names and slugs before they are interpolated into the Bedrock Nova extraction prompt. Custom categories are now placed in a structured JSON data block instead of free-text lines.

## Changes
- **`backend/src/novascan/pipeline/prompts.py`**:
  - Added `validate_category_name()`: validates display names (alphanumeric, spaces, `& / , . ( ) -`, max 64 chars)
  - Added `validate_category_slug()`: validates slugs (lowercase alphanumeric + hyphens, max 64 chars)
  - Added injection pattern detection: newlines, markdown headers (`##`), instruction-like patterns (`ignore previous instructions`, `you are now`, `system:`, etc.)
  - `build_extraction_prompt()` now validates all categories before interpolation and raises `ValueError` on invalid input
  - Custom categories output as a JSON code block instead of free-text markdown lines

## Acceptance Criteria Checklist
- [x] `build_extraction_prompt()` validates custom category names before interpolation
- [x] Category names restricted to: alphanumeric, spaces, `& / , . ( ) -`, max 64 chars
- [x] Category slugs restricted to: lowercase alphanumeric + hyphens, max 64 chars
- [x] Names containing newlines, markdown headers, or instruction-like patterns rejected with `ValueError`
- [x] Custom categories placed in structured JSON data block
- [x] Existing tests in `test_nova_structure.py` and `test_bedrock_extract.py` still pass (27/27)
- [x] `ruff check src/` passes

## Test Results
```
All checks passed!  (ruff)
27 passed, 209 deselected in 0.27s  (pytest)
```

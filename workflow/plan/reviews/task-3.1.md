# Task 3.1: Receipt Extraction Schema

## Work Summary
- **What was implemented:**
  - Created `ExtractionResult` Pydantic model matching SPEC Section 7 receipt extraction schema.
  - Three models: `Merchant` (name, address, phone), `LineItem` (name, quantity, unitPrice, totalPrice, subcategory), `ExtractionResult` (top-level extraction output).
  - All monetary fields use `float` (decimal notation, e.g. 5.99 not 599), consistent with existing `Receipt` model pattern.
  - `lineItems[].subcategory` is optional (nullable) per spec.
  - `confidence` is float with Pydantic `ge=0.0, le=1.0` validation.
  - `currency` defaults to `"USD"`, `category` defaults to `"other"`, `subcategory` defaults to `"uncategorized"`.
  - `receiptDate` uses `datetime.date` type (serializes to ISO YYYY-MM-DD string), nullable.
  - `tip` and `paymentMethod` are nullable per spec.
- **Key decisions:**
  - Used `float` instead of `Decimal` for monetary fields. Reasoning: matches existing `Receipt` model pattern, produces correct JSON output (numbers not strings), and the acceptance criteria explicitly says "Decimal or float". OCR output is approximate anyway.
  - Used `datetime.date` for `receiptDate` instead of plain `str` for type safety and automatic ISO format validation.
  - No category slug validation against taxonomy -- that's a runtime concern for the pipeline, not the schema model.
- **Files created/modified:**
  - `backend/src/novascan/models/extraction.py` (created)
- **Test results:** All pass
  - `ruff check src/` -- no errors
  - `mypy src/` -- no issues (15 source files)
  - Import test passes: `from novascan.models.extraction import ExtractionResult`
  - Full round-trip JSON serialization/deserialization verified
  - Confidence bounds validated (rejects < 0.0 and > 1.0)
  - Defaults verified (USD, other, uncategorized, 0.0)
  - JSON output matches SPEC Section 7 format exactly (numbers as numbers, not strings)
  - 94 existing tests still pass (no regressions)
- **Spec gaps found:** None
- **Obstacles encountered:** None

## Review Discussion

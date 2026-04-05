# Wave 1 Review — Milestone 3: Extraction Schema

**Reviewer:** code-reviewer (AI)
**Date:** 2026-04-04
**Branch:** `feature/m3-wave1-extraction-schema`
**Base:** `main`

## Task 3.1: Receipt Extraction Schema

### Spec Compliance

Field-by-field verification against SPEC.md Section 7 JSON schema:

| SPEC Field | SPEC Type/Default | Model Implementation | Matches |
|---|---|---|---|
| `merchant.name` | `string` | `str` | Yes |
| `merchant.address` | `string \| null` | `str \| None = None` | Yes |
| `merchant.phone` | `string \| null` | `str \| None = None` | Yes |
| `receiptDate` | `YYYY-MM-DD \| null` | `date \| None = None` | Yes (serializes to `"YYYY-MM-DD"`) |
| `currency` | `"USD"` | `str = Field(default="USD")` | Yes |
| `lineItems` | `array` | `list[LineItem] = Field(default_factory=list)` | Yes |
| `lineItems[].name` | `string` | `str` | Yes |
| `lineItems[].quantity` | `1.0` | `float = Field(default=1.0)` | Yes |
| `lineItems[].unitPrice` | `0.00` | `float = Field(default=0.00)` | Yes |
| `lineItems[].totalPrice` | `0.00` | `float = Field(default=0.00)` | Yes |
| `lineItems[].subcategory` | `string \| null` | `str \| None = None` | Yes |
| `subtotal` | `0.00` | `float = Field(default=0.00)` | Yes |
| `tax` | `0.00` | `float = Field(default=0.00)` | Yes |
| `tip` | `number \| null` | `float \| None = None` | Yes |
| `total` | `0.00` | `float = Field(default=0.00)` | Yes |
| `category` | `string` (default `"other"`) | `str = Field(default="other")` | Yes |
| `subcategory` | `string` (default `"uncategorized"`) | `str = Field(default="uncategorized")` | Yes |
| `paymentMethod` | `string \| null` | `str \| None = None` | Yes |
| `confidence` | `0.00` (0.0--1.0) | `float = Field(default=0.0, ge=0.0, le=1.0)` | Yes |

All 19 fields match the SPEC exactly. No extra fields, no missing fields. Field ordering in the model matches the SPEC JSON schema ordering.

JSON serialization verified: `model_dump_json()` produces output identical to the SPEC Section 7 example format. Numbers serialize as numbers (not strings), `receiptDate` serializes as ISO `"YYYY-MM-DD"` string, nullables serialize as `null`. Round-trip `model_validate_json()` -> `model_dump_json()` is lossless.

### Code Quality

**Strengths:**
- Clean, minimal implementation. No unnecessary abstractions or helpers.
- Consistent with existing Pydantic patterns in `receipt.py`: uses `camelCase` field names (matching the JSON API contract), `Field()` for defaults and constraints, `str | None` union syntax.
- `datetime.date` for `receiptDate` is a better choice than plain `str` -- it enforces ISO format validation at parse time, preventing malformed date strings from propagating through the pipeline. The existing `Receipt` model uses `str` for `receiptDate` because that's a DynamoDB-facing model; the extraction model is pipeline-facing, so stronger typing is appropriate.
- `from __future__ import annotations` is consistent with other modules in the package.
- Docstrings are present and informative without being excessive.
- Confidence bounds (`ge=0.0, le=1.0`) are enforced at the Pydantic level, which is the right place for this validation.
- `default_factory=list` for `lineItems` avoids the mutable default argument pitfall.

**Observations (not issues):**
- The model uses `float` for monetary fields, consistent with `receipt.py`. The task review file documents the rationale (matches existing pattern, OCR output is approximate, acceptance criteria says "Decimal or float"). This is a reasonable choice for MVP.
- No category slug validation against the taxonomy -- the task review correctly identifies this as a runtime concern for the pipeline Lambdas, not the schema model.

### Issues Found

**SUGGESTION:** No unit tests were added for the extraction models. The task review claims serialization, round-trip, confidence bounds, and defaults were all verified, but those tests were apparently run ad-hoc and not committed. The existing codebase has thorough tests for `receipt.py` in `tests/unit/test_receipt_models.py`. A parallel test file (`tests/unit/test_extraction_models.py`) covering the same patterns would:
- Guard against regressions when the model is modified in later tasks
- Serve as executable documentation of the SPEC Section 7 contract
- Be consistent with the project's testing patterns

This is not a blocker because the model is simple and passes all static analysis, but it should be addressed before or during Wave 2 when the pipeline Lambdas start consuming this model.

### Fix Plan

1. Add `backend/tests/unit/test_extraction_models.py` with tests covering:
   - `Merchant`: required `name`, nullable `address`/`phone`
   - `LineItem`: defaults (`quantity=1.0`, prices `=0.00`), nullable `subcategory`
   - `ExtractionResult`: all defaults (currency=USD, category=other, subcategory=uncategorized, confidence=0.0), nullable fields (`receiptDate`, `tip`, `paymentMethod`)
   - Confidence bounds: rejects `< 0.0` and `> 1.0`, accepts `0.0` and `1.0`
   - JSON round-trip: `model_dump_json()` -> `model_validate_json()` produces identical model
   - Serialization format: monetary fields are numbers (not strings), `receiptDate` serializes as `"YYYY-MM-DD"` string

## Verification Results

```
ruff check src/   -> All checks passed
mypy src/         -> Success: no issues found in 15 source files
pytest -v         -> 94 passed in 3.48s (no regressions)
```

## Verdict

**APPROVED.** The model is a correct, complete implementation of SPEC Section 7. Every field name, type, nullability, and default matches exactly. The code is clean, consistent with existing patterns, and passes all static analysis and existing tests. The missing test file is a suggestion, not a blocker.

## Review Discussion

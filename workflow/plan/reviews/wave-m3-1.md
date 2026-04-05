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

### Fix Plan Analysis (code-reviewer AI — 2026-04-04)

**Verdict:** approve

The fix plan is correct, complete, and feasible. Here is the detailed reasoning:

**1. Does the fix plan address the suggestion?**
Yes. The suggestion calls for a test file paralleling `test_receipt_models.py` that covers defaults, nullability, bounds, serialization, and round-trip for the extraction models. The fix plan enumerates exactly those test categories: Merchant required/nullable fields, LineItem defaults and nullable subcategory, ExtractionResult defaults and nullable fields, confidence bounds (reject <0.0 and >1.0, accept boundary values), JSON round-trip, and serialization format. This is a direct, complete response to the suggestion.

**2. Overlap with Task 3.6 (Wave 4 — Pipeline Lambda Unit Tests)?**
Minimal. Task 3.6 tests Lambda *handler* logic — given mocked AWS service responses, do the handlers produce valid `ExtractionResult` objects and handle errors correctly? Those tests treat `ExtractionResult` as an opaque output and assert on its presence and rough shape, not on the model's own validation behavior. The proposed `test_extraction_models.py` tests the model *in isolation*: default values, Pydantic validation rejection of out-of-bounds confidence, nullable field behavior, and JSON serialization format fidelity against SPEC Section 7. These are complementary, not overlapping. The model tests are also a prerequisite in spirit — if the model's own contract is wrong, the pipeline handler tests will give misleading results.

**3. Feasibility and risk assessment?**
- The implementation in `extraction.py` is 49 lines with three simple Pydantic models. Writing the proposed test file is straightforward — roughly 80-120 lines following the patterns already established in `test_receipt_models.py`.
- No new dependencies are required. The tests use `pytest`, `pydantic.ValidationError`, and the extraction models — all already available.
- Risk is negligible. The tests are additive (new file, no modifications to existing code) and purely verify existing behavior.

**4. Any missing test cases?**
The fix plan covers the important cases. Two minor additions worth considering during implementation (but not blockers to approving the plan):
- Negative monetary values: the model does not constrain `subtotal`, `tax`, `total`, etc. to non-negative. A test documenting that negative values *are* accepted (intentional, since OCR may produce refund/credit amounts) would serve as executable documentation of that design decision.
- `lineItems` as empty list by default: worth an explicit assertion since `default_factory=list` is a correctness-critical pattern.

Both are minor and can be included at the implementer's discretion. The fix plan as written is sufficient.

### Fix Results (backend-engineer AI — 2026-04-04)

**Branch:** `fix/3.1-extraction-tests` (based on `feature/m3-wave1-extraction-schema`)

**SUGGESTION (missing extraction model tests) — Fixed**
- What was changed: Added `backend/tests/unit/test_extraction_models.py` with comprehensive model tests
- Files created: `backend/tests/unit/test_extraction_models.py`

**Verification:**
- ruff check — PASS
- pytest (new tests) — PASS (50 tests)
- pytest (full suite) — PASS (144 tests)

### Fix Verification (qa-engineer AI — 2026-04-04)

**SUGGESTION (missing extraction model tests) — Fixed**
- Tests added: 50 tests in `test_extraction_models.py`
- Fix plan coverage: complete — all 6 items covered:
  - Merchant: required name, nullable address/phone (TestMerchant — 6 tests)
  - LineItem: defaults (quantity=1.0, prices=0.00), nullable subcategory (TestLineItem — 9 tests)
  - ExtractionResult: all defaults (currency=USD, category=other, subcategory=uncategorized, confidence=0.0, subtotal/tax/total=0.00, lineItems=[]), nullable fields (receiptDate, tip, paymentMethod) (TestExtractionResultDefaults — 9 tests, TestExtractionResultNullableFields — 4 tests)
  - Confidence bounds: rejects <0.0 and >1.0, accepts 0.0, 1.0, and midpoint (TestConfidenceBounds — 7 tests)
  - JSON round-trip: minimal, full, null fields, line items (TestJsonRoundTrip — 4 tests)
  - Serialization format: monetary fields as numbers, receiptDate as "YYYY-MM-DD", nulls as null (TestSerializationFormat — 7 tests)
  - Bonus: negative monetary values accepted (TestNegativeMonetaryValues — 4 tests)
- All tests pass: yes (50/50 passed in 0.05s)
- No regressions: yes (144/144 full suite passed in 3.50s)
- Linting: ruff check tests/ — all checks passed
- Verification: PASS

# Wave 1 Review: Dashboard Summary + Transactions Backend APIs

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (1M context) (code-reviewer)
Cross-referenced: SPEC.md Section 5 (Dashboard & Transactions), api-contracts.md (GET /api/dashboard/summary, GET /api/transactions), HANDOFF.md

## Task 5.1: Dashboard Summary Endpoint

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Queries user's confirmed receipts via GSI1 for target month and previous month | PASS | `_query_all_gsi1` queries the combined range, then splits by `receiptDate` |
| Aggregates: totalSpent, previousMonthTotal, monthlyChangePercent | PASS | Plain Python (defaultdict, sorted) -- correct since pandas removed in 3.17 |
| Aggregates: weeklySpent, previousWeekTotal, weeklyChangePercent | PASS | Weekly queried separately via `_query_all_gsi1` |
| Top categories: up to 5, sorted by total descending, includes percent of total | PASS | Sorted by value desc, capped at 5 |
| Recent activity: up to 5 most recent receipts | PASS | Takes first 5 from GSI1 descending results |
| `month` query param defaults to current month (YYYY-MM) | PASS | Regex validated, defaults to `today.year`/`today.month` |
| Weekly is current calendar week (Monday-Sunday) regardless of month param | PASS | `_monday_of_week` computes Monday correctly |
| Change percentages: positive = increase, negative = decrease, null if no prior data | PASS | `_compute_change_percent` returns None when previous == 0 |
| Only confirmed receipts in totals | PASS | Both monthly and weekly loops check `status == "confirmed"` |
| `ruff check src/` passes | PASS | Verified |

### Issues Found

**[S1] -- SUGGESTION: `sortBy=date` with merchant search performs a wasteful double-fetch in transactions.py**

`transactions.py:244-280` -- When `sortBy=date` and `merchant` is present, the code first runs the standard DynamoDB paginated query (line 244), applies merchant filter, builds transactions, runs a Count query for totalCount -- and then DETECTS that merchant search is active (line 270) and re-fetches ALL matching records via `_fetch_all_matching`. This means:

1. The initial paginated query + Count query at lines 244-268 are completely wasted work.
2. DynamoDB reads are doubled for this code path.

The merchant search check at line 270 should be moved before the initial query at line 244, so the code can skip straight to the in-memory path when `merchant` is provided. This would halve the DynamoDB read cost for merchant-search requests.

Suggested fix: restructure the `sortBy == "date"` branch to check `if merchant_search` first and route directly to the `_fetch_all_matching` path, bypassing the DynamoDB-paginated path and its Count query.

**[S2] -- SUGGESTION: Duplicated cursor decode/encode/validation logic between receipts.py and transactions.py**

`transactions.py:28-57` -- The `_encode_cursor`, `_decode_cursor`, `_error_response`, `_decimal_to_float` functions and `_VALID_CURSOR_KEYS` constant are copied verbatim from `receipts.py:43-99`. This creates maintenance risk: if the cursor validation logic needs to change (as it did during security hardening in Task 3.10), it must be updated in two places.

Per project convention ("no premature abstraction -- three similar lines > one unnecessary helper"), two copies of a 30+ line function with security implications is past the threshold for extraction. These should live in a shared module (e.g., `shared/pagination.py`).

**[S3] -- SUGGESTION: Merchant sort places None merchants inconsistently depending on sort direction**

`transactions.py:320-327` -- The merchant sort uses `""` for ascending and `"\uffff"` for descending when merchant is None/missing. This means:
- Ascending: None merchants sort to the beginning (empty string sorts before all text)
- Descending: None merchants sort to the beginning ("\uffff" is highest, reversed to first)

The comment says "Sort None/missing merchants to end regardless of direction" but the ascending case sorts them to the beginning, not the end. For ascending sort, `no_merchant` should be `"\uffff"` (sorts to end); for descending sort, `no_merchant` should be `""` (sorts to end after reverse).

Fix: swap the values: `no_merchant = "\uffff" if not reverse else ""`

**[N1] -- NIT: Dashboard response uses Pydantic model serialization while transactions uses raw dict**

`dashboard.py:289` uses `result.model_dump_json()` (Pydantic serialization), while `transactions.py:373` uses `json.dumps(result)` with a raw dict. The project standard (SPEC Section 10) says "All request/response bodies defined as Pydantic models." The transactions endpoint should use a Pydantic response model for consistency, though the raw dict works correctly.

**[N2] -- NIT: Dashboard `_to_float` naming differs from transactions `_decimal_to_float`**

`dashboard.py:89` defines `_to_float` which has different semantics (returns 0.0 for None) vs `transactions.py:73` `_decimal_to_float` (returns None for None). The different names correctly signal different behavior, but the inconsistency is worth noting. The naming is fine given the functional difference.

## Task 5.2: Transactions Endpoint

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Queries user's receipts via GSI1 with optional date range KeyCondition | PASS | Key condition built with between/gte/lte as appropriate |
| Supports filters: startDate, endDate, category, merchant, status | PASS | Date range via KeyCondition, category/status via FilterExpression, merchant via in-memory |
| Supports sorting: sortBy (date, amount, merchant), sortOrder (asc, desc) | PASS | date via native GSI1, amount/merchant via in-memory sort |
| Merchant search: case-insensitive substring match in Lambda | PASS | `_apply_post_query_filters` uses `.lower()` comparison |
| Returns totalCount via parallel Count query or derived from fetched set | PASS | Count query for `sortBy=date` (no merchant), derived for in-memory paths |
| Cursor-based pagination using ExclusiveStartKey/LastEvaluatedKey | PASS | DynamoDB cursor for native sort, linear-scan cursor for in-memory |
| Category/status applied as FilterExpression (post-query) | PASS | Built as `Attr("status").eq()` / `Attr("category").eq()` |
| `ruff check src/` passes | PASS | Verified |

### Issues Found

See [S1], [S2], [S3] above (scoped to Task 5.2).

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| GET /api/dashboard/summary response shape (api-contracts.md) | All fields present: month, totalSpent, previousMonthTotal, monthlyChangePercent, weeklySpent, previousWeekTotal, weeklyChangePercent, receiptCount, confirmedCount, processingCount, failedCount, topCategories, recentActivity | PASS |
| Dashboard uses pandas for aggregation (SPEC line ~681) | Uses plain Python (defaultdict, sorted) -- pandas was removed in Task 3.17 | PASS (intentional deviation, documented in task review) |
| Only confirmed receipts in totals (api-contracts.md) | Both monthly and weekly loops check `status == "confirmed"` | PASS |
| Weekly always based on current date (api-contracts.md) | `_monday_of_week(today)` used regardless of month param | PASS |
| GET /api/transactions response shape (api-contracts.md) | All fields present: transactions[], nextCursor, totalCount | PASS |
| sortBy=date uses GSI1SK natively; amount/merchant use in-memory (PLAN.md) | Three code paths correctly implement this | PASS |
| Merchant search: case-insensitive substring (SPEC) | `merchant_lower in str(item["merchant"]).lower()` | PASS |
| CategoryDisplay/subcategoryDisplay resolved (api-contracts.md) | Falls back to `get_category_display_name` / `get_subcategory_display_name` from constants | PASS |
| Cursor validation (security: H1 from M3.1) | `_decode_cursor` validates key set and user ownership | PASS |
| Error sanitization (security: M7 from M3.1) | Logger.warning for details, generic message to client | PASS |

## Things Done Well

- **Clean separation of query strategies.** The transactions endpoint correctly identifies three distinct code paths (native GSI1 date sort, date sort with merchant requiring full fetch, and amount/merchant in-memory sort) and handles each appropriately. The task review documents these decisions clearly.
- **Consistent security patterns.** Both files reuse the cursor validation and error sanitization patterns established in M3.1 security hardening. Cursor ownership checks are present on all decode paths.
- **Correct weekly calculation.** The dashboard correctly queries weekly data separately from monthly data since the current calendar week may not overlap with the requested month. This is a subtlety that could easily have been missed.
- **Proper aggregation without pandas.** The dashboard uses `defaultdict` and sorted operations cleanly. The code is more readable than a pandas equivalent would be for this use case.
- **GSI1 date range pattern.** Both files correctly use the `{end_date}~` trailing tilde pattern for inclusive end-date queries, matching the established pattern in `receipts.py`.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| S1 | SUGGESTION | 5.2 | sortBy=date with merchant search double-fetches from DynamoDB | Restructure to skip initial paginated query when merchant is present |
| S2 | SUGGESTION | 5.1/5.2 | Cursor/pagination helpers copy-pasted between receipts.py and transactions.py | Extract to shared/pagination.py |
| S3 | SUGGESTION | 5.2 | Merchant sort places None merchants at beginning for ascending (should be end) | Swap no_merchant sentinel values |
| N1 | NIT | 5.2 | Transactions uses raw dict instead of Pydantic response model | Add Pydantic model for consistency |
| N2 | NIT | 5.1 | _to_float naming differs from _decimal_to_float | Naming is intentional, just noting |

**Overall verdict:** Solid implementation. Both endpoints are functionally correct, spec-compliant, and follow established project patterns. The three SUGGESTIONs are quality improvements: [S1] is a performance concern (double DynamoDB fetch), [S2] is a maintainability concern (duplicated security-sensitive code), and [S3] is a correctness bug in edge-case sorting behavior for null merchants. No BLOCKERs.

## Review Discussion

### Fix Plan (Claude Opus 4.6 (1M context) -- 2026-04-08)

**Note:** Generated in the same context as the review. Run `/agentic-dev:review fix-plan-analysis wave 1` in a separate session for a truly independent second opinion.

**Scope: 3 issues (0 BLOCKERs, 3 SUGGESTIONs). NITs deferred.**

**[S1] (sortBy=date with merchant search double-fetches from DynamoDB)**
- Independent assessment: Reading `transactions.py:220-300`, the `sortBy == "date"` branch runs a paginated query, a Count query, and THEN checks `if merchant_search` at line 270 to re-run via `_fetch_all_matching`. The initial query and Count query results are discarded. This is a control flow ordering problem -- the merchant check should happen before any DynamoDB calls.
- Review comparison: Agree. The code is functionally correct (the final result is right) but performs unnecessary DynamoDB reads. At MVP scale (~1,200 items/year) the cost is negligible, but the wasted round-trips add latency.
- Fix: Restructure the `sortBy == "date"` branch into two sub-branches: (a) `if merchant_search` -- go straight to `_fetch_all_matching`, in-memory pagination, derive totalCount; (b) else -- existing DynamoDB-paginated path with Count query. This eliminates the double-fetch.
- Risk: The restructure touches pagination/cursor logic in a complex function. If the in-memory pagination path for `sortBy=date` + merchant diverges from the `sortBy=amount|merchant` path, cursor behavior could become inconsistent. Mitigate by extracting the in-memory pagination logic into a shared helper (relates to [S2]).
- Files: `backend/src/novascan/api/transactions.py`

**[S2] (Duplicated cursor/pagination helpers)**
- Independent assessment: Reading both `receipts.py:43-99` and `transactions.py:28-73`, the `_encode_cursor`, `_decode_cursor`, `_error_response`, `_decimal_to_float`, and `_VALID_CURSOR_KEYS` are identical. `_decode_cursor` contains security-critical validation (cursor key checking, user ownership). Duplicating security code is a maintenance liability.
- Review comparison: Agree. The "three similar lines" threshold from CLAUDE.md doesn't apply -- these are 30+ line functions with security implications, not simple one-liners.
- Fix: Create `backend/src/novascan/shared/pagination.py` containing `encode_cursor`, `decode_cursor`, `VALID_CURSOR_KEYS`. Create `backend/src/novascan/shared/responses.py` containing `error_response` and `decimal_to_float` (these are also shared). Update `receipts.py` and `transactions.py` to import from the shared modules. Run existing tests to verify no regressions.
- Risk: Moving functions to a new module could break imports if any test directly patches the private function path (e.g., `unittest.mock.patch("api.receipts._decode_cursor")`). Existing tests in `test_receipts_list.py` and `test_security_cursor.py` may need import path updates. Verify by running `grep -r "_decode_cursor\|_encode_cursor\|_error_response" backend/tests/` after the move.
- Files: `backend/src/novascan/shared/pagination.py` (create), `backend/src/novascan/shared/responses.py` (create), `backend/src/novascan/api/receipts.py` (modify), `backend/src/novascan/api/transactions.py` (modify)

**[S3] (Merchant sort places None merchants inconsistently)**
- Independent assessment: Reading `transactions.py:320-327`, the sort key for None merchants is `""` when ascending (`reverse=False`) and `"\uffff"` when descending (`reverse=True`). For ascending: `""` sorts before `"a"`, so None merchants appear first -- the comment says "to end" which is wrong. For descending with `reverse=True`: `"\uffff"` sorts last in raw order, and `reverse=True` puts it first -- so None merchants appear first again. The bug: None merchants always sort to the beginning regardless of direction.
- Review comparison: Agree. The sentinel values are inverted.
- Fix: Swap the sentinel values: `no_merchant = "\uffff" if not reverse else ""`. With ascending (`reverse=False`): `"\uffff"` sorts last -- None merchants at end. With descending (`reverse=True`): `""` sorts first in raw order, `reverse=True` puts it last -- None merchants at end.
- Risk: Low. This only affects the sort position of receipts with no merchant name. No downstream logic depends on the position of None-merchant items. Existing tests may need updating if they assert on the order of None-merchant items.
- Files: `backend/src/novascan/api/transactions.py`

**Execution order:**
1. [S3] -- one-line fix, no dependencies
2. [S2] -- extract shared modules (must complete before S1 to avoid merge conflicts)
3. [S1] -- restructure transactions.py using the shared pagination helper from S2

**Verification:**
```bash
cd backend && uv run ruff check src/ && uv run mypy src/novascan/api/transactions.py src/novascan/api/receipts.py && uv run pytest tests/ -v
```

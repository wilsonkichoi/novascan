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

## Security Review

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (1M context) (security-reviewer)
Methodology: STRIDE threat model, OWASP Top 10, CWE Top 25

### Threat Model Summary

| Component | Threats Assessed | Findings |
|-----------|-----------------|----------|
| GET /api/dashboard/summary | S: user_id from JWT (OK). T: aggregation read-only (OK). R: no mutations (OK). I: date params unvalidated (S4). D: unbounded full-partition fetch (S5). E: user_id scoped queries (OK). | S4, S5 |
| GET /api/transactions | S: user_id from JWT (OK). T: read-only (OK). R: no mutations (OK). I: error logging leaks cursor details in str(e) (S6). D: unbounded full-partition fetch same as dashboard (S5). E: cursor ownership checked (OK). | S5, S6 |
| Shared cursor/pagination code | S: cursor ownership validated (OK). T: cursor key validation (OK). I: cursor ValueError messages include internal structure (S6). | S6 |
| API Gateway auth | All /api/{proxy+} routes use Cognito JWT authorizer. /api/health excluded (correct). No new auth gaps. | None |

### Issues Found

**[S4] -- SUGGESTION: startDate/endDate query parameters lack format validation in transactions.py**

`transactions.py:167-168` -- The `startDate` and `endDate` parameters are taken directly from query string and used in DynamoDB KeyConditionExpressions without any format validation. While DynamoDB treats these as string comparisons (so a malformed date like `"x"` or `"9999-99-99"` won't cause a crash or data corruption), the lack of validation has two consequences:

1. **Unexpected query behavior.** A `startDate` of `"abc"` would match against GSI1SK strings like `"2026-04-08#01HQ..."`, returning zero results silently rather than a 400 error. This violates the principle of failing fast on invalid input (CWE-20: Improper Input Validation).
2. **No injection risk.** DynamoDB KeyConditionExpressions use parameterized conditions (via boto3 `Key().between()`), so there is no injection vector here -- this is purely a validation gap, not a security vulnerability.

This is a pre-existing pattern carried over from `receipts.py:195-213` (M2), but this wave copies and extends it in `transactions.py`. The dashboard endpoint validates its `month` parameter with a regex (`_MONTH_RE`), which is the correct pattern.

OWASP: A03:2021 Injection (low -- parameterized queries mitigate). CWE-20: Improper Input Validation.

Suggested fix: Add a `_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")` validation in `transactions.py` (and backport to `receipts.py` in the shared extraction from [S2]). Return 400 VALIDATION_ERROR for malformed dates.

**[S5] -- SUGGESTION: Unbounded full-partition data fetch in dashboard and transactions endpoints enables resource exhaustion**

`dashboard.py:66-85` (`_query_all_gsi1`) and `transactions.py:126-150` (`_fetch_all_matching`) -- Both functions paginate through ALL matching DynamoDB records in the user's partition with no upper bound. For the dashboard, this happens on every request (lines 158 and 226 -- two separate full-partition fetches per call). For transactions, this happens when `sortBy=amount|merchant` or when merchant search is active.

At MVP scale (~100 receipts/month), this is fine. But the design has no circuit breaker:
- A user with 10,000 receipts would cause the Lambda to fetch all records into memory, consuming ~50MB+ of Lambda memory and potentially timing out (30s limit).
- An attacker with a valid JWT could submit many concurrent dashboard requests, each triggering two full-partition scans, amplifying DynamoDB read consumption.

STRIDE: Denial of Service. CWE-400: Uncontrolled Resource Consumption. OWASP: A04:2021 Insecure Design (missing resource limits).

This is an accepted trade-off at MVP scale (SPEC line 681 acknowledges this: "O(all receipts for the month) per request... First candidate for pre-computed aggregates if performance degrades"). Flagging it here to ensure the trade-off is documented, not to mandate a fix.

Suggested mitigation (if desired): Add a safety cap (e.g., 10,000 items) to `_query_all_gsi1` and `_fetch_all_matching`. If the cap is hit, return the result with a warning or log an alert. This prevents Lambda OOM without changing the business logic.

**[S6] -- SUGGESTION: Cursor decode error messages expose internal cursor structure**

`transactions.py:47` and `transactions.py:53` -- When cursor decoding fails, the `ValueError` messages include internal details:
- `"Cursor decode failed: {type(e).__name__}"` -- leaks the exception class name
- `"Cursor has invalid keys: {set(decoded.keys())}"` -- leaks the actual keys the attacker sent, confirming to them what the expected structure is

These messages are caught by the handler at lines 231-235 and logged server-side (correctly), but the same ValueError is also caught at `transactions.py:295-296` with `except Exception: pass` -- meaning in the merchant-search re-pagination path, a malformed cursor is silently ignored rather than returning an error. This is inconsistent with the primary cursor validation path.

The same pattern exists in `receipts.py:63-68` (pre-existing from M3.1 security hardening). However, the M3.1 hardening specifically addressed this issue (SECURITY-REVIEW.md H1/M7), and the current `transactions.py` copy preserves the fix for the primary path but introduces a silent-ignore path at line 295.

STRIDE: Information Disclosure (minor). CWE-209: Generation of Error Message Containing Sensitive Information. OWASP: A04:2021 Insecure Design (inconsistent error handling).

Suggested fix: The silent `except Exception: pass` at `transactions.py:295-296` should log a warning (matching the pattern at line 231) rather than silently ignoring the error. The cursor has already been validated once at line 229, so reaching line 295 with an invalid cursor indicates a programming error, not a user input issue -- but silent suppression makes debugging harder.

### Data Classification Assessment

| Data Element | Classification | Protection | Verdict |
|-------------|---------------|-----------|---------|
| User receipts (merchant, total, category) | Confidential (PII-adjacent financial data) | Scoped to PK=USER#{userId}, JWT-authenticated | PASS |
| Spending totals/aggregates | Confidential | Computed in Lambda memory, not cached, scoped to user | PASS |
| Pagination cursors | Internal | Base64-encoded DynamoDB keys, ownership-validated | PASS |
| Error messages to client | Public | Generic messages, no internal state leaked | PASS (minor concern in S6) |
| Server-side logs | Internal | Detailed errors logged to CloudWatch only | PASS |

### Auth/Authz Verification

| Endpoint | Auth Required | User Scoping | Role Check | Verdict |
|----------|-------------|-------------|-----------|---------|
| GET /api/dashboard/summary | JWT via API Gateway | `user_id` from `sub` claim, GSI1PK=USER#{userId} | None (correct -- all users) | PASS |
| GET /api/transactions | JWT via API Gateway | `user_id` from `sub` claim, GSI1PK=USER#{userId} | None (correct -- all users) | PASS |

Both endpoints extract `user_id` from `router.current_event.request_context.authorizer.jwt_claim["sub"]` which is populated by the API Gateway Cognito JWT authorizer. All DynamoDB queries are scoped to `GSI1PK = USER#{user_id}`. No cross-user data access is possible through these endpoints.

### Security Assessment

**Overall security posture:** The M5 Wave 1 implementation follows the security patterns established during M3.1 hardening. Authentication and data isolation are correctly implemented on both endpoints. The three suggestions are all low-to-medium severity: [S4] is an input validation gap that doesn't enable exploitation (parameterized queries prevent injection), [S5] is an acknowledged MVP trade-off for unbounded data fetches, and [S6] is a minor inconsistency in error handling on a secondary code path. No blockers. The cursor ownership validation and error sanitization patterns from M3.1 have been correctly carried forward.

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

### Fix Plan Analysis (Claude Opus 4.6 (1M context) — 2026-04-08)

**Scope check:** The fix plan covers 3 code review SUGGESTIONs (S1, S2, S3) and defers NITs. However, the security review identified 3 additional SUGGESTIONs (S4, S5, S6). The fix plan does not address these. S4 (date param validation) is actionable and low-risk. S5 (unbounded fetch) is an acknowledged MVP trade-off — deferral is reasonable. S6 (silent cursor exception) is a minor inconsistency worth fixing alongside S1/S2. Recommendation: add S4 and S6 to the fix scope; defer S5 with a TODO comment.

**[S1] (sortBy=date with merchant search double-fetches from DynamoDB) — Approve**
My approach: Reading `transactions.py:223-314` independently, I traced the `sortBy == "date"` code path. At line 237, the code runs a paginated DynamoDB query with `Limit`. At lines 250-265, it runs a Count query loop. Then at line 270, it checks `if merchant_search` and calls `_fetch_all_matching` — which re-queries the entire partition. The initial paginated query (line 237-239) and the Count query (lines 250-265) are thrown away. The fix is to check `merchant_search` before line 237 and branch early to the in-memory path, skipping both the paginated query and the Count query.
Plan's approach: Restructure into two sub-branches within `sortBy == "date"` — merchant-search goes to `_fetch_all_matching` directly, non-merchant stays on the DynamoDB-paginated path. Aligns with my analysis. The risk note about cursor divergence between the `sortBy=date+merchant` path and the `sortBy=amount|merchant` path is valid and well-identified. The suggestion to extract in-memory pagination into a helper (linking to S2) is a good mitigation.

**[S2] (Duplicated cursor/pagination helpers) — Revise**
My approach: Comparing `receipts.py:43-83` and `transactions.py:28-61` side by side, the `_encode_cursor`, `_decode_cursor`, `_VALID_CURSOR_KEYS`, `_error_response`, and `_decimal_to_float` are functionally identical. I would extract `encode_cursor`, `decode_cursor`, and `VALID_CURSOR_KEYS` into `shared/pagination.py`. I would extract `error_response` into `shared/responses.py`. I would NOT extract `_decimal_to_float` — the dashboard has `_to_float` with different semantics (returns 0.0 for None vs None for None). Extracting both under a shared name would create confusion about which behavior is expected, and callers have different needs. Keeping `_decimal_to_float` local avoids a false abstraction.
Plan's approach includes extracting `decimal_to_float` into `shared/responses.py`. This is flawed because:
1. `_decimal_to_float` in `receipts.py:86-90` and `transactions.py:73-77` return `None` for `None` input. The dashboard's `_to_float` (line 88-94) returns `0.0` for `None`. Extracting one version creates a naming collision risk.
2. `_decimal_to_float` is a 3-line function. Per project convention ("three similar lines > one unnecessary helper"), it does not clear the threshold for extraction despite appearing in two files. The security argument that justified extracting `_decode_cursor` (30+ lines of security-critical code) does not apply to a trivial type conversion.
3. `_error_response` is also used in `receipts.py`, `transactions.py`, `upload.py`, and `categories.py` — but not all copies are identical (`upload.py` has a different error shape for validation errors). Extracting only the standard version is fine, but scope it carefully.
**Alternative:** Extract only `encode_cursor`, `decode_cursor`, `VALID_CURSOR_KEYS` into `shared/pagination.py`. Extract `error_response` into `shared/responses.py`. Leave `_decimal_to_float` and `_to_float` as module-local helpers.

**[S3] (Merchant sort places None merchants inconsistently) — Approve**
My approach: At `transactions.py:332`, when `reverse=False` (ascending), `no_merchant = ""`. Empty string sorts before all real merchant names, placing None merchants at the start, not the end. When `reverse=True` (descending), `no_merchant = "\uffff"`. In raw order, `"\uffff"` sorts last; after `reverse=True`, it ends up first. Both directions put None merchants at the beginning. The fix: `no_merchant = "\uffff" if not reverse else ""`. Ascending: `"\uffff"` sorts after all real names -> None at end. Descending: `""` sorts first in raw order, reversed to last -> None at end.
Plan's approach: Identical. Swap the sentinel values. The risk assessment (low, no downstream dependencies on None-merchant position) is accurate.

**[S4] (startDate/endDate lack format validation — from security review) — Missing from fix plan**
My approach: Reading `transactions.py:167-168`, `startDate` and `endDate` are used directly in DynamoDB KeyConditionExpression without validation. The dashboard validates its `month` param with `_MONTH_RE` regex (line 24). The transactions endpoint should do the same for date params. Add `_DATE_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")` and validate both params, returning 400 on mismatch. This is a quick addition that matches the established pattern and should be included in the fix scope.

**[S5] (Unbounded full-partition data fetch — from security review) — Acceptable deferral**
The security review itself acknowledges this is an accepted MVP trade-off (SPEC line 681). Adding a safety cap is a good idea for a future iteration but not urgent. Recommend adding a `# TODO(post-MVP): Add safety cap per SECURITY-REVIEW S5` comment at `dashboard.py:66` and `transactions.py:126` so it is not lost.

**[S6] (Silent cursor exception at transactions.py:295 — from security review) — Missing from fix plan**
My approach: At `transactions.py:295-296`, the `except Exception: pass` silently swallows cursor decode errors in the merchant-search re-pagination path. The cursor was already validated at line 228-235 (where errors return 400). Reaching line 295 with an invalid cursor means something changed between the two decode calls — logically impossible in a single request, but the silent `pass` makes debugging future issues harder. Fix: replace `pass` with `logger.warning("Cursor re-decode failed in merchant search path", extra={"user_id": user_id})`. Low risk, improves observability.

**Execution order (revised to include S4 and S6):**
1. [S3] — one-line sentinel swap, no dependencies
2. [S4] — add date regex validation to transactions.py (independent, quick)
3. [S6] — replace silent `except: pass` with logger.warning (independent, quick)
4. [S2] — extract shared modules (revised: pagination.py + responses.py, but NOT decimal_to_float)
5. [S1] — restructure transactions.py merchant-search branch

**Verification:**
```bash
cd backend && uv run ruff check src/ && uv run mypy src/novascan/api/transactions.py src/novascan/api/receipts.py src/novascan/shared/pagination.py src/novascan/shared/responses.py && uv run pytest tests/ -v
```

### Fix Results (Claude Opus 4.6 (1M context) -- 2026-04-08)

**Branch:** `fix/wave-m5-1` (based on `feature/m5-wave1-backend-apis`)
**Status: 5/5 fixed, 1 deferred (S5)**

**[S1] (sortBy=date with merchant search double-fetches from DynamoDB) -- Fixed**
- What was changed: Restructured the `sortBy == "date"` branch condition to `sortBy == "date" and not merchant_search`. When merchant search is active with date sort, the code now falls through directly to the in-memory `else` branch, avoiding the wasted DynamoDB paginated query + Count query.
- Files modified: `backend/src/novascan/api/transactions.py`

**[S2] (Duplicated cursor/pagination helpers) -- Fixed**
- What was changed: Extracted `encode_cursor`, `decode_cursor`, and `VALID_CURSOR_KEYS` into `shared/pagination.py`. Extracted `error_response` into `shared/responses.py`. Updated `receipts.py`, `transactions.py`, and `categories.py` to import from shared modules. Removed all local duplicates. Per fix plan analysis, `_decimal_to_float` and `_to_float` were intentionally left as module-local helpers (different semantics, below extraction threshold).
- Files modified: `backend/src/novascan/shared/pagination.py` (created), `backend/src/novascan/shared/responses.py` (created), `backend/src/novascan/api/receipts.py`, `backend/src/novascan/api/transactions.py`, `backend/src/novascan/api/categories.py`

**[S3] (Merchant sort places None merchants inconsistently) -- Fixed**
- What was changed: Swapped the sentinel values: `no_merchant = "\uffff" if not reverse else ""`. Ascending now places None merchants at end; descending also places them at end.
- Files modified: `backend/src/novascan/api/transactions.py`

**[S4] (startDate/endDate lack format validation) -- Fixed**
- What was changed: Added `_DATE_RE` regex pattern and validation checks for `startDate` and `endDate` query params, returning 400 VALIDATION_ERROR for malformed dates. Matches the established pattern from dashboard's `_MONTH_RE`.
- Files modified: `backend/src/novascan/api/transactions.py`

**[S5] (Unbounded full-partition data fetch) -- Deferred**
- Reason: Acknowledged MVP trade-off per SPEC. Added TODO comments at `dashboard.py:_query_all_gsi1` and `transactions.py:_fetch_all_matching` to track for post-MVP.

**[S6] (Silent cursor exception at transactions.py:295) -- Fixed**
- What was changed: The silent `except Exception: pass` was eliminated as part of the [S1] restructure. The `sortBy=date` + merchant path now uses the `else` branch which has proper `logger.warning` + error_response on cursor decode failure.
- Files modified: `backend/src/novascan/api/transactions.py`

**Verification:**
- `ruff check src/` -- PASS
- `mypy src/novascan/api/transactions.py src/novascan/api/receipts.py src/novascan/api/categories.py src/novascan/shared/pagination.py src/novascan/shared/responses.py` -- PASS
- `pytest tests/ -v` -- PASS (482 passed)

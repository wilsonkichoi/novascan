# Wave 1 Review: Security Hardening — Critical Fixes + Independent Hardening

Reviewed: 2026-04-04
Reviewer: Claude Opus 4.6 (1M context)
Cross-referenced: SPEC.md Section 3 (Auth), Section 5 (DB Schema), Section 12 (Security); HANDOFF.md; SECURITY-REVIEW.md (C1, C2, H1, H2, H3, M2, M4, M7, M13)

## Task 3.8: Sanitize Custom Category Inputs in Extraction Prompt [C1]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| `build_extraction_prompt()` validates custom category names before interpolation | PASS | Calls `validate_category_name()` + `validate_category_slug()` for each category |
| Category names restricted to: alphanumeric, spaces, `& / , . ( ) -`, max 64 chars | PASS | `_VALID_NAME_RE = r"^[a-zA-Z0-9 &/,.()\-]+$"`, `_MAX_CATEGORY_LENGTH = 64` |
| Category slugs restricted to: lowercase alphanumeric + hyphens, max 64 chars | PASS | `_VALID_SLUG_RE = r"^[a-z0-9\-]+$"` |
| Names containing newlines, markdown headers, or instruction-like patterns rejected with `ValueError` | PASS | 7 injection patterns checked including `\n\r`, `##`, `ignore previous instructions`, etc. |
| Custom categories placed in structured JSON data block | PASS | Uses `json.dumps()` inside a fenced code block |
| Existing tests pass | PASS | 27 passed |
| Ruff check passes | PASS | |

### Issues Found

No issues found for Task 3.8. The implementation is solid:
- Validation-before-interpolation pattern is correct
- The structured JSON block prevents format-escape attacks
- `parentCategory` is also validated when present
- Injection pattern list covers common prompt injection vectors

---

## Task 3.9: Replace DynamoDB Scan with GSI2 Query [C2 + M13]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| DynamoDB table has GSI2: `GSI2PK` (S), projection KEYS_ONLY | PASS | `storage.py:44-48` |
| `_lookup_user_id` uses `table.query(IndexName="GSI2")` | PASS | `load_custom_categories.py:202-207` |
| LoadCustomCategories Lambda IAM grants only `dynamodb:Query` and `dynamodb:GetItem` | PASS | `pipeline.py:202-210`, no `Scan` permission |
| Upload endpoint sets `GSI2PK = receiptId` on receipt creation | PASS | `upload.py:75` |
| `RECEIPTS_BUCKET` env var set on all pipeline Lambdas | PASS | All 5 Lambdas: load_custom_categories, textract_extract, nova_structure, bedrock_extract, finalize |
| CDK synth succeeds, snapshot regenerated | PASS | |
| Existing tests pass | PASS | 72 infra + 3 integration |

### Issues Found

**[S1] -- SUGGESTION: `load_custom_categories.py:92` leaks exception message in error response**

`backend/src/novascan/pipeline/load_custom_categories.py:92` -- The error handler returns `{"error": str(e), "errorType": type(e).__name__}`, which includes the raw exception message. This is the same pattern flagged by SECURITY-REVIEW H4 (Error Payloads) and is scheduled for remediation in Task 3.13 (Wave 2).

This is not a blocker for Wave 1 because the error payload is internal to the Step Functions state machine (never reaches an API client directly), and the fix is explicitly planned in the next wave. Noting it here for cross-wave traceability.

---

## Task 3.10: Validate Pagination Cursor + Sanitize API Errors [H1 + M7]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| `_decode_cursor()` validates decoded JSON has exactly `{GSI1PK, GSI1SK, PK, SK}` keys | PASS | `receipts.py:53` |
| Decoded cursor's `GSI1PK` must equal `USER#{authenticated_userId}` | PASS | `receipts.py:58-60` |
| Error response uses generic message `"Invalid pagination cursor"` (no `str(e)`) | PASS | `receipts.py:128` |
| Detailed error logged server-side via `logger.warning()` | PASS | `receipts.py:121-124` |
| Existing list receipts tests updated and passing | PASS | 29 tests |
| Ruff check passes | PASS | |

### Issues Found

**[S2] -- SUGGESTION: Cursor PK/SK values not validated for ownership**

`backend/src/novascan/api/receipts.py:53-60` -- The cursor validation checks `GSI1PK` matches the authenticated user, but does not check that `PK` also matches `USER#{user_id}`. A crafted cursor could have `GSI1PK: USER#me` but `PK: USER#someone-else`. Since the GSI query uses `KeyConditionExpression` on `GSI1PK`, DynamoDB will only return items from the authenticated user's partition regardless, so this is not a data exposure risk. However, it could cause unexpected pagination behavior (skipping items or returning no results) if `PK` points to a non-existent position. Validating `PK` would make the defense-in-depth more complete.

Suggested fix:
```python
expected_pk = f"USER#{user_id}"
if decoded.get("PK") != expected_pk:
    raise ValueError("Cursor PK does not match authenticated user")
```

---

## Task 3.11: Auth Construct Hardening [H2 + H3 + M4]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| `AllowedFirstAuthFactors` contains only `["EMAIL_OTP"]` (PASSWORD removed) | PASS | `auth.py:84` |
| Post-Confirmation Lambda IAM scoped to `userpool/novascan-*` (not `userpool/*`) | PASS | `auth.py:90-101` |
| Refresh token validity set to 7 days | PASS | `auth.py:114` via `cdk.Duration.days(7)` |
| CDK synth succeeds, snapshot regenerated | PASS | |
| Auth construct CDK tests updated and passing | PASS | 15/15 auth tests, 75/75 full infra |

### Issues Found

No issues found for Task 3.11. All three hardening changes are correct and well-tested:
- The `EMAIL_OTP`-only policy directly addresses H2
- The scoped ARN `novascan-*` narrows the blast radius without breaking the circular dependency workaround (H3)
- Refresh token validity is explicit at 7 days instead of Cognito's default 30 days (M4)
- Test coverage includes direct assertions on the CloudFormation template for all three properties

---

## Task 3.12: CloudFront Security Response Headers [M2]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| `Strict-Transport-Security: max-age=63072000; includeSubdomains` | PASS | `frontend.py:38-42` |
| `X-Content-Type-Options: nosniff` | PASS | `frontend.py:43-45` |
| `X-Frame-Options: DENY` | PASS | `frontend.py:46-49` |
| `Referrer-Policy: strict-origin-when-cross-origin` | PASS | `frontend.py:50-53` |
| CSP with required directives | PASS | `frontend.py:54-62` |
| Policy attached to distribution's `default_behavior` | PASS | `frontend.py:75` |
| CDK synth succeeds, snapshot regenerated | PASS | |
| Frontend CDK tests updated and passing | PASS | 13 tests (6 existing + 7 new) |

### Issues Found

No issues found for Task 3.12. The implementation matches the PLAN acceptance criteria exactly. The CSP directive string matches the SECURITY-REVIEW M2 recommendation. All 5 security headers are configured with `override=True`. Test coverage verifies each header individually plus the policy attachment.

---

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| SPEC S12: IAM least-privilege for Lambda roles | LoadCustomCategories scoped to Query+GetItem only (no Scan) | PASS |
| SPEC S12: Presigned URLs expire after 15 min | Not in wave scope -- existing behavior unchanged | N/A |
| SPEC S3: Cognito email OTP (passwordless) | PASSWORD removed, EMAIL_OTP only | PASS |
| SPEC S3: Post-Confirmation Lambda adds user to group | IAM scoped to `novascan-*` user pools | PASS |
| SPEC S5: GSI1 for receipt queries | Cursor validation ensures GSI1PK ownership | PASS |
| SPEC S5: DynamoDB single-table design | GSI2 added for receipt-to-user lookup | PASS |
| SPEC S12: All data in transit over HTTPS | CloudFront HSTS + security headers added | PASS |
| SPEC S3: Data isolation (PK scoping) | Cursor injection prevented via key+ownership validation | PASS |
| SECURITY-REVIEW C1: Prompt injection | Category name/slug validation + JSON block | PASS |
| SECURITY-REVIEW C2: Cross-user data exposure via scan | Scan replaced with GSI2 query | PASS |
| SECURITY-REVIEW H1: Cursor injection | Key set + GSI1PK ownership validated | PASS |
| SECURITY-REVIEW H2: PASSWORD auth enabled | Removed from AllowedFirstAuthFactors | PASS |
| SECURITY-REVIEW H3: Wildcard Cognito IAM | Scoped to `novascan-*` | PASS |
| SECURITY-REVIEW M2: Missing security headers | All 5 headers configured on CloudFront | PASS |
| SECURITY-REVIEW M4: Refresh token TTL | Set to 7 days | PASS |
| SECURITY-REVIEW M7: Error info leak | Generic "Invalid pagination cursor" message | PASS |
| SECURITY-REVIEW M13: Excessive IAM | Scan removed from policy | PASS |

## Things Done Well

- **Defense-in-depth on prompt injection (3.8):** The implementation layers three defenses: character allowlist, injection pattern detection, and structured JSON output. Any single layer failing still leaves protection.
- **GSI2 design (3.9):** KEYS_ONLY projection is the right choice -- minimal cost, minimal data exposure, solves the exact problem.
- **Scoped IAM on LoadCustomCategories (3.9):** Replacing the broad `grant_read_data()` with explicit `Query`+`GetItem` actions is proper least-privilege.
- **Error sanitization separation (3.10):** Clean separation between the generic client-facing message and the detailed server-side log.
- **Auth hardening test quality (3.11):** The CDK assertion tests directly verify CloudFormation template output, which is the right level for infrastructure tests. The `Fn::Join` ARN matcher for the scoped IAM is particularly well-crafted.
- **Comprehensive security header tests (3.12):** Each header gets its own test, plus a test for the policy-to-distribution attachment. This prevents regression if individual headers are accidentally removed.
- **RECEIPTS_BUCKET propagation (3.9):** Adding the env var to all 5 pipeline Lambdas proactively unblocks Wave 2 Task 3.13 (S3 key validation needs the bucket name).
- **Commit hygiene:** Each task is a focused, single-purpose commit on the feature branch.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| S1 | SUGGESTION | 3.9 | `load_custom_categories.py:92` leaks `str(e)` in error response | Defer to Task 3.13 (Wave 2) -- already planned |
| S2 | SUGGESTION | 3.10 | Cursor `PK` value not validated for user ownership | Add `PK` ownership check for defense-in-depth |

**Overall verdict:** Wave 1 is solid. All 5 tasks meet their acceptance criteria, and the implementations match the security review recommendations. Two low-severity suggestions identified: S1 is already scoped for Wave 2 remediation, and S2 is a defense-in-depth improvement that does not represent a data exposure risk. No blockers.

## Review Discussion

### Fix Plan (Claude Opus 4.6 (1M context) -- 2026-04-04)

**Note:** Generated in the same context as the review. Run `/agentic-dev:review fix-plan-analysis wave 1` in a separate session for an independent second opinion.

**Scope: 2 issues (0 BLOCKERs, 2 SUGGESTIONs)**

**[S1] (load_custom_categories.py leaks str(e) in error response)**
- Independent assessment: Reading `load_custom_categories.py:87-92`, the error handler catches all exceptions from `_query_custom_categories()` and returns the raw exception message via `str(e)`. This could expose DynamoDB error details (table name, key structure) in the Step Functions execution history, which is visible in the AWS Console. However, this payload is internal to Step Functions and never reaches an API client directly.
- Review comparison: Agree with the review's characterization. This is correctly categorized as a SUGGESTION rather than a BLOCKER because (a) the exposure is limited to Step Functions state, not client-facing, and (b) Task 3.13 in Wave 2 explicitly addresses H4 (error sanitization) for all pipeline Lambdas including this one.
- Fix: **Defer to Task 3.13 (Wave 2).** No action needed in this wave. The fix will sanitize the return to `{"error": "load_custom_categories_failed", "errorType": type(e).__name__}`.
- Risk: None from deferral -- Step Functions execution history is only accessible to users with IAM Console access, not end users.
- Files: `backend/src/novascan/pipeline/load_custom_categories.py` (Wave 2)

**[S2] (Cursor PK value not validated for user ownership)**
- Independent assessment: Reading `receipts.py:53-62`, the cursor validation checks key names and GSI1PK ownership but not PK ownership. Since the DynamoDB GSI query uses `KeyConditionExpression` on `GSI1PK`, a mismatched PK value cannot cause data from another user's partition to be returned. The worst case is that pagination starts from an unexpected position within the user's own partition (items could be skipped or duplicated in a page transition). This is a pagination correctness issue, not a security issue.
- Review comparison: Agree. The review correctly identifies this as defense-in-depth rather than a security vulnerability. The GSI1PK check is the security-critical one, and it's present.
- Fix: Add PK ownership validation in `_decode_cursor()`:
  ```python
  expected_pk = f"USER#{user_id}"
  if decoded.get("PK") != expected_pk:
      raise ValueError("Cursor PK does not match authenticated user")
  ```
  One-line addition after the GSI1PK check at line 60.
- Risk: Could reject legitimate cursors if there's ever a case where PK format differs from `USER#{sub}`. Currently all receipt records use this format, so the risk is negligible.
- Files: `backend/src/novascan/api/receipts.py`

**Execution order:**
1. S2 first (simple one-line addition, immediate)
2. S1 deferred to Wave 2 Task 3.13

**Verification:**
- `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_receipts_list.py -v`

### Fix Plan Analysis (Claude Opus 4.6 (1M context) -- 2026-04-04)

**Phase A — Independent source read performed before reviewing the fix plan.**

**[S1] (load_custom_categories.py leaks str(e) in error response) — Approve**
My approach: Reading `load_custom_categories.py:87-92` before the fix plan, I observed the `except Exception` block returns `{"error": str(e), "errorType": type(e).__name__}`. The `str(e)` can leak DynamoDB internals (table name, key condition expressions, throttling details) into the Step Functions execution history JSON, which is visible to anyone with `states:DescribeExecution` IAM permissions. However, this is not client-facing — the Step Functions output feeds into the Finalize Lambda or gets caught by the Catch block, never returned to an API caller. My independent fix would be to replace line 92 with `{"error": "load_custom_categories_failed", "errorType": type(e).__name__}`, but since Task 3.13 (Wave 2) explicitly addresses H4 error sanitization across all pipeline Lambdas including this one, deferral is correct.
Plan's approach: Defer to Task 3.13 (Wave 2). Aligns with my analysis because: (a) the fix is already scoped in Wave 2 with the exact same replacement pattern I would use, (b) fixing it now would create a merge conflict when Task 3.13 touches the same file, and (c) the blast radius is limited to IAM-authenticated AWS Console users — not end users.

**[S2] (Cursor PK value not validated for user ownership) — Approve**
My approach: Reading `receipts.py:53-62` before the fix plan, I identified that `_decode_cursor()` validates `GSI1PK` ownership (line 58-60) but not `PK`. Since the GSI1 query uses `KeyConditionExpression` on `GSI1PK` (line 90), DynamoDB enforces partition isolation at the query level — a mismatched PK cannot return another user's data. The gap is pagination correctness: DynamoDB uses `ExclusiveStartKey` as a position marker, and a PK pointing to a different user's partition could cause the cursor to resolve to no items (empty page) or skip items within the user's own partition. My independent fix: add `if decoded.get("PK") != f"USER#{user_id}": raise ValueError(...)` immediately after the GSI1PK check on line 60.
Plan's approach: Add a PK ownership check after line 60 with the same pattern. Aligns with my analysis — both the fix location and the code are identical to what I designed independently. The identified risk (future PK format divergence) is negligible given that the `USER#{sub}` pattern is established across all entities in the single-table design (SPEC Section 5) and changing it would require a data migration.

**Overall assessment:** Both fixes are sound. The execution order (S2 immediate, S1 deferred) is correct — S2 is a one-line addition with no cross-wave dependency, while S1 deferral avoids duplicate work and merge conflicts with Task 3.13. No revisions needed.

### Fix Results

**Branch:** `feature/m3.1-wave1-critical-fixes` (fix commit `217f353`)
**Date:** 2026-04-04

**[S1] (load_custom_categories.py leaks str(e) in error response) — Deferred to Wave 2 Task 3.13**
No code change in this wave. The `str(e)` leak at `load_custom_categories.py:92` will be remediated when Task 3.13 applies H4 error sanitization across all pipeline Lambdas.

**[S2] (Cursor PK value not validated for user ownership) — Fixed**
Commit `217f353` adds PK ownership check in `_decode_cursor()` at `receipts.py:62-64`:
```python
expected_pk = f"USER#{user_id}"
if decoded.get("PK") != expected_pk:
    raise ValueError("Cursor PK does not match authenticated user")
```
Also removed unused `RECEIPT` import from `load_custom_categories.py` (leftover from task 3.9 merge).

### Fix Verification (Claude Opus 4.6 (1M context) -- 2026-04-04)

**Status: 1/2 fixed, 1/2 deferred (0 not fixed, 0 regressions)**

**[S1] (load_custom_categories.py leaks str(e) in error response) — Deferred (correct)**
Verified: `load_custom_categories.py:92` still contains `{"error": str(e), "errorType": type(e).__name__}`. This is intentionally deferred to Task 3.13 (Wave 2), which explicitly addresses H4 error sanitization for all pipeline Lambdas. No action needed in this wave. The deferral avoids duplicate work and merge conflicts.

**[S2] (Cursor PK value not validated for user ownership) — Fixed**
Verified by:
1. Source code inspection: `receipts.py:62-64` adds `expected_pk = f"USER#{user_id}"` and rejects cursors where `PK` does not match. The check is placed immediately after the existing `GSI1PK` check (line 58-60), maintaining the defense-in-depth layering.
2. `git diff 217f353^..217f353` confirms exactly +4 lines in `receipts.py` (the PK check) and -1/+1 line in `load_custom_categories.py` (unused import removal). No unrelated changes.
3. Unused `RECEIPT` import removed from `load_custom_categories.py:21` — clean side fix, no functional impact.

**Verification commands:**
- `cd backend && uv run ruff check src/` — PASS (all checks passed)
- `cd backend && uv run pytest tests/unit/test_receipts_list.py -v` — PASS (29/29 tests passed)

**Note:** No existing test specifically covers the case where `GSI1PK` matches the authenticated user but `PK` does not (the exact gap S2 addresses). The existing `test_cursor_targeting_other_user_returns_400` test uses a cursor where both `GSI1PK` and `PK` belong to "attacker-user", so it trips on the `GSI1PK` check first. A dedicated test for mismatched PK would strengthen coverage; this is appropriate scope for Task 3.18 (Wave 3 security tests).

**Verdict:** 1/2 issues resolved in this wave. 1/2 correctly deferred to Wave 2 (Task 3.13). No regressions found. Wave 1 is ready to merge.

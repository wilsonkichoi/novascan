# Wave 3 Review: Security Hardening Tests

Reviewed: 2026-04-04
Reviewer: Claude Opus 4.6 (1M context)
Cross-referenced: SPEC.md (Sections 5, 7, 12), HANDOFF.md, SECURITY-REVIEW.md, PLAN-M3.1.md

## Task 3.18: Security Hardening Backend Tests [TEST]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Prompt injection tests: names with newlines/markdown/instruction-like text rejected; safe names accepted; invalid slugs rejected | PASS | 34 tests covering C1 vectors: newlines, carriage returns, markdown headers, instruction-like patterns, special chars, length limits |
| Cursor tests: tampered cursor (wrong GSI1PK, extra keys, missing keys) returns 400; valid cursor accepted | PASS | 13 tests covering H1/M7: cross-user GSI1PK, mismatched PK, extra/missing keys, non-base64, non-JSON, array-instead-of-object |
| Pipeline tests: missing required event fields return `"error": "invalid_event"`; oversized image returns error; error payloads never contain raw exception messages | PASS | 25 tests covering H4/H5/H6/L5/M8: event validation, S3 key format, image size guard, model ID allowlist, error sanitization |
| Finalize tests: duplicate pipeline execution doesn't create duplicate line items; idempotent receipt updates | PASS | 8 tests covering H4/M11/M12/L8: generic failure reason, idempotency, S3 encryption, internal fields |
| Upload tests: presigned URL includes ContentLength; ValidationError response sanitized | PASS | 9 tests covering M6/L4 + GSI2PK creation check |
| `cd backend && uv run pytest tests/unit/test_security_*.py -v` passes | PASS | 101 passed, 8 warnings (metrics flush — harmless) in 1.91s |

### Issues Found

**[S1] -- SUGGESTION: Unused imports in multiple test files**

`backend/tests/unit/test_security_pipeline.py:13-15,20` -- `os`, `typing.Any`, `unittest.mock.patch`, and `ALLOWED_MODEL_IDS` are imported but never used.

`backend/tests/unit/test_security_finalize.py:13-15` -- `json`, `dataclasses.dataclass`, and `decimal.Decimal` are imported but never used.

`backend/tests/integration/test_security_pipeline_flow.py:11-14` -- `json`, `os`, and `decimal.Decimal` are imported but never used.

Why it matters: ruff lint fails (`cd backend && uv run ruff check tests/`) with 18 errors across these files. The project CI runs ruff as part of quality gates. Import ordering (I001) also flagged in `test_security_cursor.py`, `test_security_finalize.py`, `test_security_pipeline.py`, `test_security_prompt_injection.py`, `test_security_upload.py`, and `test_security_pipeline_flow.py`.

Fix: Run `uv run ruff check --fix` in the backend directory to auto-fix all 16 fixable errors (unused imports + import ordering). The remaining 2 E501 line-length violations in `test_security_pipeline_flow.py:255-256` need manual wrapping.

**[S2] -- SUGGESTION: Unused import in CDK test file**

`infra/tests/test_security_hardening.py:21` -- `Capture` is imported from `aws_cdk.assertions` but never used.

Why it matters: Same as S1 -- ruff lint fails with 1 error.

Fix: Remove `Capture` from the import.

**[S3] -- SUGGESTION: Weak assertion in Nova error sanitization test**

`backend/tests/unit/test_security_pipeline.py:332-336` -- `test_nova_error_payload_no_raw_exception` sends an event with an invalid S3 key (`01ABCDEFGHIJKLMNOPQRSTUV.jpg`, 25 chars instead of 26) which triggers the `invalid_event` path rather than the actual exception-handling `except` block. The test then uses a conditional `if "error" in result:` which means the assertion is effectively always about the validation path, never actually testing the error sanitization path (H4) for Nova.

Why it matters: The test name and docstring claim to verify that raw exception messages are not leaked, but it is testing the wrong code path. If the `except Exception` block in `nova_structure.handler` contained a bug that leaked `str(e)`, this test would not catch it.

Fix: Either (a) provide a valid event structure and mock the internal Bedrock call to raise an exception (similar to the Textract test at line 270), or (b) rename the test to clarify it is only testing the validation path.

**[N1] -- NIT: Line length violations**

`backend/tests/integration/test_security_pipeline_flow.py:255-256` -- Two lines exceed 120 chars (129 and 124). These are inline dict literals with long error strings.

Fix: Break the dicts across multiple lines.

## Task 3.19: Security Hardening CDK + Integration Tests [TEST]

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| CDK tests verify: GSI2 exists with KEYS_ONLY projection | PASS | Two dedicated tests: `test_gsi2_exists_with_gsi2pk` and `test_gsi2_projection_is_keys_only` |
| No PASSWORD in AllowedFirstAuthFactors | PASS | Iterates all UserPool resources, asserts PASSWORD absent and EMAIL_OTP present |
| Cognito IAM not wildcard userpool/* | PASS | Checks both string and Fn::Join ARN forms |
| CloudFront has security headers (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP) | PASS | 6 tests: policy existence + each header individually |
| S3 PutObject IAM scoped to receipts/* prefix | PASS | Checks serialized ARN for `/receipts/*` |
| API Gateway throttling configured (burst=10, rate=5) | PASS | Checks DefaultRouteSettings + access logging |
| Bedrock IAM region-scoped (references AWS::Region) | PASS | Verifies Fn::Join contains `Ref: AWS::Region` |
| No dynamodb:Scan in dedicated LoadCustomCategories IAM policy | PASS | Finds policy with Query+GetItem without Scan or PutItem |
| S3 lifecycle rules exist (IA + Glacier transitions) | PASS | Verifies at least 2 transitions in lifecycle config |
| Refresh token validity set to 7 days | PASS | Checks RefreshTokenValidity=7, TokenValidityUnits=days |
| Textract IAM uses resources=["*"] (AWS requirement) | PASS | Verifies Resource: * for textract:AnalyzeExpense |
| Integration test: GSI2 query returns correct userId for a given receiptId | PASS | 4 GSI2 tests: basic lookup, nonexistent receipt, multi-user isolation, custom categories pass-through |
| `cd infra && uv run pytest tests/test_security_hardening.py -v` passes | PASS | 18 passed in 5.23s |
| `cd backend && uv run pytest tests/integration/ -v` passes | PASS | 37 passed (6 new + 31 existing) in 2.61s |

### Issues Found

S2 above applies to this task (unused `Capture` import in `test_security_hardening.py`).

**[S4] -- SUGGESTION: Fix to existing test not documented as out-of-scope change**

`backend/tests/integration/test_pipeline_flow.py:806-832` -- The diff modifies `test_failure_reason_populated` in a file outside the task's planned scope. The task review file documents this as fixing a pre-existing test broken by H4 error sanitization from task 3.14, which is a valid reason. However, the PLAN-M3.1.md file lists for task 3.19 does not include `test_pipeline_flow.py`.

Why it matters: Minor discrepancy between planned scope and actual changes. The fix is correct and necessary -- the old assertion (`"Textract error" in failure_reason`) directly contradicts the H4 security hardening that task 3.14 implemented. Not fixing it would leave a broken pre-existing test. This is more of a documentation note than a real issue.

Fix: No code change needed. The task review file already documents this change with rationale. Acknowledged as appropriate scope expansion.

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| SPEC Section 12 Security: IAM least-privilege | CDK tests verify scoped S3, Bedrock, LoadCustomCategories IAM policies; no Scan permission | PASS |
| SPEC Section 12 Security: Data isolation (PK = USER#{userId}) | GSI2 integration tests verify user isolation across multiple users | PASS |
| SPEC Section 12 Security: Presigned URLs expire after 15 minutes | Upload tests verify ContentLength parameter in presigned URL params | PASS |
| SPEC Section 5 DB Schema: GSI2 for receipt-to-user lookup | CDK tests verify GSI2 exists with GSI2PK partition key, KEYS_ONLY projection | PASS |
| SPEC Section 12 Security: All data encrypted at rest | Finalize tests verify S3 metadata update includes encryption; CDK lifecycle tests exist | PASS |
| SECURITY-REVIEW C1: Prompt injection prevention | 34 tests covering name/slug validation + prompt builder integration | PASS |
| SECURITY-REVIEW C2: Cross-user data exposure via Scan | GSI2 integration tests replace Scan with Query; CDK test verifies no Scan in IAM | PASS |
| SECURITY-REVIEW H1+M7: Cursor injection + error info leak | 13 tests covering all cursor tampering vectors; error messages verified generic | PASS |
| SECURITY-REVIEW H2+H3+M4: Auth hardening | CDK tests verify EMAIL_OTP only, scoped Cognito IAM, 7-day refresh token | PASS |
| SECURITY-REVIEW H4: Error payload sanitization | Tests across pipeline, finalize, and integration verify generic error messages | PASS |
| SECURITY-REVIEW H5: S3 key validation | 10 tests covering path traversal, wrong prefix, wrong extension, bucket mismatch | PASS |
| SECURITY-REVIEW H6: Event validation | Tests verify missing/empty/None fields detected | PASS |
| SECURITY-REVIEW L5: Image size guard | 5 tests covering exact max, over max, small, zero, very large | PASS |
| SECURITY-REVIEW M5: API Gateway throttling | CDK tests verify burst=10, rate=5, access logging enabled | PASS |
| SECURITY-REVIEW M8: Model ID validation | 5 tests covering nova-lite, nova-pro, unknown, empty, arbitrary | PASS |
| SECURITY-REVIEW M11: Idempotency | Finalize tests verify no duplicate line items on re-execution, stable receipt data | PASS |

## Things Done Well

1. **Comprehensive security contract testing.** 125 new tests (101 unit + 18 CDK + 6 integration) covering all SECURITY-REVIEW findings from C1 through L8. The test-per-finding coverage is thorough.

2. **Black-box test approach.** The tests correctly test the security *contract* rather than the implementation. For example, cursor tests encode tampered cursors and assert HTTP 400 without knowing the validation internals. This makes the tests resilient to refactoring.

3. **Strong CDK assertion patterns.** The CDK security tests use a good mix of `Template.has_resource_properties` with `Match.object_like` for structural assertions (headers, GSI2) and raw JSON traversal for more complex checks (IAM policy analysis with Fn::Join). This is the right level of specificity.

4. **Multi-user isolation test.** `test_gsi2_query_multiple_users_isolated` in the integration tests explicitly creates two users and verifies that each GSI2 lookup returns the correct userId. This is the exact test needed for C2.

5. **Idempotency test pattern.** The finalize idempotency tests call `_invoke` twice with the same event and verify line item count doesn't double. This directly validates M11.

6. **Appropriate fix to pre-existing test.** The change to `test_pipeline_flow.py` correctly updates the assertion to match the new H4 behavior rather than leaving a broken test.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| S1 | SUGGESTION | 3.18 | Unused imports + import ordering in 3 backend test files (18 ruff errors) | `uv run ruff check --fix` + manual line wrapping |
| S2 | SUGGESTION | 3.19 | Unused `Capture` import in CDK test file (1 ruff error) | Remove unused import |
| S3 | SUGGESTION | 3.18 | Nova error sanitization test tests wrong code path (validation, not exception handling) | Mock Bedrock call to test actual H4 path |
| S4 | SUGGESTION | 3.19 | Modification to out-of-scope file not in PLAN task file list | Acknowledged -- fix is correct and documented |
| N1 | NIT | 3.18 | Two lines exceed 120 chars in integration test | Break dicts across multiple lines |

**Overall verdict:** Solid wave. All 125 tests pass and cover every SECURITY-REVIEW finding in scope. The issues found are all SUGGESTION-level: lint failures from unused imports (S1, S2) are trivially fixable, the Nova test weakness (S3) is a gap in H4 coverage for one Lambda but not a blocker, and the scope note (S4) is informational only. No BLOCKERs.

## Review Discussion

### Fix Plan (Claude Opus 4.6 (1M context) -- 2026-04-04)

Generated in the same review context (no subagent available). Run `/agentic-dev:review fix-plan-analysis wave 3` in a separate session for an independent second opinion.

**Scope: 5 issues (0 BLOCKERs, 4 SUGGESTIONs, 1 NIT)**

**[S1] (Unused imports + import ordering in backend test files)**
- Independent assessment: Read each test file and confirmed unused imports: `os`, `Any`, `patch`, `ALLOWED_MODEL_IDS` in `test_security_pipeline.py`; `json`, `dataclass`, `Decimal` in `test_security_finalize.py`; `json`, `os`, `Decimal` in `test_security_pipeline_flow.py`. All import blocks also have I001 ordering violations (third-party before stdlib grouping).
- Review comparison: Agrees fully. These are leftover imports from drafting that were never cleaned up.
- Fix: Run `cd backend && uv run ruff check --fix tests/unit/test_security_*.py tests/integration/test_security_pipeline_flow.py` to auto-fix 16 of 18 errors. Then manually wrap lines 255-256 in `test_security_pipeline_flow.py` to fix the 2 E501 violations.
- Risk: ruff `--fix` could reorder imports in a way that changes runtime behavior if there are side-effect imports. Verified: none of the removed imports have side effects. No risk.
- Files: `backend/tests/unit/test_security_pipeline.py`, `backend/tests/unit/test_security_finalize.py`, `backend/tests/unit/test_security_cursor.py`, `backend/tests/unit/test_security_prompt_injection.py`, `backend/tests/unit/test_security_upload.py`, `backend/tests/integration/test_security_pipeline_flow.py`

**[S2] (Unused `Capture` import in CDK test file)**
- Independent assessment: Confirmed `Capture` is imported but never referenced in any test class.
- Review comparison: Agrees.
- Fix: `cd infra && uv run ruff check --fix tests/test_security_hardening.py` or manually remove `Capture, ` from line 21.
- Risk: None. `Capture` is not used.
- Files: `infra/tests/test_security_hardening.py`

**[S3] (Nova error sanitization test tests wrong code path)**
- Independent assessment: Read `nova_structure.py` handler. Event validation runs first: it calls `validate_s3_key` on the `key` field. The key `receipts/01ABCDEFGHIJKLMNOPQRSTUV.jpg` has 25 chars in the ULID portion (not 26), so `validate_s3_key` returns False, and the handler returns `{"error": "invalid_event"}` before any Bedrock/S3 call. The test's `if "error" in result:` guard means it asserts on the `"invalid_event"` error, not on the actual exception-handling path. The Textract test (line 270) correctly demonstrates the pattern: mock the internal function (`_call_textract`) to raise an exception, then verify the error payload is sanitized.
- Review comparison: Agrees. The test is testing validation, not error sanitization.
- Fix: Rewrite the test to mirror the Textract pattern. Provide a valid 26-char ULID in the key, include all required event fields, and mock `nova_structure._read_image_from_s3` or `nova_structure._call_bedrock` to raise `RuntimeError("Super secret internal error details")`. Assert `result["error"] == "nova_structure_failed"` and `"Super secret" not in str(result)`.
- Risk: The mock target function name (`_read_image_from_s3` or `_call_bedrock`) could change in future refactors, breaking the test. This is inherent to any mock-based test. Acceptable trade-off.
- Files: `backend/tests/unit/test_security_pipeline.py`

**[S4] (Modification to out-of-scope file)**
- Independent assessment: The change to `test_pipeline_flow.py:826-832` replaces an assertion that checks for raw error text (`"Textract error" in failure_reason`) with one that checks for the generic CloudWatch message. This aligns with the H4 security hardening from task 3.14.
- Review comparison: Agrees this is an appropriate scope expansion. The old assertion was broken by the security hardening.
- Fix: No code change needed. Already correctly handled.
- Risk: None.
- Files: N/A

**[N1] (Line length violations)**
- Independent assessment: Lines 255-256 in `test_security_pipeline_flow.py` have inline dict literals that exceed 120 chars.
- Review comparison: Agrees.
- Fix: Break the dict across multiple lines.
- Risk: None.
- Files: `backend/tests/integration/test_security_pipeline_flow.py`

**Execution order:**
1. S1 + S2: Run `ruff check --fix` in both backend and infra directories (parallel)
2. N1: Manually wrap lines 255-256 in `test_security_pipeline_flow.py`
3. S3: Rewrite `test_nova_error_payload_no_raw_exception` to mock `_read_image_from_s3`
4. Run all tests to verify: `cd backend && uv run ruff check tests/ && uv run pytest tests/unit/test_security_*.py tests/integration/test_security_pipeline_flow.py -v && cd ../infra && uv run ruff check tests/ && uv run pytest tests/test_security_hardening.py -v`

**Verification:**
```
cd backend && uv run ruff check tests/unit/test_security_*.py tests/integration/test_security_pipeline_flow.py
cd backend && uv run pytest tests/unit/test_security_*.py tests/integration/test_security_pipeline_flow.py -v
cd infra && uv run ruff check tests/test_security_hardening.py
cd infra && uv run pytest tests/test_security_hardening.py -v
```

### Fix Results (Claude Opus 4.6 (1M context) — 2026-04-05)

Applied by orchestrator (fixes were trivial enough to apply directly).

| ID | Status | Details |
|----|--------|---------|
| S1 | Fixed | `uv run ruff check --fix` removed unused imports and fixed ordering in 5 backend test files (16 auto-fixed) |
| S2 | Fixed | `uv run ruff check --fix` removed unused `Capture` import in `test_security_hardening.py` |
| S3 | Fixed | Rewrote `test_nova_error_payload_no_raw_exception` to mock `_read_image_from_s3` with `RuntimeError`, set `RECEIPTS_BUCKET` env var, and use valid 26-char ULID key. Now tests actual H4 exception path instead of validation path. |
| S4 | No action | Already correct — `test_pipeline_flow.py` assertion updated to match H4 hardening. |
| N1 | Fixed | Broke long dict literals across multiple lines in `test_security_pipeline_flow.py` lines 251-258. |

Commit: `7e2bd29` on branch `feature/m3.1-wave3-security-tests`.

### Fix Verification (Claude Opus 4.6 (1M context) — 2026-04-05)

All fixes verified:

| ID | Status | Verification |
|----|--------|-------------|
| S1 | Fixed | `uv run ruff check tests/unit/test_security_*.py tests/integration/test_security_pipeline_flow.py` — All checks passed |
| S2 | Fixed | `uv run ruff check tests/test_security_hardening.py` — All checks passed |
| S3 | Fixed | `test_nova_error_payload_no_raw_exception` PASSED — asserts `result["error"] == "nova_structure_failed"` and `"Super secret" not in str(result)` |
| S4 | N/A | No action required |
| N1 | Fixed | No E501 violations remaining |

**Full test results:** 107 backend security tests passed, 18 CDK security tests passed. 0 regressions.

Tasks 3.18 and 3.19 marked `done`.

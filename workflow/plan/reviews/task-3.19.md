# Task 3.19 Review: Security Hardening CDK + Integration Tests [TEST]

## Summary
Created CDK security configuration tests and GSI2 integration tests. Also fixed a pre-existing test in `test_pipeline_flow.py` that was broken by H4 error sanitization from task 3.14.

## Changes
- **`infra/tests/test_security_hardening.py`** (create): 18 CDK tests verifying security configuration across all SECURITY-REVIEW findings.
- **`backend/tests/integration/test_security_pipeline_flow.py`** (create): 6 integration tests for GSI2 lookup and error sanitization in integrated pipeline context.
- **`backend/tests/integration/test_pipeline_flow.py`** (modify): Fixed `test_failure_reason_populated` assertion to match the new H4 behavior (generic failureReason referencing CloudWatch, not raw error text).

## Acceptance Criteria Checklist
- [x] CDK tests verify: GSI2 exists with KEYS_ONLY projection
- [x] No PASSWORD in AllowedFirstAuthFactors
- [x] Cognito IAM not wildcard userpool/*
- [x] CloudFront has security headers (HSTS, X-Content-Type-Options, X-Frame-Options, Referrer-Policy, CSP)
- [x] S3 PutObject IAM scoped to receipts/* prefix
- [x] API Gateway throttling configured (burst=10, rate=5)
- [x] Bedrock IAM region-scoped (references AWS::Region)
- [x] No dynamodb:Scan in dedicated LoadCustomCategories IAM policy
- [x] S3 lifecycle rules exist (IA + Glacier transitions)
- [x] Refresh token validity set to 7 days
- [x] Textract IAM uses resources=["*"] (AWS requirement)
- [x] Integration test: GSI2 query returns correct userId for a given receiptId
- [x] `cd infra && uv run pytest tests/test_security_hardening.py -v` passes
- [x] `cd backend && uv run pytest tests/integration/ -v` passes

## Test Results
```
CDK security hardening tests: 18 passed in 5.18s
Backend integration tests: 37 passed (6 new + 31 existing) in 2.61s
```

## Test Breakdown
| File | Tests | Coverage |
|------|-------|----------|
| infra/tests/test_security_hardening.py | 18 | C2, H2, H3, M1-M5, M9, M10, M13, L2, L3 |
| backend/tests/integration/test_security_pipeline_flow.py | 6 | C2 (GSI2), H4 (error sanitization), M12 |
| **Total new** | **24** | |

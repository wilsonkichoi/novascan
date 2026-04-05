# Milestone 3.1: Security Hardening

> Remediates all actionable findings from the security review (`workflow/reviews/SECURITY-REVIEW.md`).
> Insert this section into PLAN.md between Milestone 3 and Milestone 4.

---

### Wave 1: Critical Fixes + Independent Hardening

#### [ ] Task 3.8: Sanitize Custom Category Inputs in Extraction Prompt [C1]
- **Role:** security-engineer
- **Depends on:** none (M3 complete)
- **Security ref:** SECURITY-REVIEW.md >> C1 (Critical — Prompt Injection)
- **Files:**
  - `backend/src/novascan/pipeline/prompts.py` (modify — sanitize displayName/slug before embedding in prompt, lines 143-151)
- **Acceptance criteria:**
  - `build_extraction_prompt()` validates custom category names before interpolation
  - Category names restricted to: alphanumeric, spaces, `& / , . ( ) -`, max 64 chars
  - Category slugs restricted to: lowercase alphanumeric + hyphens, max 64 chars
  - Names containing newlines, markdown headers (`##`), or instruction-like patterns are rejected with `ValueError`
  - Custom categories placed in a structured JSON data block rather than free-text lines
  - Existing unit tests in `test_nova_structure.py` and `test_bedrock_extract.py` still pass
  - `cd backend && uv run ruff check src/ && uv run pytest tests/unit/ -v -k "nova or bedrock or prompt"` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run pytest tests/unit/ -v -k "nova or bedrock"`

#### [ ] Task 3.9: Replace DynamoDB Scan with GSI2 Query [C2 + M13]
- **Role:** senior-engineer
- **Depends on:** none (M3 complete)
- **Security ref:** SECURITY-REVIEW.md >> C2 (Critical — Cross-User Data Exposure), M13 (Medium — Excessive IAM)
- **Files:**
  - `infra/cdkconstructs/storage.py` (modify — add GSI2 with `GSI2PK` partition key, line ~30)
  - `backend/src/novascan/pipeline/load_custom_categories.py` (modify — replace `_lookup_user_id` scan with GSI2 query, lines 192-236)
  - `backend/src/novascan/api/upload.py` (modify — set `GSI2PK = receiptId` on receipt creation, lines 60-76)
  - `infra/cdkconstructs/pipeline.py` (modify — replace `table.grant_read_data()` with scoped `dynamodb:Query`+`dynamodb:GetItem` policy, line 199; add `RECEIPTS_BUCKET` env var to all pipeline Lambdas)
- **Acceptance criteria:**
  - DynamoDB table has GSI2: `GSI2PK` (S) partition key, projection KEYS_ONLY (only need PK to extract userId)
  - `_lookup_user_id` uses `table.query(IndexName="GSI2", ...)` instead of `table.scan()`
  - LoadCustomCategories Lambda IAM policy grants only `dynamodb:Query` and `dynamodb:GetItem` (no `Scan`)
  - Upload endpoint (`upload.py`) sets `GSI2PK = receiptId` on receipt creation (needed for the GSI2 query to work)
  - `RECEIPTS_BUCKET` environment variable set on all pipeline Lambdas (unblocks H5 S3 key validation in Task 3.13)
  - `cdk synth` succeeds, CDK snapshot regenerated
  - Existing tests updated to account for GSI2
  - `cd infra && uv run cdk synth --context stage=dev > /dev/null && echo "PASS"`
  - `cd backend && uv run pytest tests/unit/ -v -k "load_custom" && cd ../infra && uv run pytest -v`
- **Test command:** `cd infra && uv run cdk synth --context stage=dev > /dev/null && cd ../backend && uv run pytest tests/unit/ -v -k "load_custom"`

#### [ ] Task 3.10: Validate Pagination Cursor + Sanitize API Errors [H1 + M7]
- **Role:** security-engineer
- **Depends on:** none (M3 complete)
- **Security ref:** SECURITY-REVIEW.md >> H1 (High — Cursor Injection), M7 (Medium — Error Info Leak)
- **Files:**
  - `backend/src/novascan/api/receipts.py` (modify — validate decoded cursor keys + GSI1PK ownership, sanitize error message, lines 31-93)
- **Acceptance criteria:**
  - `_decode_cursor()` validates decoded JSON has exactly `{GSI1PK, GSI1SK, PK, SK}` keys
  - Decoded cursor's `GSI1PK` must equal `USER#{authenticated_userId}` — rejects cursors targeting other users
  - Error response uses generic message `"Invalid pagination cursor"` (no `str(e)`)
  - Detailed error logged server-side via `logger.warning()`
  - Existing list receipts tests updated and passing
  - `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_receipts_list.py -v` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_receipts_list.py -v`

#### [x] Task 3.11: Auth Construct Hardening [H2 + H3 + M4]
- **Role:** devops-engineer
- **Depends on:** none (M3 complete)
- **Security ref:** SECURITY-REVIEW.md >> H2 (High — PASSWORD Auth), H3 (High — Wildcard Cognito IAM), M4 (Medium — Refresh Token TTL)
- **Files:**
  - `infra/cdkconstructs/auth.py` (modify — remove PASSWORD from AllowedFirstAuthFactors line 84, scope Cognito IAM ARN lines 90-101, set refresh token validity)
- **Acceptance criteria:**
  - `AllowedFirstAuthFactors` contains only `["EMAIL_OTP"]` (PASSWORD removed)
  - Post-Confirmation Lambda IAM policy scoped to `arn:aws:cognito-idp:{region}:{account}:userpool/novascan-*` (not `userpool/*`)
  - Refresh token validity set to 7 days (via App Client token validity config)
  - `cdk synth` succeeds, CDK snapshot regenerated
  - Auth construct CDK tests updated and passing
  - `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest tests/test_auth_construct.py -v`
- **Test command:** `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest tests/test_auth_construct.py -v`

#### [ ] Task 3.12: CloudFront Security Response Headers [M2]
- **Role:** devops-engineer
- **Depends on:** none (M3 complete)
- **Security ref:** SECURITY-REVIEW.md >> M2 (Medium — Missing Security Headers)
- **Files:**
  - `infra/cdkconstructs/frontend.py` (modify — add `ResponseHeadersPolicy` with HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy)
- **Acceptance criteria:**
  - CloudFront distribution uses a `ResponseHeadersPolicy` with:
    - `Strict-Transport-Security: max-age=63072000; includeSubdomains`
    - `X-Content-Type-Options: nosniff`
    - `X-Frame-Options: DENY`
    - `Referrer-Policy: strict-origin-when-cross-origin`
    - `Content-Security-Policy: default-src 'self'; connect-src 'self' https://*.amazonaws.com https://*.execute-api.*.amazonaws.com; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'`
  - `cdk synth` succeeds, CDK snapshot regenerated
  - Frontend CDK tests updated and passing
  - `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest tests/test_frontend_construct.py -v`
- **Test command:** `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest tests/test_frontend_construct.py -v`

---

### Wave 2: Pipeline + API + IAM Hardening

#### [ ] Task 3.13: Pipeline Lambda Input Validation + Error Sanitization [H4 + H5 + H6 + L5 + M8 + L6 + L7]
- **Role:** security-engineer
- **Depends on:** 3.8 (file overlap: `prompts.py` imported by `nova_structure.py`, `bedrock_extract.py`), 3.9 (file overlap: `load_custom_categories.py`)
- **Security ref:** SECURITY-REVIEW.md >> H4, H5, H6 (High), L5, L6, L7 (Low), M8 (Medium)
- **Files:**
  - `backend/src/novascan/pipeline/textract_extract.py` (modify — add event validation, sanitize error return, validate S3 key)
  - `backend/src/novascan/pipeline/nova_structure.py` (modify — add event validation, sanitize error return, validate S3 key, add image size guard, validate model ID)
  - `backend/src/novascan/pipeline/bedrock_extract.py` (modify — add event validation, sanitize error return, validate S3 key, add image size guard, validate model ID)
  - `backend/src/novascan/pipeline/load_custom_categories.py` (modify — sanitize error return, validate S3 key format in `_extract_receipt_id`, sanitize log payloads)
- **Acceptance criteria:**
  - **H6 — Event validation**: Each Lambda validates its event payload at entry. Required fields fail fast with `"error": "invalid_event"`. Use Pydantic models or manual validation (consistent with project style).
  - **H5 — S3 key validation**: Shared validation function checks `key` matches `^receipts/[A-Za-z0-9]{26}\.(jpg|jpeg|png)$` and `bucket` matches `RECEIPTS_BUCKET` env var. Pass expected bucket name via CDK environment variable.
  - **H4 — Error sanitization**: All `except Exception` blocks return `{"error": "<lambda_name>_failed", "errorType": type(e).__name__}` (no `str(e)`). Detailed error logged to CloudWatch only.
  - **L5 — Image size guard**: `_read_image_from_s3` checks `ContentLength` before `.read()`. Max 10MB. Raises `ValueError` if exceeded.
  - **M8 — Model ID validation**: Nova/Bedrock Lambdas validate `MODEL_ID` against allowlist `{"amazon.nova-lite-v1:0", "amazon.nova-pro-v1:0"}` at module load.
  - **L6 + L7 — Log hygiene**: `logger.exception` calls reviewed; S3 event payloads logged as structure presence only (not full body). Stack traces acceptable but bucket/key stripped from error `extra` dicts.
  - Existing pipeline unit tests updated to match new error format
  - `cd backend && uv run ruff check src/ && uv run pytest tests/unit/ -v -k "textract or nova or bedrock or load_custom"` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run pytest tests/unit/ -v -k "textract or nova or bedrock or load_custom"`

#### [ ] Task 3.14: Finalize Lambda Hardening [H4-finalize + M11 + M12 + L8]
- **Role:** backend-engineer
- **Depends on:** 3.9 (file overlap: `finalize.py` reads from same DynamoDB table modified by GSI2 changes; no direct file overlap but wave ordering ensures consistent schema)
- **Security ref:** SECURITY-REVIEW.md >> H4 (High — Error Payloads), M11 (Medium — Idempotency), M12 (Medium — S3 Encryption), L8 (Low — Internal Fields)
- **Files:**
  - `backend/src/novascan/pipeline/finalize.py` (modify — sanitize error payloads, add idempotency guards, add S3 encryption, review return fields)
- **Acceptance criteria:**
  - **H4 — Error sanitization**: `failure_reason` written to DynamoDB is generic: `"Pipeline processing failed. Check CloudWatch logs for details."` Raw error details logged to CloudWatch only. Pipeline record `error` field stores error classification, not raw exception message.
  - **M11 — Idempotency**:
    - `_update_receipt` uses `ConditionExpression="attribute_not_exists(updatedAt) OR updatedAt < :now"` to prevent stale overwrites
    - `_create_line_items` deletes existing items for the receipt before writing new ones (delete-then-write pattern)
    - Pipeline record writes documented as last-write-wins (acceptable for telemetry)
  - **M12 — S3 encryption**: `copy_object` call includes `ServerSideEncryption="AES256"` explicitly
  - **L8 — Return fields**: `selectedPipeline`, `rankingWinner`, `usedFallback` retained for observability but documented as internal-only (comment in code)
  - Existing finalize unit tests updated and passing
  - `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_finalize.py -v` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_finalize.py -v`

#### [ ] Task 3.15: Upload Endpoint Hardening [M6 + L4]
- **Role:** backend-engineer
- **Depends on:** 3.10
- **Security ref:** SECURITY-REVIEW.md >> M6 (Medium — No Content-Length), L4 (Low — ValidationError Leak)
- **Files:**
  - `backend/src/novascan/api/upload.py` (modify — add ContentLength to presigned URL params, sanitize Pydantic ValidationError response)
- **Acceptance criteria:**
  - **M6**: `generate_presigned_url` includes `ContentLength: file_req.fileSize` in `Params` — S3 rejects uploads that don't match declared size
  - **L4**: Pydantic `ValidationError` handler returns sanitized field-level errors: `[{"field": name, "message": msg}]` — no raw Pydantic `str(e)` to client. Full error logged server-side.
  - Existing upload unit tests updated and passing
  - `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_upload.py -v` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run pytest tests/unit/test_upload.py -v`

#### [ ] Task 3.16: CDK IAM + API Gateway Hardening [M1 + M5 + M9 + M10]
- **Role:** devops-engineer
- **Depends on:** 3.11, 3.12
- **Security ref:** SECURITY-REVIEW.md >> M1 (Medium — Broad S3 IAM), M5 (Medium — No Rate Limiting), M9 (Medium — Textract Wildcard), M10 (Medium — Bedrock Wildcard Region)
- **Files:**
  - `infra/cdkconstructs/api.py` (modify — scope S3 grants to `receipts/*` prefix, add API Gateway route-level throttling + access logging)
  - `infra/cdkconstructs/pipeline.py` (modify — add comment documenting Textract `resources=["*"]` is required, scope Bedrock ARN to deployment region)
- **Acceptance criteria:**
  - **M1**: API Lambda S3 permissions scoped: `grant_put(fn, "receipts/*")` + `grant_read(fn, "receipts/*")` instead of `grant_read_write(fn)`
  - **M5**: API Gateway stage configured with route-level throttling on `POST /api/receipts/upload-urls` (burst=10, rate=5). Access logging enabled to CloudWatch log group.
  - **M9**: Comment added to Textract IAM statement: `# Textract does not support resource-level permissions — * is required`
  - **M10**: Bedrock IAM ARN scoped to deployment region: `arn:aws:bedrock:{cdk.Aws.REGION}::foundation-model/amazon.nova-lite-v1:0`
  - `cdk synth` succeeds, CDK snapshot regenerated
  - `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest -v`
- **Test command:** `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest -v`

#### [ ] Task 3.17: Storage Lifecycle + Encryption + Dependency Cleanup [M3 + L2 + L3]
- **Role:** devops-engineer
- **Depends on:** 3.9
- **Security ref:** SECURITY-REVIEW.md >> M3 (Medium — No Lifecycle), L2 (Low — Default Encryption), L3 (Low — Unused pandas)
- **Files:**
  - `infra/cdkconstructs/storage.py` (modify — add S3 lifecycle rules, optionally upgrade DynamoDB encryption)
  - `backend/pyproject.toml` (modify — remove `pandas` from dependencies)
- **Acceptance criteria:**
  - **M3**: Receipts S3 bucket has lifecycle rules: IA transition at 90 days, Glacier at 365 days, expiration at 2555 days (~7 years)
  - **L2**: Deferred — add TODO comment in `storage.py` documenting upgrade path to `CUSTOMER_MANAGED` with KMS key + rotation (not implementing for personal MVP; ~$1/month + complexity).
  - **L3**: `pandas` removed from `backend/pyproject.toml` `[project.dependencies]`. Verify no import exists.
  - `cdk synth` succeeds, CDK snapshot regenerated
  - `cd backend && uv sync && uv run ruff check src/`
  - `cd infra && uv run cdk synth --context stage=dev > /dev/null && uv run pytest tests/test_storage_construct.py -v`
- **Test command:** `cd infra && uv run cdk synth --context stage=dev > /dev/null && cd ../backend && uv sync`

---

### Wave 3: Security Tests

#### [ ] Task 3.18: Security Hardening Backend Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 3.8, 3.10, 3.13, 3.14, 3.15
- **Security ref:** SECURITY-REVIEW.md >> C1, H1, H4, H5, H6, M6, M7, M11, L4, L5
- **Files:**
  - `backend/tests/unit/test_security_prompt_injection.py` (create)
  - `backend/tests/unit/test_security_cursor.py` (create)
  - `backend/tests/unit/test_security_pipeline.py` (create)
  - `backend/tests/unit/test_security_finalize.py` (create)
  - `backend/tests/unit/test_security_upload.py` (create)
- **Test scope:** Tests security contract — cursor tampering rejected, prompt injection sanitized, error messages generic, idempotency enforced. Do NOT read implementation.
- **Acceptance criteria:**
  - Prompt injection tests: category names with newlines/markdown/instruction-like text rejected; safe names accepted; invalid slugs rejected
  - Cursor tests: tampered cursor (wrong GSI1PK, extra keys, missing keys) returns 400; valid cursor accepted
  - Pipeline tests: missing required event fields return `"error": "invalid_event"`; oversized image returns error; error payloads never contain raw exception messages
  - Finalize tests: duplicate pipeline execution doesn't create duplicate line items; idempotent receipt updates
  - Upload tests: presigned URL includes ContentLength; ValidationError response sanitized
  - `cd backend && uv run pytest tests/unit/test_security_*.py -v` passes
- **Test command:** `cd backend && uv run pytest tests/unit/test_security_*.py -v`

#### [ ] Task 3.19: Security Hardening CDK + Integration Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 3.9, 3.11, 3.12, 3.16, 3.17
- **Security ref:** SECURITY-REVIEW.md >> C2, H2, H3, M1, M2, M3, M4, M5, M9, M10, M13, L2, L3
- **Files:**
  - `infra/tests/test_security_hardening.py` (create)
  - `backend/tests/integration/test_security_pipeline_flow.py` (create)
- **Test scope:** Tests CDK security configuration and GSI2 lookup. Do NOT read implementation.
- **Acceptance criteria:**
  - CDK tests verify: GSI2 exists; no PASSWORD in auth factors; Cognito IAM not wildcard; CloudFront has security headers; S3 IAM scoped; throttling configured; Bedrock IAM region-scoped; no Scan in LoadCustomCategories IAM; lifecycle rules exist
  - Integration test: GSI2 query returns correct userId for a given receiptId (moto)
  - `cd infra && uv run pytest tests/test_security_hardening.py -v`
  - `cd backend && uv run pytest tests/integration/test_security_pipeline_flow.py -v`
- **Test command:** `cd infra && uv run pytest tests/test_security_hardening.py -v && cd ../backend && uv run pytest tests/integration/ -v`

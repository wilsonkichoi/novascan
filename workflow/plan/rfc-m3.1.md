# RFC: Milestone 3.1 — Security Hardening Task Decomposition

**Date:** 2026-04-04
**Status:** Draft — awaiting human review

---

## Task Decomposition Rationale

The security review identified 29 actionable findings (2C + 6H + 13M + 8L). These were grouped into 12 tasks across 3 waves by:

1. **File ownership** — no two tasks in the same wave modify the same file
2. **Causal dependency** — M13 (scope IAM) depends on C2 (remove scan), so they're in one task
3. **Severity front-loading** — all Critical and High findings land in Wave 1-2
4. **Logical grouping** — related findings in the same file (e.g., H2+H3+M4 all in `auth.py`) become one task

## Wave Grouping Decisions

**Wave 1 (5 tasks):** All Critical + independent High/Medium fixes. Each task touches a distinct file set — full parallelism.

**Wave 2 (5 tasks):** Pipeline hardening + CDK IAM. Depends on Wave 1 due to **file overlap** (not functional coupling):
- Task 3.13 depends on 3.8 (file overlap: `prompts.py` is imported by `nova_structure.py` and `bedrock_extract.py`; `textract_extract.py` and `finalize.py` do NOT import `prompts.py`)
- Task 3.13 depends on 3.9 (file overlap: both modify `load_custom_categories.py`)
- Task 3.14 depends on 3.9 (wave ordering ensures consistent DynamoDB schema; no direct file overlap)
- Task 3.16 depends on 3.11/3.12 (CDK snapshot needs auth + frontend changes committed)
- Task 3.17 depends on 3.9 (file overlap: both modify `storage.py`)

**Wave 3 (2 tasks):** Test-only wave. Separate test authoring from implementation per project convention.

## Key Design Decisions

### C2: GSI2 over S3 key restructure
Chose GSI2 (Option B) over encoding userId in S3 key (Option A) because:
- Option A requires coordinated changes to `upload.py`, all 5 pipeline Lambdas, and existing S3 data migration
- Option B touches only `storage.py` (CDK), `load_custom_categories.py`, `pipeline.py` (IAM), and `upload.py` (add GSI2PK to receipt record)
- Aligns with the existing Spec Gap #6 resolution direction

### M6: ContentLength param over presigned POST
Chose `ContentLength` in `generate_presigned_url` params over `generate_presigned_post` because:
- No frontend upload rewrite needed
- Upload API already validates `fileSize` in the request body — this enforces it at S3 level
- Simpler diff, lower risk

### M5: Throttling only, no WAF
WAF adds cost and complexity inappropriate for a ~100-user personal MVP. Route-level throttling via API Gateway is zero-cost and effective.

### Task 3.13 scope
This is the largest task (7 findings, 4 files), but it applies the same 4 patterns (event validation, S3 key check, error sanitization, image size guard) across the same file set. Splitting into per-file tasks would create artificial boundaries between related changes. Estimated at ~200-300 lines of changes.

## Low Confidence Areas

1. ~~**H5 — `RECEIPTS_BUCKET` env var**~~: **Resolved (F2).** Confirmed `RECEIPTS_BUCKET` is not set on any pipeline Lambda. Added to Task 3.9 scope (already modifies `pipeline.py`). Task 3.9 now sets `RECEIPTS_BUCKET` on all pipeline Lambdas, unblocking H5 validation in Task 3.13.

2. **M11 — `ConditionExpression` on `updatedAt`**: The idempotency guard assumes `updatedAt` is consistently set. Need to verify the existing `_update_receipt` always writes `updatedAt` and that the condition doesn't block legitimate first writes (where `updatedAt` doesn't exist yet — the `attribute_not_exists` clause handles this).

3. **M6 — `ContentLength` enforcement**: `generate_presigned_url` with `ContentLength` in Params generates a URL that requires the `Content-Length` header to match exactly. The frontend must send `Content-Length` in the PUT request, which browsers typically do automatically for `fetch()` with a `Blob` body. Need to verify this doesn't break existing upload flow.

4. **Task 3.9 — GSI2 projection**: Using KEYS_ONLY projection to minimize GSI storage. The query only needs PK (to extract userId). If any pipeline Lambda needs additional attributes from the receipt during lookup, KEYS_ONLY would be insufficient.

---

## Finding → Task Cross-Reference

| Finding | Severity | Task | Description |
|---------|----------|------|-------------|
| C1 | Critical | 3.8 | Prompt injection via custom categories |
| C2 | Critical | 3.9 | DynamoDB full-table scan |
| H1 | High | 3.10 | Pagination cursor injection |
| H2 | High | 3.11 | PASSWORD auth factor enabled |
| H3 | High | 3.11 | Wildcard Cognito IAM |
| H4 | High | 3.13 + 3.14 | Error payloads leak internal state |
| H5 | High | 3.13 | No S3 key validation |
| H6 | High | 3.13 | No event payload validation |
| M1 | Medium | 3.16 | Overly broad S3 IAM |
| M2 | Medium | 3.12 | Missing CloudFront security headers |
| M3 | Medium | 3.17 | No S3 lifecycle policy |
| M4 | Medium | 3.11 | Refresh token TTL |
| M5 | Medium | 3.16 | No API rate limiting |
| M6 | Medium | 3.15 | No content-length on presigned URLs |
| M7 | Medium | 3.10 | Error messages leak details |
| M8 | Medium | 3.13 | Bedrock model ID not validated |
| M9 | Medium | 3.16 | Textract IAM wildcard (document only) |
| M10 | Medium | 3.16 | Bedrock IAM wildcard region |
| M11 | Medium | 3.14 | Finalize idempotency |
| M12 | Medium | 3.14 | S3 copy_object encryption |
| M13 | Medium | 3.9 | Excessive LoadCustomCategories IAM |
| L2 | Low | 3.17 | DynamoDB default encryption (optional) |
| L3 | Low | 3.17 | Unused pandas dependency |
| L4 | Low | 3.15 | Pydantic ValidationError leak |
| L5 | Low | 3.13 | No image size guard |
| L6 | Low | 3.13 | Stack traces in logs |
| L7 | Low | 3.13 | Full S3 event logged on error |
| L8 | Low | 3.14 | Internal fields in SFN output |

---

*FEEDBACK:* (Codebase-verified review — 2026-04-04)

**Overall:** Plan is solid. All 29 findings correctly mapped, line references verified against codebase, severity front-loading and wave isolation are sound. Five issues found and resolved below.

**F1 — Dependency rationale is misleading (Wave 2 → 3.9):**
The RFC states Tasks 3.13/3.14 depend on 3.9 because "C2 changes `load_custom_categories.py`." The actual reason is **file overlap** — both 3.9 and 3.13 modify `load_custom_categories.py`. It is a standalone Lambda with zero cross-imports from other pipeline Lambdas. Similarly, the 3.8 dependency only applies to `nova_structure.py` and `bedrock_extract.py` (which import `build_extraction_prompt` from `prompts.py`); `textract_extract.py` and `finalize.py` do not import `prompts.py`.

**F2 — RECEIPTS_BUCKET env var missing → add to Task 3.9:**
Low Confidence Area #1 confirmed: `RECEIPTS_BUCKET` is not passed to any pipeline Lambda. Resolved by adding it to Task 3.9 scope (already modifies `pipeline.py`). Task 3.9 acceptance criteria should include: "`RECEIPTS_BUCKET` environment variable set on all pipeline Lambdas." This unblocks Task 3.13's S3 key validation (H5).

**F3 — upload.py overlap between Task 3.9 (Wave 1) and Task 3.15 (Wave 2):**
Both tasks modify `backend/src/novascan/api/upload.py`. No line-level conflict: 3.9 adds `GSI2PK` to receipt creation (lines 60-76), 3.15 adds `ContentLength` to presigned URL generation (lines 80-89). Wave ordering prevents concurrent edits. Noted for awareness.

**F4 — L2 (DynamoDB KMS) deferred:**
Task 3.17 L2 acceptance criteria changed to: add TODO comment documenting upgrade path to `CUSTOMER_MANAGED` with KMS key + rotation. Not implementing for personal MVP (~$1/month + complexity).

**F5 — All line references verified:**
Every line number and code pattern cited in the security review and plan matches the current codebase. No stale references found.

---

*AI:* All 5 feedback items addressed:

- **F1:** Fixed dependency rationale in both RFC (Wave Grouping Decisions) and PLAN-M3.1.md (Tasks 3.13, 3.14). Dependencies now correctly describe file overlap, not functional coupling. Clarified that `textract_extract.py` and `finalize.py` do NOT import `prompts.py`.
- **F2:** Added `RECEIPTS_BUCKET` env var to Task 3.9 scope and acceptance criteria. Added `pipeline.py` note about setting it on all pipeline Lambdas. Marked Low Confidence Area #1 as resolved.
- **F3:** Acknowledged. Wave ordering prevents conflict. Added `upload.py` explicitly to Task 3.9 Files list for visibility.
- **F4:** Changed Task 3.17 L2 acceptance criteria from "Optional — user decision" to "Deferred — add TODO comment" with rationale.
- **F5:** No changes needed.

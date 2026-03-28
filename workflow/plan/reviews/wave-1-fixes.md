# Wave 1 Review Fixes

## Work Summary
- **What was implemented:** Fixed all 6 issues from the Wave 1 scaffolding review (1 high, 1 medium, 4 low/trivial)
- **Key decisions:**
  - Used `TYPE_CHECKING` guard for `mypy_boto3_dynamodb` import to avoid runtime dependency on stubs
  - Removed font names ("Inter", "Manrope") rather than adding Google Fonts loader — re-add when font loading is implemented
  - Extracted all 7 page stubs to `src/pages/` with default exports for clean imports
  - Used `CDK_DEFAULT_ACCOUNT`/`CDK_DEFAULT_REGION` (populated by CDK CLI from user's AWS profile/SSO) instead of hardcoded values
- **Files created/modified:**
  - `frontend/src/types/index.ts` (modified — "completed" → "confirmed")
  - `backend/src/novascan/shared/dynamo.py` (modified — added return type annotation)
  - `backend/tests/conftest.py` (modified — removed unused `import os`)
  - `infra/app.py` (modified — replaced hardcoded account/region)
  - `frontend/src/index.css` (modified — removed unloaded font references)
  - `frontend/src/App.tsx` (modified — imports from pages/)
  - `frontend/src/pages/LoginPage.tsx` (created)
  - `frontend/src/pages/DashboardPage.tsx` (created)
  - `frontend/src/pages/UploadPage.tsx` (created)
  - `frontend/src/pages/ReceiptsPage.tsx` (created)
  - `frontend/src/pages/ReceiptDetailPage.tsx` (created)
  - `frontend/src/pages/TransactionsPage.tsx` (created)
  - `frontend/src/pages/NotFoundPage.tsx` (created)
- **Test results:**
  - `mypy --strict src/` — pass (7 source files, no issues)
  - `ruff check .` (full backend) — pass
  - `npm run build` — pass (built in 394ms)
  - `cdk synth --context stage=dev` — pass
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Issues Fixed

| # | Severity | File | Fix |
|---|----------|------|-----|
| 1 | High | `frontend/src/types/index.ts` | `"completed"` → `"confirmed"` per SPEC Section 5 |
| 2 | Medium | `backend/src/novascan/shared/dynamo.py` | Added `-> Table` return type with `TYPE_CHECKING` guard |
| 3 | Trivial | `backend/tests/conftest.py` | Removed unused `import os` |
| 4 | Low | `infra/app.py` | Replaced hardcoded account/region with `CDK_DEFAULT_*` env vars |
| 5 | Low | `frontend/src/index.css` | Removed unloaded "Inter" and "Manrope" font references |
| 6 | Low | `frontend/src/App.tsx` | Extracted 7 page stubs to `src/pages/` per SPEC Section 9 |

## Cross-Reference Verification

All fixes verified against:
- SPEC.md Section 5 (status field: `processing / confirmed / failed`)
- SPEC.md Section 9 (project structure: `src/pages/`)
- HANDOFF.md (acceptance criteria: "Processing" → "Confirmed")
- PLAN.md Task 1.2/1.3 acceptance criteria
- pyproject.toml mypy strict config

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.}

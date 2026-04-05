# Task 3.17 Review: Storage Lifecycle + Encryption + Dependency Cleanup [M3 + L2 + L3]

## Summary
Added S3 lifecycle rules for cost optimization, documented KMS encryption upgrade path, and removed unused pandas dependency.

## Changes
- **`infra/cdkconstructs/storage.py`**:
  - M3: Added lifecycle rules to receipts S3 bucket — Infrequent Access at 90 days, Glacier at 365 days, expiration at 2555 days (~7 years).
  - L2: Added TODO comment documenting upgrade path to CUSTOMER_MANAGED encryption with KMS key + rotation. Deferred for personal MVP (~$1/month + complexity).
- **`backend/pyproject.toml`**:
  - L3: Removed `pandas` from `[project.dependencies]`. Verified no import exists in backend source.
- **`backend/uv.lock`**: Updated to reflect removed pandas dependency (pandas + numpy uninstalled).
- CDK snapshot regenerated.

## Acceptance Criteria Checklist
- [x] M3 — S3 lifecycle rules: IA at 90 days, Glacier at 365 days, expire at 2555 days
- [x] L2 — TODO comment documenting KMS upgrade path
- [x] L3 — pandas removed from dependencies, no imports found
- [x] `cdk synth` succeeds
- [x] `uv sync` succeeds
- [x] `ruff check src/` passes

## Test Results
```
CDK synth: PASS
Storage construct tests: 9 passed
ruff: All checks passed!
uv sync: Uninstalled pandas==3.0.1, numpy==2.4.3
```

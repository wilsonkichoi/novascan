# Retrospective Review: Milestone 3.1

**Retrospective file:** `workflow/retro/RETRO-M3.1.md`
**Reviewer:** Claude Opus 4.6 (1M context) — QA Engineer role
**Date:** 2026-04-05

## Verification Results

| Suite | Result | Notes |
|-------|--------|-------|
| Backend (`cd backend && uv run pytest`) | 386/386 passed | 75 warnings (metrics flush — harmless) |
| Infra (`cd infra && uv run pytest`) | 100/100 passed | Snapshot was stale — regenerated during verification |
| Backend lint (`cd backend && uv run ruff check src/`) | Clean | Source files pass |
| Backend lint (`cd backend && uv run ruff check tests/`) | 18 errors | Pre-existing from M3, not M3.1. All in M3 test files. |
| README.md | Adequate | No stale placeholders found |

## Issues Found During Verification

1. **CDK snapshot stale on `main`.** `infra/tests/snapshots/novascan-dev.template.json` did not reflect M3.1 CDK changes (GSI2, scoped IAM, lifecycle rules, security headers, throttling). Regenerated during this verification. This needs to be committed.

2. **Pre-existing lint errors in M3 test files.** 18 ruff errors (unused imports, import ordering) in `test_pipeline_flow.py`, `test_finalize.py`, `test_textract_extract.py`, `test_nova_structure.py`, `test_bedrock_extract.py`, `test_ranking.py`. These are not M3.1 regressions — they existed before the security hardening. Should be fixed as a chore.

## Areas of Low Confidence

- **Section 5 (Test Separation Effectiveness):** The assessment that S3 (Nova error sanitization test) "would have been missed if the implementation and test authors were the same session" is plausible but not provable. The test was written by the same model in a different context window. Whether a separate human or a different model would have caught it is speculative.

- **Section 6 (Subagent type impact):** Stated the impact of wrong subagent types as "unclear." This is honest but unsatisfying. Without a controlled comparison (same tasks, correct roles), we cannot quantify the effect. The zero-defect Wave 2 result suggests role-specific prompting may not be critical for well-specified security tasks.

- **Process failure completeness:** The 9 process failures were provided by the orchestrator. There may be additional process issues not surfaced (e.g., context window utilization, token costs, time-to-completion per agent). The retrospective can only cover what was reported.

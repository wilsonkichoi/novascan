# Retrospective: Milestone 3.1 — Security Hardening

## 1. Summary

Remediated all 25 findings from `SECURITY-REVIEW.md` (2 Critical, 3 High, 8 Medium, 5 Low, plus bundled sub-items) across backend pipeline Lambdas, API endpoints, CDK constructs, and auth configuration. Added 125 new security tests (101 backend unit, 18 CDK, 6 integration).

- **Milestone:** 3.1 — Security Hardening
- **Tasks completed:** 12/12 (3.8--3.19)
- **Waves completed:** 3

## 2. What Went Well

- **Wave 2 was zero-defect.** Tasks 3.13--3.17 passed review with no issues found -- the shared `validation.py` pattern from Task 3.13 set a consistent contract that all subsequent tasks followed.
- **Defense-in-depth on prompt injection (Task 3.8):** Three-layer defense (character allowlist + injection pattern detection + structured JSON output) exceeded the SECURITY-REVIEW C1 recommendation.
- **GSI2 design (Task 3.9):** KEYS_ONLY projection was the right call -- minimal cost, minimal data exposure, solves cross-user data lookup (C2) cleanly.
- **Black-box test approach (Tasks 3.18--3.19):** Security tests verified the contract (tampered cursor returns 400, error payload is generic) without coupling to implementation internals, making them resilient to refactoring.
- **Proactive unblocking:** Task 3.9 added `RECEIPTS_BUCKET` env var to all pipeline Lambdas, unblocking Task 3.13's S3 key validation without cross-wave rework.

## 3. What Needed Human Intervention

- **All 13 agents used `general-purpose` type** instead of role-matched `subagent_type` (security-engineer, devops-engineer, etc.). Role-specific prompting was not applied, meaning agents lacked domain-specific heuristics.
- **PLAN-M3.1.md checkboxes never marked `[x]` by agents** -- the orchestrator backfilled them retroactively. Agents should update their task status on completion.
- **Wave 3 fixes applied by orchestrator directly** instead of spawning an agent via `/agentic-dev:execute fix`. Violated the process contract (fix author should not be the fix verifier).
- **Wave 3 verify-fixes (Step 5) skipped entirely** -- the fix author verified their own work. No independent verification occurred for S1-S3 fixes in `wave-m3.1-3.md`.
- **Wave 3 Fix Results and Verification sections backfilled by orchestrator** instead of being written by independent agents, undermining the separation of concerns.
- **`/agentic-dev:verify` never invoked after milestone completed** -- running it now retroactively. Should be triggered automatically when all tasks reach `done`.
- **PROGRESS.md and PROGRESS-M3.1.md went out of sync** -- two sources of truth for the same milestone. The orchestrator had to reconcile them manually.
- **Task review files lost during branch switching in Wave 1** -- the sequential agent did not commit before switching branches, losing uncommitted review files.
- **`wave-m3.1-2.md` Review Discussion left empty** -- no placeholder text was inserted, leaving the section ambiguous (was it intentionally empty or forgotten?).

## 4. Spec Gaps Discovered

- **No security section in SPEC.md for error sanitization.** The spec says "Let Lambda Powertools handle unexpected errors" (Section 10) but does not specify what error information is safe to return to clients vs. log internally. SECURITY-REVIEW had to define this contract.
- **`userId` not in S3 event payload** (PROGRESS.md gap #6): This was the root cause of C2 (cross-user data exposure via DynamoDB Scan). The SPEC assumed userId would be available in pipeline input but never specified how it gets from S3 event to Step Functions. GSI2 was the fix, but the gap should have been caught in spec review.
- **No spec for pipeline Lambda input validation.** SPEC Section 3 describes the happy-path processing flow but does not specify what happens when a Lambda receives a malformed event. H6 findings were entirely unspecified.

## 5. Test Separation Effectiveness

- **Yes, separately-authored tests caught a real issue.** The Wave 3 review identified that `test_nova_error_payload_no_raw_exception` (Task 3.18, S3) was testing the validation path instead of the actual H4 exception-handling path. An invalid 25-char ULID triggered `invalid_event` rather than the `except Exception` block. This would have been missed if the implementation and test authors were the same session.
- **CDK security tests (Task 3.19) provided independent verification** of IAM scoping, lifecycle rules, and auth configuration that the CDK construct tests from earlier milestones did not cover.
- **Wave 3 test tasks were appropriately scoped.** 101 + 24 tests across two tasks was dense but manageable. Splitting backend and CDK/integration into separate tasks was the right call.

## 6. Cost & Efficiency

- **13 agents total across 3 waves**, all using Claude Opus 4.6 (1M context).
- **Subagent type mismatch:** All 13 agents ran as `general-purpose` instead of `security-engineer`, `devops-engineer`, `backend-engineer`, or `qa-engineer`. This negated role-specific prompt tuning. Impact: unclear, since Wave 2 was zero-defect despite the wrong role type. May matter more for specialized domains.
- **Orchestrator overhead was high.** 5 of the 9 process failures (checkbox backfill, fix application, fix verification, section backfill, verify invocation) were orchestrator tasks that should have been automated or delegated.
- **Wave 3 self-review violated separation of concerns.** The fix author verified their own fixes. For lint fixes (S1, S2, N1) this is low-risk. For S3 (rewritten test logic) it reduces confidence. Future: always spawn a separate verify agent.
- **CDK snapshot was stale at verification time.** The snapshot was regenerated during M3.1 but the final commit on `main` did not include the updated snapshot. Found and fixed during this verification run. This is a process gap: snapshot regeneration should be part of the merge checklist.
- **18 ruff lint errors in pre-existing M3 test files** (`test_pipeline_flow.py`, `test_finalize.py`, `test_textract_extract.py`, `test_nova_structure.py`, `test_bedrock_extract.py`, `test_ranking.py`) were not caught because M3 did not enforce `ruff check tests/`. M3.1 security test files are clean.

## 7. Recommendations for Next Milestone

1. **Enforce `subagent_type` matching.** Map task roles (security-engineer, devops-engineer, etc.) to the correct subagent type. Validate at spawn time.
2. **Automate checkbox updates.** Agents must mark their task `[x]` in PLAN.md upon completion. Add this to the execute skill's post-step.
3. **Single source of truth for progress.** Eliminate `PROGRESS-M3.1.md` -- use only `PROGRESS.md`. The milestone-specific file created unnecessary sync overhead.
4. **Always use independent verify agents for fixes.** Never let the fix author verify their own work, even for "trivial" fixes.
5. **Add `ruff check tests/` to the test task acceptance criteria.** M3 pre-existing lint errors were not caught because the test command only ran `ruff check src/`.
6. **CDK snapshot regeneration in merge checklist.** Any PR that modifies CDK constructs must include an updated snapshot. Fail CI if snapshot is stale.
7. **Add error contract to SPEC.md.** Define what error information is safe to return to API clients vs. log internally. This prevents future security review findings on the same topic.
8. **Insert placeholder text in empty review sections** (e.g., "No issues found -- no fix cycle required") so empty sections are explicitly intentional.
9. **Commit before branch switching.** Add a pre-switch check to the execute skill that warns if there are uncommitted changes.

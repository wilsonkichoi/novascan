# Retrospective: Milestone 4 -- Receipt Management

## 1. Summary

Built the full receipt management layer: receipt CRUD (GET/PUT/DELETE detail, bulk line item replacement), category management (predefined taxonomy + custom categories), receipt detail page with inline line item editing, category picker with create/delete custom, and staff-only pipeline comparison toggle. Added 174 new tests (96 backend API + 78 frontend UI).

- **Milestone:** 4 -- Receipt Management
- **Tasks completed:** 7/7 (4.1--4.7)
- **Waves completed:** 4

## 2. What Went Well

- **Task 4.1 was the heaviest and landed cleanly.** 13 categories with 67 subcategories matched category-taxonomy.md exactly on first attempt. All four CRUD endpoints passed acceptance criteria. The 10-issue review (6 code + 4 security) was thorough but all were SUGGESTIONs -- zero BLOCKERs.
- **Wave 4 tests (Tasks 4.6, 4.7) found no implementation bugs.** 174 tests written spec-first, all passed against the implementation on first run. The only issue was a cosmetic `cognito:groups` format inconsistency in one test file (S1 in wave-m4-4.md).
- **Fix plan analysis pattern worked well.** Every wave review included a fix plan, an independent fix plan analysis, fix results, and independent fix verification. This four-step process caught the missing security review coverage in wave-m4-1.md (S5-S8 omitted from the initial fix plan) and the subcategory-clearing behavior correction in wave-m4-3.md (S4).
- **DR-004 (Cognito Groups RBAC) proven correct.** Pipeline results endpoint's staff-only check works cleanly with `cognito:groups` claim. Both backend 403 enforcement and frontend visibility gating are consistent.
- **Security hardening from M3.1 carried forward.** Error sanitization, ULID validation, Pydantic `extra="forbid"`, and Decimal conversion patterns were applied to M4 endpoints consistently.

## 3. What Needed Human Intervention

- **CDK snapshot stale at verification time** (again -- same issue as M3.1). The snapshot was not regenerated after M4 code merged to main. Required manual regeneration during verification. This is a recurring process gap.
- **PROGRESS.md had Tasks 4.2 and 4.3 stuck in `review` status** despite fixes being verified. Updated to `done` during verification.
- **All agents used `general-purpose` subagent type** (same issue flagged in RETRO-M3.1). Role-matched `subagent_type` (backend-engineer, frontend-developer, qa-engineer) was not enforced.

## 4. Spec Gaps Discovered

- **api-contracts.md says PUT /api/receipts/{id} returns 400 for "invalid category slug"**, but the implementation intentionally allows unknown category slugs (they could be custom categories). Only subcategory validation is enforced against the parent category's known list. Minor spec imprecision (task-4.6.md).
- **No spec for subcategory selection UX.** SPEC Section 8 says "category picker" but does not detail how subcategory selection should work. The acceptance criteria said "selecting a category/subcategory" but the original implementation only supported top-level category selection. Fixed in wave-m4-3 review (S4) by adding a separate `<select>` for subcategories.
- **No spec for null-vs-absent field distinction on PUT.** `exclude_none=True` strips both explicit nulls and absent fields, making it impossible to clear a field to null. Documented as S2 in wave-m4-1.md; deferred for post-MVP.

## 5. Test Separation Effectiveness

- **Separately-authored tests did NOT catch implementation bugs in M4.** All 174 tests passed on first run. This could indicate either (a) the implementation was solid, or (b) the test coverage missed edge cases.
- **However, the review process caught 26 issues across 4 waves** (10 in wave 1, 8 in wave 2, 6 in wave 3, 2 in wave 4). The fix plan analysis process caught 6 additional issues from security reviews that the initial fix plans missed (S5-S8 in wave 1, S6/S8 in wave 2). So the review cycle compensated for what tests did not catch.
- **Test task scoping was appropriate.** Two test tasks (backend API + frontend UI) for a 5-implementation-task milestone is the right ratio. Each test task was completable in a single session.

## 6. Cost & Efficiency

- **~16 agents across 4 waves** (7 implementation, 4 review, 4 fix, 1 verification), all Claude Opus 4.6.
- **Wave 1 was disproportionately heavy.** Task 4.1 (category taxonomy + 4 CRUD endpoints) was the largest single task in the milestone. The 10-issue review with fix plan analysis generated the most review content of any wave. Consider splitting similarly large tasks in future milestones.
- **Subagent type mismatch persists** (flagged in M3.1 retro, not fixed). All agents ran as `general-purpose`.
- **CDK snapshot regeneration overhead.** This is the third milestone where the snapshot was stale at verification time (M3, M3.1, M4). Needs a process fix, not just a recommendation.
- **No context limit issues.** All tasks completed within a single session. The largest wave review (wave-m4-1.md) is ~540 lines but fit comfortably.

## 7. Recommendations for Next Milestone

1. **Automate CDK snapshot regeneration.** Add a pre-commit hook or merge checklist item that runs `cdk synth` and updates the snapshot file. This has been recommended three consecutive milestones and not implemented.
2. **Enforce `subagent_type` matching.** Same recommendation from M3.1. Not yet implemented.
3. **Split large implementation tasks.** Task 4.1 had 4 CRUD endpoints + full category taxonomy in a single task. For M5, the dashboard aggregation (Task 5.1) should remain atomic (single endpoint), but verify no task tries to pack multiple unrelated features.
4. **Add subcategory UX to the spec.** The gap discovered in S4 (wave-m4-3.md) should be captured in SPEC.md for M5+ reference.
5. **Consider adding `exclude_unset` as a future improvement.** The null-vs-absent field distinction (S2, wave-m4-1.md) will become relevant as more users edit receipts.
6. **Run `ruff check tests/` in test task acceptance criteria.** Recommended in M3.1 retro, not yet adopted.

# Retrospective: Milestone 5 -- Dashboard & Transactions

## 1. Summary

Built the dashboard summary endpoint (weekly/monthly spending totals, % change, top categories, recent activity), transactions ledger endpoint (filtering, sorting, merchant search, cursor pagination), dashboard page with stat cards and category breakdown, transactions page with sortable table and responsive card layout, and analytics placeholder. Added 149 new tests (71 backend API + 78 frontend UI). Extracted shared pagination and response helpers.

- **Milestone:** 5 -- Dashboard & Transactions
- **Tasks completed:** 6/6 (5.1--5.6)
- **Waves completed:** 3

## 2. What Went Well

- **Wave 1 backend APIs landed cleanly on first attempt.** Both the dashboard summary (5.1) and transactions (5.2) endpoints passed all acceptance criteria with zero BLOCKERs. The review found only SUGGESTIONs (S1--S6), all quality/performance improvements rather than correctness bugs.
- **Plain Python aggregation instead of pandas.** Task 3.17 removed pandas in M3.1 security hardening. Task 5.1 correctly used `defaultdict` and `sorted` instead, avoiding a dependency that had been removed. The decision was documented in the task review and the code is more readable than a pandas equivalent.
- **Fix plan analysis process caught 2 missing items.** The initial fix plan for Wave 1 covered only the 3 code review SUGGESTIONs (S1--S3). The fix plan analysis identified 2 additional security review items (S4: date param validation, S6: silent cursor exception) that should have been included, plus validated the S5 deferral. This four-step review-fixplan-analysis-verify process continues to justify itself.
- **Shared module extraction (S2) reduced duplicated security code.** `shared/pagination.py` and `shared/responses.py` now house the cursor encode/decode/validation and error response helpers. Three API modules (`receipts.py`, `transactions.py`, `categories.py`) import from shared modules instead of maintaining local copies of 30+ lines of security-critical code.
- **Wave 3 tests (5.5, 5.6) found no implementation bugs.** 149 tests all passed on first run. The tests cover all API contract fields, all 6 sort combinations, combined filters, user isolation, cursor security, debounce behavior, and dual desktop/mobile rendering.
- **DR-003 (decoupled pipeline ingestion) indirectly validated.** Dashboard and transactions endpoints query only DynamoDB (via GSI1), completely decoupled from the pipeline. No performance or data freshness issues at MVP scale.

## 3. What Needed Human Intervention

- **CDK snapshot stale at verification time (4th consecutive milestone).** The snapshot was not regenerated after M5 code merged to main. Required manual regeneration during verification. This has been recommended in every retro since M3 and has not been fixed. Needs a process gate, not just a recommendation.
- **README.md "Current Capabilities" section was stuck at M4.** Updated to M5 during this verification. Test counts were also out of date (482/253 instead of 553/331). This should be part of the merge checklist for each milestone.
- **PROGRESS.md was already up to date.** All 6 tasks correctly marked `done`. No manual status reconciliation needed this milestone -- an improvement over M4.

## 4. Spec Gaps Discovered

- **SPEC says dashboard uses pandas for aggregation (line ~681)** but pandas was removed in Task 3.17 (M3.1 security hardening, L3 finding). The SPEC should be updated to remove the pandas reference. The implementation correctly uses plain Python. Minor spec staleness, no implementation impact.
- **No spec for date param format validation.** The transactions endpoint's `startDate`/`endDate` params had no format validation specified. The dashboard's `month` param was validated (regex in the implementation) but the spec didn't call for it either. The security review (S4) identified this gap. A general input validation policy should be added to SPEC Section 10.
- **No spec for None-merchant sort behavior.** When sorting by merchant, the spec does not define where receipts with no merchant name should appear. The implementation initially placed them inconsistently (beginning for both asc/desc). Fixed in Wave 1 review (S3) to always place at end.

## 5. Test Separation Effectiveness

- **Separately-authored tests did NOT catch implementation bugs in M5.** All 149 tests passed on first run. However, the review process caught 7 issues across 3 waves (6 in Wave 1, 1 BLOCKER in Wave 2, 0 in Wave 3). The code review continues to be the primary defect-finding mechanism, not the separately-authored tests.
- **The Wave 2 review caught B1 (wrong category slugs in TransactionFilters)** -- 11 of 13 category slugs were fabricated values that would never match backend data. This is a data correctness issue that tests could have caught if they cross-referenced `category-taxonomy.md`, but the UI tests focused on rendering behavior rather than data accuracy.
- **Test task scoping was appropriate.** Two test tasks (backend API + frontend UI) for a 4-implementation-task milestone is the right ratio.

## 6. Cost & Efficiency

- **~12 agents across 3 waves** (6 implementation, 3 review, 2 fix, 1 verification), all Claude Opus 4.6.
- **Milestone was the cleanest yet.** No BLOCKERs in backend APIs, one BLOCKER in frontend (category slugs -- a data entry error, not an architecture problem). All fixes verified in a single cycle.
- **Wave 1 review was the densest.** The combined code + security review for Tasks 5.1/5.2 produced 6 code findings + 3 security findings with full fix plan, analysis, fix results, and verification -- all in a single review file. This is the most thorough single-wave review to date.
- **No context limit issues.** All tasks completed within single sessions. The Wave 1 review file (`wave-m5-1.md`) is the longest at ~330 lines but fit comfortably.
- **Subagent type mismatch persists** (flagged in M3.1 and M4 retros, not fixed). All agents ran as `general-purpose`.

## 7. Recommendations for Next Milestone

1. **Automate CDK snapshot regeneration.** This is the 4th consecutive milestone where this has been flagged. Add a pre-commit hook or a CI gate that fails when the snapshot is stale. Stop recommending it and just implement it.
2. **Add README update to the merge checklist.** "Current Capabilities" section and test counts must be updated when merging a milestone.
3. **Update SPEC.md to remove pandas reference.** Line ~681 still says "aggregates with pandas in Lambda" but pandas was removed in M3.1. Replace with "aggregates in Lambda" or "aggregates with plain Python in Lambda."
4. **Add date format validation to the spec.** SPEC Section 10 should specify that date query parameters must be validated (YYYY-MM-DD format) and rejected with 400 on mismatch. This prevents the gap that led to S4.
5. **Cross-reference category-taxonomy.md in frontend test tasks.** The B1 bug (wrong category slugs) could have been caught by test acceptance criteria that explicitly required matching the canonical taxonomy. Add "category slugs match category-taxonomy.md exactly" to any test task involving category dropdowns.
6. **Enforce `subagent_type` matching.** Same recommendation from M3.1 and M4. Still not implemented.
7. **Run `ruff check tests/` in test task acceptance criteria.** Recommended in M3.1 retro, partially adopted. Should be standard for all backend test tasks.

## 8. Areas of Low Confidence

- **Test coverage gap for category data accuracy.** Tests verify that the category filter renders and propagates values, but no test verifies that the hardcoded category values match the canonical taxonomy. The B1 bug proves this is a real risk. The recommendation in Section 7 mitigates this for future milestones, but existing category-related tests may have similar blind spots.
- **Unbounded full-partition fetch (S5) deferred.** The dashboard and transactions endpoints both paginate through ALL matching records with no safety cap. At MVP scale this is fine, but the TODO comments added during M5 are the only guard. If a user accumulates thousands of receipts, Lambda memory and timeout could become an issue. Approximate threshold: ~10,000 receipts per user before this matters.
- **Merchant sort with None values is tested only at the code review level.** No dedicated test verifies that None-merchant receipts sort to the end. The fix was validated during review, but a regression could reintroduce the inconsistency silently.

## Review Discussion


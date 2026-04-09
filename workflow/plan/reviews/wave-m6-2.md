# Wave 2 Review: Manual DNS + Runbooks

Reviewed: 2026-04-09
Reviewer: Claude Opus 4.6 (code-reviewer)
Cross-referenced: SPEC.md §11 (Logging & Troubleshooting), §12 (Non-Functional Requirements), §13 (Deployment Architecture), HANDOFF.md

**Scope:** Tasks 6.4, 6.5, 6.6 (documentation tasks). Task 6.3 is MANUAL (pending human execution) — skipped.

---

## Task 6.4: Deploy & Teardown Guide

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Covers dev stack lifecycle: deploy, update, teardown | PASS | Sections: Dev Stack Deploy, Update, Teardown |
| Covers prod stack lifecycle: deploy, update, teardown (with ACM/DNS prereqs) | PASS | Sections: Prod Stack First-Time Deploy, Update, Teardown. References cloudflare-custom-domain.md |
| Includes frontend build + S3 upload + CloudFront invalidation steps | PASS | Steps 3-5 in dev deploy, steps 2-4 in prod deploy |
| Includes environment variable reference (stage-specific config from cdk.json) | PASS | Three tables: stage config, frontend build env vars, CDK stack outputs |
| Includes pre-deploy checklist (tests pass, CDK snapshot current, env vars set) | PASS | 6-step checklist at top of guide |
| Includes rollback instructions (redeploy previous commit) | PASS | Dedicated section with infra-only and frontend-only rollback variants |

### Issues Found

**[S1] — SUGGESTION: Incorrect health check URL**

`workflow/guides/deploy-teardown.md:141` — Dev verification uses `/health` but the actual API endpoint is `/api/health`.

The health endpoint is registered at `/api/health` in both the Lambda Powertools resolver (`backend/src/novascan/api/app.py:27`) and the API Gateway route (`infra/cdkconstructs/api.py:168`). The guide omits the `/api` prefix.

Same issue at line 230 for prod verification:
```
curl -s https://<ApiUrl from outputs>/health
```
Should be:
```
curl -s https://<ApiUrl from outputs>/api/health
```

Anyone following this guide to verify a deployment would get a 403 (unauthorized catch-all route) or 404 instead of 200, creating confusion about whether the deploy succeeded.

---

## Task 6.5: Monitoring Guide

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Documents all CloudWatch metrics published by pipeline Lambdas | PASS | Section 2: all 6 metrics with dimensions, units, and descriptions. Verified against `finalize.py` |
| Includes at least 5 CloudWatch Logs Insights queries | PASS | Section 3: 7 queries (pipeline failures, slow executions, error rates, API 4xx/5xx, auth failures, fallback usage, cold starts) |
| Lists key CloudWatch log groups and how to locate them | PASS | Section 1: inventory table with all 9 log groups plus CLI commands |
| Covers Step Functions console usage for inspecting pipeline executions | PASS | Section 4: filtering, CLI commands, log correlation workflow |
| Includes manual alarm setup instructions (SNS + CloudWatch alarm) | PASS | Section 5: 5 alarms with full CLI commands |
| Includes cost monitoring guidance | PASS | Section 6: per-service Cost Explorer commands, AWS Budgets setup |

### Issues Found

No issues found for Task 6.5.

---

## Task 6.6: Troubleshooting Guide

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| 10+ failure scenarios with symptoms/diagnosis/fix | PASS | 15 scenarios across 5 layers |
| Pipeline: Textract timeout | PASS | Section 2.1 |
| Pipeline: Bedrock throttling | PASS | Section 2.2 |
| Pipeline: Both pipelines fail | PASS | Section 2.3 |
| Pipeline: S3 event not triggering SQS | PASS | Section 2.4 |
| API: 401 expired token | PASS | Section 3.1 |
| API: 403 wrong user | PASS | Section 3.2 |
| API: 500 Lambda error | PASS | Section 3.3 |
| API: CORS errors | PASS | Section 3.4 |
| Auth: OTP not received | PASS | Section 4.1 |
| Auth: Session expired | PASS | Section 4.2 |
| Auth: Refresh token invalid | PASS | Section 4.3 |
| Frontend: Blank page (S3 deploy) | PASS | Section 5.1 |
| Frontend: Stale cache (CloudFront) | PASS | Section 5.2 |
| CDK: Deploy fails | PASS | Section 6.1 |
| CDK: Drift detection | PASS | Section 6.2 |
| Documents Lambda Powertools structured logs | PASS | Section 1: correlation IDs, X-Ray, Logs Insights queries |
| Includes how to replay failed pipeline execution | PASS | Section 7: re-upload and manual SFN trigger |
| Includes DynamoDB inspection examples | PASS | Section 8: 7 query examples |

### Issues Found

**[S2] — SUGGESTION: Incorrect refresh token lifetime**

`workflow/guides/troubleshooting.md:496` — States "Refresh token: 30 days (configurable in User Pool settings)" but the actual CDK configuration is `refresh_token_validity=cdk.Duration.days(7)` (7 days), set by Task 3.11 auth construct hardening (`infra/cdkconstructs/auth.py:114`).

Same incorrect value at line 524: "Refresh token expired (default 30 days)" — should be 7 days.

This matters because a user troubleshooting auth issues would expect their refresh token to be valid for 30 days when it actually expires after 7 days. Misdiagnosis could waste time investigating other causes.

**[N1] — NIT: Duplicate `--expression-attribute-values` flag in CLI example**

`workflow/guides/troubleshooting.md:873-885` — The "Count receipts by status for a user" DynamoDB CLI example specifies `--expression-attribute-values` twice. The second instance overrides the first (AWS CLI behavior), so the command works because the second includes both `:pk` and `:status`. But the first occurrence is dead code and confusing.

Should consolidate into a single `--expression-attribute-values` with both values.

---

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| SPEC §11 — Log group patterns for all Lambdas | Monitoring guide §1 lists all 9 log groups matching SPEC §11 table | PASS |
| SPEC §11 — Custom metrics: ReceiptUploaded, PipelineCompleted, PipelineLatency, RankingDecision, RankingScoreDelta, ReceiptStatus, UsedFallback | Monitoring guide §2 documents all except ReceiptUploaded (noted as not yet implemented) | PASS |
| SPEC §11 — Troubleshooting receipt processing (5-step flow) | Troubleshooting guide covers all 5 steps across sections 2, 7, 8 | PASS |
| SPEC §11 — "No custom dashboards for MVP" | Monitoring guide §5 provides manual alarm setup via CLI, no CDK-deployed dashboards | PASS |
| SPEC §13 — Manual deployment steps | Deploy-teardown guide matches SPEC §13 4-step deploy sequence | PASS |
| SPEC §13 — Custom domain setup (5-step flow) | Deploy-teardown guide references cloudflare-custom-domain.md for DNS steps | PASS |
| SPEC §13 — Frontend env vars (VITE_API_URL, etc.) | Deploy-teardown guide §Frontend Build Environment Variables matches SPEC §13 table | PASS |
| SPEC §13 — Resource naming `novascan-{stage}-{resource}` | All guides use correct naming convention | PASS |

## Things Done Well

- **All three guides are production-ready and copy-pasteable.** Every CLI command uses real resource names derived from CDK constructs, not hypothetical placeholders.
- **The deploy-teardown one-liners with `jq`** (lines 320-347) are a standout — they chain CDK deploy → extract outputs → build → upload → invalidate in a single command. Practical for daily use.
- **Monitoring guide metric reference table** accurately maps all 6 custom metrics with correct dimensions, units, and descriptions — verified line-by-line against `finalize.py`.
- **Troubleshooting guide's 15 scenarios** follow a consistent Symptoms/Diagnosis/Fix pattern with real Logs Insights queries, making it a genuinely useful ops runbook rather than generic advice.
- **Cross-referencing between guides** is well done — deploy-teardown references cloudflare-custom-domain.md, monitoring guide references troubleshooting guide's flowchart pattern.
- **The DynamoDB key schema reference table** (troubleshooting guide §8) is a valuable quick reference that accurately reflects the actual data model.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| S1 | SUGGESTION | 6.4 | Incorrect health check URL (`/health` → `/api/health`) | Fix 2 occurrences in deploy-teardown.md |
| S2 | SUGGESTION | 6.6 | Incorrect refresh token lifetime (30 days → 7 days) | Fix 2 occurrences in troubleshooting.md |
| N1 | NIT | 6.6 | Duplicate `--expression-attribute-values` in DynamoDB CLI example | Consolidate to single flag |

**Overall verdict:** Strong documentation wave. All three guides are comprehensive, well-structured, and largely accurate. The 2 SUGGESTIONs are factual inaccuracies that could cause real troubleshooting confusion and should be fixed. The NIT is cosmetic.

## Review Discussion

### Fix Plan (Claude Opus 4.6 — 2026-04-09)

**Scope: 3 issues (0 BLOCKERs, 2 SUGGESTIONs, 1 NIT)**

**[S1] Incorrect health check URL**
- Independent assessment: Reading deploy-teardown.md:140 shows `curl ... /health`. Cross-referencing `backend/src/novascan/api/app.py:27` (`@app.get("/api/health")`) and `infra/cdkconstructs/api.py:168` (`path="/api/health"`) confirms the endpoint is `/api/health`. The `/health` path would hit the catch-all authorized route and return 403/404, causing a user to misdiagnose a successful deploy as failed.
- Review comparison: Agree fully. Same root cause, same two locations (lines 140, 230).
- Fix: Replace `/health` with `/api/health` on both lines (140, 230) in deploy-teardown.md.
- Risk: None meaningful. The `/api/health` path is verified in two source files. The only risk is if someone later changes the health endpoint path without updating the guide, but that is a future maintenance concern, not a regression from this fix.
- Files: `workflow/guides/deploy-teardown.md`

**[S2] Incorrect refresh token lifetime**
- Independent assessment: Reading troubleshooting.md:494 ("Refresh token: 30 days") and line 524 ("default 30 days"). Cross-referencing `infra/cdkconstructs/auth.py:114` shows `refresh_token_validity=cdk.Duration.days(7)`. The 30-day value is the Cognito default before Task 3.11 hardened it to 7 days. The guide was likely written against Cognito defaults rather than the actual CDK configuration.
- Review comparison: Agree fully. Same two locations, same root cause.
- Fix: Replace "30 days" with "7 days" at both occurrences (line 494 and line 524) in troubleshooting.md.
- Risk: If someone later changes the CDK `refresh_token_validity` setting, the guide would again be out of date. Consider adding a comment noting the source of truth is `infra/cdkconstructs/auth.py`, but that may be over-engineering for a docs fix.
- Files: `workflow/guides/troubleshooting.md`

**[N1] Duplicate `--expression-attribute-values` in DynamoDB CLI example**
- Independent assessment: Lines 875-877 define `--expression-attribute-values` with only `:pk`. Lines 881-884 redefine it with both `:pk` and `:status`. AWS CLI last-wins behavior means it works, but the first block is dead code. Confusing for anyone reading/adapting the command.
- Review comparison: Agree fully.
- Fix: Remove the first `--expression-attribute-values` block (lines 875-877) and keep only the second (lines 881-884) which contains both `:pk` and `:status`. Reorder flags so `--filter-expression` and `--expression-attribute-names` appear before the single `--expression-attribute-values`.
- Risk: Minimal. The consolidated command is functionally identical to the current last-wins behavior. The only risk is a copy-paste error during editing that breaks the JSON syntax, which will be caught by visual inspection.
- Files: `workflow/guides/troubleshooting.md`

**Execution order:**

All three fixes are independent (different files or non-overlapping regions). They can be applied in parallel, but for clean commits:
1. Fix S1 in deploy-teardown.md (2 line changes)
2. Fix S2 in troubleshooting.md (2 line changes)
3. Fix N1 in troubleshooting.md (restructure 1 CLI example)

**Verification commands:**

```bash
# S1: Verify /api/health appears in deploy-teardown.md and /health alone does not
grep -n '/health' workflow/guides/deploy-teardown.md
# Should show /api/health on lines ~140 and ~230, no bare /health

# S2: Verify 7 days appears and 30 days does not
grep -n 'days' workflow/guides/troubleshooting.md | grep -i 'refresh'
# Should show "7 days" in both locations

# N1: Verify single --expression-attribute-values in the "Count receipts" example
sed -n '868,890p' workflow/guides/troubleshooting.md
# Should show exactly one --expression-attribute-values flag
```

### Fix Plan Analysis (Claude Opus 4.6 — 2026-04-09)

**[S1] (Incorrect health check URL) — Approve**
My approach: Read `deploy-teardown.md` lines 130–145 and 220–235. Found `/health` at lines 140 and 230. Cross-referenced `backend/src/novascan/api/app.py:27` (`@app.get("/api/health")`) — the endpoint is definitively `/api/health`. Fix: replace `/health` with `/api/health` at both locations.
Plan's approach: Same two locations, same replacement. Aligns with my analysis — both identified the same root cause (missing `/api` prefix) and the same two lines.

**[S2] (Incorrect refresh token lifetime) — Revise**
My approach: Searched `troubleshooting.md` for all "30 days" references near refresh token context. Found **3 occurrences**, not 2:
- Line 494: `Refresh token: 30 days (configurable in User Pool settings)`
- Line 504: `If the refresh token is also expired (30 days), the user must re-authenticate.`
- Line 524: `Refresh token expired (default 30 days)`
Cross-referenced `infra/cdkconstructs/auth.py:114` — `refresh_token_validity=cdk.Duration.days(7)`. All three should read "7 days".
Plan's approach is incomplete — it identifies lines 494 and 524 but **misses line 504**. Applying only 2 of 3 fixes would leave contradictory information in the same section (§4.2 would say "7 days" on line 494 but "30 days" on line 504, six lines later).
**Alternative:** Replace "30 days" with "7 days" at all three occurrences (lines 494, 504, 524). Additionally, line 494's parenthetical should be updated from "configurable in User Pool settings" to "configured in `infra/cdkconstructs/auth.py`" for source-of-truth traceability, though this is optional.

**[N1] (Duplicate `--expression-attribute-values`) — Approve**
My approach: Read lines 868–885. The first `--expression-attribute-values` (lines 875–877) only has `:pk`, the second (lines 881–884) has both `:pk` and `:status`. AWS CLI last-wins means the command works but the first block is dead code. Fix: remove lines 875–877, keep lines 881–884.
Plan's approach: Same removal target. Plan additionally suggests reordering flags (`--filter-expression` and `--expression-attribute-names` before `--expression-attribute-values`) — this is a readability improvement, not strictly necessary but harmless. Aligns with my analysis on the core fix.

### Fix Results (Claude Opus 4.6 — 2026-04-09)

**Branch:** `fix/wave-2-docs-corrections` (based on `feature/m6-wave2-dns-runbooks`)
**Status: 3/3 fixed, 0 deferred**

**[S1] (Incorrect health check URL) — Fixed**
- What was changed: Replaced `/health` with `/api/health` at both occurrences (lines 140, 230)
- Files modified: `workflow/guides/deploy-teardown.md`

**[S2] (Incorrect refresh token lifetime) — Fixed**
- What was changed: Replaced "30 days" with "7 days" at all 3 occurrences (lines 494, 504, 524). Updated line 494 parenthetical to reference `infra/cdkconstructs/auth.py` as source of truth. Applied the revised fix plan (3 occurrences, not 2).
- Files modified: `workflow/guides/troubleshooting.md`

**[N1] (Duplicate `--expression-attribute-values`) — Fixed**
- What was changed: Removed the first `--expression-attribute-values` block (dead code with only `:pk`). Reordered flags so `--filter-expression` and `--expression-attribute-names` appear before the single `--expression-attribute-values`. Moved `--select COUNT` to end for readability.
- Files modified: `workflow/guides/troubleshooting.md`

**Verification:**
- `grep '/health' workflow/guides/deploy-teardown.md` — PASS (only `/api/health` on lines 140, 230)
- `grep 'days.*[Rr]efresh\|[Rr]efresh.*days' workflow/guides/troubleshooting.md` — PASS (all 3 lines show "7 days")
- DynamoDB CLI example (lines 868–882) — PASS (single `--expression-attribute-values` with both `:pk` and `:status`)

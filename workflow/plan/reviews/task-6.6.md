# Task 6.6: Troubleshooting Guide

## Work Summary
- **What was implemented:** Created a comprehensive troubleshooting guide covering 15 failure scenarios across pipeline, API, auth, frontend, and CDK layers. Includes structured log reading, pipeline replay instructions, and DynamoDB inspection examples.
- **Key decisions:** Organized by layer (pipeline, API, auth, frontend, CDK) for fast lookup. Each scenario follows a strict Symptoms / Diagnosis / Fix pattern with actual AWS CLI commands and CloudWatch Logs Insights queries. Used real Lambda function names, DynamoDB key patterns, and error payloads from the codebase.
- **Files created/modified:**
  - `workflow/guides/troubleshooting.md` (created)
  - `workflow/plan/reviews/task-6.6.md` (created)
  - `workflow/plan/PLAN.md` (updated -- task checkbox marked)
  - `workflow/plan/PROGRESS.md` (updated -- status set to review)
- **Test results:** `test -f workflow/guides/troubleshooting.md && echo "PASS"` -- PASS
- **Spec gaps found:** None
- **Obstacles encountered:** None

## Acceptance Criteria Verification

| Criterion | Status | Notes |
|-----------|--------|-------|
| 10+ failure scenarios with symptoms/diagnosis/fix | Done | 15 scenarios: 4 pipeline, 4 API, 3 auth, 2 frontend, 2 CDK |
| Pipeline: Textract timeout | Done | Section 2.1 |
| Pipeline: Bedrock throttling | Done | Section 2.2 |
| Pipeline: Both pipelines fail | Done | Section 2.3 |
| Pipeline: S3 event not triggering SQS | Done | Section 2.4 |
| API: 401 expired token | Done | Section 3.1 |
| API: 403 wrong user | Done | Section 3.2 |
| API: 500 Lambda error | Done | Section 3.3 |
| API: CORS errors | Done | Section 3.4 |
| Auth: OTP not received | Done | Section 4.1 |
| Auth: Session expired | Done | Section 4.2 |
| Auth: Refresh token invalid | Done | Section 4.3 |
| Frontend: Blank page (S3 deploy) | Done | Section 5.1 |
| Frontend: Stale cache (CloudFront) | Done | Section 5.2 |
| CDK: Deploy fails (resource limit, IAM) | Done | Section 6.1 |
| CDK: Drift detection | Done | Section 6.2 |
| Lambda Powertools structured logs | Done | Section 1 -- correlation IDs, X-Ray, Logs Insights queries |
| Replay failed pipeline execution | Done | Section 7 -- re-upload and manual SFN trigger |
| DynamoDB inspection examples | Done | Section 8 -- 7 query examples with full CLI commands |

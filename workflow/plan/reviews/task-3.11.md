# Task 3.11: Auth Construct Hardening [H2 + H3 + M4]

## Work Summary
- **Branch:** `task/3.11-auth-construct-hardening` (based on `feature/m3.1-wave1-critical-fixes`)
- **What was implemented:** Three security hardening fixes to the Cognito auth CDK construct: removed PASSWORD from AllowedFirstAuthFactors (EMAIL_OTP only), scoped Post-Confirmation Lambda IAM ARN from `userpool/*` to `userpool/novascan-*`, and set refresh token validity to 7 days.
- **Key decisions:** CDK stores `Duration.days(7)` as 10080 minutes internally, so the test assertion matches `RefreshTokenValidity: 10080` with `TokenValidityUnits.RefreshToken: "minutes"` rather than 7 days.
- **Files created/modified:**
  - `infra/cdkconstructs/auth.py` (modified — 3 changes: EMAIL_OTP only, scoped IAM ARN, refresh token validity)
  - `infra/tests/test_auth_construct.py` (modified — added `TestAuthSecurityHardening` class with 2 new tests + 1 refresh token test)
  - `infra/tests/snapshots/novascan-dev.template.json` (regenerated)
  - `workflow/plan/PLAN-M3.1.md` (marked task checkbox)
  - `workflow/plan/PROGRESS-M3.1.md` (updated status to review)
- **Test results:** 15/15 auth construct tests pass, 75/75 full infra tests pass (including snapshot), CDK synth passes
- **Spec gaps found:** none
- **Obstacles encountered:** CDK `Fn::Join` produces a single ARN string element (not split), and CDK internally stores Duration.days as minutes — both required test matcher adjustments.

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.
Append-only — never overwrite previous entries.}

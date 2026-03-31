# Task 1.12: Dev Stack Deployment + E2E Smoke Test

## Work Summary
- **What was implemented:** First deployment of `novascan-dev` CDK stack to AWS, frontend build/upload to S3, CloudFront invalidation, and full E2E smoke test (health check, auth gate, sign-up/sign-in/dashboard/sign-out).
- **Key decisions:**
  - Added `FrontendBucketName` and `DistributionId` CfnOutputs to enable frontend upload and cache invalidation
  - Fixed Cognito `SignInPolicy.AllowedFirstAuthFactors` to include `EMAIL_OTP` (CDK L2 doesn't expose this — used CloudFormation escape hatch)
  - Fixed OTP input field from 6-digit to 8-digit (Cognito EMAIL_OTP default code length)
- **Files created/modified:**
  - `infra/stacks/novascan_stack.py` — added 2 CfnOutputs
  - `infra/cdkconstructs/auth.py` — added `EMAIL_OTP` + `PASSWORD` to `AllowedFirstAuthFactors` via escape hatch
  - `infra/tests/snapshots/novascan-dev.template.json` — regenerated
  - `frontend/src/pages/LoginPage.tsx` — OTP input maxLength 6 → 8
  - `.gitignore` — added `cdk-outputs.json`
- **Test results:**
  - `cd infra && uv run pytest` — 47 passed
  - `cd frontend && npm run build` — PASS
  - CDK deploy — PASS (39 resources created)
  - `/api/health` — 200 OK
  - Unauthenticated `/api/receipts` — 401
  - CloudFront SPA — 200 OK
  - E2E auth flow (sign-up → OTP → dashboard → nav → sign-out → protected redirect) — PASS
- **Spec gaps found:**
  1. **CRITICAL: Pre-Sign-Up auto-confirm allows unauthenticated account creation with arbitrary emails.** See details below.
  2. Cognito `AllowedFirstAuthFactors` not configurable via CDK L2 — requires escape hatch.
  3. Cognito EMAIL_OTP sends 8-digit codes; frontend and spec assumed 6-digit.
- **Obstacles encountered:**
  - CDK deploy failed on first attempt: interactive IAM approval prompt not supported in non-interactive shell. Resolved with `--require-approval never` after reviewing diff.
  - CDK deploy failed with `EMAIL_OTP`-only sign-in policy: Cognito requires `PASSWORD` always present in `AllowedFirstAuthFactors`. Fixed by including both.

## Spec Gap: Pre-Sign-Up Auto-Confirm Security Issue

**Problem:** The Pre-Sign-Up Lambda auto-confirms users and auto-verifies their email without any proof of email ownership. This means:
- Anyone can call Cognito `SignUp` with any email address → account is created as `CONFIRMED`
- Attacker cannot sign in (OTP goes to real email owner), but can:
  - Pollute the user pool with junk accounts
  - Trigger unsolicited OTP emails to arbitrary email addresses (email spam/harassment)
  - Incur Lambda + SES costs

**Root cause:** Auto-confirm was a UX shortcut to make first-time sign-up invisible (single OTP code). It skips email ownership verification.

**Proposed fix:** Remove `autoConfirmUser` from Pre-Sign-Up Lambda. First-time users will receive two emails:
1. Account verification code (proves email ownership, confirms account)
2. Sign-in OTP (normal login challenge)

Returning users still get a single OTP. No password needed — `SignUp` API passes a random throwaway password since sign-in is always via EMAIL_OTP.

**Frontend changes needed:** Handle `confirmSignUp` step in the auth flow when user is `UNCONFIRMED`.

**Status:** Must be resolved before Milestone 1 is considered complete.

## Review Discussion


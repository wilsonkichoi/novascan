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

### Fix Results (Claude Opus 4.6 — 2026-03-31)

**Issue 1 (Pre-Sign-Up Auto-Confirm Security) — Fixed**
- What was changed: Removed `autoConfirmUser`/`autoVerifyEmail` flags from Pre-Sign-Up Lambda (now a no-op). Added `confirmSignUp()` and `resendConfirmationCode()` to frontend auth module. Added "confirm" step to LoginPage between email and OTP steps. New users now receive a 6-digit verification code before the 8-digit sign-in OTP.
- Files modified:
  - `backend/src/novascan/auth/pre_signup.py` — no-op handler
  - `infra/cdkconstructs/auth.py` — updated Lambda description
  - `frontend/src/lib/auth.ts` — added `confirmSignUp`, `resendConfirmationCode`, `UserNotConfirmedException` handling
  - `frontend/src/pages/LoginPage.tsx` — added "confirm" step with resend button
  - `frontend/src/lib/__tests__/auth.test.ts` — updated + 5 new tests (30 total)
  - `frontend/src/pages/__tests__/LoginPage.test.tsx` — updated + 3 new tests (22 total)
  - `infra/tests/snapshots/novascan-dev.template.json` — regenerated

**Verification:**
- `cd infra && uv run pytest` — 47 passed
- `cd frontend && npm run build` — PASS
- `cd frontend && npm run test -- --run` — 86 passed (up from 78)
- CDK deploy — PASS
- E2E new user (email → 6-digit confirm → 8-digit OTP → dashboard) — PASS
- E2E returning user (email → 8-digit OTP → dashboard) — PASS
- `cd infra && uv run cdk destroy --context stage=dev --force` — PASS

### Fix Plan (Claude Opus 4.6 — 2026-03-31)

**Issue 1 (Pre-Sign-Up Auto-Confirm Security)**

- **Verified:** `pre_signup.py:23-24` unconditionally sets `autoConfirmUser=True` and `autoVerifyEmail=True`. The frontend `auth.ts:126-138` catches `UserNotFoundException`, calls `signUp`, then immediately retries `sendInitiateAuth` — this only works because the Lambda auto-confirms. No other mechanism prevents arbitrary account creation. The `VITE_COGNITO_CLIENT_ID` is public in the SPA bundle, so any HTTP client can call the Cognito `SignUp` API.

- **Alternatives considered:**
  | Approach | Verdict |
  |----------|---------|
  | A. Remove auto-confirm, add `ConfirmSignUp` step | **Chosen** — standard Cognito flow, email verified before account is usable |
  | B. Delete Pre-Sign-Up Lambda entirely (vs keep as no-op) | Valid but higher blast radius — removes Lambda + trigger from CDK, requires CDK test updates + snapshot regen for the removal. Keeping as no-op is safer for deployed stack. |
  | C. Custom Message Lambda to unify confirmation + OTP into one code | **Rejected** — not feasible, Cognito confirmation codes and EMAIL_OTP are separate mechanisms |
  | D. Pre-Authentication Lambda with rate limiting | **Rejected** — Pre-Authentication fires on `InitiateAuth`, not `SignUp`. Doesn't address the attack vector. |
  | E. Disable self-signup, use AdminCreateUser | **Rejected** — disproportionate complexity for personal MVP |

- **Fix:** Make Pre-Sign-Up Lambda a no-op (remove the two flag assignments). Add `ConfirmSignUp` and `ResendConfirmationCode` support to frontend. New users see a two-code flow (verification + OTP); returning users are unaffected.

- **Post-Confirmation Lambda:** Unaffected. It fires after `ConfirmSignUp` succeeds — same trigger event, just now triggered by user-submitted code instead of auto-confirm.

- **Files:**
  | File | Change |
  |------|--------|
  | `backend/src/novascan/auth/pre_signup.py` | Remove auto-confirm/auto-verify flags, keep as no-op |
  | `infra/cdkconstructs/auth.py` | Update Lambda description string |
  | `frontend/src/lib/auth.ts` | Import `ConfirmSignUpCommand`, `ResendConfirmationCodeCommand`. Add `confirmSignUp()`, `resendConfirmationCode()`. Modify `initiateAuth` to return `CONFIRM_SIGN_UP` on `UserNotFoundException` (after signup) and `UserNotConfirmedException` (resend code). |
  | `frontend/src/pages/LoginPage.tsx` | Add `"confirm"` step between `"email"` and `"otp"`. Confirmation code input, "Resend code" button, then auto-proceed to OTP. |
  | `frontend/src/lib/__tests__/auth.test.ts` | Update `initiateAuth` tests, add `confirmSignUp`/`resendConfirmationCode` tests |
  | `frontend/src/pages/__tests__/LoginPage.test.tsx` | Add tests for confirm step, resend, error handling |
  | `infra/tests/snapshots/novascan-dev.template.json` | Regenerate (Lambda description change) |

- **No changes needed:**
  - `frontend/src/types/auth.ts` — `challengeName` is already `string`
  - `frontend/src/hooks/useAuth.ts` — `confirmSignUp` used directly from `@/lib/auth`, not via context
  - `infra/tests/test_auth_construct.py` — Pre-Sign-Up Lambda trigger still attached
  - `backend/src/novascan/auth/post_confirmation.py` — fires on `ConfirmSignUp` as before

- **Edge cases:**
  | Scenario | Handling |
  |----------|----------|
  | User signs up, never confirms, tries again | `InitiateAuth` throws `UserNotConfirmedException` → resend code → show confirm step |
  | Confirmation code expires | `ConfirmSignUp` throws `ExpiredCodeException` → show error + "Resend code" button |
  | Existing confirmed user on dev stack | No impact — `InitiateAuth` works normally |

**Execution order:**
1. `pre_signup.py` + `auth.py` description (backend + CDK)
2. `auth.ts` (new functions + modified `initiateAuth`)
3. `LoginPage.tsx` (confirm step UI)
4. `auth.test.ts` + `LoginPage.test.tsx` (updated + new tests)
5. Snapshot regeneration: `cd infra && uv run cdk synth --context stage=dev`
6. Run all tests: `cd infra && uv run pytest` + `cd frontend && npm run test -- --run`
7. Deploy: `cd infra && uv run cdk deploy --context stage=dev --require-approval never`
8. Delete existing test user from Cognito (auto-confirmed under old flow)
9. E2E verification: new user (email → confirm code → OTP → dashboard), returning user (email → OTP → dashboard)

**Verification:**
```bash
cd infra && uv run cdk synth --context stage=dev    # CDK synth
cd infra && uv run pytest                            # CDK tests
cd frontend && npm run build                         # frontend build
cd frontend && npm run test -- --run                 # frontend tests
cd infra && uv run cdk deploy --context stage=dev --require-approval never  # deploy
# Manual E2E on dev stack
```

### Fix Plan Analysis (Claude Opus 4.6 — 2026-03-31)

**Issue 1 (Pre-Sign-Up Auto-Confirm Security) — Approve with one clarification**

Per-fix evaluation:

| # | Fix | Verdict | Notes |
|---|-----|---------|-------|
| 1 | `pre_signup.py` — remove flag assignments, keep as no-op | **Approve** | Minimal change, Lambda trigger stays wired in CDK, no blast radius |
| 2 | `auth.py` — update Lambda description | **Approve** | Cosmetic but correct for maintainability |
| 3 | `auth.ts` — add `confirmSignUp()`, `resendConfirmationCode()`, handle `UserNotConfirmedException` | **Approve with clarification** | See note below |
| 4 | `LoginPage.tsx` — add `"confirm"` step | **Approve** | Clean state machine extension |
| 5 | Tests — update auth + LoginPage tests | **Approve** | Necessary coverage |
| 6 | Snapshot regen | **Approve** | Required after description change |

**Clarification on fix #3 — `initiateAuth` restructuring:**

The fix plan says: "Modify `initiateAuth` to return `CONFIRM_SIGN_UP` on `UserNotFoundException` (after signup) and `UserNotConfirmedException` (resend code)."

This needs careful implementation. The current `initiateAuth` structure is:

```
try { sendInitiateAuth } catch UserNotFoundException { signUp → sendInitiateAuth }
```

After the fix, the retry `sendInitiateAuth` will throw `UserNotConfirmedException` (user exists but isn't confirmed). Two paths must be handled:

1. **New user**: `UserNotFoundException` → `signUp()` → retry → `UserNotConfirmedException` → return `CONFIRM_SIGN_UP`
2. **Returning unconfirmed user**: `sendInitiateAuth()` → `UserNotConfirmedException` → resend code → return `CONFIRM_SIGN_UP`

Rather than nested try/catch, skip the retry entirely — after `signUp`, the user is UNCONFIRMED and Cognito has already sent the verification email. Retrying `sendInitiateAuth` would just throw `UserNotConfirmedException` (wasted API call). Recommended approach:

```typescript
export async function initiateAuth(email: string): Promise<AuthChallengeResult> {
  try {
    return await sendInitiateAuth(email);
  } catch (error: unknown) {
    if (isUserNotFoundException(error)) {
      await signUp(email);
      // User is UNCONFIRMED — Cognito sent verification email on signup
      return { session: "", challengeName: "CONFIRM_SIGN_UP" };
    }
    if (isUserNotConfirmedException(error)) {
      await resendConfirmationCode(email);
      return { session: "", challengeName: "CONFIRM_SIGN_UP" };
    }
    throw error;
  }
}
```

**SPEC deviation (acceptable):** SPEC line 40 says "Pre-Sign-Up Lambda auto-confirms". The fix changes this to a two-step flow for new users. This is a necessary deviation — the original spec has a security gap. Update SPEC after fix is applied.

**Alternatives evaluation:** Well-reasoned. Keeping the Lambda as a no-op (vs deleting) is the right call — lower blast radius, can be repurposed later for rate limiting or domain validation.

**Edge cases:** All three scenarios in the fix plan are correctly handled. One additional edge case: if a user signs up on device A, confirms on device B, and device A still shows the confirm step — `confirmSignUp` returns `NotAuthorizedException` ("User cannot be confirmed. Current status is CONFIRMED"). Frontend should catch this and treat as success (proceed to OTP step).

**No regressions identified.** Post-Confirmation Lambda fires on `ConfirmSignUp` completion — same trigger event, just now from user-submitted code instead of auto-confirm. Verified: `post_confirmation.py` docstring confirms this.

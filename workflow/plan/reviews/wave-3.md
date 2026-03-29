# Wave 3 Review: Tasks 1.7 + 1.8

Reviewed: 2026-03-28

## Task 1.7: API + Frontend CDK Constructs

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| API Gateway HTTP API with Cognito JWT authorizer | PASS | Correctly wired with issuer URL + audience |
| API Lambda with Powertools handler | PASS | `APIGatewayHttpResolver` + Logger + Tracer |
| CORS: GET/POST/PUT/DELETE/OPTIONS, Authorization/Content-Type | PASS | All methods and headers present |
| CloudFront with S3 origin + SPA error routing (403/404 → /index.html 200) | PASS | OAC (not legacy OAI), TTL=0 on errors |
| Lambda env vars: TABLE_NAME, LOG_LEVEL, STAGE | PASS | Plus POWERTOOLS_SERVICE_NAME, POWERTOOLS_LOG_LEVEL |
| Health check excluded from authorizer | PASS | Separate route with no authorizer arg |
| Stack outputs: API URL, CloudFront domain, User Pool ID, App Client ID | PASS | All 4 CfnOutputs present |

### Issues Found

**Issue 1 — Medium: CORS `allow_origins=["*"]` deviates from spec**

`infra/cdkconstructs/api.py:98` — Spec Section 13 says: "Allowed origins: CloudFront domain (dev: default URL, prod: `https://subdomain.example.com`)". The code uses `["*"]` with a comment about tightening later.

This is solvable. In `novascan_stack.py`, the Frontend construct is created after Api, but CDK resolves references lazily via CloudFormation tokens. You could either:
- Reorder so Frontend is created first, then pass `f"https://{self.frontend.domain_name}"` to the Api construct
- For prod, at minimum hardcode `https://subdomain.example.com` since it's a known constant

Using `*` in dev is tolerable. Using `*` in prod is a real security gap. Must be parameterized before M6 at the latest.

**Issue 2 — Medium: Lambda dependencies not bundled**

`infra/cdkconstructs/api.py:53-57` — Uses `lambda_.Function` + `Code.from_asset`, which zips the source directory as-is. The API Lambda imports `aws_lambda_powertools` and `pydantic` (see `backend/pyproject.toml`), neither of which exists in the Lambda runtime. This Lambda will fail at deploy time with `ImportError`.

The auth Lambdas are fine — they only use `boto3` + stdlib, which are included in the Lambda runtime. The API Lambda is different.

The spec's Risk #4 mentions `PythonFunction` from `@aws-cdk/aws-lambda-python-alpha` for bundling with `uv`, but `infra/pyproject.toml` doesn't include that dependency, and the code uses the base `lambda_.Function`.

This is not a workaround — it's an incomplete implementation. The Lambda code is correct but won't run. Must be resolved before task 1.12 (deployment). Options:
1. Switch to `PythonFunction` (requires adding `aws-cdk.aws-lambda-python-alpha` dependency)
2. Add a Lambda Layer with Powertools + Pydantic
3. Use `Code.from_asset` with a bundled build step

**Issue 3 — Low: Redundant `function` property**

`infra/cdkconstructs/api.py:133-135` — `self.api_function` is already a public attribute. The `@property` accessor `function` is an unnecessary alias. Not harmful, but adds indirection.

---

## Task 1.8: Login Page UI

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Email input with submit button | PASS | |
| After email submit, transitions to OTP input | PASS | State machine: `"email"` → `"otp"` |
| Error states: invalid email, incorrect OTP, network failure | PASS | `friendlyError()` covers CodeMismatch, Expired, RateLimit, NotAuthorized, network |
| Loading spinner during auth calls | PASS | `Loader2` from lucide-react with `animate-spin` |
| On success, redirect to dashboard | PASS | `navigate("/", { replace: true })` |
| Authenticated users redirected away from login | PASS | Early return check at top |
| `npm run build` succeeds | PASS | Per review summary |

### Issues Found

**Issue 4 — Medium: `isLoading` state ignored — flash of login form**

`frontend/src/pages/LoginPage.tsx:22-25` checks `isAuthenticated` but not `isLoading` from `useAuth()`. On page refresh, while the session is being restored from localStorage (`refreshTokens()` in the AuthProvider), `isAuthenticated` is `false` and `isLoading` is `true`. The user sees the login form for a split second before being redirected.

Fix:
```tsx
const { signIn, verifyOtp, isAuthenticated, isLoading } = useAuth();

if (isLoading) return null; // or a loading spinner

if (isAuthenticated) {
  return <Navigate to="/" replace />;
}
```

**Issue 5 — Low: Imperative `navigate()` during render**

`frontend/src/pages/LoginPage.tsx:23` — Calling `navigate()` during render is a side effect. The idiomatic React Router approach is the declarative `<Navigate to="/" replace />` component. The imperative call works but fires twice in StrictMode development builds and is technically incorrect per React's rules.

**Issue 6 — Low: Fragile network error string matching**

`frontend/src/pages/LoginPage.tsx:164` — String-matching `"network"`, `"Network"`, or `"fetch"` in error messages is brittle across browsers. A more reliable check:
```tsx
if (err instanceof TypeError && err.message === "Failed to fetch") {
  return "Network error...";
}
```
This is the standard `fetch` API failure pattern.

**Issue 7 — Trivial: No `maxLength` on OTP input**

Cognito email OTPs are 6 digits. Adding `maxLength={6}` and `pattern="[0-9]{6}"` would improve mobile UX. Not a bug.

---

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| API Gateway HTTP API (not REST) | `apigwv2.HttpApi` | Correct |
| Cognito JWT authorizer | `HttpJwtAuthorizer` with correct issuer/audience | Correct |
| Lambda Powertools for routing | `APIGatewayHttpResolver` | Correct |
| No Amplify, no FastAPI, no Mangum | Direct SDK + Powertools only | Correct |
| CloudFront with OAC | `S3BucketOrigin.with_origin_access_control` | Correct |
| SPA routing via error responses | 403→200, 404→200 with `/index.html` | Correct |
| CORS methods/headers | Match spec exactly | Correct |
| CORS origins per-stage | **Deviates** — `*` instead of stage-specific | See Issue 1 |
| Email OTP two-step flow | Email → OTP → redirect | Correct |
| Auto-signup on first sign-in | Handled in `auth.ts` (not LoginPage's concern) | Correct |
| Tokens in memory + refresh in localStorage | Handled in `auth.ts` | Correct |
| Passwordless, no password UI | No password fields anywhere | Correct |

---

## Summary

| # | Severity | Task | Issue | Action |
|---|----------|------|-------|--------|
| 1 | Medium | 1.7 | CORS `allow_origins=["*"]` — spec says per-stage CloudFront domain | Fix before prod (M6); acceptable in dev |
| 2 | Medium | 1.7 | Lambda deps not bundled — `Code.from_asset` doesn't install Powertools/Pydantic | Must fix before task 1.12 (deploy) |
| 3 | Low | 1.7 | Redundant `function` property | Remove or keep — not blocking |
| 4 | Medium | 1.8 | `isLoading` not checked — flash of login form on refresh | Fix now — simple one-liner |
| 5 | Low | 1.8 | `navigate()` during render — use `<Navigate>` component | Fix with Issue 4 |
| 6 | Low | 1.8 | Fragile network error string matching | Improve if touching `friendlyError()` |
| 7 | Trivial | 1.8 | No `maxLength` on OTP input | Nice-to-have |

**Overall verdict:** Solid implementation. Both constructs are well-structured, follow AWS best practices (OAC not OAI, HTTP API not REST, Powertools not custom routing), and match the spec's architecture. The three medium issues are real but none are blocking for this wave — Issue 2 (bundling) is the most important and must be resolved before deployment in task 1.12, while Issue 4 (isLoading) is a quick fix that should be done now.

## Review Discussion

### feedback:
I use another AI tool to review the Wave 3 results and found some issues. Please review the finding above and fix ALL of them regardless of severity, if the issue doesn't really need to be fixed, let me know. Don't rush to start, come up with a plan and let me approve it.

### AI:
All 7 issues reviewed. Here's the fix plan:

**Issue 1 (Medium) — CORS `allow_origins=["*"]` → per-stage CloudFront domain**
- Accept `allowed_origins: list[str]` param on `ApiConstruct`.
- In `novascan_stack.py`, reorder so `FrontendConstruct` is created before `ApiConstruct`, then pass `f"https://{self.frontend.domain_name}"` as the origin.
- CDK resolves the CloudFormation token lazily, so this works at synth time.
- Files: `infra/cdkconstructs/api.py`, `infra/stacks/novascan_stack.py`

**Issue 2 (Medium) — Lambda deps not bundled** *(revised per feedback)*
- Keep `lambda_.Function` + `Code.from_asset`. Do NOT add `aws-cdk.aws-lambda-python-alpha`.
- Point `Code.from_asset` at the `backend/` directory (instead of `backend/src/novascan`) so `pyproject.toml` and `uv.lock` are in scope.
- Add `bundling=cdk.BundlingOptions(...)` using the `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` Docker image.
- Bundling commands: `uv export --frozen --no-dev --no-editable -o requirements.txt`, then `uv pip install --no-cache -r requirements.txt --target /asset-output`, then `cp -au src/novascan/. /asset-output/` to copy the application source.
- Result: Lambda zip contains installed deps (Powertools, Pydantic, etc.) alongside the app source (`api/app.py`, etc.). Handler path `api.app.handler` resolves correctly.
- Files: `infra/cdkconstructs/api.py`

**Issue 3 (Low) — Redundant `function` property**
- Remove the `@property` accessor. `self.api_function` is already public.
- Files: `infra/cdkconstructs/api.py`

**Issue 4 (Medium) — `isLoading` not checked → flash of login form**
- Destructure `isLoading` from `useAuth()`. Add early `return null` when loading.
- Files: `frontend/src/pages/LoginPage.tsx`

**Issue 5 (Low) — Imperative `navigate()` → declarative `<Navigate>`**
- Replace imperative `navigate()` during render with `<Navigate to="/" replace />` component.
- Keep `useNavigate` for the post-OTP redirect inside the event handler.
- Files: `frontend/src/pages/LoginPage.tsx`

**Issue 6 (Low) — Fragile network error string matching**
- Replace `.includes("network")/...` with `err instanceof TypeError && err.message === "Failed to fetch"` (standard fetch API failure pattern).
- Files: `frontend/src/pages/LoginPage.tsx`

**Issue 7 (Trivial) — No `maxLength` on OTP input**
- Add `maxLength={6}` and `pattern="[0-9]{6}"` to the OTP `<Input>`.
- Genuinely optional UX nicety, not a bug — but it's a one-line change so worth doing.
- Files: `frontend/src/pages/LoginPage.tsx`

**Execution order:**
1. Infra changes (Issues 1, 2, 3) — `api.py`, `novascan_stack.py`, `infra/pyproject.toml`
2. Frontend changes (Issues 4, 5, 6, 7) — `LoginPage.tsx`
3. Verify: `cd infra && uv sync && uv run cdk synth --context stage=dev` and `cd frontend && npm run build`
4. Update review file with results

### feedback:
Another AI tool reviewed the fix plan

**Are the issues real?**
Yes, all 7 issues are real. 

**Is the plan to fix them a good one?**
The plans for Issues 1, 3, 4, 5, 6, and 7 are correct and executable. 
However, the fix plan for **Issue 2 is fundamentally flawed** and must be rewritten:

1. **Violates Global Directives**: `aws-cdk.aws-lambda-python-alpha` relies implicitly on `pip`, `poetry`, or `pipenv` under the hood via Docker. You are strictly mandated to use `uv` and completely avoid `pip`.
2. **Path Misalignment**: The current `BACKEND_CODE_PATH` points directly to `backend/src/novascan`. If `PythonFunction` uses this as the entry path, it lacks visibility into the parent `backend/` directory where `pyproject.toml` and `uv.lock` actually reside.
3. **No Native `uv.lock` Support**: The alpha construct does not natively recognize `uv.lock` dependencies.

**Required Course Correction for Issue 2:**
Do not pull in `aws-cdk.aws-lambda-python-alpha`. Keep `lambda_.Function` and `Code.from_asset`, but inject a custom `bundling` configuration (`cdk.BundlingOptions`) that explicitly uses the `ghcr.io/astral-sh/uv` Docker image to install dependencies directly into the CDK `/asset-output` directory, or use a local build wrapper script before triggering `cdk synth`.

### AI:
Agreed — the feedback on Issue 2 is correct on all three points. `PythonFunction` alpha uses pip/poetry internally, doesn't understand `uv.lock`, and would need the entry path to contain `pyproject.toml` which ours doesn't (it's at `backend/`, not `backend/src/novascan/`).

**Revised Issue 2 plan:** Keep `lambda_.Function` + `Code.from_asset`, point it at `backend/` (where `pyproject.toml` and `uv.lock` live), and add `bundling=cdk.BundlingOptions(...)` with the `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` image. The bundling commands:
1. `uv export --frozen --no-dev --no-editable -o requirements.txt` — deterministic export from lockfile
2. `uv pip install --no-cache -r requirements.txt --target /asset-output` — install deps into output
3. `cp -au src/novascan/. /asset-output/` — copy app source alongside deps

No new infra dependencies needed. Plan above has been updated in-place.

### AI — Fix Results:

All 7 issues fixed. Verification passed (`cdk synth`, `npm run build`, `ruff check`).

**Issue 1 (CORS origins) — Fixed**
- `ApiConstruct` now accepts `allowed_origins: list[str]` parameter
- `novascan_stack.py`: reordered `FrontendConstruct` before `ApiConstruct`, passes `f"https://{self.frontend.domain_name}"`
- Verified in synthesized template: `AllowOrigins` resolves to `Fn::Join ["https://", Fn::GetAtt [CloudFront, DomainName]]`
- Files: `infra/cdkconstructs/api.py`, `infra/stacks/novascan_stack.py`

**Issue 2 (Lambda bundling) — Fixed**
- Kept `lambda_.Function` + `Code.from_asset` — no alpha dependency added
- `BACKEND_CODE_PATH` → `BACKEND_DIR`, now points to `backend/` (where `pyproject.toml` and `uv.lock` live)
- Added `_UvLocalBundling` class (`@jsii.implements(cdk.ILocalBundling)`) for local bundling via host `uv`
- Docker fallback via `ghcr.io/astral-sh/uv:python3.13-bookworm-slim` for CI environments
- Both paths: export deps → install to target → copy source, excluding `auth/` and `__pycache__/`
- Verified: bundled asset contains `pydantic`, `aws_lambda_powertools`, `api/app.py`, no `auth/`
- Files: `infra/cdkconstructs/api.py`

**Issue 3 (Redundant property) — Fixed**
- Removed `@property function` accessor. Grep confirmed nothing references it.
- Files: `infra/cdkconstructs/api.py`

**Issue 4 (isLoading flash) — Fixed**
- Destructures `isLoading` from `useAuth()`, returns `null` while loading before the auth check
- Files: `frontend/src/pages/LoginPage.tsx`

**Issue 5 (Imperative navigate) — Fixed**
- Replaced `navigate("/", { replace: true })` during render with `<Navigate to="/" replace />`
- `useNavigate` retained for post-OTP redirect inside event handler (correct usage)
- Files: `frontend/src/pages/LoginPage.tsx`

**Issue 6 (Fragile network error) — Fixed**
- Replaced `.includes("network")/...` chain with `err instanceof TypeError && err.message === "Failed to fetch"`
- Files: `frontend/src/pages/LoginPage.tsx`

**Issue 7 (OTP maxLength) — Fixed**
- Added `maxLength={6}` and `pattern="[0-9]{6}"` to OTP input
- Files: `frontend/src/pages/LoginPage.tsx`

**Verification results:**
- `cd infra && uv run cdk synth --context stage=dev` — PASS
- `cd frontend && npm run build` — PASS
- `uvx ruff check cdkconstructs/api.py stacks/novascan_stack.py` — PASS
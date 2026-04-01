# Implementation Plan

---

## Prerequisites

#### [x] Task 0.1: Development Environment Verification
- **Role:** senior-engineer
- **Depends on:** none
- **Spec reference:** SPEC.md >> Section 9 (Development Environment Setup)
- **Files:** none (verification only)
- **Acceptance criteria:**
  - `uv --version` returns a version (uv is installed and available)
  - `uv python list` shows Python 3.13+ available
  - `uv venv --python 3.13` creates a virtual environment successfully (verify in a temp directory, then clean up)
  - `node --version` returns v22.x (Node.js 22 LTS)
  - `aws sts get-caller-identity` returns the expected AWS account ID
  - `aws configure get region` returns the target region (or `AWS_DEFAULT_REGION` / `AWS_REGION` env var is set)
  - AWS CLI profile is configured (either default or via `AWS_PROFILE` env var)
  - `docker --version` returns a version (needed for DynamoDB Local in tests)
  - Document the verified AWS account ID, region, Python version, and profile name in `workflow/plan/PROGRESS.md` under a new "Environment" section
- **Test: inline** — command outputs are the verification
- **Test command:** `uv --version && uv python list --python-preference only-managed | head -5 && node --version && aws sts get-caller-identity --query Account --output text && echo "PASS"`

---

## Milestone 1: Foundation & Authentication

### Wave 1: Project Scaffolding

#### [x] Task 1.1: CDK Project Scaffolding
- **Role:** devops-engineer
- **Depends on:** none
- **Spec reference:** SPEC.md >> Section 9 (Development Environment Setup), Section 3 (Architecture)
- **Files:**
  - `infra/pyproject.toml` (create)
  - `infra/cdk.json` (create — with `context.config.dev` and `context.config.prod` settings)
  - `infra/app.py` (create — CDK app entry point, reads stage from context)
  - `infra/stacks/__init__.py` (create)
  - `infra/stacks/novascan_stack.py` (create — main stack with stub imports for all 5 constructs: storage, auth, api, pipeline, frontend)
  - `infra/cdkconstructs/__init__.py` (create)
  - `infra/cdkconstructs/storage.py` (create — empty construct stub)
  - `infra/cdkconstructs/auth.py` (create — empty construct stub)
  - `infra/cdkconstructs/api.py` (create — empty construct stub)
  - `infra/cdkconstructs/pipeline.py` (create — empty construct stub)
  - `infra/cdkconstructs/frontend.py` (create — empty construct stub)
- **Acceptance criteria:**
  - `cd infra && uv sync` installs dependencies without errors
  - `cd infra && uv run cdk synth --context stage=dev` produces a valid (empty) CloudFormation template without errors
  - `cdk.json` contains all 6 config keys for both dev and prod stages (`pipelineMaxConcurrency`, `presignedUrlExpirySec`, `maxUploadFiles`, `maxUploadSizeMb`, `logLevel`, `defaultPipeline`)
  - Stack file imports all 5 construct stubs without import errors
- **Test: inline** — `cdk synth` is the verification
- **Test command:** `cd infra && uv run cdk synth --context stage=dev > /dev/null && echo "PASS"`

#### [x] Task 1.2: Backend Project Scaffolding
- **Role:** backend-engineer
- **Depends on:** none
- **Spec reference:** SPEC.md >> Section 9 (Project Structure, Key Dependencies)
- **Files:**
  - `backend/pyproject.toml` (create — aws-lambda-powertools, pydantic, boto3, python-ulid, pandas; dev: pytest, moto, ruff, mypy)
  - `backend/src/novascan/__init__.py` (create)
  - `backend/src/novascan/api/__init__.py` (create)
  - `backend/src/novascan/pipeline/__init__.py` (create)
  - `backend/src/novascan/models/__init__.py` (create)
  - `backend/src/novascan/shared/__init__.py` (create)
  - `backend/src/novascan/shared/dynamo.py` (create — DynamoDB client helper, table name from env var)
  - `backend/src/novascan/shared/constants.py` (create — entity type constants: PROFILE, RECEIPT, ITEM, PIPELINE, CUSTOMCAT)
  - `backend/tests/__init__.py` (create)
  - `backend/tests/conftest.py` (create — pytest fixtures, moto setup)
  - `backend/tests/unit/__init__.py` (create)
  - `backend/tests/integration/__init__.py` (create)
- **Acceptance criteria:**
  - `cd backend && uv sync` installs all dependencies
  - `cd backend && uv run python -c "from novascan.shared.dynamo import get_table; from novascan.shared.constants import RECEIPT"` succeeds
  - `cd backend && uv run ruff check src/` passes with no errors
  - `cd backend && uv run pytest` runs (0 tests collected, no errors)
- **Test: inline** — import verification and linter pass
- **Test command:** `cd backend && uv sync && uv run ruff check src/ && uv run pytest`

#### [x] Task 1.3: Frontend Project Scaffolding
- **Role:** frontend-developer
- **Depends on:** none
- **Spec reference:** SPEC.md >> Section 9 (Project Structure, Key Dependencies)
- **Files:**
  - `frontend/package.json` (create)
  - `frontend/tsconfig.json` (create)
  - `frontend/tsconfig.app.json` (create)
  - `frontend/tsconfig.node.json` (create)
  - `frontend/vite.config.ts` (create)
  - `frontend/index.html` (create)
  - `frontend/postcss.config.js` (create)
  - `frontend/eslint.config.js` (create)
  - `frontend/src/main.tsx` (create)
  - `frontend/src/App.tsx` (create — React Router setup with route placeholders)
  - `frontend/src/index.css` (create — Tailwind CSS v4 imports)
  - `frontend/src/lib/utils.ts` (create — `cn()` helper)
  - `frontend/src/types/index.ts` (create — shared TypeScript types)
  - `frontend/components.json` (create — shadcn/ui config)
- **Acceptance criteria:**
  - `package.json` includes `msw` as a dev dependency (API mocking for tests, per SPEC Section 9)
  - `cd frontend && npm install` completes without errors
  - `cd frontend && npm run build` produces a valid build in `dist/`
  - `cd frontend && npm run dev` starts dev server and renders a page
  - Tailwind CSS v4 processes utility classes (visible in built CSS)
  - shadcn/ui CLI can add components: `npx shadcn@latest add button` succeeds
- **Test: inline** — build verification
- **Test command:** `cd frontend && npm install && npm run build`

---

### Wave 2: Core Infrastructure + Frontend Auth

#### [x] Task 1.4: Storage Construct — DynamoDB + S3 Frontend Bucket
- **Role:** devops-engineer
- **Depends on:** 1.1
- **Spec reference:** SPEC.md >> Section 5 (Database Schema)
- **Files:**
  - `infra/cdkconstructs/storage.py` (modify — implement DynamoDB table + GSI1 + S3 frontend bucket)
- **Acceptance criteria:**
  - `cdk synth` produces a template containing a DynamoDB table named `novascan-{stage}` with:
    - Partition key `PK` (S), sort key `SK` (S)
    - GSI1 with `GSI1PK` (S) and `GSI1SK` (S), projection ALL
    - Billing mode PAY_PER_REQUEST
    - Point-in-time recovery enabled
    - Deletion protection enabled for prod, disabled for dev
  - Template contains an S3 bucket for frontend assets with `BlockPublicAccess` enabled
  - Storage construct exports table name, table ARN, and frontend bucket references for other constructs
- **Test command:** `cd infra && uv run cdk synth --context stage=dev | python -c "import sys,json; t=json.load(sys.stdin); resources=[v for v in t['Resources'].values()]; dynamo=[r for r in resources if r['Type']=='AWS::DynamoDB::Table']; assert len(dynamo)==1, 'Expected 1 DynamoDB table'; print('PASS')"`

#### [x] Task 1.5: Auth Construct + Cognito Lambda Triggers
- **Role:** backend-engineer
- **Depends on:** 1.1, 1.2
- **Spec reference:** SPEC.md >> Section 3 (Auth Flow, RBAC)
- **Files:**
  - `infra/cdkconstructs/auth.py` (modify — Cognito User Pool, App Client, three groups, Pre-Sign-Up + Post-Confirmation Lambda triggers)
  - `backend/src/novascan/auth/__init__.py` (create)
  - `backend/src/novascan/auth/pre_signup.py` (create — auto-confirm, auto-verify email only)
  - `backend/src/novascan/auth/post_confirmation.py` (create — add user to `user` Cognito group via `admin_add_user_to_group`)
- **Acceptance criteria:**
  - `cdk synth` produces template with:
    - Cognito User Pool with email-only sign-in, USER_AUTH flow enabled
    - App Client with `ALLOW_USER_AUTH` and `ALLOW_REFRESH_TOKEN_AUTH` explicit auth flows
    - Three Cognito Groups: `user` (precedence 2), `staff` (precedence 1), `admin` (precedence 0)
    - Pre-Sign-Up Lambda trigger configured on the User Pool
    - Post-Confirmation Lambda trigger configured on the User Pool
  - Pre-Sign-Up Lambda: sets `autoConfirmUser=True` and `autoVerifyEmail=True` (flags only — cannot call Cognito APIs because user doesn't exist yet)
  - Post-Confirmation Lambda: calls `admin_add_user_to_group` to add user to `user` group (user exists at this point)
  - **Verify assumption:** Confirm Post-Confirmation trigger fires after user creation and that `admin_add_user_to_group` works within it. If not, document the deviation and adjust.
  - Auth construct exports User Pool ID, User Pool ARN, and App Client ID for other constructs
- **Test command:** `cd infra && uv run cdk synth --context stage=dev | python -c "import sys,json; t=json.load(sys.stdin); r=t['Resources']; pools=[v for v in r.values() if v['Type']=='AWS::Cognito::UserPool']; assert len(pools)==1; groups=[v for v in r.values() if v['Type']=='AWS::Cognito::UserPoolGroup']; assert len(groups)==3; print('PASS')"`

#### [x] Task 1.6: Frontend Auth Module
- **Role:** frontend-developer
- **Depends on:** 1.3
- **Spec reference:** SPEC.md >> Section 3 (Auth Flow)
- **Files:**
  - `frontend/src/lib/auth.ts` (create — Cognito SDK wrapper: initiateAuth, signUp, respondToChallenge, refreshTokens, signOut)
  - `frontend/src/hooks/useAuth.ts` (create — auth context provider, token state, isAuthenticated, user info)
  - `frontend/src/types/auth.ts` (create — AuthState, AuthUser types)
- **Acceptance criteria:**
  - Auth module uses `@aws-sdk/client-cognito-identity-provider` directly (no Amplify)
  - `initiateAuth` handles USER_AUTH flow; catches `UserNotFoundException` and triggers signup+retry flow
  - `respondToChallenge` handles EMAIL_OTP challenge type
  - Token storage: access/ID tokens in memory, refresh token in localStorage
  - `useAuth` hook provides: `isAuthenticated`, `user` (with userId, email, roles), `signIn`, `signOut`, `isLoading`
  - Roles extracted from `cognito:groups` claim in ID token
  - `cd frontend && npm run build` succeeds with no TypeScript errors
- **Test command:** `cd frontend && npx tsc --noEmit`

---

### Wave 3: Serving Constructs + Login Page

#### [x] Task 1.7: API + Frontend CDK Constructs
- **Role:** devops-engineer
- **Depends on:** 1.2, 1.4, 1.5
- **Spec reference:** SPEC.md >> Section 3 (Component Overview), Section 13 (Deployment Architecture, CORS)
- **Files:**
  - `infra/cdkconstructs/api.py` (modify — API Gateway HTTP API, Cognito authorizer, API Lambda, CORS config)
  - `infra/cdkconstructs/frontend.py` (modify — CloudFront distribution, S3 origin, SPA error routing)
  - `backend/src/novascan/api/app.py` (create — Lambda Powertools resolver, health check `/api/health` endpoint)
- **Acceptance criteria:**
  - `cdk synth` produces template with:
    - API Gateway HTTP API with Cognito JWT authorizer
    - API Lambda function with Powertools handler
    - CORS configured: allowed methods GET/POST/PUT/DELETE/OPTIONS, allowed headers Authorization/Content-Type
    - CloudFront distribution with S3 origin and custom error responses (403→/index.html 200, 404→/index.html 200)
  - API Lambda has environment variables: `TABLE_NAME`, `LOG_LEVEL`, `STAGE`
  - Health check endpoint responds without auth (excluded from authorizer)
  - CDK stack outputs: API URL, CloudFront domain, User Pool ID, App Client ID
- **Test command:** `cd infra && uv run cdk synth --context stage=dev | python -c "import sys,json; t=json.load(sys.stdin); r=t['Resources']; apis=[v for v in r.values() if v['Type']=='AWS::ApiGatewayV2::Api']; cfs=[v for v in r.values() if v['Type']=='AWS::CloudFront::Distribution']; assert len(apis)==1 and len(cfs)==1; print('PASS')"`

#### [x] Task 1.8: Login Page UI
- **Role:** frontend-developer
- **Depends on:** 1.6
- **Spec reference:** SPEC.md >> Section 3 (Auth Flow)
- **Files:**
  - `frontend/src/pages/LoginPage.tsx` (create — email input → OTP input → redirect)
  - `frontend/src/components/ui/input.tsx` (create via shadcn — if not already present)
  - `frontend/src/components/ui/button.tsx` (create via shadcn — if not already present)
- **Acceptance criteria:**
  - Login page shows email input field with submit button
  - After email submission, UI transitions to OTP input field
  - Error states shown for: invalid email, incorrect OTP, network failure
  - Loading spinner during auth API calls
  - On successful auth, redirects to dashboard route
  - Unauthenticated users visiting any protected route are redirected to login
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 4: App Shell + CDK Tests

#### [x] Task 1.9: App Shell — Navigation + Protected Routes
- **Role:** frontend-developer
- **Depends on:** 1.8
- **Spec reference:** SPEC.md >> Milestone 1 Acceptance Criteria
- **Files:**
  - `frontend/src/components/AppShell.tsx` (create — layout wrapper with navigation)
  - `frontend/src/components/ProtectedRoute.tsx` (create — redirects to login if unauthenticated)
  - `frontend/src/pages/DashboardPage.tsx` (create — empty dashboard shell placeholder)
  - `frontend/src/pages/ReceiptsPage.tsx` (create — empty placeholder)
  - `frontend/src/pages/TransactionsPage.tsx` (create — empty placeholder)
  - `frontend/src/pages/AnalyticsPage.tsx` (create — empty placeholder)
  - `frontend/src/pages/ScanPage.tsx` (create — empty placeholder)
  - `frontend/src/App.tsx` (modify — wire up routes with AppShell and ProtectedRoute)
- **Acceptance criteria:**
  - Navigation shows 5 items: Home (dashboard), Scan, Analytics, Transactions, Receipts
  - Mobile (< 768px): bottom navigation bar
  - Desktop (>= 768px): sidebar navigation
  - All routes except `/login` are wrapped in `ProtectedRoute`
  - Sign out button in navigation
  - Active route is visually highlighted in navigation
  - Empty placeholder pages render without errors for all routes
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

#### [x] Task 1.10: CDK Infrastructure Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 1.4, 1.5, 1.7
- **Spec reference:** SPEC.md >> Section 5 (Database Schema), Section 3 (Auth Flow, Architecture)
- **Files:**
  - `infra/tests/__init__.py` (create)
  - `infra/tests/test_storage_construct.py` (create)
  - `infra/tests/test_auth_construct.py` (create)
  - `infra/tests/test_api_construct.py` (create)
  - `infra/tests/test_frontend_construct.py` (create)
  - `infra/tests/test_stack.py` (create — full stack snapshot test)
- **Test scope:** Tests CDK construct outputs against spec requirements. Do NOT read implementation.
- **Acceptance criteria:**
  - Storage tests verify: DynamoDB table key schema (PK/SK), GSI1 key schema, billing mode, PITR enabled
  - Auth tests verify: User Pool exists, 3 groups created, Pre-Sign-Up Lambda trigger attached, App Client auth flows
  - API tests verify: HTTP API exists, Cognito authorizer attached, Lambda function exists, CORS config
  - Frontend tests verify: CloudFront distribution exists, S3 origin, error responses for SPA routing
  - Stack test: snapshot test of full synthesized template
  - `cd infra && uv run pytest` passes all tests
- **Test command:** `cd infra && uv run pytest -v`

#### [x] Task 1.11: Frontend Auth + UI Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 1.6, 1.8, 1.9
- **Spec reference:** SPEC.md >> Section 3 (Auth Flow), Milestone 1 Acceptance Criteria
- **Files:**
  - `frontend/src/lib/__tests__/auth.test.ts` (create)
  - `frontend/src/hooks/__tests__/useAuth.test.tsx` (create)
  - `frontend/src/pages/__tests__/LoginPage.test.tsx` (create)
  - `frontend/src/components/__tests__/AppShell.test.tsx` (create)
  - `frontend/src/components/__tests__/ProtectedRoute.test.tsx` (create)
  - `frontend/vitest.config.ts` (create or modify — test setup)
  - `frontend/src/test/setup.ts` (create — test setup with jsdom)
- **Test scope:** Tests auth flow logic, component rendering, and routing behavior. Do NOT read implementation.
- **Acceptance criteria:**
  - Auth module tests: signIn flow (happy path), UserNotFoundException → signup → retry, OTP challenge response, token storage, signOut clears tokens
  - Login page tests: renders email input, transitions to OTP after submit, shows error on failure, redirects on success
  - App shell tests: renders navigation items, active route highlighting, responsive layout detection
  - Protected route tests: redirects unauthenticated users, renders children for authenticated users
  - `cd frontend && npm run test` passes all tests
- **Test command:** `cd frontend && npm run test -- --run`

---

### Wave 5: Integration Verification

#### [x] Task 1.12: Dev Stack Deployment + E2E Smoke Test
- **Role:** devops-engineer
- **Depends on:** 1.7, 1.9, 1.10
- **Spec reference:** SPEC.md >> Milestone 1 Acceptance Criteria
- **Files:**
  - `workflow/plan/PROGRESS.md` (modify — update M1 task statuses)
- **Acceptance criteria:**
  - `cd infra && uv run cdk deploy --context stage=dev` completes without errors
  - All CDK stack outputs are emitted (API URL, CloudFront domain, User Pool ID, App Client ID)
  - Frontend built with stack output values and uploaded to S3
  - CloudFront URL loads the frontend SPA
  - `/api/health` returns 200
  - Unauthenticated API requests return 401
  - Sign up → sign in → see empty dashboard → sign out flow works
  - `cdk destroy --context stage=dev` tears down cleanly
- **Test command:** `cd infra && uv run cdk deploy --context stage=dev && echo "DEPLOY PASS"`

---

## Milestone 2: Receipt Upload & Storage

### Wave 1: Backend Models + Upload UI

#### [x] Task 2.1: Receipts S3 Bucket + Pydantic Models
- **Role:** backend-engineer
- **Depends on:** none (M1 complete)
- **Spec reference:** SPEC.md >> Section 5 (Receipt Attributes, Line Item Attributes), api-contracts.md >> POST /api/receipts/upload-urls
- **Files:**
  - `infra/cdkconstructs/storage.py` (modify — add receipts S3 bucket: private, SSE-S3, BlockPublicAccess, versioning)
  - `backend/src/novascan/models/receipt.py` (create — Receipt, UploadRequest, UploadResponse, ReceiptListResponse Pydantic models)
- **Acceptance criteria:**
  - `cdk synth` includes a second S3 bucket with: SSE-S3, BlockPublicAccess, versioning enabled
  - Receipts bucket created without event notification (S3 notifications require a destination; SQS queue created in M3 Task 3.5, which configures the notification)
  - Pydantic models match api-contracts.md field definitions exactly
  - `UploadRequest` validates: 1-10 files, contentType in [image/jpeg, image/png], fileSize 1-10485760
  - `cd backend && uv run ruff check src/ && uv run mypy src/` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run python -c "from novascan.models.receipt import Receipt, UploadRequest; print('PASS')"`

#### [x] Task 2.2: Upload UI Components
- **Role:** frontend-developer
- **Depends on:** none (M1 complete)
- **Spec reference:** SPEC.md >> Section 3 (Upload Flow), Milestone 2 Acceptance Criteria
- **Files:**
  - `frontend/src/components/UploadArea.tsx` (create — camera capture button, file picker, drag-and-drop zone)
  - `frontend/src/components/UploadProgress.tsx` (create — per-file progress indicators, status badges)
  - `frontend/src/components/UploadSummary.tsx` (create — success/failure count, retry option for failed files)
  - `frontend/src/types/receipt.ts` (create — Receipt, UploadFile TypeScript types)
- **Acceptance criteria:**
  - Camera capture via `<input type="file" accept="image/jpeg,image/png" capture="environment">`
  - File picker for single and multi-file selection (up to 10)
  - Client-side validation: reject non-JPEG/PNG, reject files > 10 MB
  - Per-file progress bar with status (uploading, success, failed)
  - Upload summary shows "{N} of {M} receipts uploaded" with retry button for failures
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 2: API Endpoints

#### [ ] Task 2.3: Upload URLs API Endpoint
- **Role:** backend-engineer
- **Depends on:** 2.1
- **Spec reference:** api-contracts.md >> POST /api/receipts/upload-urls
- **Files:**
  - `backend/src/novascan/api/upload.py` (create — POST /api/receipts/upload-urls handler)
  - `backend/src/novascan/api/app.py` (modify — register upload router)
- **Acceptance criteria:**
  - Generates ULID for each receipt
  - Creates DynamoDB receipt records with status `processing`, `imageKey`, `createdAt`
  - Sets `GSI1PK = USER#{userId}` and `GSI1SK = {createdAt}#{ulid}` on receipt records (using `createdAt` as fallback since `receiptDate` is not yet extracted). Pipeline Finalize Lambda (Task 3.4) updates `GSI1SK` to `{receiptDate}#{ulid}` after OCR extraction.
  - Generates presigned S3 PUT URLs with `presignedUrlExpirySec` from env (default 900)
  - Returns 201 with `receipts` array containing `receiptId`, `uploadUrl`, `imageKey`, `expiresIn`
  - Validates request body via Pydantic: rejects >10 files, invalid contentType, invalid fileSize
  - All DynamoDB records scoped to `PK = USER#{userId}` from JWT `sub` claim
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/`

#### [ ] Task 2.4: List Receipts API Endpoint
- **Role:** backend-engineer
- **Depends on:** 2.1
- **Spec reference:** api-contracts.md >> GET /api/receipts
- **Files:**
  - `backend/src/novascan/api/receipts.py` (create — GET /api/receipts handler)
  - `backend/src/novascan/api/app.py` (modify — register receipts router)
- **Acceptance criteria:**
  - Queries GSI1 (`GSI1PK = USER#{userId}`) for receipt listing, sorted by date descending
  - Supports query params: `status`, `category`, `startDate`, `endDate`, `limit` (1-100, default 50), `cursor`
  - Status and category applied as FilterExpression on GSI1 results
  - Date range applied as KeyConditionExpression on GSI1SK: `GSI1SK BETWEEN '{startDate}' AND '{endDate}~'` (trailing `~` ensures all ULIDs on the end date are included, per SPEC line 662)
  - Returns presigned GET URLs for receipt images (1-hour expiry)
  - Cursor-based pagination using DynamoDB `ExclusiveStartKey`/`LastEvaluatedKey`
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/`

---

### Wave 3: Frontend Integration

#### [ ] Task 2.5: Upload Flow Integration
- **Role:** frontend-developer
- **Depends on:** 2.2, 2.3
- **Spec reference:** SPEC.md >> Section 3 (Upload Flow)
- **Files:**
  - `frontend/src/api/receipts.ts` (create — API client functions for receipt endpoints)
  - `frontend/src/hooks/useUpload.ts` (create — upload flow orchestration hook)
  - `frontend/src/pages/ScanPage.tsx` (modify — integrate UploadArea + upload flow)
- **Acceptance criteria:**
  - Upload flow: request presigned URLs → parallel PUT to S3 → show summary
  - Failed uploads retry up to 3 times with exponential backoff (1s, 2s, 4s)
  - If presigned URL expires during retry, requests a new URL for the failed file
  - Upload state transitions: idle → uploading → complete (with per-file status)
  - After upload completes, navigates to receipts list or shows confirmation
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

#### [ ] Task 2.6: Receipts List Page
- **Role:** frontend-developer
- **Depends on:** 2.2, 2.4
- **Spec reference:** Milestone 2 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/ReceiptsPage.tsx` (modify — receipt list with cards/table)
  - `frontend/src/components/ReceiptCard.tsx` (create — receipt summary card with status badge)
  - `frontend/src/hooks/useReceipts.ts` (create — TanStack Query hook for receipts list)
- **Acceptance criteria:**
  - Displays receipt list with: merchant name, date, total, category, status badge
  - Status badges: Processing (yellow), Confirmed (green), Failed (red)
  - Receipts with status `processing` show placeholder values for merchant/total
  - Pagination via "Load More" button using cursor
  - Receipt card links to receipt detail page (placeholder route for M4)
  - TanStack Query manages server state with stale-while-revalidate
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 4: Tests

#### [ ] Task 2.7: Receipt Upload + Storage API Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 2.3, 2.4
- **Spec reference:** api-contracts.md >> POST /api/receipts/upload-urls, GET /api/receipts
- **Files:**
  - `backend/tests/unit/test_upload.py` (create)
  - `backend/tests/unit/test_receipts_list.py` (create)
  - `backend/tests/unit/test_receipt_models.py` (create)
- **Test scope:** Tests API contract for upload-urls and list-receipts endpoints. Do NOT read implementation.
- **Acceptance criteria:**
  - Upload tests: valid request creates receipts and returns presigned URLs, rejects >10 files, rejects invalid contentType, rejects oversized files, each receipt gets unique ULID, DynamoDB records created with correct PK/SK/status
  - List tests: returns user's receipts sorted by date desc, pagination with cursor, filters by status/category/date range, does not return other users' receipts
  - Model tests: Pydantic validation accepts valid data, rejects invalid
  - `cd backend && uv run pytest tests/unit/test_upload.py tests/unit/test_receipts_list.py tests/unit/test_receipt_models.py -v` passes
- **Test command:** `cd backend && uv run pytest tests/unit/ -v`

#### [ ] Task 2.8: Upload + Receipts List UI Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 2.5, 2.6
- **Spec reference:** SPEC.md >> Milestone 2 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/__tests__/ScanPage.test.tsx` (create)
  - `frontend/src/pages/__tests__/ReceiptsPage.test.tsx` (create)
  - `frontend/src/components/__tests__/UploadArea.test.tsx` (create)
  - `frontend/src/hooks/__tests__/useUpload.test.ts` (create)
- **Test scope:** Tests upload flow, retry logic, validation, and receipt list rendering. Do NOT read implementation.
- **Acceptance criteria:**
  - Upload area tests: accepts JPEG/PNG, rejects other types, rejects >10 MB, limits to 10 files
  - Upload flow tests: calls upload-urls API, uploads to presigned URLs, retries on failure with backoff, requests new URL on expiry
  - Receipts page tests: renders receipt cards, shows correct status badges, pagination works
  - `cd frontend && npm run test -- --run` passes
- **Test command:** `cd frontend && npm run test -- --run`

---

## Milestone 3: OCR Processing Pipeline

### Wave 1: Extraction Schema

#### [ ] Task 3.1: Receipt Extraction Schema
- **Role:** backend-engineer
- **Depends on:** none (M2 complete)
- **Spec reference:** SPEC.md >> Section 7 (Receipt Extraction Schema)
- **Files:**
  - `backend/src/novascan/models/extraction.py` (create — ExtractionResult Pydantic model matching Section 7 schema)
- **Acceptance criteria:**
  - Pydantic model includes: merchant (name, address, phone), receiptDate, currency, lineItems (name, quantity, unitPrice, totalPrice, subcategory), subtotal, tax, tip, total, category, subcategory, paymentMethod, confidence
  - All monetary fields are `Decimal` or `float`
  - `lineItems[].subcategory` is optional (nullable)
  - `confidence` is float 0.0–1.0
  - `currency` defaults to `"USD"`
  - Model can serialize to/from JSON matching the exact schema in SPEC Section 7
  - `cd backend && uv run ruff check src/ && uv run mypy src/` passes
- **Test command:** `cd backend && uv run python -c "from novascan.models.extraction import ExtractionResult; print('PASS')"`

---

### Wave 2: Pipeline Lambdas

#### [ ] Task 3.2: OCR-AI Pipeline Lambdas (Textract + Nova)
- **Role:** backend-engineer
- **Depends on:** 3.1
- **Spec reference:** SPEC.md >> Section 3 (Processing Flow — Main pipeline)
- **Files:**
  - `backend/src/novascan/pipeline/textract_extract.py` (create — calls Textract AnalyzeExpense sync, returns raw output)
  - `backend/src/novascan/pipeline/nova_structure.py` (create — takes Textract output + image + taxonomy, calls Bedrock Nova, returns ExtractionResult JSON)
  - `backend/src/novascan/pipeline/prompts.py` (create — structured JSON extraction prompt template with taxonomy placeholder)
- **Acceptance criteria:**
  - `textract_extract` Lambda handler: receives S3 bucket/key, calls `analyze_expense` (sync), returns raw Textract `ExpenseDocuments` output
  - `nova_structure` Lambda handler: receives Textract output + image S3 ref + predefined taxonomy + custom categories, constructs a Bedrock prompt, calls `invoke_model` with Nova, parses response into ExtractionResult schema
  - Prompt template includes: full category taxonomy, custom categories (if any), extraction instructions, output schema
  - Both handlers use Lambda Powertools Logger and Tracer
  - Error handling: exceptions caught and returned as error payload (not raised), enabling Step Functions Catch
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run python -c "from novascan.pipeline.textract_extract import handler; from novascan.pipeline.nova_structure import handler; print('PASS')"`

#### [ ] Task 3.3: AI-Multimodal Pipeline Lambda (Bedrock Extract)
- **Role:** backend-engineer
- **Depends on:** 3.1
- **Spec reference:** SPEC.md >> Section 3 (Processing Flow — Shadow pipeline)
- **Files:**
  - `backend/src/novascan/pipeline/bedrock_extract.py` (create — sends image to Bedrock Nova multimodal, returns ExtractionResult JSON)
- **Acceptance criteria:**
  - Lambda handler: receives image S3 ref + predefined taxonomy + custom categories, reads image from S3, constructs multimodal Bedrock prompt with image + taxonomy, calls `invoke_model`, parses response into ExtractionResult schema
  - Uses same prompt template from `prompts.py` (taxonomy + extraction instructions)
  - Uses Lambda Powertools Logger and Tracer
  - Error handling: exceptions caught and returned as error payload
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run python -c "from novascan.pipeline.bedrock_extract import handler; print('PASS')"`

#### [ ] Task 3.4: Finalize Lambda + LoadCustomCategories Lambda
- **Role:** backend-engineer
- **Depends on:** 3.1
- **Spec reference:** SPEC.md >> Section 3 (Processing Flow — Finalize), Section 4 (Pipeline State Machine diagram — LoadCustomCategories step)
- **Files:**
  - `backend/src/novascan/pipeline/finalize.py` (create — main/shadow logic, ranking, DDB update, S3 metadata)
  - `backend/src/novascan/pipeline/ranking.py` (create — `rank_results` function: confidence, field completeness, line item count, total consistency)
  - `backend/src/novascan/pipeline/load_custom_categories.py` (create — queries user's `CUSTOMCAT#` entities from DynamoDB, returns merged taxonomy for pipeline prompts)
- **Acceptance criteria:**
  - Main/shadow selection: if main succeeded → use main; if main failed + shadow succeeded → use shadow with `usedFallback: true`; if both failed → status `failed`
  - `defaultPipeline` env var determines which pipeline is "main" (default: `ocr-ai`)
  - `rank_results` computes composite `rankingScore` (0–1) for each pipeline based on: confidence, field completeness (fraction of non-null fields), line item count, total consistency (do line items sum to subtotal/total?)
  - Sets `rankingWinner` on receipt to whichever pipeline scored higher
  - Stores both pipeline results as `PIPELINE#ocr-ai` and `PIPELINE#ai-multimodal` DynamoDB records with `rankingScore`, `processingTimeMs`, `modelId`
  - Updates receipt record: extracted data (merchant, total, line items, category, etc.), status, `usedFallback`, `rankingWinner`
  - Updates `GSI1SK` from `{createdAt}#{ulid}` to `{receiptDate}#{ulid}` if `receiptDate` was extracted (keeps `createdAt` fallback if OCR didn't extract a date)
  - Creates line item records as `RECEIPT#{ulid}#ITEM#{nnn}` entities
  - `load_custom_categories` Lambda handler: receives `userId` from Step Functions input, queries `PK=USER#{userId}` with `SK begins_with CUSTOMCAT#`, returns list of custom categories merged with predefined taxonomy (used by pipeline Lambdas in their prompts)
  - Updates S3 object metadata: `x-amz-meta-status`, `x-amz-meta-receipt-id`, `x-amz-meta-processed-at`
  - Publishes CloudWatch metrics: `PipelineCompleted`, `PipelineLatency`, `RankingDecision`, `RankingScoreDelta`, `ReceiptStatus`, `UsedFallback`
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/ && uv run python -c "from novascan.pipeline.finalize import handler; from novascan.pipeline.ranking import rank_results; print('PASS')"`

---

### Wave 3: Pipeline CDK Construct

#### [ ] Task 3.5: Pipeline CDK Construct — SQS + EventBridge Pipes + Step Functions
- **Role:** devops-engineer
- **Depends on:** 3.2, 3.3, 3.4
- **Spec reference:** SPEC.md >> Section 3 (Processing Flow, Pipeline State Machine diagram)
- **Files:**
  - `infra/cdkconstructs/pipeline.py` (modify — SQS queue, EventBridge Pipes, Step Functions state machine, Lambda functions, IAM roles)
- **Acceptance criteria:**
  - Configures S3 event notification on receipts bucket for `ObjectCreated` events on `receipts/` prefix → SQS queue (this notification is configured here, not in the storage construct, because the SQS destination must exist first)
  - SQS queue receives S3 `ObjectCreated` events from receipts bucket `receipts/` prefix
  - EventBridge Pipes: source=SQS, target=Step Functions, `MaximumConcurrency` from `pipelineMaxConcurrency` config. Note: uses L1 `CfnPipe` construct (no L2 exists for Pipes) — requires manual IAM role wiring.
  - **Verify assumption:** Confirm `CfnPipe` supports `MaximumConcurrency` as a top-level property. If CDK/CloudFormation doesn't yet support it, document the gap and use an alternative rate-limiting approach.
  - Step Functions state machine:
    - `LoadCustomCategories` step: Lambda queries user's `CUSTOMCAT#` entities from DynamoDB
    - Parallel state with two branches:
      - Main (OCR-AI): TextractExtract → NovaStructure, each with Catch → error payload
      - Shadow (AI-multimodal): BedrockExtract, with Catch → error payload
    - Finalize step: processes both results
  - Each pipeline Lambda has IAM permissions: DynamoDB read/write, S3 read, Textract (textract Lambda), Bedrock invoke (nova + bedrock Lambdas)
  - Finalize Lambda has: DynamoDB write, S3 write (copy_object for metadata), CloudWatch Metrics
  - `cdk synth` produces valid template with all resources
- **Test command:** `cd infra && uv run cdk synth --context stage=dev | python -c "import sys,json; t=json.load(sys.stdin); r=t['Resources']; sqs=[v for v in r.values() if v['Type']=='AWS::SQS::Queue']; sfn=[v for v in r.values() if v['Type']=='AWS::StepFunctions::StateMachine']; print(f'SQS: {len(sqs)}, SFN: {len(sfn)}'); assert len(sqs)>=1 and len(sfn)>=1; print('PASS')"`

---

### Wave 4: Tests

#### [ ] Task 3.6: Pipeline Lambda Unit Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 3.2, 3.3, 3.4
- **Spec reference:** SPEC.md >> Section 7 (Extraction Schema), Section 3 (Processing Flow)
- **Files:**
  - `backend/tests/unit/test_textract_extract.py` (create)
  - `backend/tests/unit/test_nova_structure.py` (create)
  - `backend/tests/unit/test_bedrock_extract.py` (create)
  - `backend/tests/unit/test_finalize.py` (create)
  - `backend/tests/unit/test_ranking.py` (create)
- **Test scope:** Tests Lambda handler logic with mocked AWS services. Do NOT read implementation.
- **Acceptance criteria:**
  - Textract extract tests: successful extraction, Textract API error returns error payload
  - Nova structure tests: valid Textract output → valid ExtractionResult, Bedrock error returns error payload
  - Bedrock extract tests: valid image → valid ExtractionResult, Bedrock error returns error payload
  - Finalize tests: main success → uses main, main fail + shadow success → uses shadow with fallback flag, both fail → status failed, ranking scores computed correctly, DynamoDB records created (receipt update, pipeline results, line items), S3 metadata updated
  - Ranking tests: perfect result scores near 1.0, empty result scores near 0.0, inconsistent totals reduce score
  - `cd backend && uv run pytest tests/unit/test_textract_extract.py tests/unit/test_nova_structure.py tests/unit/test_bedrock_extract.py tests/unit/test_finalize.py tests/unit/test_ranking.py -v` passes
- **Test command:** `cd backend && uv run pytest tests/unit/ -v -k "pipeline or textract or nova or bedrock or finalize or ranking"`

#### [ ] Task 3.7: Pipeline CDK + Integration Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 3.5
- **Spec reference:** SPEC.md >> Section 3 (Processing Flow)
- **Files:**
  - `infra/tests/test_pipeline_construct.py` (create)
  - `backend/tests/integration/test_pipeline_flow.py` (create)
- **Test scope:** Tests CDK construct structure and end-to-end pipeline data flow. Do NOT read implementation.
- **Acceptance criteria:**
  - CDK tests: SQS queue exists with correct event source, EventBridge Pipes configured with MaxConcurrency, Step Functions state machine has correct structure (LoadCustomCategories → Parallel → Finalize), Lambda functions have correct IAM permissions
  - Integration test: simulates pipeline flow with mocked Textract/Bedrock responses, verifies DynamoDB records created correctly (receipt updated, pipeline results stored, line items created)
  - `cd infra && uv run pytest tests/test_pipeline_construct.py -v` passes
  - `cd backend && uv run pytest tests/integration/ -v` passes
- **Test command:** `cd infra && uv run pytest tests/test_pipeline_construct.py -v && cd ../backend && uv run pytest tests/integration/ -v`

---

## Milestone 4: Receipt Management

### Wave 1: Backend Foundation

#### [ ] Task 4.1: Category Constants + Receipt CRUD Endpoints
- **Role:** backend-engineer
- **Depends on:** none (M3 complete)
- **Spec reference:** SPEC.md >> Section 8, api-contracts.md >> GET/PUT/DELETE receipts, PUT items
- **Files:**
  - `backend/src/novascan/models/category.py` (create — Category, Subcategory, CustomCategory Pydantic models)
  - `backend/src/novascan/shared/constants.py` (modify — add predefined category taxonomy dict from category-taxonomy.md)
  - `backend/src/novascan/api/receipts.py` (modify — add GET /{id}, PUT /{id}, DELETE /{id}, PUT /{id}/items)
- **Acceptance criteria:**
  - Category constants: all 13 predefined categories with their subcategories, slugs matching category-taxonomy.md exactly
  - `GET /api/receipts/{id}`: returns receipt with line items, presigned image URL, 404 if not found, 403 if wrong user
  - `PUT /api/receipts/{id}`: partial update (only provided fields), validates category/subcategory against taxonomy, returns full receipt, 404/400
  - `DELETE /api/receipts/{id}`: deletes all DynamoDB records (receipt + items + pipeline results via `begins_with RECEIPT#{ulid}` query + BatchWriteItem) AND S3 image, returns 204
  - `PUT /api/receipts/{id}/items`: bulk replaces line items (delete existing + insert new), validates 0-100 items, sortOrder/name/quantity/unitPrice/totalPrice required, subcategory optional, returns full receipt
  - All operations scoped to `PK = USER#{authenticated userId}`
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/`

---

### Wave 2: Category + Pipeline APIs + Receipt Detail UI

#### [ ] Task 4.2: Category + Pipeline Results Endpoints
- **Role:** backend-engineer
- **Depends on:** 4.1
- **Spec reference:** api-contracts.md >> GET/POST/DELETE categories, GET pipeline-results
- **Files:**
  - `backend/src/novascan/api/categories.py` (create — GET /api/categories, POST /api/categories, DELETE /api/categories/{slug})
  - `backend/src/novascan/api/app.py` (modify — register categories router)
- **Acceptance criteria:**
  - `GET /api/categories`: returns predefined categories merged with user's custom categories (from `CUSTOMCAT#` records), predefined first
  - `POST /api/categories`: auto-generates slug from displayName, validates optional parentCategory against predefined slugs, creates `CUSTOMCAT#{slug}` record, returns 201, 409 on duplicate slug
  - `DELETE /api/categories/{slug}`: deletes custom category, 403 for predefined categories, 404 if not found, returns 204
  - Custom category slugs are unique per user (PK-scoped)
  - `GET /api/receipts/{id}/pipeline-results`: returns both pipeline extraction outputs with ranking scores and rankingWinner, 403 for non-staff users (checks `cognito:groups` claim), 404 if receipt not found
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/`

#### [ ] Task 4.3: Receipt Detail Page
- **Role:** frontend-developer
- **Depends on:** 4.1
- **Spec reference:** SPEC.md >> Milestone 4 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/ReceiptDetailPage.tsx` (create — image + extracted data side-by-side)
  - `frontend/src/hooks/useReceipt.ts` (create — TanStack Query hook for single receipt)
  - `frontend/src/api/receipts.ts` (modify — add getReceipt, updateReceipt, deleteReceipt, updateItems API functions)
  - `frontend/src/App.tsx` (modify — add `/receipts/:id` route)
- **Acceptance criteria:**
  - Desktop: image on left, extracted data on right (side-by-side)
  - Mobile: image on top, extracted data below (stacked)
  - Displays: merchant, date, total, subtotal, tax, tip, payment method, category, status badge
  - Line items displayed in a table: name, quantity, unit price, total price, subcategory
  - Receipt image loads via presigned URL
  - Loading state while fetching receipt data
  - 404 handling for non-existent receipts
  - Delete button with confirmation dialog: clicking delete shows "Are you sure?" dialog, confirm calls `DELETE /api/receipts/{id}`, on success navigates back to receipts list
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 3: Detail Page Features

#### [ ] Task 4.4: Line Item Editing UI
- **Role:** frontend-developer
- **Depends on:** 4.1, 4.3
- **Spec reference:** SPEC.md >> Milestone 4 Acceptance Criteria (line item editing)
- **Files:**
  - `frontend/src/components/LineItemEditor.tsx` (create — inline editing table with add/remove rows)
  - `frontend/src/pages/ReceiptDetailPage.tsx` (modify — integrate line item editor)
- **Acceptance criteria:**
  - Each line item row has inline editable fields: name, quantity, price, subcategory
  - Add new line item button appends a row
  - Remove line item button on each row with confirmation
  - Save button calls `PUT /api/receipts/{id}/items` with full item list
  - Cancel button reverts to original data
  - Validation: name required, quantity > 0, prices >= 0
  - Optimistic update with rollback on failure
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

#### [ ] Task 4.5: Category Picker + Pipeline Comparison Toggle
- **Role:** frontend-developer
- **Depends on:** 4.2, 4.3
- **Spec reference:** SPEC.md >> Section 8 (Custom Categories UX Flow), Milestone 4 Acceptance Criteria
- **Files:**
  - `frontend/src/components/CategoryPicker.tsx` (create — dropdown with predefined + custom categories, create/delete custom)
  - `frontend/src/components/PipelineComparison.tsx` (create — side-by-side pipeline results, staff-only)
  - `frontend/src/hooks/useCategories.ts` (create — TanStack Query hook for categories)
  - `frontend/src/api/categories.ts` (create — API client for category endpoints)
  - `frontend/src/pages/ReceiptDetailPage.tsx` (modify — integrate category picker and pipeline toggle)
- **Acceptance criteria:**
  - Category picker dropdown: lists predefined categories, then custom categories
  - "Create Custom Category" option at bottom of dropdown opens modal: display name + optional parent category
  - Custom categories show delete icon; delete calls API and removes from list
  - Selecting a category/subcategory calls `PUT /api/receipts/{id}` to save
  - Pipeline comparison toggle: only visible to staff-role users (check `cognito:groups` from auth context)
  - Toggle shows both OCR-AI and AI-multimodal results side-by-side with confidence scores and ranking winner
  - Non-staff users see no pipeline toggle
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 4: Tests

#### [ ] Task 4.6: Receipt Management API Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 4.1, 4.2
- **Spec reference:** api-contracts.md >> all M4 endpoints
- **Files:**
  - `backend/tests/unit/test_receipt_crud.py` (create)
  - `backend/tests/unit/test_categories.py` (create)
  - `backend/tests/unit/test_pipeline_results.py` (create)
  - `backend/tests/unit/test_category_constants.py` (create)
- **Test scope:** Tests API contracts for receipt CRUD, categories, and pipeline results. Do NOT read implementation.
- **Acceptance criteria:**
  - Receipt CRUD tests: GET returns receipt with items, PUT updates only provided fields, DELETE removes DDB records + S3 image, PUT items replaces all line items, 404 for non-existent, 403 for wrong user
  - Category tests: GET returns predefined + custom merged, POST creates custom with auto-slug, POST rejects duplicate slug (409), DELETE removes custom, DELETE rejects predefined (403)
  - Pipeline results tests: returns both pipeline outputs for staff users, returns 403 for non-staff
  - Constants tests: all 13 categories present, slug format valid, subcategories exist for each category
  - `cd backend && uv run pytest tests/unit/test_receipt_crud.py tests/unit/test_categories.py tests/unit/test_pipeline_results.py tests/unit/test_category_constants.py -v` passes
- **Test command:** `cd backend && uv run pytest tests/unit/ -v -k "receipt_crud or categories or pipeline_results or category_constants"`

#### [ ] Task 4.7: Receipt Management UI Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 4.3, 4.4, 4.5
- **Spec reference:** SPEC.md >> Milestone 4 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/__tests__/ReceiptDetailPage.test.tsx` (create)
  - `frontend/src/components/__tests__/LineItemEditor.test.tsx` (create)
  - `frontend/src/components/__tests__/CategoryPicker.test.tsx` (create)
  - `frontend/src/components/__tests__/PipelineComparison.test.tsx` (create)
- **Test scope:** Tests receipt detail rendering, line item editing, category management, and pipeline toggle visibility. Do NOT read implementation.
- **Acceptance criteria:**
  - Detail page tests: renders receipt data, displays image, responsive layout, loading state, 404 handling
  - Line item tests: inline editing works, add/remove rows, save calls API, cancel reverts, validation errors shown
  - Category picker tests: shows predefined + custom, create modal works, delete custom works, selecting category updates receipt
  - Pipeline comparison tests: visible for staff users, hidden for non-staff, displays both pipeline results
  - `cd frontend && npm run test -- --run` passes
- **Test command:** `cd frontend && npm run test -- --run`

---

## Milestone 5: Dashboard & Transactions

### Wave 1: Backend APIs

#### [ ] Task 5.1: Dashboard Summary Endpoint
- **Role:** backend-engineer
- **Depends on:** none (M4 complete)
- **Spec reference:** api-contracts.md >> GET /api/dashboard/summary
- **Files:**
  - `backend/src/novascan/api/dashboard.py` (create — GET /api/dashboard/summary handler)
  - `backend/src/novascan/api/app.py` (modify — register dashboard router)
- **Acceptance criteria:**
  - Queries user's confirmed receipts via GSI1 for the target month and previous month
  - Aggregates with pandas: totalSpent, previousMonthTotal, monthlyChangePercent, weeklySpent, previousWeekTotal, weeklyChangePercent, receiptCount (with confirmed/processing/failed breakdown)
  - Top categories: up to 5, sorted by total descending, includes percent of total
  - Recent activity: up to 5 most recent receipts
  - `month` query param defaults to current month (YYYY-MM)
  - Weekly is current calendar week (Monday-Sunday) regardless of month param
  - Change percentages: positive = spending increase, negative = decrease, null if no prior data
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/`

#### [ ] Task 5.2: Transactions Endpoint
- **Role:** backend-engineer
- **Depends on:** none (M4 complete)
- **Spec reference:** api-contracts.md >> GET /api/transactions
- **Files:**
  - `backend/src/novascan/api/transactions.py` (create — GET /api/transactions handler)
  - `backend/src/novascan/api/app.py` (modify — register transactions router)
- **Acceptance criteria:**
  - Queries user's receipts via GSI1 with optional date range KeyCondition
  - Supports filters: startDate, endDate, category, merchant (partial case-insensitive), status
  - Supports sorting: `sortBy` (date, amount, merchant), `sortOrder` (asc, desc). **Note:** `sortBy=date` uses GSI1SK order natively. `sortBy=amount` and `sortBy=merchant` require fetching all matching records and sorting in-memory in Lambda (acceptable at MVP scale per SPEC line ~674).
  - Merchant search: case-insensitive substring match in Lambda
  - Returns `totalCount` via a parallel DynamoDB Count query (`Select="COUNT"` with identical filters). At MVP scale (~1,200 items/year), this is single-digit milliseconds and fractions of a cent. For `sortBy=amount|merchant`, since all records are fetched for in-memory sort, `totalCount` is derived from the fetched set — no separate Count query needed.
  - Cursor-based pagination using DynamoDB `ExclusiveStartKey`/`LastEvaluatedKey`
  - Category/status/merchant applied as FilterExpression (post-query)
  - `cd backend && uv run ruff check src/` passes
- **Test command:** `cd backend && uv run ruff check src/`

---

### Wave 2: Frontend Pages

#### [ ] Task 5.3: Dashboard Page + Analytics Placeholder
- **Role:** frontend-developer
- **Depends on:** 5.1
- **Spec reference:** SPEC.md >> Milestone 5 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/DashboardPage.tsx` (modify — full dashboard implementation)
  - `frontend/src/pages/AnalyticsPage.tsx` (modify — "Coming Soon" placeholder)
  - `frontend/src/hooks/useDashboard.ts` (create — TanStack Query hook for dashboard summary)
  - `frontend/src/api/dashboard.ts` (create — API client for dashboard endpoint)
  - `frontend/src/components/StatCard.tsx` (create — metric card with value + change indicator)
  - `frontend/src/components/CategoryBreakdown.tsx` (create — top categories list)
  - `frontend/src/components/RecentActivity.tsx` (create — recent receipts list)
- **Acceptance criteria:**
  - Dashboard shows: weekly total + % change, monthly total + % change, receipt count
  - Top categories: up to 5, with amounts and percentages
  - Recent activity: up to 5 receipts with merchant, amount, date
  - Positive change = upward indicator, negative = downward, null = no indicator
  - Analytics page shows "Coming Soon" with no broken UI
  - Mobile-friendly layout (single column on 375px viewport)
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

#### [ ] Task 5.4: Transactions Page
- **Role:** frontend-developer
- **Depends on:** 5.2
- **Spec reference:** SPEC.md >> Milestone 5 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/TransactionsPage.tsx` (modify — full transactions table)
  - `frontend/src/hooks/useTransactions.ts` (create — TanStack Query hook)
  - `frontend/src/api/transactions.ts` (create — API client for transactions endpoint)
  - `frontend/src/components/TransactionTable.tsx` (create — sortable table)
  - `frontend/src/components/TransactionFilters.tsx` (create — date range, category, status, merchant search)
- **Acceptance criteria:**
  - Sortable table with columns: date, merchant, category, amount, status
  - Column header click toggles sort direction
  - Date range filter: start date and end date pickers
  - Category filter: dropdown with predefined categories
  - Status filter: processing/confirmed/failed
  - Merchant search: text input with debounced API call
  - Pagination via cursor (Load More or infinite scroll)
  - Mobile layout: card view instead of table at 375px viewport
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 3: Tests

#### [ ] Task 5.5: Dashboard + Transactions API Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 5.1, 5.2
- **Spec reference:** api-contracts.md >> GET /api/dashboard/summary, GET /api/transactions
- **Files:**
  - `backend/tests/unit/test_dashboard.py` (create)
  - `backend/tests/unit/test_transactions.py` (create)
- **Test scope:** Tests API contracts for dashboard and transactions endpoints. Do NOT read implementation.
- **Acceptance criteria:**
  - Dashboard tests: correct monthly/weekly totals, correct % change calculation, top categories sorted by total, receipt count breakdown, null change when no prior data, only confirmed receipts in totals
  - Transactions tests: date range filter works, category filter works, merchant search partial match, sort by date/amount/merchant + asc/desc, pagination with cursor, totalCount correct
  - `cd backend && uv run pytest tests/unit/test_dashboard.py tests/unit/test_transactions.py -v` passes
- **Test command:** `cd backend && uv run pytest tests/unit/ -v -k "dashboard or transactions"`

#### [ ] Task 5.6: Dashboard + Transactions UI Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 5.3, 5.4
- **Spec reference:** SPEC.md >> Milestone 5 Acceptance Criteria
- **Files:**
  - `frontend/src/pages/__tests__/DashboardPage.test.tsx` (create)
  - `frontend/src/pages/__tests__/TransactionsPage.test.tsx` (create)
  - `frontend/src/pages/__tests__/AnalyticsPage.test.tsx` (create)
  - `frontend/src/components/__tests__/TransactionTable.test.tsx` (create)
  - `frontend/src/components/__tests__/TransactionFilters.test.tsx` (create)
- **Test scope:** Tests dashboard rendering, transaction table sorting/filtering, and analytics placeholder. Do NOT read implementation.
- **Acceptance criteria:**
  - Dashboard tests: renders stat cards with correct values, change indicators, top categories, recent activity
  - Transactions tests: table renders columns, sort toggles on header click, filters update query, merchant search debounces, pagination loads more
  - Analytics tests: renders "Coming Soon" text
  - Mobile tests: dashboard single column, transactions card view at 375px
  - `cd frontend && npm run test -- --run` passes
- **Test command:** `cd frontend && npm run test -- --run`

---

## Milestone 6: Custom Domain & Production Polish

### Wave 1: CDK + UX Polish

#### [ ] Task 6.1: Custom Domain CDK — ACM + CloudFront Alternate Domain
- **Role:** devops-engineer
- **Depends on:** none (M5 complete)
- **Spec reference:** SPEC.md >> Section 13 (Custom Domain Setup), Milestone 6 Acceptance Criteria
- **Files:**
  - `infra/cdkconstructs/frontend.py` (modify — add ACM certificate for `subdomain.example.com` in us-east-1, CloudFront alternate domain name, conditional on stage=prod)
  - `infra/stacks/novascan_stack.py` (modify — output ACM CNAME validation records and CloudFront domain for DNS setup)
- **Acceptance criteria:**
  - `cdk synth --context stage=prod` includes ACM certificate for `subdomain.example.com` in us-east-1
  - CloudFront distribution has `subdomain.example.com` as alternate domain name (prod only)
  - `cdk synth --context stage=dev` does NOT create ACM certificate or alternate domain
  - Stack outputs include DNS validation CNAME records for the ACM certificate
  - Stack outputs include CloudFront distribution domain name (for CNAME target)
- **Test command:** `cd infra && uv run cdk synth --context stage=prod | python -c "import sys,json; t=json.load(sys.stdin); certs=[v for v in t['Resources'].values() if v['Type']=='AWS::CertificateManager::Certificate']; assert len(certs)>=1; print('PASS')"`

#### [ ] Task 6.2: UX Polish — Error Boundaries, Skeletons, Empty States, 404
- **Role:** frontend-developer
- **Depends on:** none (M5 complete)
- **Spec reference:** SPEC.md >> Milestone 6 Acceptance Criteria
- **Files:**
  - `frontend/src/components/ErrorBoundary.tsx` (create — React error boundary with fallback UI)
  - `frontend/src/components/LoadingSkeleton.tsx` (create — skeleton variants for receipt list, dashboard, transaction table)
  - `frontend/src/components/EmptyState.tsx` (create — empty state variants: no receipts, no transactions, new user welcome)
  - `frontend/src/pages/NotFoundPage.tsx` (create — 404 page)
  - `frontend/src/App.tsx` (modify — wrap with ErrorBoundary, add 404 catch-all route)
  - `frontend/src/pages/DashboardPage.tsx` (modify — use loading skeleton and empty state)
  - `frontend/src/pages/ReceiptsPage.tsx` (modify — use loading skeleton and empty state)
  - `frontend/src/pages/TransactionsPage.tsx` (modify — use loading skeleton and empty state)
- **Acceptance criteria:**
  - Error boundary catches component crashes and shows user-friendly message with retry option (not raw error JSON)
  - Loading skeletons shown while data fetches: receipt list cards, dashboard stat cards, transaction table rows
  - Empty states: new user with no receipts sees welcome CTA ("Scan your first receipt"), no transactions shows friendly message
  - 404 page for unknown routes with link back to dashboard
  - All error scenarios display user-friendly messages
  - `cd frontend && npm run build` succeeds
- **Test command:** `cd frontend && npm run build`

---

### Wave 2: Tests + Production Deployment

#### [ ] Task 6.3: UX Polish Tests [TEST]
- **Role:** qa-engineer
- **Depends on:** 6.2
- **Spec reference:** SPEC.md >> Milestone 6 Acceptance Criteria
- **Files:**
  - `frontend/src/components/__tests__/ErrorBoundary.test.tsx` (create)
  - `frontend/src/components/__tests__/LoadingSkeleton.test.tsx` (create)
  - `frontend/src/components/__tests__/EmptyState.test.tsx` (create)
  - `frontend/src/pages/__tests__/NotFoundPage.test.tsx` (create)
- **Test scope:** Tests error handling, loading states, and empty states. Do NOT read implementation.
- **Acceptance criteria:**
  - Error boundary tests: catches thrown error, renders fallback, retry resets error state
  - Skeleton tests: renders correct skeleton variants for each page type
  - Empty state tests: correct messages and CTAs for each variant
  - 404 tests: renders on unknown route, has link to dashboard
  - `cd frontend && npm run test -- --run` passes
- **Test command:** `cd frontend && npm run test -- --run`

#### [ ] Task 6.4: Production Deployment + DNS + E2E Verification
- **Role:** devops-engineer
- **Depends on:** 6.1, 6.2
- **Spec reference:** SPEC.md >> Milestone 6 Acceptance Criteria, Section 13 (Manual Deployment Steps, Custom Domain Setup)
- **Files:**
  - `workflow/plan/PROGRESS.md` (modify — update all M6 task statuses)
- **Acceptance criteria:**
  - `cdk deploy --context stage=prod` completes without errors
  - ACM certificate validated (Cloudflare DNS CNAME added)
  - Frontend built with prod stack outputs and uploaded to prod S3 bucket
  - CloudFront invalidation completed
  - `https://subdomain.example.com` loads the frontend
  - HTTPS enforced (HTTP redirects)
  - Full flow: sign up → sign in → upload receipt → see processing → see confirmed receipt → view detail → edit line items → dashboard shows totals → transactions shows entry → sign out
  - `cdk destroy --context stage=prod` removes all resources
  - Dev and prod are isolated (separate stacks, separate resources)
- **Test command:** `curl -s -o /dev/null -w "%{http_code}" https://subdomain.example.com`

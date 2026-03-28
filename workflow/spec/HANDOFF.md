# NovaScan — Specification Handoff

---

## Document Index

| Document | Location | Purpose |
|----------|----------|---------|
| Technical Specification | [workflow/spec/SPEC.md](SPEC.md) | Architecture, milestones, database schema, dev setup, standards, NFRs |
| API Contracts | [workflow/spec/api-contracts.md](api-contracts.md) | REST endpoint specifications |
| Category Taxonomy | [workflow/spec/category-taxonomy.md](category-taxonomy.md) | Predefined categories, subcategories, grocery departments |
| Research Summary | [workflow/research/final/research.md](../research/final/research.md) | Phase 1 findings and tech stack decisions |
| Phase 1 RFC | [workflow/research/final/rfc.md](../research/final/rfc.md) | Decision log across 4 feedback rounds |
| DR-001: Frontend | [workflow/decisions/DR-001-frontend-web-app-vs-flutter.md](../decisions/DR-001-frontend-web-app-vs-flutter.md) | Vite + React decision |
| DR-002: OCR Pipeline | [workflow/decisions/DR-002-ocr-pipeline-single-call-vs-tiered.md](../decisions/DR-002-ocr-pipeline-single-call-vs-tiered.md) | Tiered pipeline + A/B testing |
| DR-003: Pipeline Ingestion | [workflow/decisions/DR-003-pipeline-ingestion-decoupled.md](../decisions/DR-003-pipeline-ingestion-decoupled.md) | SQS + EventBridge Pipes rate limiting |
| DR-004: RBAC | [workflow/decisions/DR-004-rbac-cognito-groups.md](../decisions/DR-004-rbac-cognito-groups.md) | Cognito Groups for role-based access |
| Runbook | [workflow/spec/runbook.md](runbook.md) | Local dev, deployment, troubleshooting, ops tasks |

---

## Milestone Ordering

```
M1: Foundation & Auth
 └─► M2: Receipt Upload & Storage
      └─► M3: OCR Processing Pipeline
           └─► M4: Receipt Management
                └─► M5: Dashboard & Transactions
                     └─► M6: Custom Domain & Production Polish
```

**Why this order:**

| Dependency | Reason |
|-----------|--------|
| M1 → M2 | Upload requires auth (JWT for presigned URLs) and infrastructure (S3, DynamoDB, API Gateway) |
| M2 → M3 | Pipeline triggers on S3 uploads — needs images in S3 to process |
| M3 → M4 | Receipt management displays OCR-extracted data — needs processing to produce it |
| M4 → M5 | Dashboard aggregates receipt data — needs confirmed receipts with categories and amounts |
| M5 → M6 | Custom domain and polish applied after core functionality is complete and testable |

---

## Execution Sequence Within Milestones

### Milestone 1: Foundation & Auth

1. CDK project scaffolding (`infra/`, `cdk.json`, `app.py`, construct stubs)
2. Storage construct: DynamoDB table, S3 frontend bucket
3. Auth construct: Cognito User Pool (email OTP, passwordless), Pre-Sign-Up Lambda, Cognito Groups (`user`, `staff`, `admin`)
4. API construct: API Gateway HTTP API, Cognito authorizer, API Lambda (hello world)
5. Frontend construct: S3 origin, CloudFront distribution, SPA error routing
6. Deploy to dev — verify `cdk deploy` succeeds
7. Frontend project scaffolding: Vite + React + Tailwind + shadcn/ui
8. Auth module: Cognito SDK integration (`InitiateAuth`, `RespondToAuthChallenge`)
9. Login page UI: email input → OTP input → redirect to dashboard
10. App shell: navigation (bottom bar mobile, sidebar desktop), protected routes
11. End-to-end test: sign up → sign in → see empty dashboard → sign out

### Milestone 2: Receipt Upload & Storage

1. S3 receipts bucket (in storage construct, private, encrypted)
2. Pydantic models: `Receipt`, `UploadRequest`, `UploadResponse`
3. API endpoint: `POST /api/receipts/upload-urls`
4. API endpoint: `GET /api/receipts`
5. Upload UI: camera capture button, file picker, bulk selection (max 10)
6. Upload flow: request presigned URLs → upload to S3 → show confirmation
7. Receipts page: card/list view with status badges
8. Deploy and test: upload images, verify in S3, see receipts in list

### Milestone 3: OCR Processing Pipeline

1. Receipt extraction schema as Pydantic model
2. Lambda: `textract_extract` — calls Textract `AnalyzeExpense` (sync), returns raw output
3. Lambda: `nova_structure` — takes Textract output + image, calls Bedrock Nova, returns structured JSON
4. Lambda: `bedrock_extract` — takes image, calls Bedrock Nova (multimodal), returns structured JSON
5. Lambda: `load_custom_categories` — queries user's `CUSTOMCAT#` entities from DynamoDB, returns merged taxonomy for pipeline prompts
6. Lambda: `finalize` — main/shadow logic (use main, fallback to shadow if main fails), ranks both results (`rankingScore` per pipeline, `rankingWinner` on receipt — data point only), stores both pipeline results with ranking scores, updates receipt record, updates S3 object metadata, sets status
7. Step Functions state machine: LoadCustomCategories → Parallel (Main + Shadow branches with Catch) → Finalize
8. SQS queue: receives S3 `ObjectCreated` events from `receipts/` prefix (burst buffer)
9. EventBridge Pipes: consumes from SQS with configurable `MaximumConcurrency` (from `cdk.json`) → starts Step Functions execution
10. Pipeline construct in CDK: SQS, EventBridge Pipes, state machine, Lambdas, IAM roles
11. Integration test: upload receipt image, verify both pipeline results in DynamoDB
12. Test with multiple receipt types (grocery, restaurant, gas station)

### Milestone 4: Receipt Management

1. API endpoint: `GET /api/receipts/{id}` (with line items)
2. API endpoint: `PUT /api/receipts/{id}`
3. API endpoint: `PUT /api/receipts/{id}/items`
4. API endpoint: `DELETE /api/receipts/{id}` (DynamoDB + S3 cleanup)
5. Category constants module (predefined taxonomy from category-taxonomy.md)
6. API endpoint: `GET /api/categories`
7. API endpoint: `POST /api/categories`
8. API endpoint: `DELETE /api/categories/{slug}`
9. API endpoint: `GET /api/receipts/{id}/pipeline-results` (staff role only)
10. Receipt detail page: image display, extracted data, line items table
11. Per-receipt pipeline comparison toggle (staff role only, UI-only — no DB mutation)
12. Line item editing: inline edit (name, quantity, price, subcategory), add/remove rows, save
13. Category picker: dropdown with predefined + custom categories
14. Receipt delete: confirmation dialog, hard delete
15. User isolation verification: confirm all CRUD operations scoped to authenticated user
16. Test: edit receipt → save → verify changes persist

### Milestone 5: Dashboard & Transactions

1. API endpoint: `GET /api/dashboard/summary` (pandas aggregation)
2. Dashboard page: weekly + monthly spending totals, % change, receipt count, top categories, recent activity
3. API endpoint: `GET /api/transactions` (with filters, sort, search)
4. Transactions page: sortable table, column headers
5. Filter UI: date range picker, category dropdown, status filter
6. Search UI: merchant name search input
7. Analytics page: "Coming Soon" with placeholder content
8. Mobile layout review: verify all pages at 375px viewport
9. Test: add multiple receipts across categories → verify dashboard totals and transaction filters

### Milestone 6: Custom Domain & Production Polish

1. ACM certificate construct for `subdomain.example.com`
2. CloudFront alternate domain configuration
3. Write Cloudflare DNS setup instructions (CNAME, DNS-only mode)
4. Error boundary component (React)
5. Loading skeletons for receipt list, dashboard, transaction table
6. Empty state components (no receipts, no transactions)
7. 404 page
8. Production deployment: `cdk deploy --context stage=prod`
9. Cloudflare DNS configuration (manual)
10. Verify: `https://subdomain.example.com` loads, auth works, upload → process → view flow

---

## Acceptance Criteria

### Per-Milestone

See [SPEC.md Section 2](SPEC.md#2-milestones) for detailed acceptance criteria per milestone.

### System-Level (all milestones complete)

The system is complete and correct when:

1. A new user can sign up with email OTP, sign in, and reach the dashboard
2. User can upload a receipt photo from mobile browser camera
3. User can bulk upload up to 10 receipt images
4. Uploaded receipts are automatically processed by both OCR pipelines in parallel (rate-limited via SQS + EventBridge Pipes, configurable concurrency)
5. User sees receipt status transition from "Processing" to "Confirmed" (or "Failed")
6. User can view the receipt image alongside extracted merchant, date, totals, and line items
6a. Staff-role users can toggle between OCR-AI and AI-multimodal results per receipt (UI-only comparison)
7. User can edit line items (name, quantity, price) and save changes
8. User can change the category and subcategory of a receipt
9. User can create custom categories and assign them to receipts
10. User can delete receipts (image and all data removed)
11. Dashboard shows accurate week-to-date and month-to-date totals, % change, and top categories
12. Transactions page shows a sortable, filterable ledger of all spending
13. App is accessible at `https://subdomain.example.com`
14. `cdk destroy` removes all resources cleanly (both dev and prod)
15. Monthly AWS cost under $25 at typical personal usage

---

## Known Risks

| # | Risk | Likelihood | Impact | Mitigation |
|---|------|-----------|--------|------------|
| 1 | **Textract AnalyzeExpense accuracy** on degraded thermal paper | Medium | Medium | A/B pipeline comparison provides empirical data. Can shift to AI-multimodal path if OCR-AI performs worse. |
| 2 | **Browser camera quality** varies across mobile devices | Medium | Low | Accept any JPEG/PNG quality. Frontend can suggest lighting/angle. Non-blocking. |
| 3 | **Cognito USER_AUTH + auto-signup flow** requires `SignUp` as a separate call | Low | Low | Confirmed: `InitiateAuth` fails for non-existent users. Frontend catches `UserNotFoundException`, calls `SignUp`, then retries. Pattern documented in rfc-clarification.md. |
| 4 | **CDK PythonFunction bundling** with `uv` | Low | Low | Native uv support is GA in `@aws-cdk/aws-lambda-python-alpha`. Fallback: `Code.fromAsset` with pre-built bundle. |
| 5 | **Step Functions Parallel state** fails if any branch fails | Low | Low | Mitigated: Catch blocks within each branch. Each branch always returns a result (success or error payload). Parallel state never fails. |
| 6 | **Cloudflare proxy mode** conflicts with CloudFront | Medium | Low | Documented: must use DNS-only (gray cloud). Add a note in deployment instructions. |
| 7 | **$25/month budget** with both pipelines running | Low | Medium | At ~100 users × ~100 receipts/month: Textract ~$1.50, Bedrock ~$10-20. Should be under budget but monitor. |
| 8 | **TanStack Query** — only medium-risk third-party dependency | Low | Low | If abandoned, replace with SWR or manual fetch + useState. Migration is straightforward. |
| 9 | **SQS + EventBridge Pipes** adds operational complexity | Low | Low | More components than direct EventBridge trigger, but prevents Textract throttling. Pipes is a managed service — no code to maintain. |
| 10 | **Cognito Groups `cognito:groups` claim** may not be included in ID token by default | Low | Medium | Cognito includes groups in the ID token when groups exist. If missing, a Pre-Token-Generation Lambda can inject it. Test during M1. |

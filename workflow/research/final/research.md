# Phase 1 Research & Discovery: NovaScan

**Project:** NovaScan — AI-Powered Receipt Scanner & Spending Tracker
**Date:** 2026-03-24
**Sources:** 4 manual research documents, 10 UI mockups (Google Stitch / Lumina Ledger), developer notes, independent AI research

---

## 1. Business Requirements

### Must-Have (MVP)

- **Receipt Scanning via Camera**: Users photograph physical receipts; the system extracts merchant, date, line items, totals, and tax
- **Bulk Upload**: Upload multiple receipt images at once (in addition to camera scanning)
- **Spending Dashboard**: Show total spent, top categories, recent activity — both mobile and desktop views
- **Activity History**: Searchable, filterable list of all scanned receipts with status (verified/pending)
- **Line Item Review & Edit**: After scanning, user reviews extracted items and corrects errors before committing
- **Category Assignment**: Auto-categorize transactions (groceries, dining, electronics, etc.)
- **User Authentication**: Cognito email OTP (passwordless) — fully managed, no custom auth logic
- **Mobile-Optimized Web App**: Responsive web UI that works well on mobile browsers (delay native app)
- **Local Development**: Dev AWS account (`cdk deploy` with dev stage), DynamoDB Local for unit tests
- **Simple Deployment & Teardown**: Idempotent deploy/update/rollback/delete — all resources tracked

### MVP Phase 2 (post-MVP, pre-roadmap)

- **Spending Analytics**: Charts, trends, monthly comparisons (no peer-group benchmarking)
- **AI Chatbot**: Natural language queries against spending data ("How much did I spend on groceries?") — simple Bedrock API call, evaluate AgentCore if needs grow
- **Voice Interface**: Speech-to-speech queries via Nova Sonic
- **RAG Pipeline**: Document retrieval for receipt text search and citation (using S3 Vectors)
- **CSV/PDF Export**: Export spending data

### Nice-to-Have (Post-MVP Phase 2)

- **Budget Tracking**: Set spending limits per category, track progress
- **eReceipt Integration**: OAuth email linking for automatic digital receipt ingestion
- **Multi-Page Receipt Stitching**: Composite scanning for long receipts
- **Gamification / Points System**: Rewards for scanning (Fetch model)
- **B2B Analytics Portal**: Enterprise dashboard for CPG brand partners
- **Fraud Detection**: Duplicate receipt detection, image manipulation detection

### Deprioritized (Future Roadmap)

- Performance-based advertising network (Ibotta model)
- Browser extension for online purchase tracking
- Desktop-native application
- Native mobile app (Flutter/React Native) — design backend API-first to support this later

---

## 2. Technical Constraints

### From Developer Notes (`notes.md`)

| Constraint | Detail |
|---|---|
| **Scope** | MVP — do not over-engineer |
| **Local-first** | Dev AWS account with `cdk deploy` (dev stage); DynamoDB Local for unit tests |
| **Deployment** | Simple, idempotent; must support deploy, update, rollback, delete |
| **Resource tracking** | All cloud resources and configs must be tracked and teardown-able |
| **Mobile-first web** | Web app layout optimized for mobile to delay native app |
| **API-first backend** | Design backend so a future mobile app can consume it |
| **Python tooling** | Use `uv` for package management (from global CLAUDE.md) |
| **Budget** | $25/month max for cloud services |
| **Users** | Personal tool, under 20 users |
| **Third-party risk** | Minimize third-party dependencies; prefer AWS-native solutions over adapters/abstractions |

### From Research Documents

| Constraint | Detail |
|---|---|
| **Cloud provider** | AWS (specified throughout all research docs) |
| **Region** | us-east-1 |
| **Scale-to-zero** | No always-on compute; pay-per-execution only |
| **Cost ceiling** | Minimize baseline costs; target < $0.01 per receipt processed |
| **Data structure** | AI extraction must produce schema-compliant JSON (no manual parsing) |
| **Security** | Presigned URLs for uploads, malware scanning, mandatory object tagging |
| **Auth** | Amazon Cognito email OTP (passwordless) — fully managed |

### Contradictions Identified

| # | Contradiction | Resolution |
|---|---|---|
| C1 | Notes say "MVP, keep simple" vs research docs describe enterprise platform (B2B portal, gamification, RAG, voice chatbot) | **Resolved** — scope reduced to MVP; enterprise features moved to MVP Phase 2 and beyond |
| C2 | Notes say "mobile-optimized web app first" vs research docs specify Flutter cross-platform | **Resolved** — Vite + React + Tailwind responsive web app. See DR-001 |
| C3 | Notes say "run locally with Docker" vs research docs never mention local development | **Resolved** — dev AWS account with `cdk deploy --stage dev`; DynamoDB Local for unit tests |
| C4 | Research docs mandate "scale-to-zero" but Aurora Serverless v2 has ~$45/mo floor and Timestream has baseline memory store costs | **Resolved** — Aurora and Timestream removed. DynamoDB + pandas for analytics, S3 Vectors for future RAG |
| C5 | Doc 2 uses API Gateway for presigned URLs; Doc 4 resolves to AppSync as unified API | **Resolved** — presigned URLs via API Gateway HTTP API. AppSync deferred |

---

## 3. Reference Architectures

### Receipt Scanning Apps (Competitive)

| App | Model | Key Takeaway |
|---|---|---|
| **Fetch** | Low-friction, points-based, scan everything | Maximizes data capture volume; gamification drives DAU |
| **Ibotta** | High-friction, cash-based, pre-activated offers | Higher intent signals but requires massive brand network |
| **Expensify / Emburse** | B2B expense management | Focus on accuracy, accounting integration |
| **ReceiptsAI** | Simple consumer receipt tracker | Closest to our MVP scope |

### AWS Reference Patterns

| Pattern | Source | Relevance |
|---|---|---|
| **RAGStack-Lambda** | [GitHub: HatmanStack/RAGStack-Lambda](https://github.com/HatmanStack/RAGStack-Lambda) | Scale-to-zero RAG pipeline; good pattern for post-MVP chatbot |
| **aws-samples/sample-ai-receipt-processing-methods** | [GitHub](https://github.com/aws-samples/sample-ai-receipt-processing-methods) | Direct reference for receipt processing with Textract + Bedrock |
| **freeCodeCamp serverless RAG** | [Article](https://www.freecodecamp.org/news/how-to-build-a-serverless-rag-pipeline-on-aws-that-scales-to-zero/) | Step Functions + Lambda orchestration pattern |
| **Step Functions callback pattern** | [AWS Blog](https://aws.amazon.com/blogs/compute/handle-unpredictable-processing-times-with-operational-consistency-when-integrating-asynchronous-aws-services-with-an-aws-step-functions-state-machine/) | Async Textract integration via task tokens |

### UI Reference (Google Stitch / Lumina Ledger)

The `stitch_receipt_scanner/` directory contains 10 high-fidelity mockups from Google Stitch with a "Lumina Ledger" brand and "Digital Curator" design system:

| Screen | Platform | Key Features |
|---|---|---|
| `desktop_dashboard` | Desktop | Total managed capital, spending chart, recent activity, active budgets, OCR confidence rating |
| `mobile_dashboard` | Mobile | Monthly total, scan button, scan count, digest metric, recent activity |
| `mobile_supermarket_receipt_scan` | Mobile | Camera viewfinder, scanning status, merchant detection, line item extraction with prices |
| `mobile_itemized_scanner_view` | Mobile | Successful scan confirmation, item list with prices, Edit/Continue actions |
| `mobile_recognized_items` | Mobile | Review items view, line items with quantities, subtotal/tax/total, bill splitting |
| `mobile_mobile_activity_history` | Mobile | History by day, scan count, monthly total, mini spending chart |
| `desktop_activity_history_table` | Desktop | Filterable table with date/merchant/category/amount/status, confidence insight |
| `desktop_receipt_upload_review` | Desktop | Side-by-side: receipt image with detected items + structured extraction table |
| `desktop_spending_analytics` | Desktop | Daily spending chart, monthly trend, category donut chart, anomaly detection |
| `desktop_spending_visualization` | Mobile | Weekly/monthly/yearly toggle, daily spending, top allocations |

**Design System** (from `DESIGN.md`):
- Monochromatic grayscale palette — "Digital Curator" aesthetic
- Fonts: Manrope (headlines) + Inter (body)
- No-line rule: boundaries via background color shifts, not borders
- Glassmorphism for scanning overlays
- No dividers between list items — use spacing
- Tertiary color `#006c59` only for success/money-in states

---

## 4. External Dependencies

### AWS Services

| Service | Purpose | Auth Method | Pricing Model | MVP Required? |
|---|---|---|---|---|
| **Amazon S3** | Receipt image storage | IAM / Presigned URLs | ~$0.023/GB/mo | Yes |
| **Amazon Bedrock (Nova)** | Multimodal OCR + data extraction | IAM | Per-token (~$0.06/1M input, $0.24/1M output for Nova Lite) | Yes |
| **Amazon Cognito** | User auth (email OTP, passwordless) | OAuth2 / JWT | Free < 50K MAU | Yes |
| **Amazon DynamoDB** | User data, receipts, dashboard state | IAM | Pay-per-request (on-demand) | Yes |
| **AWS Lambda** | Compute (API handlers, processing) | IAM | Pay-per-invocation + duration; 1M free/mo | Yes |
| **Amazon EventBridge** | Event routing (S3 → processing) | IAM | $1/1M events | Yes |
| **API Gateway** | REST API (HTTP API v2) | Cognito JWT | $1/M requests | Yes |
| **AWS Step Functions** | Receipt processing orchestration (tiered pipeline) | IAM | $0.025/1K transitions | Yes |
| **Amazon Textract** | OCR Expense API (tiered pipeline) | IAM | $1.50/1K pages | Yes |
| **Amazon S3 Vectors** | Vector embeddings for RAG | IAM | $0.06/GB/mo storage, pay-per-query | No (MVP Phase 2) |
| **Amazon Nova Sonic** | Voice chatbot | IAM / WebSocket | Per-second audio streaming | No (MVP Phase 2) |
| **Amazon GuardDuty** | Malware scanning for uploads | IAM | Per-scan | Recommended |

**Removed from stack:**
- ~~Amazon Timestream~~ — overkill for personal tracker. Using pandas in Lambda for analytics.
- ~~Aurora Serverless v2~~ — $45/mo minimum violates budget. S3 Vectors covers vector DB needs.
- ~~AWS AppSync~~ — GraphQL unnecessary for MVP. Using API Gateway HTTP API + presigned URLs.
- ~~Amazon Athena~~ — peer-group benchmarking removed from scope.

### Third-Party / Google

| Service | Purpose | Status | MVP Required? |
|---|---|---|---|
| **Google Stitch** | UI design generation | Experimental (Google Labs) | No — use as design reference only |

### IaC / Tooling

| Tool | Purpose |
|---|---|
| **AWS CDK (Python)** | Deploy/teardown AWS infrastructure — AWS-maintained, Python-native, generates CloudFormation |
| **Docker / Docker Compose** | DynamoDB Local for unit tests, local debugging |
| **uv** | Python package management (per global CLAUDE.md) |

**Removed from stack:**
- ~~SST (Ion v3)~~ — third-party risk, TypeScript config. Replaced by AWS CDK (Python).
- ~~LocalStack~~ — dev AWS account provides 1:1 parity. Free tier covers dev usage.

---

## 5. AI Research Additions

These findings were NOT present in the manual research materials.

### 5.1 Aurora Serverless v2 Does NOT Scale to Zero

**Critical finding.** The manual research (Doc 3, Doc 4) repeatedly states Aurora Serverless v2 with pgvector is the cost-effective vector DB choice, claiming it "scales down to 0.5 ACUs" as if this is near-zero cost. In reality:

- Minimum 0.5 ACU is always running = **~$45-50/month baseline**, even with zero traffic
- Aurora Serverless v1 had true pause/resume but was deprecated (EOL December 2024)
- No Aurora Serverless v3 has been announced

**Impact:** For an MVP with the scale-to-zero constraint, Aurora is a poor choice. For post-MVP RAG, use **Amazon S3 Vectors** (GA December 2025) — true scale-to-zero, $0.06/GB/mo storage, native AWS integration, no external service to manage.

### 5.2 Amazon Timestream Viability Concerns

- Timestream received limited feature development and has a small community
- Memory store has baseline costs even when idle — not truly scale-to-zero
- Custom SQL dialect with limited tooling ecosystem
- Heavy vendor lock-in with no clean migration path

**Impact:** For MVP, **DynamoDB alone is sufficient** for storing receipt data with time-based access patterns using composite sort keys. Analytics computed via **pandas in Lambda** — query DynamoDB, aggregate in-memory, return JSON. Timestream is overkill for a personal spending tracker with <20 users.

### 5.3 Google Stitch is Not Production-Ready

- Still in Google Labs experimental phase
- Output is primarily HTML/CSS/JS prototypes — not production-grade code
- No standardized DESIGN.md format for automated CI/CD pipelines
- No known production applications built on Stitch-generated code
- The MCP-based automated design-to-code pipeline described in the research docs is aspirational, not proven

**Impact:** Treat the Stitch mockups as **design reference only**. Build the actual frontend manually (or with AI coding assistants), using the DESIGN.md color/typography tokens and screenshots as a style guide.

### 5.4 Single Bedrock Call Can Replace Textract + Nova Pipeline

The manual research describes a multi-step pipeline: Textract (OCR) → format → Nova (structured extraction). For an MVP:

- Amazon Nova (or Claude on Bedrock) models are multimodal — they accept images directly
- A single API call with the receipt image + a JSON schema prompt can extract all fields in one pass
- Eliminates: Textract service, callback Lambda, DynamoDB token storage, SNS notification, formatting Lambda
- Cost per receipt: comparable or cheaper at MVP volumes
- Accuracy: sufficient for a personal spending tracker (not CPG-grade analytics)

**Impact:** Both approaches have merit. **Decision: use the tiered pipeline (Textract + Nova) as primary, but architect for A/B testing both paths side by side.** Both share the same input (S3 image) and output (structured JSON schema), making A/B routing straightforward via a feature flag at the Step Functions level. See DR-002.

### 5.5 AWS CDK (Python) for IaC

The developer notes require: simple deployment, idempotent, supports deploy/update/rollback/delete, all resources tracked. **AWS CDK (Python)** is the best fit:

- `cdk deploy` — deploy all resources
- `cdk destroy` — tear down everything (single command)
- Generates CloudFormation — AWS-managed state, no external state files
- First-class constructs for Lambda, S3, DynamoDB, API Gateway, Cognito, Step Functions, Textract
- Written in Python — same language as the application code
- AWS-maintained — zero third-party risk
- `cdk watch` — redeploys on file change for dev iteration

**Alternatives considered and rejected:**
- SST Ion v3: Third-party risk (team has pivoted twice), TypeScript config, Pulumi state management
- Terraform: Third-party (HashiCorp), HCL language, state file management overhead
- SAM: AWS-native but YAML-only, no programming language features
- Raw CloudFormation: Too verbose, cryptic errors

### 5.6 Vite + React + Tailwind for Frontend

The developer notes explicitly say "mobile-optimized web app first" and "delay the mobile app." The research docs specify Flutter. **Decision: Vite + React + Tailwind CSS v4 responsive web app.**

- HTML `<input type="file" accept="image/*" capture="environment">` opens the native camera on mobile
- Bulk upload with progress bars, interactive line item editing, and future analytics dashboards require rich client-side interactivity — React handles this naturally
- shadcn/ui provides copy-paste Tailwind components matching the Digital Curator aesthetic
- PWA manifest enables "Add to Home Screen" for app-like experience
- **No Xcode, Android Studio, or app signing required**
- Backend API-first design means Flutter/native can be added later without rearchitecting

**See DR-001 for the full decision record.**

### 5.7 Dev AWS Account Instead of LocalStack

None of the research docs mention local development, but the developer notes require a dev environment. **Decision: use a dev AWS account** instead of LocalStack.

- Free tier covers dev usage (Lambda 1M free requests/mo, DynamoDB 25GB free, S3 5GB free) — likely $0-3/mo
- 1:1 parity with prod — no "works in LocalStack but breaks on AWS" issues
- CDK supports `cdk deploy` with a dev stage to create isolated resources in the same account
- Bedrock/AI calls can't be emulated locally anyway — need real AWS
- One fewer tool in the stack to maintain

**Keep Docker for:** DynamoDB Local (fast unit tests without network latency).

---

## 6. Open Questions (All Resolved)

| # | Question | Answer |
|---|---|---|
| Q1 | **Project name** | NovaScan |
| Q2 | **Personal tool or product?** | Personal tool |
| Q3 | **MVP user count** | Under 20 users |
| Q4 | **Fetch/Ibotta analysis relevant?** | No — personal tracker MVP only |
| Q5 | **Cloud budget** | $25/month max |
| Q6 | **AWS region** | us-east-1 |
| Q7 | **Frontend framework** | Vite + React + Tailwind CSS v4 + shadcn/ui |
| Q8 | **Auth requirements** | Cognito email OTP (passwordless) — fully managed, no custom auth |
| Q9 | **Design system** | Use Lumina Ledger / Digital Curator as-is; AI recommends improvements but stays consistent |
| Q10 | **Multi-page stitching** | Skip for MVP |

---

## 7. Recommended Tech Stack

### MVP

| Layer | Recommendation | Version | Justification |
|---|---|---|---|
| **Backend Language** | Python | 3.13+ | Developer expertise; `uv` tooling; strong AWS SDK (boto3) |
| **Backend Framework** | AWS Lambda Powertools for Python | Latest | AWS-maintained; routing, Pydantic validation, structured logging, tracing, idempotency — no third-party adapters |
| **Data Validation** | Pydantic | v2 | Data models, request/response validation; embedded in Lambda Powertools |
| **Frontend** | Vite + React + Tailwind CSS v4 | Latest stable | Rich interactivity for bulk upload, line item editing, future analytics dashboards |
| **Component Library** | shadcn/ui | Latest | Copy-paste Tailwind components; matches Digital Curator aesthetic; not a runtime dependency |
| **Server State** | TanStack Query (React Query) | Latest | Data fetching, caching, background refetching for REST API |
| **AI / OCR** | Amazon Textract + Amazon Bedrock (Nova) | Latest | Tiered pipeline with A/B testing support for single Bedrock call. See DR-002 |
| **Database** | Amazon DynamoDB (on-demand) | N/A (managed) | True pay-per-request; single-digit ms reads; single-table design for user+receipts+dashboard |
| **Analytics** | pandas (in Lambda) | Latest | Query DynamoDB, aggregate in-memory, return JSON. Sufficient for <20 users |
| **Object Storage** | Amazon S3 | N/A (managed) | Receipt image storage; presigned URL uploads |
| **Auth** | Amazon Cognito (email OTP) | N/A (managed) | Passwordless; free < 50K MAU; JWT-based; fully managed |
| **API Layer** | API Gateway (HTTP API v2) | N/A (managed) | REST + JWT validation; presigned URL generation; $1/M requests |
| **Compute** | AWS Lambda | Python 3.13 runtime | Scale-to-zero; generous free tier |
| **Orchestration** | AWS Step Functions | N/A (managed) | Tiered OCR pipeline with A/B routing |
| **Event Routing** | Amazon EventBridge | N/A (managed) | Decouple S3 uploads from processing |
| **IaC** | AWS CDK (Python) | Latest | AWS-maintained; Python-native; `cdk deploy` / `cdk destroy`; generates CloudFormation |
| **Dev Environment** | Dev AWS account + DynamoDB Local | N/A | `cdk deploy` with dev stage; DynamoDB Local for unit tests |
| **Package Manager** | uv | Latest | Per developer global instructions |
| **Design System** | Lumina Ledger / Digital Curator | N/A | Monochromatic grayscale; Manrope + Inter fonts; glassmorphism overlays |

### MVP Phase 2 Additions

| Layer | Recommendation | When |
|---|---|---|
| **Vector DB** | Amazon S3 Vectors | When RAG pipeline is built |
| **Chatbot** | Simple Bedrock API call (evaluate AgentCore if needs grow) | When conversational interface is needed |
| **Voice** | Nova Sonic + WebSocket API Gateway | When voice queries are needed |
| **Charts** | Recharts or Chart.js (React-native) | When spending analytics UI is built |

### Future Roadmap Additions

| Layer | Recommendation | When |
|---|---|---|
| **Mobile App** | Flutter | When native mobile experience is required |
| **GraphQL** | AWS AppSync | When real-time subscriptions or complex queries justify it |

---

## 8. Inaccessible Resources

| Resource | Why Inaccessible | What It Contains |
|---|---|---|
| Google Stitch interactive prototypes | Stitch projects are tied to Google account sessions; only static exports (screenshots + HTML) were provided | Original interactive designs; may have additional screens or states not captured in screenshots |
| Ibotta IPN documentation | Behind partner/advertiser login wall | Detailed API specs for the Ibotta Performance Network; enterprise integration details |
| Fetch B2B brand portal | Behind partner login wall | Offer deployment interface; targeting capabilities |
| Several "Works cited" URLs in research docs | Many citations (e.g., refs 1-5 in Doc 3) point to unrelated sources (school branding guides, university handbooks, Hacker News threads) suggesting citation errors in the AI-generated research | Supposed to contain supporting evidence for claims made in the documents |

### Note on Citation Quality

Multiple citations across the 4 research documents appear to be **hallucinated or misattributed**. For example, Doc 3 ("Shopping App Research & Design") cites sources like "Ultimate School Brand Development Guide" and "belred arts district project" which are unrelated to receipt scanning. The technical content in the documents is generally sound, but the specific citation links should not be trusted as authoritative sources. The AWS documentation links are generally accurate.

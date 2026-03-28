# RFC: NovaScan Phase 1 Research Review

**Date:** 2026-03-24
**Author:** AI (Phase 1 Research Agent)
**Status:** Awaiting Human Review

---

## Summary of Key Findings

### The manual research is enterprise-grade; the developer wants an MVP

The 4 research documents describe a sophisticated two-sided data marketplace with B2B analytics, gamification, RAG chatbot, voice interface, and multi-agent AI orchestration. The developer notes say "MVP, don't over-engineer, keep it simple, run locally with Docker."

**The research.md resolves this by scoping down to a focused MVP** (receipt scanning, spending dashboard, activity history) and deferring everything else (chatbot, RAG, gamification, B2B portal, voice) to post-MVP.

### Three tech choices in the research docs are problematic

1. **Aurora Serverless v2** — claimed to support scale-to-zero, but minimum is 0.5 ACU (~$45/month). Violates the stated cost constraint. Deferred to post-MVP; recommended Neon Postgres as alternative.

2. **Amazon Timestream** — uncertain long-term viability, baseline costs, vendor lock-in. Replaced with DynamoDB (sufficient for MVP-scale analytics via precomputed aggregates).

3. **Google Stitch** — still experimental (Google Labs). The automated design-to-code pipeline described in the research is aspirational. Recommended using the Stitch mockups as a design reference only, not a build dependency.

### The OCR pipeline can be drastically simplified

Instead of Textract → SNS → Lambda callback → Nova (6+ services), a single Bedrock multimodal call handles OCR + extraction in one step. See DR-002.

### Recommended stack aligns with developer preferences

Python (FastAPI) backend, uv package manager, HTMX + Tailwind frontend, SST Ion for IaC, Docker + LocalStack for local dev. See research.md Section 7.

---

## Low-Confidence Areas

| Area | Confidence | Why |
|---|---|---|
| **Amazon Timestream still supported?** | Low | No deprecation announcement found, but limited recent development. Could not verify March 2026 status. |
| **SST Ion Python support maturity** | Medium | SST Ion v3 supports Python Lambdas, but the ecosystem is more JavaScript-focused. May hit rough edges. |
| **HTML camera capture quality** | Medium | Browser `<input capture>` works for basic photos, but quality/UX may not match native camera. Need to test on real devices. |
| **Bedrock single-call accuracy** | Medium | Should be sufficient for clean receipts. Unknown how well it handles severely degraded thermal paper vs dedicated Textract. Need empirical testing. |
| **Citation quality in manual research** | Low | Multiple citations in Docs 1-4 point to unrelated sources. Technical content is sound, but specific claims may lack proper sourcing. |
| **Google Stitch March 2026 status** | Medium | Based on May 2025 knowledge. It may have matured since then. Recommend checking current status. |
| **Aurora Serverless v2 pricing** | Medium | Based on May 2025 pricing. AWS may have introduced changes. Verify current ACU-hour pricing. |

---

## Decisions Requiring Your Input

1. **Confirm project name**: Is "NovaScan" correct? (Inferred from repo directory name)
2. **Confirm MVP scope**: Is the must-have list in research.md Section 1 aligned with your vision? Anything to add or remove?
3. **DR-001 (Web app vs Flutter)**: Do you agree with responsive web app for MVP?
4. **DR-002 (Single Bedrock call vs tiered pipeline)**: Do you agree with the simplified approach?
5. **Is this a personal tool or a multi-user product?** This fundamentally affects auth, data model, and compliance requirements.
6. **Monthly cloud budget tolerance**: What's acceptable? $0? $10? $50?
7. **Design system**: Should we follow the Lumina Ledger / "Digital Curator" aesthetic from the Stitch mockups?

---

**Please review `workflow/research/final/research.md` and the two decision records in `workflow/decisions/`. Add `*FEEDBACK:*` comments below if anything needs revision. I will not proceed to Phase 2 until you explicitly approve.**


# *FEEDBACK:*
1. NovaScan
2. please see additional feedback on research.md below
3. Shall we also consider Vite.js? I’m an experienced python developer but I feel that it make sense to build the frontend in .js. I’m not familiar with .js , so I need help to choose.
4. use tiered pipeline. in addition, I want to keep the option open for running both single bedrock call and tiered pipeline side by side to A/B test them.
5. $25/month max
6. yes


## additional feedback on research.md
I want to add the following to MVP:
- Beside the scanning via camera, I want to be able to bulk upload multiple receipts.

The following should be MVP phase 2:
* Spending Analytics: Charts, trends, monthly comparisons.  We don’t need peer-group benchmarking.
* AI Chatbot: Natural language queries against spending data ("How much did I spend on groceries?")
* Voice Interface: Speech-to-speech queries via Nova Sonic
* RAG Pipeline: Document retrieval for receipt text search and citation
* CSV/PDF Export: Export spending data

I don’t understand the following, please explain: 
* eReceipt Integration: OAuth email linking for automatic digital receipt ingestion
* Real-time anti-stacking technology

Technical Constraints
-  Does AWS Cognito support authentication via email magic link? So that user can sign up and login via verification code send to their email. And the backend will create the account on Cognito.

Contradictions
- C1: agree to reduce scope
- C2: See feedback
- C3: agree local-first with cloud parity
- C4: agree Aurora Serverless doesn’t make sense
- C5: please let me know the pros and cons. I’m leaning towards presigned URLs

External Dependencies:
- AWS Services:
    - Timestream: for simple analytics, can we just use something in memory method like pandas?
    - Aurora Serverless V2: is there a cheap vector DB option like S3 vector?

IaC / Tooling:
- SST (Ion v3): why this instead of Terraform or CloudFormation?
- LocalStack: if AWS service is cheap enough, would it make sense to create a dev resources / account and test it there? So 1. We don’t need to have another stack to maintain, and 2. the dev resources / account will be almost 1:1 mapping to the prod account.
- We could still run individual services locally with docker if that is easier to debug.

6. Open Questions
- Q1: NovaScan
- Q2: personal tool
- Q3: probably under 20 users
- Q4: just personal tracker MVP
- Q5: $25
- Q6: us-east-1
- Q7: Shall we also consider Vite.js? I’m an experienced python developer but I feel that it make sense to build the frontend in .js. I’m not familiar with .js , so I need help to choose.
- Q8: I want to outsource the Authentication. I don’t want to handle login.
- Q9: try to use is as-is. AI should make recommendations on what to improve and implement, just be consistent
- Q10: skip

---

# *AI:* Response to Feedback (2026-03-25)

## Decisions Confirmed

| # | Decision | Status |
|---|---|---|
| 1 | Project name: **NovaScan** | Confirmed |
| 5 | Budget: **$25/month max** | Confirmed |
| 6 | Design system: **Lumina Ledger / Digital Curator as-is** | Confirmed |
| C1 | Reduce scope to MVP | Confirmed |
| C3 | Local-first with cloud parity | Confirmed |
| C4 | Drop Aurora Serverless v2 | Confirmed |
| Q2 | Personal tool | Confirmed |
| Q3 | Under 20 users | Confirmed |
| Q4 | Personal tracker MVP | Confirmed |
| Q6 | us-east-1 | Confirmed |
| Q10 | Multi-page stitching: skip | Confirmed |

## MVP Scope Updates

**Added to MVP:**
- Bulk upload of multiple receipts (in addition to camera scanning)

**New tier — "MVP Phase 2" (post-MVP, pre-roadmap):**
- Spending Analytics (charts, trends, monthly comparisons — no peer-group benchmarking)
- AI Chatbot (natural language queries against spending data)
- Voice Interface (Nova Sonic)
- RAG Pipeline (receipt text search and citation)
- CSV/PDF Export

Will update research.md Section 1 accordingly.

---

## Explanations Requested

### eReceipt Integration

This means connecting to a user's email inbox (Gmail, Outlook, etc.) via OAuth, then automatically scanning incoming emails for digital receipts from retailers (Amazon order confirmations, Uber receipts, DoorDash, etc.). The system would parse the email HTML/attachments to extract the same structured data that camera scanning produces — but without the user needing to photograph anything.

**For NovaScan MVP:** Not needed. This is a significant feature (OAuth email flows, email parsing, retailer-specific templates). Keeping it in "Future Roadmap" is correct.

### Real-time Anti-Stacking Technology

This comes from the Ibotta competitive analysis. "Stacking" = combining multiple cash-back offers on a single purchase (e.g., manufacturer coupon + store coupon + Ibotta rebate + credit card reward). Anti-stacking technology detects and prevents users from claiming overlapping offers, which matters for a cash-back marketplace that pays real money.

**For NovaScan:** Completely irrelevant. This is a B2B marketplace feature for brands paying cash-back rebates. A personal spending tracker has no offers to stack. Removing from all tiers.

---

## Technical Questions

### Cognito Email Magic Link / OTP

**Yes, Cognito supports this natively.** As of late 2024, Amazon Cognito has built-in passwordless authentication including:

- **Email OTP**: User enters email → Cognito sends a one-time code → user enters code → authenticated. This is exactly what you described.
- **Magic Links**: User enters email → receives a clickable link → click = authenticated.
- **Passkeys** (FIDO2/WebAuthn): Biometric/hardware key auth.

You configure this by enabling the `USER_AUTH` flow and selecting email OTP as an allowed sign-in factor. Cognito handles sending the email, generating the code, and verifying it. The backend creates the user in the Cognito User Pool on first sign-up.

**Recommendation for NovaScan:** Use Cognito's native email OTP flow. It's the simplest passwordless option, fully managed, and free under 50K MAU. No Lambda triggers or custom auth flows needed for basic email OTP.

Sources:
- [AWS Blog: Implementing passwordless email authentication with Amazon Cognito](https://aws.amazon.com/blogs/mobile/implementing-passwordless-email-authentication-with-amazon-cognito/)
- [AWS Docs: Authentication flows](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html)

---

### C5: Presigned URLs vs AppSync — Pros and Cons

Your instinct is correct. Presigned URLs are the right call for MVP.

| | **Presigned URLs (API Gateway + S3)** | **AppSync (GraphQL)** |
|---|---|---|
| **Complexity** | Simple — one Lambda generates a signed URL, client uploads directly to S3 | Complex — GraphQL schema, resolvers, subscriptions setup |
| **Upload flow** | Client → Lambda (get URL) → Client → S3 (direct upload). No server touches the file bytes. | Client → AppSync → resolver → S3. More indirection. |
| **Latency** | Lower — direct S3 upload, no middleware | Higher — GraphQL resolver chain |
| **Bulk upload** | Easy — generate N presigned URLs, client uploads in parallel | Possible but more plumbing |
| **Real-time status** | Need polling or WebSocket for scan status | Built-in subscriptions (this is AppSync's strength) |
| **Cost** | API Gateway HTTP API: $1/M requests. S3 PUT: $0.005/1K | AppSync: $4/M queries + $2/M real-time updates |
| **Learning curve** | Minimal — standard REST | GraphQL schema design, resolver mapping templates |
| **Future mobile app** | Works identically from any HTTP client | GraphQL client needed (Amplify) |

**Recommendation:** Presigned URLs via API Gateway HTTP API. For scan status updates, use polling initially (simple), upgrade to WebSocket or AppSync subscriptions in MVP Phase 2 if needed.

---

### Timestream: Can We Use Pandas Instead?

**Yes, absolutely.** For <20 users with a personal spending tracker, pandas in a Lambda function is more than sufficient:

- Query receipts from DynamoDB for a date range
- Load into a pandas DataFrame
- Compute aggregates (monthly totals, category breakdowns, trends)
- Return JSON to the frontend

At MVP scale (hundreds to low thousands of receipts), this runs in <1 second in a Lambda with 256MB memory. No dedicated analytics DB needed.

**For MVP Phase 2 analytics:** Still use pandas. You'd only need a dedicated analytics service if you're processing millions of rows or need sub-second responses on complex time-series queries — which won't happen at 20 users.

**Dropping Timestream from all tiers.** It was overkill even for post-MVP.

---

### Aurora / Vector DB: Cheap Alternative?

There is no "S3 vector" product from AWS. But you don't need a vector DB at all for MVP — that's only needed for the RAG pipeline (MVP Phase 2).

When you do need one for RAG/chatbot, options ranked by cost:

| Option | Cost | Scale-to-Zero? | Notes |
|---|---|---|---|
| **Neon Postgres + pgvector** | Free tier: 0.5GB storage, 190 compute hours/mo. Paid: ~$19/mo | Yes (true pause) | Best option. Postgres you already know, pgvector for embeddings |
| **Supabase + pgvector** | Free tier: 500MB. Pro: $25/mo | No (always-on) | Good but blows the budget alone |
| **DynamoDB + application-side similarity** | Pay-per-request (~free at low scale) | Yes | Hack: store vectors as attributes, compute cosine similarity in Lambda. Works for <10K vectors |
| **SQLite + sqlite-vec** | $0 (runs in Lambda) | N/A (ephemeral) | Experimental but viable for tiny datasets bundled in Lambda |

**Recommendation:** Defer vector DB entirely. When RAG is needed, use Neon Postgres free tier with pgvector. It fits within the $25 budget.

---

### SST Ion v3: Why Not Terraform or CloudFormation?

| | **SST Ion v3** | **Terraform** | **CloudFormation** |
|---|---|---|---|
| **Language** | TypeScript (config) | HCL | YAML/JSON |
| **Abstraction level** | High — `new sst.aws.Function()` does Lambda + IAM + API route in one line | Medium — each resource explicit | Low — every resource, every property |
| **Deploy/teardown** | `sst deploy` / `sst remove` — one command | `terraform apply` / `terraform destroy` | `aws cloudformation delete-stack` |
| **State management** | Auto-managed, backed up to S3 | State file you must manage (S3 backend, locking) | AWS-managed (stack state) |
| **Live dev mode** | Yes — `sst dev` hot-reloads Lambda code in real-time | No | No |
| **Rollback** | Via Pulumi under the hood | Manual (`terraform plan` + revert) | Automatic on failure |
| **Python Lambda support** | Yes (v3 supports Python runtimes) | Yes | Yes |
| **Lines of code for this project** | ~100-150 | ~400-600 | ~800-1200 |
| **Learning curve** | Low if you know JS/TS basics | Medium (HCL is its own language) | High (verbose, error messages are cryptic) |
| **Community/ecosystem** | Smaller, serverless-focused | Massive, industry standard | AWS-only but well-documented |

**Why SST for NovaScan:**
1. Your requirements — "simple deployment, idempotent, deploy/update/rollback/delete, all resources tracked" — are literally SST's elevator pitch.
2. Live dev mode (`sst dev`) means you can iterate on Lambda functions without redeploying. Huge time saver.
3. One-command teardown (`sst remove`) deletes everything. No orphaned resources.
4. ~4x less config code than Terraform for the same infrastructure.

**The trade-off:** SST's ecosystem is JS/TS-focused. Your IaC config files will be TypeScript, even though your application code is Python. This is a ~50 line config file, not a full application — manageable even without deep JS experience.

**If you strongly prefer staying Python-only:** Use AWS CDK (Python) or Pulumi (Python). Both work but are more verbose than SST and lack the live dev mode.

Sources:
- [SST v3 announcement](https://sst.dev/blog/sst-v3/)
- [SST vs Terraform comparison](https://nivelais.com/articles/frak/frak-infrastructure-iac/)

---

### LocalStack vs Dev AWS Account

Your reasoning is sound. Here's the honest comparison:

| | **Dev AWS Account** | **LocalStack** |
|---|---|---|
| **Parity with prod** | 100% — same services, same APIs | ~85% — most services work, some have quirks |
| **Bedrock/AI services** | Works | Not emulated — need real AWS anyway |
| **Cost** | Lambda: 1M free requests/mo. DynamoDB: 25GB free. S3: 5GB free. **Likely $0-3/mo for dev.** | Free (Community Edition) |
| **Maintenance burden** | Low — same IaC deploys to dev and prod | Medium — separate config, debugging LocalStack-specific issues |
| **Offline development** | No | Yes (except Bedrock calls) |
| **Risk** | Forgetting to tear down resources; need account isolation | None |

**Recommendation: Use a dev AWS account.** Reasons:
1. Free tier covers your dev usage. With <20 users, dev costs will be near $0.
2. 1:1 parity with prod — no "works in LocalStack but breaks on AWS" surprises.
3. One fewer tool in the stack. SST already supports `sst deploy --stage dev` to create isolated dev resources in the same account.
4. You still need real AWS for Bedrock calls during development anyway.

**Keep Docker for:** DynamoDB Local (for fast unit tests without network) and any local debugging where you want instant feedback. SST's `sst dev` mode already connects to real AWS services while running your Lambda code locally, which gives you the best of both worlds.

**Dropping LocalStack from the recommended stack.**

---

## Frontend: HTMX + Tailwind vs Vite + React

This is the biggest open decision. Your instinct to use JS for the frontend is worth taking seriously. Here's the honest breakdown:

### Why HTMX was originally recommended
- You're a Python developer → stay in Python, use Jinja2 templates
- Minimal JS to learn
- Simpler build pipeline

### Why that recommendation was wrong for NovaScan

HTMX works great for simple CRUD apps. NovaScan's MVP already has interactions that push HTMX to its limits:

1. **Bulk upload with progress**: Multiple files uploading in parallel, each with a progress bar, cancel buttons. This is painful in HTMX — you'd end up writing custom JS anyway.
2. **Receipt review/edit**: Inline editing of line items, adding/removing rows, recalculating totals. HTMX can do it with `hx-swap` gymnastics, but React components handle this naturally.
3. **Camera capture flow**: Preview, crop, retake — interactive state management that's awkward in server-rendered HTML.
4. **MVP Phase 2 (analytics dashboards)**: Charts, trend visualizations, interactive filters. Chart libraries (Chart.js, Recharts) are JS-native. Forcing these through HTMX would be fighting the tool.

### Recommendation: Vite + React + Tailwind

| Aspect | Detail |
|---|---|
| **Build tool** | Vite — fast, modern, zero-config for React |
| **UI framework** | React — largest ecosystem, best AI code generation support, most tutorials/examples |
| **Styling** | Tailwind CSS v4 — same as HTMX option, works great with React |
| **Component library** | shadcn/ui — high-quality, accessible, Tailwind-based components. Not a dependency — you copy the source. |
| **Charts (Phase 2)** | Recharts or Chart.js — React-native integrations |
| **State management** | React Query (TanStack Query) for server state, minimal local state via useState |
| **API communication** | REST (FastAPI backend) → fetch/axios from React |

**Why React over Vue/Svelte/etc.:**
- Largest ecosystem = most AI-generated code examples = easier for you to get help
- shadcn/ui (React-only) gives you a polished component library that matches the Digital Curator aesthetic
- React Query handles all the data fetching/caching patterns you'll need

**The trade-off you're accepting:**
- Two languages in the project: Python backend + TypeScript frontend
- Need to learn React basics (components, hooks, JSX) — but AI assistants handle most of the generation
- Separate build step for frontend (Vite handles this, fast)

**Architecture:**
```
novascan/
├── backend/          # FastAPI (Python, uv)
│   ├── api/          # REST endpoints
│   └── ...
├── frontend/         # Vite + React + Tailwind (TypeScript)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   └── package.json
├── infra/            # SST Ion (TypeScript)
└── ...
```

FastAPI serves the API. Vite builds the frontend to static files. S3 + CloudFront (or Lambda@Edge) serves the static frontend. Clean separation.

**Do you want to proceed with Vite + React, or do you want me to reconsider HTMX?**

---

### Q8: Outsourced Authentication

Confirmed: Cognito with email OTP (passwordless). You won't write any auth logic — Cognito handles:
- User sign-up (email → OTP → account created)
- User sign-in (email → OTP → JWT issued)
- JWT validation (FastAPI middleware validates Cognito JWTs)
- Token refresh

Your backend just validates the JWT on each request. ~10 lines of middleware code.

### Q9: Design System

Will use Lumina Ledger / Digital Curator design system as-is. AI will recommend specific improvements during implementation but will maintain consistency with the established palette, typography (Manrope + Inter), and glassmorphism patterns.

---

## Updated DR-001 Recommendation

Changing from Option B (HTMX) to **Option D: Vite + React + Tailwind** based on feedback. Rationale above. Will update the decision record.

## Updated DR-002 Decision

Changing to: **Tiered pipeline (Textract + Nova) as primary, with architecture supporting A/B testing against single Bedrock call.** Both paths share the same input (S3 image) and output (structured JSON schema), making A/B routing straightforward via a feature flag or percentage-based split at the EventBridge/Step Functions level. Will update the decision record.

---

## Summary of Changes to Make

1. research.md Section 1: Add bulk upload to MVP, create "MVP Phase 2" tier, move items per feedback, remove anti-stacking
2. research.md Section 2: Add $25/month budget, Cognito email OTP, <20 users
3. research.md Section 4: Drop Timestream (all tiers), drop LocalStack, note dev AWS account approach, add pandas for analytics
4. research.md Section 7: Replace HTMX with Vite + React + Tailwind (pending your confirmation)
5. DR-001: Add Option D (Vite + React), change recommendation
6. DR-002: Change to tiered pipeline with A/B testing architecture
7. Open questions: All resolved

**Awaiting your confirmation on the frontend choice (Vite + React vs HTMX) before updating the documents. All other changes are ready to apply.**

# Feedback

## Vector DB
Amazon S3 Vectors exist https://aws.amazon.com/s3/features/vectors/ https://aws.amazon.com/s3/pricing/?nc=sn&loc=4 does it change the your opinion?

## IaC
Ok on SST

## Frontend
Vite + React + Tailwind

## Open questions
- You said FastAPI for backend, is our backend is all handled by lambda. Where is FastAPI come into play?
- For AI Chat bot, shall we consider AWS Agent Core https://aws.amazon.com/bedrock/agentcore/? does SST.dev support it?

---

# *AI:* Response to Round 2 Feedback (2026-03-25)

## Confirmed

- **IaC**: SST Ion v3
- **Frontend**: Vite + React + Tailwind

## S3 Vectors — Yes, This Changes My Recommendation

You're right, I missed this. Amazon S3 Vectors went GA in December 2025 and is a strong fit for NovaScan's future RAG needs.

**S3 Vectors pricing (us-east-1):**

| Dimension | Cost |
|---|---|
| Storage | $0.06/GB/month |
| PUT (upload) | $0.20/GB |
| Query | Per-API call + per-TB data processed (scales down with index size) |
| Baseline / minimum | **$0** — true scale-to-zero |

**Why this beats the previous options:**
- **vs Neon Postgres**: No external service to manage. Stays entirely in AWS. No free tier limits to worry about. True scale-to-zero.
- **vs DynamoDB hack**: Purpose-built for vector similarity search. No application-side cosine similarity math.
- **Cost at NovaScan scale**: A few thousand receipt text embeddings (1024-dim, 4KB each) = ~10MB total. Storage: $0.0006/month. Effectively free.

**Updated recommendation for MVP Phase 2 RAG:**
Use S3 Vectors instead of Neon Postgres. Store receipt text embeddings in an S3 vector bucket, query via the S3 Vectors API from Lambda. Zero infrastructure to manage, zero baseline cost, native AWS integration.

**Removing Neon Postgres and Aurora from all tiers.** S3 Vectors covers the vector DB need within the existing AWS stack and $25 budget.

Sources:
- [Amazon S3 Vectors GA announcement](https://aws.amazon.com/about-aws/whats-new/2025/12/amazon-s3-vectors-generally-available/)
- [S3 Vectors feature page](https://aws.amazon.com/s3/features/vectors/)
- [S3 Vectors pricing deep dive](https://murraycole.com/posts/aws-s3-vectors-pricing-deep-dive)

---

## FastAPI + Lambda — How They Work Together

FastAPI doesn't run *instead of* Lambda. It runs *inside* Lambda via an adapter called **Mangum**.

```
Client request
    → API Gateway (HTTP API)
    → Lambda function
    → Mangum adapter (converts Lambda event → ASGI request)
    → FastAPI app (routes, validation, business logic)
    → Mangum (converts ASGI response → Lambda response)
    → API Gateway
    → Client
```

You write a normal FastAPI app with routes, Pydantic models, dependency injection, etc. Then you add one line:

```python
from mangum import Mangum
from fastapi import FastAPI

app = FastAPI()

@app.get("/receipts")
async def list_receipts():
    ...

# This is what Lambda invokes
handler = Mangum(app)
```

**Why bother with FastAPI if Lambda handles HTTP?**
- **Routing**: FastAPI gives you `@app.get("/receipts/{id}")` instead of manually parsing Lambda event paths
- **Validation**: Pydantic models auto-validate request/response bodies
- **OpenAPI docs**: Auto-generated API docs at `/docs` — useful for frontend development
- **Testability**: Run `uvicorn app:app` locally without Lambda at all — just a normal Python server
- **Middleware**: Auth JWT validation, CORS, logging — all standard FastAPI middleware
- **Future-proof**: If you ever move off Lambda, the FastAPI app works unchanged on any ASGI server

**The alternative** — raw Lambda handlers (parsing `event["pathParameters"]`, manual validation) — is doable but tedious and error-prone. FastAPI + Mangum gives you a real web framework with zero Lambda-specific lock-in.

Sources:
- [Mangum adapter](https://mangum.fastapiexpert.com/)
- [FastAPI Lambda Container guide](https://rafrasenberg.com/fastapi-lambda/)

---

## AWS Bedrock AgentCore — Worth Considering, but Not for MVP Phase 2 Chatbot

**What AgentCore is:** An enterprise platform (GA October 2025) for building, deploying, and operating AI agents at scale. It provides runtime, memory, gateway, identity, policy controls, observability, and tool orchestration — all managed.

**What NovaScan's chatbot needs (MVP Phase 2):** Answer questions like "How much did I spend on groceries in February?" This is a single Bedrock API call with the user's spending data as context. No multi-step agent orchestration, no persistent agent memory, no tool chaining, no policy controls.

| | **Simple Bedrock API call** | **AgentCore** |
|---|---|---|
| **Complexity** | One Lambda → Bedrock invoke | Agent runtime + gateway + memory + identity + observability |
| **What it does** | "Here's the user's spending data. Answer this question." | Multi-tool orchestration, persistent memory across sessions, policy guardrails, evaluations |
| **Cost** | Bedrock model tokens only | AgentCore runtime + Bedrock tokens + memory storage |
| **When it's justified** | Single-turn Q&A against structured data | Complex multi-step workflows, multi-tool agents, enterprise compliance |

**Recommendation:** Start with a simple Bedrock call for the chatbot. If requirements grow (multi-turn conversations, tool use like "create a budget", "export this report"), then evaluate AgentCore. Don't over-engineer the chatbot before it exists.

**SST support:** SST doesn't have native AgentCore constructs. AWS CDK has an [alpha AgentCore construct library](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock_agentcore_alpha/README.html), and there's a [Python SDK on PyPI](https://pypi.org/project/bedrock-agentcore/) (`bedrock-agentcore`). If you do adopt AgentCore later, you'd either use the Pulumi AWS provider in SST to provision it, or use the Python SDK directly in Lambda functions. Not a blocker either way.

Sources:
- [Amazon Bedrock AgentCore](https://aws.amazon.com/bedrock/agentcore/)
- [2026 Guide to AgentCore](https://www.goml.io/blog/amazon-bedrock-agentcore)
- [CDK AgentCore construct library](https://docs.aws.amazon.com/cdk/api/v2/python/aws_cdk.aws_bedrock_agentcore_alpha/README.html)

---

## All Questions Resolved — Summary of Final Decisions

| Decision | Choice |
|---|---|
| Project name | NovaScan |
| Frontend | Vite + React + Tailwind CSS v4 + shadcn/ui |
| Backend | FastAPI (Python) on Lambda via Mangum |
| IaC | SST Ion v3 |
| OCR pipeline | Tiered (Textract + Nova) with A/B testing support for single Bedrock call |
| Database | DynamoDB (on-demand) |
| Analytics | pandas in Lambda |
| Vector DB (Phase 2) | S3 Vectors |
| Auth | Cognito email OTP (passwordless) |
| File upload | Presigned URLs via API Gateway HTTP API |
| Dev environment | Dev AWS account (`sst deploy --stage dev`), DynamoDB Local for unit tests |
| Design system | Lumina Ledger / Digital Curator as-is |
| Region | us-east-1 |
| Budget | $25/month max |
| Chatbot (Phase 2) | Simple Bedrock API call first, evaluate AgentCore if needs grow |

**No open questions remain. Ready to update research.md, DR-001, and DR-002 with all confirmed decisions. Approve to proceed?**

---

# *AI:* Response to Round 3 Feedback (2026-03-25) — Third-Party Risk Audit + Mangum

## Mangum: You're Right, Drop It

The vendor lock-in argument was BS. Everything is AWS — Lambda, DynamoDB, S3, Cognito, Bedrock, EventBridge. There's no future where you "move off Lambda" but keep everything else. Mangum adds a third-party dependency to solve a problem that doesn't exist.

**The real alternative isn't raw Lambda handlers.** It's **AWS Lambda Powertools for Python** — maintained by AWS, provides the same developer experience I was selling FastAPI for:

| Feature | FastAPI + Mangum | AWS Lambda Powertools | Raw Lambda |
|---|---|---|---|
| Routing | `@app.get("/receipts")` | `@app.get("/receipts")` | Manual `event["path"]` parsing |
| Validation | Pydantic models | Pydantic v2 (native support) | Manual / standalone Pydantic |
| OpenAPI docs | Auto-generated at `/docs` | No (use API Gateway export) | No |
| Structured logging | Via middleware | Built-in | Manual |
| Tracing (X-Ray) | Via middleware | Built-in | Manual |
| Idempotency | Manual | Built-in (DynamoDB-backed) | Manual |
| Maintained by | Mangum: 1 person (Kludex). FastAPI: community | **AWS** | N/A |
| Third-party deps | FastAPI + Mangum + Uvicorn | **Zero** (it's an AWS SDK extension) | Zero |
| Lambda-native | No (ASGI adapter layer) | **Yes** (reads Lambda events directly) | Yes |
| Local testing | `uvicorn app:app` | `pytest` with event fixtures | `pytest` with event fixtures |

**Powertools example:**
```python
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools import Logger, Tracer

app = APIGatewayHttpResolver()
logger = Logger()
tracer = Tracer()

@app.get("/receipts")
def list_receipts():
    ...

@app.post("/receipts")
def create_receipt():
    ...

@logger.inject_lambda_context
@tracer.capture_lambda_handler
def handler(event: dict, context: LambdaContext):
    return app.resolve(event, context)
```

Same routing syntax. Same Pydantic validation. But zero third-party risk, built-in observability, and no adapter layer converting events back and forth.

**The one thing you lose:** Auto-generated OpenAPI docs at `/docs`. But API Gateway HTTP API can export its OpenAPI spec, and for a team of <20 users building a personal tool, you don't need a Swagger UI endpoint. You have the API defined in your SST config and your route decorators.

**Decision: Replace FastAPI + Mangum with AWS Lambda Powertools for Python.**

Sources:
- [Powertools REST API event handler](https://docs.powertools.aws.dev/lambda/python/latest/core/event_handler/api_gateway/)
- [Powertools Pydantic parser](https://docs.aws.amazon.com/powertools/python/latest/utilities/parser/)
- [Powertools GitHub (AWS-maintained)](https://github.com/aws-powertools/powertools-lambda-python)

---

## Full Third-Party Risk Audit

Audited every non-AWS dependency across research.md and the RFC decisions.

### Backend / Infrastructure

| Dependency | Maintainer | Risk | Verdict |
|---|---|---|---|
| ~~**FastAPI**~~ | Community (Sebastián Ramírez) | Low | **REMOVED** — replaced by Lambda Powertools |
| ~~**Mangum**~~ | 1 person (Kludex) | **High** | **REMOVED** — unnecessary adapter layer |
| **Pydantic** | Community (Samuel Colvin, funded) | Low | KEEP — used standalone for data models. Also embedded in Lambda Powertools. No alternative at this quality level. |
| **SST Ion v3** | SST team (~5 people) | Medium | KEEP — uses Pulumi underneath. If SST dies, migrate to raw Pulumi (same state, same provider). Escape hatch exists. The risk is real but bounded. |
| ~~**LocalStack**~~ | LocalStack GmbH | Medium | **ALREADY REMOVED** — using dev AWS account |
| **uv** | Astral (well-funded, Charlie Marsh) | Low | KEEP — your global requirement. Growing rapidly, backed by VC. If abandoned, `pip` still works. |
| **Docker** | Docker Inc | Very Low | KEEP — industry standard, no realistic alternative |
| **boto3 / AWS SDK** | AWS | None | KEEP — first-party |
| **Lambda Powertools** | AWS | None | KEEP — first-party, replaces FastAPI+Mangum |

### Frontend

| Dependency | Maintainer | Risk | Verdict |
|---|---|---|---|
| **React** | Meta (Facebook) | Very Low | KEEP — massive adoption, not going anywhere |
| **Vite** | Evan You + StackBlitz + community | Low | KEEP — dominant build tool, well-funded |
| **Tailwind CSS v4** | Tailwind Labs (funded) | Low | KEEP — massive adoption, commercial company behind it |
| **shadcn/ui** | 1 person (shadcn) | **Low despite single author** | KEEP — it's not a dependency. You copy component source code into your repo. If shadcn disappears tomorrow, nothing breaks. Your code is your code. |
| **TanStack Query** | Tanner Linsley | Low-Medium | KEEP — widely adopted, but worth noting. Alternative: SWR (Vercel). If abandoned, replace with fetch + useState (more code but no dependency). |

### Removed from Stack (via this audit)

| Removed | Was In | Why |
|---|---|---|
| **FastAPI** | research.md Section 7 | Replaced by Lambda Powertools — no need for ASGI framework on Lambda |
| **Mangum** | RFC Round 2 | Single-maintainer adapter, unnecessary layer |
| **Neon Postgres** | RFC Round 1 | Replaced by S3 Vectors (AWS-native) |
| **LocalStack** | research.md Section 4, 7 | Replaced by dev AWS account |
| **Timestream** | research.md Section 4 | Replaced by pandas in Lambda |
| **Aurora Serverless v2** | research.md Section 4 | Budget violation, replaced by S3 Vectors for RAG |

### Remaining Risk Items

1. **SST Ion v3** — Medium risk. Mitigated by Pulumi escape hatch. If SST pivots again (they've done it twice: v1→v2→v3), you can migrate to raw Pulumi using the same state files and Terraform providers. Cost of migration: rewrite ~100-150 lines of IaC config.

2. **TanStack Query** — Low-Medium risk. If abandoned, the migration path is straightforward (SWR or manual fetch). Not load-bearing infrastructure.

Everything else is either AWS-native, industry-standard (Docker, React), or copy-paste (shadcn/ui).

---

## Updated Final Decision Table

| Decision | Choice |
|---|---|
| Project name | NovaScan |
| Frontend | Vite + React + Tailwind CSS v4 + shadcn/ui |
| Backend | **AWS Lambda Powertools for Python** (not FastAPI, not Mangum) |
| IaC | SST Ion v3 |
| OCR pipeline | Tiered (Textract + Nova) with A/B testing support for single Bedrock call |
| Database | DynamoDB (on-demand) |
| Analytics | pandas in Lambda |
| Vector DB (Phase 2) | S3 Vectors |
| Auth | Cognito email OTP (passwordless) |
| File upload | Presigned URLs via API Gateway HTTP API |
| Dev environment | Dev AWS account (`sst deploy --stage dev`), DynamoDB Local for unit tests |
| Design system | Lumina Ledger / Digital Curator as-is |
| Region | us-east-1 |
| Budget | $25/month max |
| Chatbot (Phase 2) | Simple Bedrock API call first, evaluate AgentCore if needs grow |

**Third-party dependencies reduced to: React, Vite, Tailwind, shadcn/ui (copy-paste), TanStack Query, SST, Pydantic, uv, Docker. Everything else is AWS-native.**

**Approve to proceed with updating research.md, DR-001, and DR-002?**

---

# *AI:* Response to Round 4 Feedback (2026-03-25) — Drop SST, Use AWS CDK (Python)

## Decision: Replace SST Ion v3 with AWS CDK (Python)

Same logic as Mangum: SST is a third-party abstraction over Pulumi over Terraform providers over AWS APIs. The team has pivoted twice. AI writes the code, so verbosity is irrelevant. AWS CDK is AWS-maintained, uses Python (your language), and generates CloudFormation (AWS-managed state).

**What you lose:** `sst dev` live Lambda proxy (best-in-class local dev). `cdk watch` redeployes on file change instead — slower (10-20s per change vs instant), but acceptable with a dev AWS account.

**What you gain:** Zero third-party IaC risk. Python for infrastructure code. AWS-managed CloudFormation state. Every AWS service has a CDK construct on day one.

## Updated Third-Party Risk Audit — Infrastructure

| Dependency | Maintainer | Risk | Verdict |
|---|---|---|---|
| ~~**SST Ion v3**~~ | SST team (~5 people) | Medium | **REMOVED** — replaced by AWS CDK (Python) |
| **AWS CDK (Python)** | AWS | None | KEEP — first-party, Python-native |

SST is now removed from the remaining risk items. TanStack Query is the only medium-risk dependency left in the entire stack.

## Updated Final Decision Table

| Decision | Choice |
|---|---|
| Project name | NovaScan |
| Frontend | Vite + React + Tailwind CSS v4 + shadcn/ui |
| Backend | AWS Lambda Powertools for Python + Pydantic |
| IaC | **AWS CDK (Python)** |
| OCR pipeline | Tiered (Textract + Nova) with A/B testing support for single Bedrock call |
| Database | DynamoDB (on-demand) |
| Analytics | pandas in Lambda |
| Vector DB (Phase 2) | S3 Vectors |
| Auth | Cognito email OTP (passwordless) |
| File upload | Presigned URLs via API Gateway HTTP API |
| Dev environment | Dev AWS account (`cdk deploy` with dev stage), DynamoDB Local for unit tests |
| Design system | Lumina Ledger / Digital Curator as-is |
| Region | us-east-1 |
| Budget | $25/month max |
| Chatbot (Phase 2) | Simple Bedrock API call first, evaluate AgentCore if needs grow |

**Third-party dependencies: React, Vite, Tailwind, shadcn/ui (copy-paste), TanStack Query, Pydantic, uv, Docker. Everything else is AWS-native.**

**Ready to update research.md, DR-001, and DR-002. Approve to proceed?**
# Phase 2 RFC — Clarification Research

**Context:** Pre-review research requested by the user on five areas of the Phase 2 specification RFC before providing formal feedback. This is NOT feedback — it's research to inform the review.

---

## 1. Low-Confidence Areas — Deep Research & Validation

### 1.1 Cognito USER_AUTH Flow with Auto-Signup

**Verdict: RFC hypothesis is PARTIALLY WRONG. `InitiateAuth` does NOT auto-create users.**

The USER_AUTH flow is choice-based authentication where Cognito presents available challenges (PASSWORD, EMAIL_OTP, WEB_AUTHN). However, `InitiateAuth` only works for **existing** users in the pool. Calling `InitiateAuth` for a non-existent user will fail (likely `UserNotFoundException` or `NotAuthorizedException` depending on pool settings).

**Correct flow for new users:**
```
1. Frontend: call SignUp(email, no password)     ← passwordless SignUp is supported when all conditions are met
2. Cognito: Pre-Sign-Up Lambda auto-confirms + auto-verifies email
3. Frontend: call InitiateAuth(USER_AUTH, email, PREFERRED_CHALLENGE=EMAIL_OTP)
4. Cognito: sends OTP to email
5. Frontend: call RespondToAuthChallenge(EMAIL_OTP, code)
6. Cognito: returns JWT tokens
```

**Frontend implementation pattern:**
```
try InitiateAuth → success → continue to OTP
catch UserNotFoundException → call SignUp → call InitiateAuth again → continue to OTP
```

This is a small code change. The Pre-Sign-Up Lambda auto-confirm + auto-verify pattern is well-documented. Passwordless SignUp (no password parameter) requires: passwordless sign-in active in both user pool AND app client, custom-built app with AWS SDK (not managed login).

**Confidence after research: HIGH** — the pattern is documented, just needs the `SignUp` → `InitiateAuth` two-step.

**Sources (by importance):**
1. [Authentication flows - Amazon Cognito](https://docs.aws.amazon.com/cognito/latest/developerguide/amazon-cognito-user-pools-authentication-flow-methods.html) — USER_AUTH flow details, passwordless challenges
2. [Signing up and confirming user accounts](https://docs.aws.amazon.com/cognito/latest/developerguide/signing-up-users-in-your-app.html) — passwordless SignUp without password, Pre-Sign-Up auto-confirm
3. [Authentication with Amazon Cognito user pools](https://docs.aws.amazon.com/cognito/latest/developerguide/authentication.html) — end-to-end passwordless flow
4. [Implementing passwordless email authentication with Amazon Cognito](https://aws.amazon.com/blogs/mobile/implementing-passwordless-email-authentication-with-amazon-cognito/) — AWS blog with implementation walkthrough
5. [InitiateAuth API Reference](https://docs.aws.amazon.com/cognito-user-identity-pools/latest/APIReference/API_InitiateAuth.html) — API parameters and error responses

---

### 1.2 CDK PythonFunction Bundling with uv

**Verdict: RESOLVED. Native uv support was merged into CDK.**

The `@aws-cdk/aws-lambda-python-alpha` construct now has native uv support, merged via [PR #33880](https://github.com/aws/aws-cdk/pull/33880) (closed as completed). When a `uv.lock` file is detected, CDK uses `uv pip compile` to generate a requirements.txt, which pip then installs during Docker bundling.

**Caveat:** The actual `pip install` step still uses pip, not `uv pip install`. So uv's speed advantage is limited to the lockfile resolution phase, not the actual installation. For a project this size, this is negligible.

**Fallback still valid:** If issues arise, `Code.fromAsset` with `uv pip install --target` pre-build remains a viable escape hatch. A third-party construct [uv-python-lambda](https://github.com/fourTheorem/uv-python-lambda) by fourTheorem is also available for full uv-native bundling.

**Confidence after research: HIGH** — native support is merged and released.

**Sources (by importance):**
1. [aws-lambda-python-alpha: Support uv - Issue #31238](https://github.com/aws/aws-cdk/issues/31238) — feature request, closed as completed
2. [aws-lambda-python-alpha README](https://docs.aws.amazon.com/cdk/api/v2/docs/aws-lambda-python-alpha-readme.html) — current documentation
3. [aws-lambda-python-alpha: uv support for lambda layer - Issue #35153](https://github.com/aws/aws-cdk/issues/35153) — Layer support still open
4. [aws-lambda-python-alpha: Support uv lockfile - Issue #32413](https://github.com/aws/aws-cdk/issues/32413) — related lockfile issue

---

### 1.3 Step Functions Parallel State Partial Failure

**Verdict: RFC is CORRECT. If any branch fails, the entire Parallel state fails and all branches are stopped.**

From the official docs: *"If any branch fails, because of an unhandled error or by transitioning to a Fail state, the entire Parallel state is considered to have failed and all its branches are stopped."*

**Critical caveat:** When a branch is stopped, **invoked Lambda functions continue to run** and activity workers are not stopped. Only the state machine branch tracking stops.

**Mitigation — two viable patterns:**

**Pattern A (recommended): Catch within each branch**
Each Task state within a branch has its own `Catch` block that routes to a "branch succeeded with error" Pass state instead of letting the error propagate. The branch always completes, returning either a success result or an error payload.

```json
{
  "TextractExtract": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:...:textract_extract",
    "Catch": [{
      "ErrorEquals": ["States.ALL"],
      "ResultPath": "$.error",
      "Next": "TieredFailed"
    }],
    "Next": "NovaStructure"
  },
  "TieredFailed": {
    "Type": "Pass",
    "Result": { "status": "failed" },
    "End": true
  }
}
```

**Pattern B: Catch on the Parallel state itself**
A single `Catch` on the Parallel state handles any branch failure. Less granular — you lose the successful branch's output when the Parallel state fails.

**Recommendation for NovaScan:** Pattern A. Each branch should never throw — always return a result (success or failure payload). The Finalize Lambda then inspects both results and acts accordingly (tiered success + single fail = confirmed).

**Confidence after research: HIGH** — well-documented behavior, Pattern A is standard.

**Sources (by importance):**
1. [Parallel workflow state - AWS Step Functions](https://docs.aws.amazon.com/step-functions/latest/dg/state-parallel.html) — official behavior and Catch/Retry fields
2. [Handling errors in Step Functions workflows](https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html) — Retry/Catch patterns
3. [Implementing patterns that exit early out of a parallel state](https://aws.amazon.com/blogs/compute/implementing-patterns-that-exit-early-out-of-a-parallel-state-in-aws-step-functions/) — advanced parallel patterns
4. [Handling error conditions tutorial](https://docs.aws.amazon.com/step-functions/latest/dg/tutorial-handling-error-conditions.html) — step-by-step error handling

---

### 1.4 Textract AnalyzeExpense Image Size Limits

**Verdict: RFC is CORRECT. Sync API handles up to 10MB. No differences from other sync APIs.**

**Confirmed limits for AnalyzeExpense (synchronous):**

| Constraint | Limit |
|-----------|-------|
| Max file size | 10 MB (in memory) |
| Max pages | 1 (sync only) |
| Formats | JPEG, PNG, PDF, TIFF |
| Max resolution | 10,000 px on any side |
| Min text height | 15 px (8pt @ 150 DPI) |
| TPS (us-east-1, us-west-2) | **5 TPS** |
| TPS (us-east-2) | 1 TPS |
| TPS (other regions) | 1 TPS |

**Key finding: AnalyzeExpense has the SAME file size limits as other sync APIs** (AnalyzeDocument, DetectDocumentText). The 10MB limit applies uniformly. The only difference is TPS — AnalyzeExpense gets 5 TPS in primary regions vs 10-25 TPS for AnalyzeDocument/DetectDocumentText.

**For async (StartExpenseAnalysis):** 500MB max, 3000 pages max, same 5 TPS in primary regions. But receipt images are single-page, so async offers no benefit on the file size front.

**Confidence after research: HIGH** — limits confirmed from official quotas page.

**Sources (by importance):**
1. [Amazon Textract endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/textract.html) — TPS per API per region
2. [Set Quotas in Amazon Textract](https://docs.aws.amazon.com/textract/latest/dg/limits-document.html) — file size, format, resolution limits
3. [AnalyzeExpense API Reference](https://docs.aws.amazon.com/textract/latest/dg/API_AnalyzeExpense.html) — API specification
4. [Quotas in Amazon Textract](https://docs.aws.amazon.com/textract/latest/dg/limits.html) — quota overview page

---

### 1.5 Cloudflare DNS-Only Mode for CloudFront

**Verdict: RFC is CORRECT. Cloudflare proxy must be OFF (DNS-only / gray cloud).**

**Why it conflicts:** When Cloudflare's proxy is ON (orange cloud), it terminates TLS and re-issues requests from Cloudflare IPs. CloudFront sees Cloudflare's IP, not the end user's. More critically:
- **CNAME verification fails** — CloudFront/ACM validates domain ownership by resolving the CNAME, but Cloudflare's proxy returns Cloudflare IPs instead of the target CNAME value
- **SSL conflicts** — both Cloudflare and CloudFront try to terminate TLS, causing certificate mismatches
- **CNAME flattening** — Cloudflare's CNAME flattening (on by default for root domains) converts CNAME to A records, breaking CloudFront's alternate domain validation

**Required configuration:**
1. CNAME record pointing `subdomain.example.com` → CloudFront distribution domain (e.g., `d1234.cloudfront.net`)
2. Proxy status: **DNS only** (gray cloud icon)
3. If using root domain: disable CNAME flattening for this record (or use a subdomain, which NovaScan already does)
4. SSL/TLS mode in Cloudflare: **Full (strict)** if proxy were on, but since it's off this doesn't matter

**Confidence after research: HIGH** — well-documented, straightforward configuration.

**Sources (by importance):**
1. [Use custom URLs by adding alternate domain names (CNAMEs) - CloudFront](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/CNAMEs.html) — CloudFront CNAME requirements
2. [Cannot verify a domain with CNAME - Cloudflare DNS docs](https://developers.cloudflare.com/dns/manage-dns-records/troubleshooting/cname-domain-verification/) — proxy mode causes verification failure
3. [CNAME setup (Partial) - Cloudflare DNS docs](https://developers.cloudflare.com/dns/zone-setups/partial-setup/) — DNS-only mode setup
4. [How can I use CloudFront with a root domain name? - AWS re:Post](https://repost.aws/questions/QUuXt7AVTxSGKUAkgz0pNEcQ/how-can-i-use-cloudfront-with-a-root-domain-name)

---

### 1.6 pandas in Lambda Cold Start

**Verdict: RFC concern is VALID but mitigatable. Lambda SnapStart for Python is now GA.**

**The problem:** pandas + numpy adds ~50-70MB to the Lambda deployment package. Cold start with these dependencies is 2-5 seconds. At personal usage (<20 users), cold starts happen on most invocations since the Lambda is idle between uses.

**Mitigation — Lambda SnapStart for Python (GA since late 2024):**
- Initializes the function ahead of time, takes a memory snapshot, caches it
- Subsequent cold starts resume from the cached snapshot instead of re-initializing
- Reduces pandas/numpy cold start from ~2-5s to **sub-second**
- Available for Python 3.12+ in 23+ regions
- **No provisioned concurrency needed** — SnapStart is a simpler, cheaper solution
- Just add `SnapStart: { ApplyOn: "PublishedVersions" }` to the Lambda config

**Alternative approaches (if SnapStart isn't desired):**
1. **Don't use pandas at all** — for the dashboard summary endpoint, write aggregation logic in pure Python with `decimal` module. The data volumes (<10K receipts) don't warrant pandas
2. **Use a Lambda Layer** — put pandas in a layer; helps with deployment size but not cold start
3. **Use lighter alternatives** — `polars` (faster, smaller than pandas), or just raw Python dicts/lists for simple aggregations

**Recommendation:** For the dashboard Lambda (the only place pandas is used), pure Python aggregation is simpler and avoids the dependency entirely. If pandas is genuinely needed later, SnapStart solves the cold start.

**Confidence after research: HIGH** — SnapStart for Python is GA and specifically mentions pandas as a target use case.

**Sources (by importance):**
1. [AWS Lambda SnapStart for Python and .NET functions is now generally available](https://aws.amazon.com/blogs/aws/aws-lambda-snapstart-for-python-and-net-functions-is-now-generally-available/) — GA announcement, mentions pandas specifically
2. [Improving startup performance with Lambda SnapStart](https://docs.aws.amazon.com/lambda/latest/dg/snapstart.html) — official docs
3. [Maximize Lambda SnapStart performance](https://docs.aws.amazon.com/lambda/latest/dg/snapstart-best-practices.html) — best practices for Python
4. [Understanding and Remediating Cold Starts](https://aws.amazon.com/blogs/compute/understanding-and-remediating-cold-starts-an-aws-lambda-perspective/) — cold start analysis
5. [Performance Optimization - Powertools for AWS Lambda (Python)](https://docs.aws.amazon.com/powertools/python/latest/build_recipes/performance-optimization/) — Powertools-specific optimization

---

## 2. Single Lambda Monolith — Detailed Tradeoff Analysis

### How It Works

Lambda Powertools provides an `APIGatewayHttpResolver` (for HTTP API) that maps HTTP methods + paths to handler functions via decorators:

```python
from aws_lambda_powertools.event_handler import APIGatewayHttpResolver
from aws_lambda_powertools import Logger, Tracer, Metrics

app = APIGatewayHttpResolver()
logger = Logger()
tracer = Tracer()

@app.get("/api/receipts")
@tracer.capture_method
def list_receipts():
    user_id = app.current_event.request_context.authorizer.claims["sub"]
    # ... query DynamoDB
    return {"receipts": [...]}

@app.post("/api/receipts/upload-urls")
@tracer.capture_method
def create_upload_urls():
    body = app.current_event.json_body
    # ... generate presigned URLs
    return {"receipts": [...]}, 201

@app.get("/api/receipts/<receipt_id>")
@tracer.capture_method
def get_receipt(receipt_id: str):
    # ... fetch receipt
    return {"receipt": {...}}

@logger.inject_lambda_context
@tracer.capture_lambda_handler
@metrics.log_metrics
def lambda_handler(event, context):
    return app.resolve(event, context)
```

For code organization, the `Router` class splits routes across files:
```
backend/src/
  handlers/
    receipts.py      # receipt CRUD routes
    categories.py    # category routes
    dashboard.py     # dashboard/transactions routes
  app.py             # main handler, includes all routers
```

### Tradeoffs

| Dimension | Single Lambda (Monolith) | Function-per-Route |
|-----------|------------------------|--------------------|
| **Maintainability** | All code in one package, organized via Router modules. Becomes unwieldy at ~20-30 routes / ~5K LOC. NovaScan has 11 routes — well within comfort zone. | Each function is small and focused. But shared code (models, DB helpers, auth) must be extracted into a layer or shared package. |
| **Observability** | Per-route metrics/traces via Powertools decorators (`@tracer.capture_method`). CloudWatch logs include route info. One log group to search. | Separate log groups per function. Easier to isolate one route's logs. But correlating a user request across functions is harder. |
| **Performance** | One larger package = slightly longer cold start (~500ms-1s). But once warm, serves all routes. At <20 users, the Lambda is cold most of the time anyway. | Smaller per-function packages = faster individual cold starts. But if user hits 3 routes in a session, they may trigger 3 cold starts vs 1. |
| **Deployment** | One deploy updates all routes. Higher blast radius — a bug in one route breaks the whole Lambda. Mitigated by tests. | Per-route deploys. Lower blast radius. But CDK deploy of 11 Lambdas is slower, and managing 11 functions is operationally noisy. |
| **Cost** | Identical. Lambda charges per invocation + duration regardless of function count. No difference for the same workload. | Same cost, but each function has its own concurrency reservation by default, which can be wasteful at low volume. |
| **IAM Permissions** | One IAM role with all permissions (DynamoDB, S3, etc.). Broader than needed for any single route. | Fine-grained: upload function gets S3 + DynamoDB write, dashboard function gets DynamoDB read only. Better security posture. |
| **Developer Experience** | Simple local testing, one `sam local start-api` or direct invocation. Easy to reason about the whole API. | Need to run/test each function independently. More config files, more CDK constructs, more IAM roles. |

### Why It's Right for NovaScan

1. **11 routes** — well below the 20-30 route threshold where monoliths get awkward
2. **Single developer** — no team coordination needed for separate deployments
3. **<20 users** — cold start optimization is irrelevant; the Lambda is cold on nearly every request anyway
4. **Shared dependencies** — all routes need DynamoDB, Pydantic models, auth context. Extracting shared code into layers is unnecessary complexity
5. **Powertools Router** — gives you modular code organization (receipts.py, categories.py, dashboard.py) without the operational cost of separate functions

### When to Split

Split when you see **any** of these signals:
- Package size exceeds 250MB (Lambda limit) or cold start exceeds 5s
- One route has fundamentally different scaling needs (e.g., dashboard needs provisioned concurrency but upload doesn't)
- Team grows and different people own different routes
- A route needs different IAM permissions for compliance
- Deployment blast radius becomes an actual problem (not theoretical)

**Sources:**
1. [REST API - Powertools for AWS Lambda (Python)](https://docs.aws.amazon.com/powertools/python/latest/core/event_handler/api_gateway/) — routing, Router class, observability integration
2. [Powertools for AWS Lambda](https://aws.amazon.com/powertools-for-aws-lambda/) — official overview
3. [Tutorial - Powertools for AWS Lambda (Python)](https://docs.aws.amazon.com/powertools/python/latest/tutorial/) — end-to-end example

---

## 3. DynamoDB GSIs — What They Offer and When You Need Them

### What a GSI Does

A GSI creates an **alternative key structure** over your table. You define a new partition key (and optionally sort key) from existing attributes. DynamoDB automatically maintains the index — when items are written to the base table, matching items are projected into the GSI.

### What GSIs Would Offer NovaScan

| Use Case | Without GSI (current) | With GSI |
|----------|----------------------|----------|
| **Receipts by date range** | Query `PK=USER#123, SK begins_with RECEIPT#`, return all receipts, filter by `receiptDate` in Lambda | GSI: PK=`USER#123`, SK=`receiptDate`. Query only returns receipts in the date range. |
| **Receipts by category** | Same query-all-then-filter | GSI: PK=`USER#123`, SK=`category#receiptDate`. Query returns only matching category. |
| **Receipts by status** | Same query-all-then-filter | GSI: PK=`USER#123`, SK=`status#createdAt`. Query returns only `processing` or `failed`. |
| **Cross-user admin query** | Not possible without scan | GSI: PK=`category`, SK=`receiptDate`. Query all receipts in a category across users. (Not needed for NovaScan — no admin.) |

### Cost Math — Filter in Lambda vs GSI

**Scenario: User has 5,000 receipts, wants to see only "Groceries" (500 receipts)**

**Without GSI (query + filter in Lambda):**
- Query returns 5,000 items × ~1KB each = 5MB of data read
- Eventually consistent: 5,000 KB / 4 KB = 1,250 RCUs × 0.5 = 625 RCUs
- On-demand: 625 × $0.25/1M = **$0.000156 per query**
- Lambda filters to 500 items, returns them

**With GSI (category index):**
- Query returns 500 items × ~1KB each = 500KB of data read
- 500 KB / 4 KB = 125 RCUs × 0.5 = ~63 RCUs
- On-demand: 63 × $0.25/1M = **$0.000016 per query** (10x cheaper)
- BUT: every write to the base table that touches `category` costs an additional write to the GSI

**Write cost amplification:**
- Each receipt create/update = 1 base write + 1 GSI write (if indexed attribute changes)
- On-demand: $1.25 per million writes × 2 = effectively doubles write cost for indexed attributes

**At NovaScan's scale (~100 receipts/month, ~50 queries/month):**
- Extra query cost without GSI: ~$0.008/month
- Extra write cost with GSI: ~$0.000125/month
- **Both are essentially $0.** The cost difference is irrelevant.

### When GSIs Become Necessary

| Signal | Threshold |
|--------|----------|
| Query returns too much data, Lambda times out | >100K items in a partition |
| Filter ratio is extreme (return 10 items from 50K) | <1% selectivity |
| Need cross-partition queries (admin views, analytics) | Multi-user aggregation |
| API latency matters (P99 query time) | When filter-in-Lambda adds >500ms |
| DynamoDB read costs become significant | >$10/month on reads |

### Recommendation

**No GSIs for MVP is the correct call.** At <10K receipts per user:
- Query + filter is fast (single-digit ms for DynamoDB, plus Lambda filter time)
- Cost is negligible either way
- Adding GSIs later is a non-breaking change (just add the GSI, no data migration)

**Add GSIs when:** You hit >50K receipts per user, or you add multi-user admin features, or API latency on filtered queries becomes noticeable.

**Sources:**
1. [Using Global Secondary Indexes in DynamoDB](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/GSI.html) — GSI fundamentals, projections, cost model
2. [General guidelines for secondary indexes](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/bp-indexes-general.html) — when to use, design best practices
3. [How to use DynamoDB GSIs to improve query performance and reduce costs](https://aws.amazon.com/blogs/database/how-to-use-dynamodb-global-secondary-indexes-to-improve-query-performance-and-reduce-costs/) — filter pattern vs GSI analysis
4. [How to design Amazon DynamoDB global secondary indexes](https://aws.amazon.com/blogs/database/how-to-design-amazon-dynamodb-global-secondary-indexes/) — GSI design patterns

---

## 4. Synchronous Textract and Bulk Upload

### The Throttling Problem

AnalyzeExpense sync API has **5 TPS** in us-east-1/us-west-2 (1 TPS in other regions). NovaScan allows bulk upload of up to 10 receipts. Each upload triggers a separate Step Functions execution, each calling AnalyzeExpense.

If a user uploads 10 receipts simultaneously:
- 10 Step Functions executions start within seconds (EventBridge triggers on each S3 ObjectCreated)
- Each execution calls AnalyzeExpense
- At 5 TPS, only 5 can succeed per second → the other 5 get `ProvisionedThroughputExceededException`

### Mitigation for MVP — Step Functions Retry

Step Functions has built-in retry with exponential backoff. This is the simplest solution:

```json
{
  "TextractExtract": {
    "Type": "Task",
    "Resource": "arn:aws:lambda:...:textract_extract",
    "Retry": [{
      "ErrorEquals": ["ProvisionedThroughputExceededException", "ThrottlingException"],
      "IntervalSeconds": 2,
      "MaxAttempts": 3,
      "BackoffRate": 2.0
    }],
    "Next": "NovaStructure"
  }
}
```

With jitter and backoff, 10 concurrent receipts would complete within ~10-15 seconds. Acceptable for a personal app.

### Why NOT Async for MVP

The async alternative (`StartExpenseAnalysis` → poll/SNS callback) adds:
- SNS topic for completion notifications
- Either polling logic or an SNS → Lambda → update DynamoDB callback chain
- Task token management if using Step Functions wait-for-callback
- Same 5 TPS limit anyway — async doesn't give you more throughput

**The only benefit of async is multi-page document support (up to 3000 pages).** Receipts are single-page images, so this is irrelevant.

### If Bulk Gets Larger Later (>10 receipts)

For future scaling beyond 10, a queue-based approach:
1. `POST /api/receipts/upload-urls` writes receipt records and sends messages to an SQS queue
2. SQS triggers a Lambda with `MaximumConcurrency: 3` (stays under 5 TPS)
3. That Lambda starts Step Functions executions at a controlled rate

But this is over-engineering for a personal MVP with a 10-file batch limit.

### Recommendation

**Keep sync AnalyzeExpense + Step Functions retry for MVP.** The 10-file limit + 5 TPS + retry/backoff = all receipts processed within 15 seconds. Add SQS-based throttling only if the batch limit increases or throttling becomes a real problem.

**Sources:**
1. [Amazon Textract endpoints and quotas](https://docs.aws.amazon.com/general/latest/gr/textract.html) — 5 TPS for AnalyzeExpense in us-east-1/us-west-2
2. [Handling Connection Errors - Amazon Textract](https://docs.aws.amazon.com/textract/latest/dg/handling-errors.html) — throttling behavior, retry guidance
3. [Modifying Default Quotas in Amazon Textract](https://docs.aws.amazon.com/textract/latest/dg/limits-quotas-explained.html) — how to request quota increases
4. [AnalyzeExpense API Reference](https://docs.aws.amazon.com/textract/latest/dg/API_AnalyzeExpense.html) — sync API specification
5. [StartExpenseAnalysis API Reference](https://docs.aws.amazon.com/textract/latest/dg/API_StartExpenseAnalysis.html) — async alternative

---

## 5. Pipeline Ranking Function

### Current Design (from SPEC)

Both pipelines execute in parallel via Step Functions Parallel state. Both results are stored:
- `USER#123 | RECEIPT#01HQ#PIPELINE#tiered` — with `extractedData`, `confidence`, `processingTimeMs`, `modelId`
- `USER#123 | RECEIPT#01HQ#PIPELINE#single` — same structure

The Finalize Lambda currently just picks the tiered pipeline result to populate the receipt record. The single pipeline result is stored but ignored.

### Proposed Ranking Function Design

**Yes, this is feasible and adds minimal complexity.** The Parallel state already waits for both branches. Add a ranking step between Parallel and Finalize:

```
Parallel
  ├── Tiered Pipeline (with Catch → return error payload)
  └── Single Pipeline (with Catch → return error payload)
↓
RankResults (new Lambda)
↓
Finalize (updated to use ranking decision)
```

**Ranking signals (in priority order):**

| Signal | Weight | Logic |
|--------|--------|-------|
| **Pipeline succeeded** | Must-have | Failed pipeline gets score 0 |
| **Confidence score** | High | Direct from extraction output (0.0-1.0) |
| **Field completeness** | High | Count of non-null fields: merchant, date, total, subtotal, tax, line items |
| **Line item count** | Medium | More line items = likely more accurate extraction |
| **Total consistency** | Medium | Does `sum(line items) + tax ≈ total`? If yes, boost score |
| **Processing time** | Low | Tiebreaker — faster pipeline preferred (less likely to have timed out) |

**RankResults Lambda pseudocode:**
```python
def rank(tiered_result, single_result):
    scores = {}
    for name, result in [("tiered", tiered_result), ("single", single_result)]:
        if result.get("status") == "failed":
            scores[name] = 0
            continue
        data = result["extractedData"]
        score = data["confidence"] * 40                          # 0-40 points
        score += count_non_null_fields(data) / 10 * 30           # 0-30 points
        score += min(len(data.get("lineItems", [])), 20) / 20 * 20  # 0-20 points
        score += 10 if totals_consistent(data) else 0            # 0-10 points
        scores[name] = score

    selected = max(scores, key=scores.get)
    return {
        "selectedPipeline": selected,
        "scores": scores,
        "tieredResult": tiered_result,
        "singleResult": single_result
    }
```

### Schema Changes

Add to the **Receipt** entity:

| Attribute | Type | Description |
|-----------|------|-------------|
| `selectedPipeline` | S | `tiered` or `single` — which pipeline's data is displayed |
| `pipelineScores` | M | `{ "tiered": 85.5, "single": 72.3 }` — ranking scores for debugging |

The Pipeline Result entities already have `confidence`, `processingTimeMs`, and `modelId`. No changes needed there.

### User Override

Add to `PUT /api/receipts/{id}`:
```json
{
  "selectedPipeline": "single"  // user can switch to the other pipeline's result
}
```

When `selectedPipeline` changes, the Finalize-like logic re-populates the receipt's display fields (merchant, total, line items, etc.) from the newly selected pipeline's `extractedData`.

### API Impact

The existing `GET /api/receipts/{id}/pipeline-results` endpoint already returns both results. Add `selectedPipeline` and `scores` to the response so the frontend can show which was auto-selected and why.

### Complexity Assessment

- **RankResults Lambda:** ~50 lines of Python, straightforward scoring logic
- **Schema changes:** 2 new attributes on receipt entity
- **Finalize update:** Read `selectedPipeline` from ranking output instead of hardcoding `tiered`
- **API change:** Add `selectedPipeline` to PUT receipts, add scores to pipeline-results endpoint
- **Frontend:** Optional "switch pipeline" button on receipt detail page

**Verdict: Worth including in MVP.** The complexity is low (~1-2 hours of additional work in M3), and it makes the dual-pipeline architecture actually useful instead of just storing data you never look at. Without ranking, the single pipeline is pure cost with no benefit.

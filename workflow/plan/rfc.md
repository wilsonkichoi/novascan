# Phase 3 RFC — Task Decomposition Rationale

**Date:** 2026-03-27
**Status:** Awaiting human review

---

## Overview

Decomposed 6 milestones into **44 tasks** (32 implementation, 11 test, 1 deployment verification) across **24 waves**. Average ~7 tasks per milestone. M1 is the largest (12) because it establishes all three project foundations (CDK, backend, frontend) in parallel.

---

## Key Decomposition Decisions

### 1. CDK Scaffolding Creates All Construct Stubs

**Decision:** Task 1.1 creates the full CDK project including stub files for all 5 constructs (storage, auth, api, pipeline, frontend) and wires them into the stack file.

**Why:** If each construct task also modified the stack file (`novascan_stack.py`), those tasks would share mutable state and couldn't run in parallel. By pre-creating stubs, each subsequent construct task only modifies its own construct file — enabling true parallelism in Wave 2.

**Trade-off:** Task 1.1 is slightly larger, but it's still well under 200 lines. The parallelism payoff across 4 construct tasks justifies it.

### 2. OCR-AI Pipeline Lambdas Combined into One Task

**Decision:** Task 3.2 implements both `textract_extract` and `nova_structure` Lambdas together.

**Why:** These two Lambdas are sequentially connected in the OCR-AI pipeline (Textract output feeds into Nova). While they're separate Lambda functions with no code imports between them, they share the same pipeline context and the nova_structure Lambda's input format depends on Textract's output format. Implementing them together ensures the interface is consistent.

**Trade-off:** Task 3.2 is ~200 lines across 2 files. Below the 500-line threshold and still a single concern ("OCR-AI extraction pipeline").

### 3. API + Frontend CDK Constructs Combined (Task 1.7)

**Decision:** The API Gateway construct and CloudFront construct are implemented in the same task.

**Why:** Both are "serving layer" infrastructure with tight CDK composition (the API construct needs Cognito from auth, the frontend construct needs S3 from storage). Splitting them would create two very small tasks (~80 lines each). Combined, they're ~160 lines and share the same verification step (`cdk synth`).

**Trade-off:** Single task touches 3 files across infra/ and backend/. Acceptable since the files are in different directories with no overlap.

### 4. Category Constants Bundled with Receipt CRUD (Task 4.1)

**Decision:** The predefined category taxonomy constants module is created in the same task as the receipt CRUD endpoints.

**Why:** The receipt PUT endpoint needs to validate category slugs against the taxonomy. Creating the constants module separately would produce a task too small to justify (~50 lines). Bundling them keeps a natural data dependency within a single task.

**Trade-off:** Task 4.1 is the largest in M4 (~250 lines across 3 files). Still under the 500-line threshold.

### 5. Test Tasks Grouped by Milestone Layer

**Decision:** Each milestone has 2 test tasks: one for backend API tests, one for frontend UI tests. Tests are not split per-endpoint or per-component.

**Why:** Individual endpoint/component tests would create many tiny test tasks (3-4 test files each). Grouping by layer allows the test author to design a cohesive test suite with shared fixtures and setup. The test author still only sees the spec/contracts — not the implementation.

**Trade-off:** Test tasks are larger (5-6 test files each), but they test related functionality and share test infrastructure.

---

## Wave Grouping Rationale

### Milestone 1 Waves (5 waves)

| Wave | Tasks | Rationale |
|------|-------|-----------|
| 1 | 1.1, 1.2, 1.3 | Zero dependencies. Three project foundations (CDK/backend/frontend) are independent codebases. |
| 2 | 1.4, 1.5, 1.6 | 1.4 and 1.5 modify different CDK construct files (enabled by stub approach). 1.6 is pure frontend code — different component, no shared state. |
| 3 | 1.7, 1.8 | 1.7 depends on storage+auth constructs. 1.8 depends on auth module. Different components, no shared state. |
| 4 | 1.9, 1.10, 1.11 | 1.9 (app shell) depends on login page. 1.10 and 1.11 are test tasks — depend on their respective implementation tasks. All three are independent. |
| 5 | 1.12 | Integration/deploy depends on everything. Sequential by nature. |

### Milestones 2-6

Follow the same pattern: backend data layer → API endpoints → frontend integration → tests. Backend and frontend tasks in the same wave when they belong to different components with no shared state.

---

## Low-Confidence Areas

### 1. Pre-Sign-Up Lambda + Cognito Group Assignment

**Concern:** The spec says the Pre-Sign-Up Lambda auto-confirms the user, auto-verifies email, AND adds the user to the `user` Cognito group. However, Pre-Sign-Up triggers typically can only set `autoConfirmUser` and `autoVerifyEmail` flags — they cannot call `adminAddUserToGroup` because the user doesn't exist yet when the trigger fires.

**Risk:** Group assignment may need to be a Post-Confirmation trigger instead, or handled by a separate mechanism.

**Mitigation:** Task 1.5 should investigate the correct trigger timing. If Pre-Sign-Up can't assign groups, the task should use Post-Confirmation and document the deviation. Low impact — the trigger type changes, but the behavior is the same.

### 2. EventBridge Pipes MaxConcurrency Configuration

**Concern:** EventBridge Pipes `MaximumConcurrency` is a relatively new feature. CDK support may be limited to L1 constructs (`CfnPipe`) rather than higher-level constructs.

**Risk:** Task 3.5 may need to use L1 CloudFormation constructs for Pipes, which is more verbose but functionally equivalent.

**Mitigation:** Acceptable trade-off. L1 constructs are stable and well-documented. This doesn't affect the pipeline behavior.

### 3. Transactions `totalCount` with Cursor Pagination

**Concern:** The spec requires `totalCount` (total matching before pagination) in the transactions response. DynamoDB doesn't provide a count with paginated queries. Computing it requires either a separate Count query or scanning all results.

**Risk:** For a user with thousands of receipts, this could be slow. At MVP scale (~100 receipts/month), it's fine.

**Mitigation:** Task 5.2 should implement a separate Count query or use the `Select.COUNT` parameter. Document the scaling limitation. Acceptable at MVP scale.

### 4. S3 Event Notification + SQS in Separate Constructs

**Concern:** The receipts S3 bucket is created in the storage construct (Task 2.1), but the SQS queue that receives its events is in the pipeline construct (Task 3.5). S3 bucket notification configuration requires the SQS queue to exist.

**Risk:** The storage construct can't configure S3 notifications until the pipeline construct creates the SQS queue. This creates a cross-construct dependency.

**Mitigation:** Task 3.5 (pipeline construct) should configure the S3 notification by referencing the bucket from the storage construct. This is standard CDK cross-construct wiring. The notification is set up when the pipeline construct is added, not when the bucket is created. No issue, but noted for awareness.

---

## Summary Statistics

| Metric | Value |
|--------|-------|
| Total tasks | 44 |
| Implementation tasks | 32 |
| Test tasks | 11 |
| Deployment/verification tasks | 1 |
| Tasks per milestone (avg) | 7.3 |
| Tasks per milestone (range) | 4–12 |
| Max waves per milestone | 5 (M1) |
| Inline test tasks | 3 (M1 scaffolding) |


# feedback round 1

## pre-sign up lambda + cognito group assignment
- please elaborate with concrete examples. what is Pre-Sign-Up Lambda? what is Post-Confirmation trigger? 

## EventBridge Pipes MaxConcurrency Configuration
- please elaborate with concrete examples. what is L1 constructs (CfnPipe)? what is L1 CloudFormation constructs for Pipes and how does it help to configure MaxConcurrency?

## Transactions `totalCount` with Cursor Pagination
- does DynamoDB provide a count query? can we just make another query to get the count? would that be too slow or expensive? 

## S3 Event Notification + SQS in Separate Constructs
- looks like you have already addressed this concern in the mitigation section. why Low-Confidence?

## additional note
- when I work as software engineer, I usually add poc task for new technology or service to validate the plan would work before the actual implementation. the result is that I have the reference links to the official doc and simple working code (throwaway code) on specific services/APIs, which helps me to implement the actual feature quickly and correctly. does it make sense to add poc tasks in the plan? AI will perform the implementation, is this a useful appoach or waste of time/token for AI?

---

# AI response round 1

## Pre-Sign-Up Lambda + Cognito Group Assignment

*AI:* Here's the concrete breakdown:

**Pre-Sign-Up Lambda** — A Lambda function triggered by Cognito *before* the user record is created. Cognito passes an event, and the Lambda can modify the response to auto-confirm and auto-verify:

```python
# Pre-Sign-Up Lambda handler
def handler(event, context):
    event["response"]["autoConfirmUser"] = True
    event["response"]["autoVerifyEmail"] = True
    return event
```

This is the only thing Pre-Sign-Up can do: set flags on the response object. It **cannot** call `adminAddUserToGroup` because the user doesn't exist yet in the User Pool — the user record is created *after* the Pre-Sign-Up trigger returns.

**Post-Confirmation Lambda** — A Lambda triggered *after* the user record is created and confirmed. At this point the user exists, so you CAN call `adminAddUserToGroup`:

```python
# Post-Confirmation Lambda handler
import boto3

cognito = boto3.client("cognito-idp")

def handler(event, context):
    cognito.admin_add_user_to_group(
        UserPoolId=event["userPoolId"],
        Username=event["userName"],
        GroupName="user",
    )
    return event
```

**The concern:** The SPEC says the Pre-Sign-Up Lambda "adds user to `user` Cognito group." That's technically impossible in a Pre-Sign-Up trigger. The fix is straightforward — we need **two** Lambda triggers:
1. **Pre-Sign-Up** → auto-confirm + auto-verify email (flags only)
2. **Post-Confirmation** → add user to `user` group (API call)

Or we use a single Lambda for Post-Confirmation that does the group assignment, and rely on Cognito's `SignUp` with passwordless config for auto-confirm behavior. Either way, Task 1.5 will implement the correct trigger(s).

**Impact on plan:** Minimal. Task 1.5 already has the auth construct. It may produce 2 Lambda functions instead of 1, or a single Post-Confirmation Lambda that handles both. The CDK wiring is nearly identical. No task boundary changes needed.

**Recommendation:** Update the SPEC to say "Post-Confirmation Lambda assigns the `user` group" instead of Pre-Sign-Up. Keep Pre-Sign-Up for auto-confirm/auto-verify only. Task 1.5 acceptance criteria should verify both behaviors.

---

## EventBridge Pipes MaxConcurrency Configuration

*AI:* CDK has two levels of constructs:

- **L2 (high-level):** Idiomatic Python classes like `dynamodb.Table()`, `s3.Bucket()`. These have sensible defaults, typed props, and helper methods. Most CDK code uses L2.
- **L1 (low-level):** Direct 1:1 mappings to CloudFormation resources, prefixed with `Cfn`. Example: `CfnPipe` maps directly to `AWS::Pipes::Pipe`. Every CloudFormation property is exposed, but there are no convenience methods or defaults.

**The issue:** As of CDK, EventBridge Pipes has no L2 construct. There's only `CfnPipe` (L1). This means we write something like:

```python
# L2 construct (does NOT exist for Pipes):
# pipes.Pipe(self, "Pipeline", source=queue, target=sfn, max_concurrency=2)

# L1 construct (what we actually use):
from aws_cdk import aws_pipes as pipes

pipes.CfnPipe(self, "ReceiptPipeline",
    role_arn=pipe_role.role_arn,
    source=queue.queue_arn,
    source_parameters=pipes.CfnPipe.PipeSourceParametersProperty(
        sqs_queue_parameters=pipes.CfnPipe.PipeSourceSqsQueueParametersProperty(
            batch_size=1,
            maximum_batching_window_in_seconds=0,
        ),
    ),
    target=state_machine.state_machine_arn,
    target_parameters=pipes.CfnPipe.PipeTargetParametersProperty(
        step_function_state_machine_parameters=pipes.CfnPipe.PipeTargetStateMachineParametersProperty(
            invocation_type="FIRE_AND_FORGET",
        ),
    ),
    # MaxConcurrency is set here at the Pipe level:
    # This limits how many concurrent Step Functions executions can run
    log_configuration=...,  # optional
)
```

**MaxConcurrency** is a top-level property on `CfnPipe` (added in 2023). It caps how many target invocations run simultaneously. We set it to `pipelineMaxConcurrency` from `cdk.json` (default: 2) to stay under Textract's 5 TPS limit.

**Why this is low-confidence:** It's not that the feature doesn't exist — it's that L1 constructs are more verbose and require manual IAM role wiring (no `grant_*` methods). The implementation task (3.5) just needs to account for this verbosity. Not a blocker, just a different coding style than the rest of the CDK code.

**Impact on plan:** None. Task 3.5 already targets the pipeline construct. The L1 approach is ~30 lines more than an L2 would be, well within the 500-line budget.

---

## Transactions `totalCount` with Cursor Pagination

*AI:* Yes, DynamoDB has a `Select.COUNT` parameter for Query operations. Here's how it works:

```python
# Normal query (returns items):
response = table.query(
    KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("RECEIPT#"),
    FilterExpression=Attr("category").eq("groceries"),  # if filtered
    Limit=50,
)

# Count query (returns count only, no items):
response = table.query(
    KeyConditionExpression=Key("PK").eq(f"USER#{user_id}") & Key("SK").begins_with("RECEIPT#"),
    FilterExpression=Attr("category").eq("groceries"),  # same filters
    Select="COUNT",
)
total = response["Count"]
# NOTE: if results span multiple pages, you must loop through all pages summing Count
```

**Cost:** A Count query reads the same capacity units as a normal query — it scans the same items, it just doesn't return the data. For a user with 100 receipts/month, even a year's worth (1,200 items) is ~1,200 RCUs in eventual consistency mode (4KB per RCU). That's a fraction of a cent.

**Speed:** DynamoDB Count queries on a single partition key are fast. For 1,200 items it would be single-digit milliseconds. For 10,000+ items you'd need to paginate the count query itself (DynamoDB returns max 1MB per query), adding latency. Not a concern at MVP scale.

**The plan:** Task 5.2 will issue two parallel DynamoDB calls:
1. A paginated query (with `Limit` + `ExclusiveStartKey` for cursor) returning the current page of items
2. A Count query (with identical filters but `Select="COUNT"`) returning the total

Both queries hit the same partition key, so they're fast and cheap. The Count query adds negligible latency when run in parallel.

**Impact on plan:** None. This is a standard implementation pattern within Task 5.2.

---

## S3 Event Notification + SQS in Separate Constructs

*AI:* You're right — the mitigation fully addresses the concern. I was being overly cautious. This is standard CDK cross-construct wiring that every non-trivial CDK project uses. Removing it from the Low-Confidence section.

**Updated assessment:** This is a normal CDK pattern, not a risk. The pipeline construct receives the storage bucket as a parameter and configures the S3 notification. No special handling needed.

---

## POC Tasks for AI Implementation

*AI:* This is a good question. The short answer: **POC tasks are less valuable for AI but not zero value.** Here's the nuanced breakdown:

**Why POCs are less useful for AI:**
- AI already has broad knowledge of AWS APIs, SDK patterns, and CDK constructs from training data. It doesn't need to "learn" a new API by experimenting.
- The throwaway code pattern (write PoC → learn → throw away → rewrite properly) is a human learning optimization. AI doesn't retain learning between sessions — each task starts fresh regardless.
- Token cost of a PoC task + the real task is roughly 2x the cost of just the real task. The AI doesn't get faster on the second pass.

**Where POCs still help with AI:**
- **Validating assumptions in the plan.** If the RFC flags something as low-confidence (like "does CfnPipe support MaxConcurrency?"), a targeted PoC task that deploys a minimal stack and verifies the behavior catches problems *before* the real implementation task is blocked. This saves more tokens than it costs.
- **Complex integrations with underdocumented APIs.** If the AI's training data might be outdated (e.g., a feature was GA'd in 2025), a PoC that actually deploys and tests the feature confirms it works.

**Recommendation for this project:** Don't add blanket POC tasks. Instead, for the two genuinely uncertain items (Cognito Pre-Sign-Up group assignment and CfnPipe MaxConcurrency), the implementation tasks should include explicit acceptance criteria that verify the uncertain behavior. If the behavior doesn't work as expected, the task adjusts on the spot — which is effectively a PoC embedded in the real task. This avoids the 2x token cost while still catching issues.

If you want, I can add specific "verify this assumption" acceptance criteria to Tasks 1.5 and 3.5. That gets the validation benefit without separate tasks.


# feedback round 2

## Pre-Sign-Up Lambda + Cognito Group Assignment
- straightforward fix with two Lambda triggers is good

## EventBridge Pipes MaxConcurrency Configuration
- OK, use L1 construct as needed. don't fixate on 500 lines budget. (if there are 500 lines rule somewhere, please update it as a general guideline not a hard rule)

## dynamodb pagination
- OK, use cursor pagination with two parallel queries (one for items, one for count)

## POC Tasks for AI Implementation
- OK, no blanket POC tasks, but add specific acceptance criteria to verify uncertain behavior

## additional notes after review plan.md
- how the AI knows which aws profile, region, and account to use? How the AI knows if uv is setup and available? does it make sure the development environment is ready before starting the tasks?

### I also asked AI to review the plan.md against spec documents and here is what it found:
Cross-Reference Review: PLAN.md vs Spec Documents
Significant Issues
1. System Architecture Diagram is Stale
system-architecture.mmd shows separate LRank (Rank Results) and LFin (Finalize) Lambdas (lines 37-38), with flow SF → LRank → LFin → DDB. But the SPEC (Section 3), HANDOFF (M3 step 5), pipeline state machine diagram, and PLAN (Task 3.4) all consolidated ranking into the Finalize Lambda. The system architecture diagram also omits the LoadCustomCategories Lambda/step that the pipeline state machine diagram and SPEC both define. This diagram needs to be updated to match the final design.

2. Task 2.1 — Impossible S3 Event Notification
PLAN.md:290 says: "Receipts bucket has S3 event notification configuration for ObjectCreated events on receipts/ prefix (notification target configured later in M3)". You cannot create an S3 event notification without a destination. The SQS queue doesn't exist until M3 Task 3.5. This AC should either be removed from Task 2.1 and moved entirely to Task 3.5, or reworded to: "receipts bucket created; event notification deferred to M3."

3. GSI1SK for processing Receipts — Unresolved Design Gap
The SPEC defines GSI1SK = {receiptDate}#{ulid}. But receipts created at upload time (Task 2.3) have status=processing and no receiptDate yet — that's extracted later by the pipeline. This means either:

Processing receipts won't have GSI1 entries → invisible in GET /api/receipts (which Task 2.4 queries via GSI1)
GSI1SK needs a fallback value (e.g., createdAt when receiptDate is null)
The API contract explicitly says processing receipts should appear in the list with null merchant/total/category. Neither the SPEC nor the PLAN addresses how GSI1SK is set for processing receipts. This needs a decision — likely use createdAt as a fallback in GSI1SK and update it to receiptDate after processing.

4. User Profile Entity — Never Created
The SPEC (Section 5) defines a User Profile entity (PK=USER#{userId}, SK=PROFILE) with email, displayName, timestamps. But no task in the PLAN creates this record. The Pre-Sign-Up Lambda (Task 1.5) auto-confirms and adds to the user group, but doesn't write to DynamoDB. No API endpoint or pipeline step creates it either. Either:

Add profile creation to the Pre-Sign-Up Lambda (Task 1.5) — needs DynamoDB permissions
Add it to the first API call (lazy creation)
Decide it's unnecessary for MVP (email/sub available from JWT)

Minor Issues
5. HANDOFF.md M3 Step Numbering Gap
HANDOFF.md:83 — Steps jump from 9 to 11 (step 10 is missing). Cosmetic but worth fixing.

6. HANDOFF.md M3 Omits LoadCustomCategories
HANDOFF.md:79, M3 step 6 describes the state machine as "Parallel (Main + Shadow branches with Catch) → Finalize". Missing the LoadCustomCategories pre-step that the SPEC's state machine diagram and PLAN Task 3.5 both include. Should be: "LoadCustomCategories → Parallel (Main + Shadow with Catch) → Finalize".

7. RFC Key Decisions Section Stale on GSIs
rfc.md:17 still says "No Global Secondary Indexes for MVP." But the final SPEC added GSI1 (Receipts by Date). The RFC is marked "Approved (Round 5)" but the key decisions summary wasn't updated to reflect the GSI addition during feedback rounds. Could confuse someone reading it later.

8. /api/health Not in API Contracts
PLAN Task 1.7 defines a /api/health endpoint excluded from the authorizer. This endpoint isn't listed in api-contracts.md. Either add it to api-contracts.md or note it's an operational endpoint outside the formal contract.

9. msw Dependency Not in Frontend Scaffolding
SPEC Section 9 Test Configuration specifies msw (API mocking) for frontend tests. But PLAN Task 1.3 (Frontend Scaffolding) doesn't mention adding msw as a dev dependency. It would be picked up by test tasks later, but it's cleaner to list it in scaffolding.

What Looks Correct
All 6 milestones match between HANDOFF, SPEC, and PLAN, in the correct dependency order
All 12 API endpoints in api-contracts.md are covered by PLAN tasks (M2: upload-urls, list; M4: CRUD + categories + pipeline-results; M5: dashboard + transactions)
DynamoDB key schema (PK/SK, entity types, GSI1) is consistent between SPEC and PLAN tasks
Pipeline architecture (SQS → EventBridge Pipes → Step Functions → Parallel branches → Finalize) is consistent across SPEC, HANDOFF, pipeline state machine diagram, and PLAN
Auth flow (USER_AUTH, SignUp fallback, OTP, Pre-Sign-Up Lambda) is consistent across all documents
RBAC (3 Cognito groups, staff-only pipeline-results endpoint) is consistent
Category taxonomy (13 categories, custom categories in DynamoDB, pipeline integration) is consistent between category-taxonomy.md, SPEC, and PLAN tasks
Configuration keys in cdk.json (6 keys) match between SPEC, runbook, and PLAN Task 1.1
Wave structure in PLAN correctly respects task dependencies
Summary: 5 significant issues (diagram stale, impossible AC, GSI1SK gap, missing profile creation), 5 minor issues. The PLAN is otherwise well-structured and faithfully implements the spec. The GSI1SK gap (#3) is the most critical to resolve before implementation since it affects the core list endpoint.

The decision records agent confirmed all four DRs are consistent with the PLAN and SPEC. No additional issues found from the decision records — DR-001 (React), DR-002 (tiered pipeline + A/B), DR-003 (SQS + EventBridge Pipes), and DR-004 (Cognito Groups) are all faithfully reflected in the PLAN's task structure.

One minor note from DR-002: it mentions a pipeline_mode: "tiered" | "single" | "ab_split" config in DynamoDB, which was an early proposal. The final SPEC simplified this to defaultPipeline in cdk.json (always runs both, just controls which is main vs shadow). The PLAN correctly follows the final SPEC, not the DR's early proposal. No action needed — just noting the DR is slightly outdated relative to the final design, which is expected.

### another AI review 

  Here's my cross-reference review of PLAN.md against the spec, handoff, API contracts, diagrams, decisions, and taxonomy.

  Overall Verdict: Solid — well-structured, internally consistent

  The plan is well-organized with clear wave-based parallelism, proper dependency chains, and acceptance criteria that trace back to the spec. That said, I found several issues ranging from minor
  inconsistencies to a few real gaps:

  ---
  Issues Found

  1. DR-002 Architecture Drift (Medium)

  DR-002 describes an A/B testing architecture with a routing choice at the Step Functions entry point and a pipeline_mode DynamoDB config item ("tiered" | "single" | "ab_split" with percentage-based
  splits). The SPEC.md (Section 3) evolved this into the main/shadow parallel model where both pipelines always run, controlled by defaultPipeline in cdk.json.

  The PLAN correctly follows the SPEC (not DR-002), which is the right call — but DR-002 is now stale and misleading. Anyone reading the decision records would get a different mental model of how the
  pipeline works.

  Recommendation: Update DR-002 with an addendum noting the evolved design, or mark it superseded by the spec's parallel-always approach.

  2. Missing ranking.py in SPEC Project Structure (Minor)

  PLAN Task 3.4 creates backend/src/novascan/pipeline/ranking.py for the rank_results function. The SPEC's project structure tree (Section 9, line ~797) lists pipeline files but doesn't include
  ranking.py. The SPEC does describe ranking in Section 3 (Processing Flow), so the logic is spec'd — the file just wasn't listed in the directory tree.

  Impact: Low — the plan is correct to create this file; the spec tree is just incomplete.

  3. Missing LoadCustomCategories Lambda in Plan Task 3.5 (Medium)

  The SPEC's pipeline state machine diagram (Section 4) shows a LoadCustomCategories step before the Parallel state. Task 3.5's acceptance criteria correctly mention it. However, no task creates the
  Lambda handler for LoadCustomCategories. Task 3.5 describes the CDK construct assuming the Lambda exists, and Tasks 3.2–3.4 create textract_extract, nova_structure, bedrock_extract, and finalize — but
   not the custom categories loader.

  The SPEC's project structure also doesn't list a load_custom_categories.py file.

  Recommendation: Either:
  - Add a load_custom_categories.py Lambda in Task 3.4 or create a new sub-task under Wave 2
  - Or clarify that the Finalize Lambda handles this query (folding it into finalize.py) — but that contradicts the state machine diagram showing it as a separate step

  4. S3 Event Notification Timing (Minor)

  Task 2.1 says the receipts bucket has "S3 event notification configuration for ObjectCreated events on receipts/ prefix (notification target configured later in M3)." But S3 event notifications need a
   destination when created. You can't configure the filter prefix without a target.

  Recommendation: Don't configure the S3 event notification in Task 2.1. Configure it entirely in Task 3.5 when the SQS queue exists. The storage construct should just create the bucket; the pipeline
  construct adds the notification.

  5. GSI1SK Format for Date Filtering (Minor — Worth Verifying)

  SPEC defines GSI1SK = {receiptDate}#{ulid}. Task 2.4 says "Date range applied as KeyConditionExpression on GSI1SK". This works for BETWEEN queries but the key format means the sort is receiptDate
  first, then ULID within the same date. The startDate/endDate filter in the API contract uses YYYY-MM-DD, so the BETWEEN condition needs to be GSI1SK BETWEEN '{startDate}' AND '{endDate}~' (with tilde
  or similar high Unicode char to include all ULIDs on the end date).

  The SPEC mentions this at line 662 (GSI1SK BETWEEN {startDate} AND {endDate}~). The plan doesn't explicitly call this out in Task 2.4, which could lead to an off-by-one on the end date during
  implementation.

  Recommendation: Add a note in Task 2.4 acceptance criteria about the trailing ~ for end-date inclusivity.

  6. sortBy Complexity in Transactions (Minor)

  Task 5.2 accepts sortBy=amount and sortBy=merchant, but DynamoDB GSI1 only sorts by date+ULID. Sorting by amount or merchant requires fetching all matching records and sorting in-memory in Lambda. The
   SPEC acknowledges this is acceptable at MVP scale (line ~674), but the plan's Task 5.2 doesn't explicitly state that non-date sorts happen in-memory. This could confuse the implementing engineer.

  Recommendation: Add a note to Task 5.2 that sortBy=amount|merchant requires post-query in-memory sort.

  7. totalCount in Transactions Response (Minor)

  The API contract for GET /api/transactions returns totalCount — total matching transactions before pagination. With DynamoDB, getting a total count while also paginating requires either: (a) a SELECT
  COUNT query in addition to the data query, or (b) scanning all results to count and then paginating. Neither is cheap. Task 5.2 doesn't address how totalCount is computed.

  Recommendation: Add a note to Task 5.2 on the totalCount implementation strategy. At MVP scale with in-memory sorting already happening, you'll likely fetch all records anyway — so counting is free.
  But this should be explicit.

  8. Missing Receipt Delete Confirmation (Minor)

  Task 4.3 (Receipt Detail Page) lists receipt display but receipt delete with confirmation dialog is in the HANDOFF (line 101: "Receipt delete: confirmation dialog, hard delete") and SPEC Milestone 4
  acceptance criteria. Neither Task 4.3 nor Task 4.4 explicitly includes the delete button + confirmation dialog on the receipt detail page. Task 4.1 implements the DELETE API, but the frontend delete
  UI seems to fall through the cracks.

  Recommendation: Add delete button + confirmation dialog to Task 4.3 or Task 4.4's acceptance criteria.

  9. Missing Versioning on Receipts S3 Bucket (Potential)

  Task 2.1 mentions "versioning" for the receipts S3 bucket. SPEC Section 12 (Reliability) confirms "S3 versioning on receipt bucket." Good — this is consistent.

  10. HANDOFF Step 10 Missing (Numbering Gap)

  HANDOFF Milestone 3 skips from step 9 to step 11 (line 83). This appears to be a numbering typo in the HANDOFF, not a missing step. The plan covers all the actual content.

  11. Category Count: "13 predefined categories" (Verified)

  Task 4.6 says "all 13 predefined categories." Counting the taxonomy: Groceries & Food, Dining, Retail & Shopping, Automotive & Transit, Health & Wellness, Entertainment & Travel, Home & Utilities,
  Education, Pets, Gifts & Donations, Financial & Insurance, Office & Business, Other = 13. Correct.

  ---
  What's Well Done

  - Wave parallelism is well thought out — Tasks 1.1/1.2/1.3 run in parallel, 2.1/2.2 in parallel, 3.2/3.3/3.4 in parallel, 5.1/5.2 in parallel, 6.1/6.2 in parallel. No dependency violations.
  - Test tasks are separated from implementation tasks with "Do NOT read implementation" instructions — this prevents tests from being shaped by the code rather than the spec.
  - Acceptance criteria consistently reference the right spec sections and API contract endpoints.
  - The milestone ordering matches the HANDOFF exactly (M1→M2→M3→M4→M5→M6).
  - CDK construct boundaries (storage, auth, api, pipeline, frontend) match the SPEC's project structure.
  - Config keys in cdk.json (Task 1.1) match all 6 settings from SPEC Section 9.

  ---
  Summary of Action Items

  ┌─────┬──────────┬─────────────────────────────────────────────────────┬─────────────────────────────────────────────────┐
  │  #  │ Severity │                        Issue                        │                       Fix                       │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 1   │ Medium   │ DR-002 is stale vs actual spec                      │ Add superseded note to DR-002                   │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 3   │ Medium   │ No LoadCustomCategories Lambda handler task         │ Add Lambda or clarify it's folded into finalize │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 4   │ Minor    │ S3 event notification in Task 2.1 before SQS exists │ Move to Task 3.5                                │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 5   │ Minor    │ End-date inclusivity trick for GSI1SK               │ Add note to Task 2.4                            │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 6   │ Minor    │ In-memory sort for non-date sorts                   │ Add note to Task 5.2                            │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 7   │ Minor    │ totalCount computation strategy                     │ Add note to Task 5.2                            │
  ├─────┼──────────┼─────────────────────────────────────────────────────┼─────────────────────────────────────────────────┤
  │ 8   │ Minor    │ Receipt delete UI missing from frontend tasks       │ Add to Task 4.3                                 │
  └─────┴──────────┴─────────────────────────────────────────────────────┴─────────────────────────────────────────────────┘

  Items 1 and 3 are the most important. The rest are implementation notes that a good engineer would figure out, but it's better to be explicit in the plan.

---

# AI response round 2

## Feedback Round 2 Responses

### Pre-Sign-Up Lambda + Cognito Group Assignment

*AI:* Done. Task 1.5 updated:
- Renamed to "Auth Construct + Cognito Lambda Triggers"
- Now creates two Lambdas: `pre_signup.py` (auto-confirm + auto-verify only) and `post_confirmation.py` (calls `admin_add_user_to_group`)
- CDK construct wires both triggers to the User Pool
- Added verification AC: "Confirm Post-Confirmation trigger fires after user creation and that `admin_add_user_to_group` works within it."

### EventBridge Pipes MaxConcurrency Configuration

*AI:* Acknowledged. The 500-line threshold in the plan skill instructions is treated as a **general guideline**, not a hard rule. If a task is a single concern and exceeds 500 lines (e.g., L1 CfnPipe construct with manual IAM wiring), that's fine — the determining factor is whether the task is truly a single concern, not line count.

Task 3.5 updated with explicit note about L1 `CfnPipe` usage and a verification AC: "Confirm `CfnPipe` supports `MaximumConcurrency` as a top-level property."

### DynamoDB Pagination

*AI:* Done. Task 5.2 updated with explicit implementation notes:
- `sortBy=date` uses GSI1SK natively; `sortBy=amount|merchant` requires fetching all matching records + in-memory sort
- `totalCount` via parallel `Select="COUNT"` query for date-sorted results; derived from fetched set for in-memory sort cases

### POC Tasks

*AI:* Done. No separate POC tasks added. Instead, Tasks 1.5 and 3.5 now have explicit "Verify assumption" acceptance criteria that test the uncertain behavior during implementation.

### Development Environment Readiness

*AI:* Good catch. Added **Task 0.1: Development Environment Verification** as a prerequisite before any M1 tasks. It verifies:

- `uv --version` — Python toolchain available
- `node --version` — Node.js 22 LTS
- `aws sts get-caller-identity` — correct AWS account
- `aws configure get region` — target region set
- `docker --version` — needed for DynamoDB Local in tests
- Documents the verified account ID, region, and profile in PROGRESS.md

This task runs first and ensures the AI (and human) know which AWS environment they're targeting. The AI doesn't "know" the profile/region implicitly — it reads them from the environment or stack context. Task 0.1 makes this explicit and recorded.

---

## Cross-Reference Review Responses

Both AI reviews surfaced overlapping issues. Here's the consolidated action taken for each:

### 1. System Architecture Diagram is Stale (Significant)

*AI:* Acknowledged. The `system-architecture.mmd` diagram shows separate LRank and LFin Lambdas and omits LoadCustomCategories. This diagram needs to be updated to match the final SPEC (consolidated Finalize Lambda + LoadCustomCategories step). **Not updating the diagram in this phase** — it's a spec artifact, not a plan artifact. Noting it here for the build phase to address.

**Action:** Added to PROGRESS.md "Spec Gaps Discovered" section as a known stale artifact.

### 2. Task 2.1 — Impossible S3 Event Notification (Significant)

*AI:* Fixed. Removed the S3 event notification AC from Task 2.1. The receipts bucket is created without notifications. Task 3.5 (Pipeline CDK Construct) now explicitly configures the S3 → SQS notification, since the SQS queue must exist as the destination.

### 3. GSI1SK for Processing Receipts (Significant)

*AI:* Fixed. This was a real gap. The solution:

- **Task 2.3** (Upload URLs): Sets `GSI1SK = {createdAt}#{ulid}` as fallback when creating `processing` receipt records. This ensures processing receipts appear in GSI1 queries (GET /api/receipts list).
- **Task 3.4** (Finalize Lambda): Updates `GSI1SK` to `{receiptDate}#{ulid}` after OCR extraction, if `receiptDate` was successfully extracted. If OCR didn't extract a date, keeps the `createdAt` fallback.

This means processing receipts are always visible in the list endpoint with their creation timestamp, and confirmed receipts sort by their actual receipt date.

### 4. User Profile Entity — Never Created (Significant)

*AI:* Decision: **Skip for MVP.** The SPEC defines a User Profile entity (`PK=USER#{userId}`, `SK=PROFILE`) with email, displayName, timestamps. But:

- No API endpoint reads or writes user profiles
- Email and userId (sub) are available from the JWT on every request
- displayName defaults to email prefix — but nothing in the UI displays it

The profile entity is defined in the schema for future use (settings, preferences). For MVP, it's dead code. If needed later, lazy-create on first API call.

**Action:** Noted in PROGRESS.md "Spec Gaps Discovered".

### 5. HANDOFF Step 10 Missing (Minor)

*AI:* Fixed. Renumbered M3 steps in HANDOFF.md. Also added the missing LoadCustomCategories step (see #6).

### 6. Missing LoadCustomCategories Lambda (Medium)

*AI:* Fixed. Added `load_custom_categories.py` Lambda to Task 3.4. This Lambda:
- Receives `userId` from Step Functions input
- Queries `PK=USER#{userId}` with `SK begins_with CUSTOMCAT#`
- Returns custom categories merged with predefined taxonomy
- Used by pipeline Lambdas (nova_structure, bedrock_extract) in their prompts

Task 3.5 already references `LoadCustomCategories` as the first step in the state machine. Now the Lambda handler that backs it exists.

HANDOFF.md M3 updated: step 7 now reads "LoadCustomCategories → Parallel (Main + Shadow branches with Catch) → Finalize".

### 7. DR-002 Stale (Medium)

*AI:* Fixed. Added an addendum to DR-002 explaining the evolution from A/B routing (pipeline_mode + percentage splits) to the parallel-always model (both run, `defaultPipeline` controls main/shadow). Status updated to "Decided (design evolved — see Addendum below)".

### 8. GSI1SK End-Date Inclusivity (Minor)

*AI:* Fixed. Task 2.4 AC now explicitly includes: `GSI1SK BETWEEN '{startDate}' AND '{endDate}~'` with trailing `~` for end-date inclusivity.

### 9. In-Memory Sort for Non-Date Sorts (Minor)

*AI:* Fixed. Task 5.2 AC now explicitly states that `sortBy=amount|merchant` requires in-memory sort.

### 10. totalCount Computation (Minor)

*AI:* Fixed. Task 5.2 AC now documents the strategy: parallel `Select="COUNT"` for date-sorted queries; derived from fetched set when in-memory sorting is already happening.

### 11. Receipt Delete UI Missing (Minor)

*AI:* Fixed. Task 4.3 AC now includes: "Delete button with confirmation dialog: clicking delete shows 'Are you sure?' dialog, confirm calls DELETE /api/receipts/{id}, on success navigates back to receipts list."

### 12. /api/health Not in API Contracts (Minor)

*AI:* Intentionally omitted from api-contracts.md. The health endpoint is an operational endpoint (used by CDK deployment verification), not a user-facing API. Task 1.7 defines it. No change needed — it's outside the formal contract by design.

### 13. msw Dependency Not in Frontend Scaffolding (Minor)

*AI:* Fixed. Task 1.3 AC now includes: "package.json includes msw as a dev dependency."

### 14. Missing ranking.py in SPEC Project Structure (Minor)

*AI:* No action. The SPEC tree listing is incomplete but the logic is fully spec'd in Section 3. The plan correctly creates `ranking.py`. The SPEC tree is a convenience reference, not exhaustive.

---

## Summary of All Changes Made

| File | Change |
|------|--------|
| PLAN.md | Added Task 0.1 (environment verification) |
| PLAN.md | Task 1.3: added msw dev dependency |
| PLAN.md | Task 1.5: split into Pre-Sign-Up + Post-Confirmation Lambdas |
| PLAN.md | Task 2.1: removed impossible S3 notification AC |
| PLAN.md | Task 2.3: added GSI1SK fallback (createdAt) for processing receipts |
| PLAN.md | Task 2.4: added end-date inclusivity note (trailing ~) |
| PLAN.md | Task 3.4: added LoadCustomCategories Lambda |
| PLAN.md | Task 3.5: added S3 notification config + CfnPipe verification AC |
| PLAN.md | Task 4.3: added delete button + confirmation dialog |
| PLAN.md | Task 5.2: added in-memory sort + totalCount strategy notes |
| PROGRESS.md | Added Task 0.1, updated Task 1.5 and 3.4 titles, updated counts |
| HANDOFF.md | Fixed M3 step numbering, added LoadCustomCategories step |
| DR-002 | Added superseded addendum noting evolved design |

Total tasks: **45** (was 44, added Task 0.1)

# feedback round 3 
- task 0.1 should include
    - uv python venv is created
    
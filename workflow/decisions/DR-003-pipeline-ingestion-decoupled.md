# DR-003: Pipeline Ingestion — Decoupled with SQS + EventBridge Pipes

**Phase:** 2 — Specification
**Date:** 2026-03-27
**Status:** Decided

## Context

The OCR processing pipeline uses Amazon Textract `AnalyzeExpense` (synchronous), which has a hard limit of 5 TPS in us-east-1/us-west-2. NovaScan allows bulk upload of up to 10 receipts and serves ~100 users. If multiple users upload simultaneously, or a single user uploads a 10-file batch, the system can exceed 5 TPS and receive HTTP 429 errors from Textract.

The original design (DR-002) used direct EventBridge triggers from S3 ObjectCreated events to start Step Functions executions, with Step Functions retry/backoff to handle throttling. This works technically but is bad engineering: throttling errors become expected behavior, polluting monitoring and alerting.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Direct EventBridge → Step Functions + retry** | Simplest, fewest components | Throttling is expected behavior (noisy monitoring), no backpressure, 429s at burst |
| **SQS queue + Lambda consumer (MaxConcurrency)** | Simple, well-understood | Extra Lambda between SQS and Step Functions, more code to maintain |
| **SQS queue + EventBridge Pipes (MaxConcurrency)** | Managed rate limiting, no custom Lambda, declarative concurrency control | Newer AWS service (GA 2023), slightly more complex CDK setup |
| **Async Textract (StartExpenseAnalysis)** | Handles higher volume | Same 5 TPS limit, adds SNS/callback complexity, no benefit for single-page receipts |

## Decision

**SQS queue + EventBridge Pipes** with `MaximumConcurrency: 2`.

Flow: S3 ObjectCreated → SQS queue (burst buffer) → EventBridge Pipes (rate limiter, max concurrency 2) → Step Functions execution.

Setting max concurrency to 2 ensures at most 2 Textract calls are in-flight at any time, staying well under the 5 TPS limit. SQS provides durable buffering — no messages are lost during bursts. EventBridge Pipes is a fully managed service that handles the SQS → Step Functions integration with declarative concurrency control, eliminating custom polling/dispatching code.

## Consequences

- **Throttling eliminated:** Textract never receives more than 2 concurrent requests. No 429 errors in steady state.
- **Clean monitoring:** Any Textract error is a genuine failure worth investigating, not expected throttling.
- **Burst tolerance:** 10-file bulk uploads and concurrent user uploads are absorbed by SQS without dropping requests.
- **Latency trade-off:** Under burst conditions, receipts may queue for processing rather than starting immediately. This is acceptable — users see "Processing" status regardless.
- **Additional components:** SQS queue + EventBridge Pipes + DLQ adds operational surface. All are managed services with minimal maintenance.
- **Cost:** SQS and Pipes costs are negligible at this scale (<$0.01/month).

## Discussion

*FEEDBACK:* (Round 1) The assumption to use synchronous AnalyzeExpense for a consumer mobile app with direct EventBridge triggers is incorrect. A 5 TPS hard limit means if 6 users press "Scan" in the exact same millisecond, the 6th receives a 429. Relying on catching throttling errors and retrying is bad engineering and adds noise to monitoring. Decouple ingestion from processing to handle micro-bursts.

*AI:* Agreed. Adopted the decoupled architecture with SQS as burst buffer and EventBridge Pipes as rate limiter. Step Functions retry on Textract throttling is removed — if a 429 occurs now, it's a genuine anomaly.

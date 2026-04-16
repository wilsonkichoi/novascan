# Service Pause & Resume Guide

How to pause and resume NovaScan services without destroying infrastructure.

## When to Pause

- **Cost saving** — stop paying for per-request services (Textract, Bedrock, Lambda invocations) during inactive periods
- **Incident response** — quickly block all traffic while investigating an issue
- **Maintenance** — prevent user activity during data migrations or schema changes

## What Pausing Does

| Component | Paused State | Effect |
|-----------|-------------|--------|
| CloudFront | Distribution disabled | Frontend inaccessible, returns error |
| API Gateway | Throttled to 0 requests/sec | All API calls rejected (429) |
| EventBridge Pipe | Stopped | No new pipeline executions start |

## What Pausing Does NOT Do

- **Does not delete any data** — DynamoDB, S3 (receipts + frontend assets), Cognito users are all preserved
- **Does not stop in-flight Step Functions** — already running pipeline executions will complete
- **Does not stop SQS message accumulation** — S3 events still queue in SQS while the pipe is stopped; they'll process when resumed (up to 4-day retention)
- **Does not affect Lambda functions** — they still exist and could be invoked directly (but have no trigger path)

## Quick Reference

```bash
# Check current state
uv run scripts/service.py status prod

# Pause (with confirmation prompt)
uv run scripts/service.py pause prod

# Pause (skip confirmation)
uv run scripts/service.py pause prod --yes

# Resume
uv run scripts/service.py resume prod
```

## Pause/Resume Order

The script handles ordering automatically:

**Pause** (user-facing first, backends last):
1. CloudFront — blocks frontend traffic immediately
2. API Gateway — blocks direct API access
3. EventBridge Pipe — stops pipeline processing

**Resume** (backends first, frontend last):
1. EventBridge Pipe — restart pipeline processing
2. API Gateway — restore API throttle limits
3. CloudFront — expose frontend (only after backends are ready)

> **Note:** Self-service sign-up is permanently disabled. Users are created via
> `uv run scripts/add_user.py --stage <stage> --email <email> [--group admin|staff|user]`.

## Timing

- **API Gateway throttle**: immediate
- **EventBridge Pipe stop/start**: ~10-30 seconds
- **CloudFront disable/enable**: 5-15 minutes to propagate globally

## Manual Console Fallback

If the script is unavailable, you can pause manually:

### CloudFront
1. Go to **CloudFront** > **Distributions**
2. Select the distribution (ID from stack outputs)
3. Click **Disable**

### API Gateway
1. Go to **API Gateway** > **APIs** > `novascan-{stage}`
2. Go to **Stages** > `$default`
3. Set **Default route throttling** to burst=0, rate=0

### EventBridge Pipe
1. Go to **EventBridge** > **Pipes** > `novascan-{stage}-receipt-pipe`
2. Click **Stop**

Reverse all steps to resume (start pipe, restore throttle to burst=10/rate=5, re-enable CloudFront).

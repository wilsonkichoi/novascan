# Deploy & Teardown Guide

Complete lifecycle guide for deploying, updating, and tearing down NovaScan dev and prod stacks.

## Prerequisites

- AWS CLI configured (`aws sts get-caller-identity` returns correct account)
- [uv](https://docs.astral.sh/uv/) installed (Python package manager)
- Node.js 22 LTS + npm installed
- CDK bootstrapped in us-east-1: `cd infra && uv run cdk bootstrap`

## Pre-Deploy Checklist

Run these before every deploy. All must pass.

```bash
# 1. Backend tests
cd backend && uv run pytest

# 2. Backend lint + type check
cd backend && uv run ruff check .
cd backend && uv run mypy src/

# 3. Frontend tests
cd frontend && npm run test

# 4. Frontend build (smoke test)
cd frontend && npm run build

# 5. CDK snapshot is current (no unexpected diff)
# Asset hashes are normalized in comparison, so code-only changes won't fail.
# If you changed infra, update the snapshot first:
#   cd infra && uv run pytest --snapshot-update
cd infra && uv run cdk synth --context stage=dev > /dev/null
cd infra && uv run pytest

# 6. Verify AWS credentials
aws sts get-caller-identity
```

## Environment Variable Reference

### Stage-Specific Config (`infra/cdk.json`)

| Key | dev | prod |
|-----|-----|------|
| `presignedUrlExpirySec` | 900 | 900 |
| `maxUploadFiles` | 10 | 10 |
| `maxUploadSizeMb` | 10 | 10 |
| `logLevel` | DEBUG | INFO |
| `defaultPipeline` | ocr-ai | ocr-ai |
| `domainName` | (none) | subdomain.example.com |

### Frontend Build Environment Variables

These are Vite build-time variables sourced from CDK stack outputs. They are baked into the JavaScript bundle at `npm run build` time.

| Variable | Description | Source (stack output key) |
|----------|-------------|--------------------------|
| `VITE_API_URL` | API Gateway URL | `ApiUrl` |
| `VITE_COGNITO_USER_POOL_ID` | Cognito User Pool ID | `UserPoolId` |
| `VITE_COGNITO_CLIENT_ID` | Cognito App Client ID | `AppClientId` |
| `VITE_AWS_REGION` | AWS region | Always `us-east-1` |

### CDK Stack Outputs Reference

| Output Key | Description | Stages |
|------------|-------------|--------|
| `ApiUrl` | API Gateway endpoint URL | dev, prod |
| `CloudFrontDomain` | CloudFront distribution domain name | dev, prod |
| `UserPoolId` | Cognito User Pool ID | dev, prod |
| `AppClientId` | Cognito App Client ID | dev, prod |
| `FrontendBucketName` | S3 bucket for frontend static assets | dev, prod |
| `ReceiptsBucketName` | S3 bucket for receipt images | dev, prod |
| `DistributionId` | CloudFront distribution ID (for cache invalidation) | dev, prod |
| `CustomDomain` | Custom domain name (`subdomain.example.com`) | prod only |
| `CloudFrontCnameTarget` | CNAME target for custom domain DNS | prod only |

---

## Dev Stack

### Deploy (First Time or Update)

```bash
# 1. Deploy infrastructure (includes Lambda code bundling)
cd infra && uv run cdk deploy --context stage=dev --outputs-file cdk-outputs-dev.json

# 2. Capture stack outputs
#    The outputs file is saved to infra/cdk-outputs-dev.json (gitignored).
#    Extract the values you need:
cat infra/cdk-outputs-dev.json
```

Example `cdk-outputs-dev.json`:
```json
{
  "novascan-dev": {
    "ApiUrl": "https://abc123.execute-api.us-east-1.amazonaws.com",
    "CloudFrontDomain": "d1234abcdef.cloudfront.net",
    "UserPoolId": "us-east-1_AbCdEf",
    "AppClientId": "1a2b3c4d5e6f7g8h9i0j",
    "FrontendBucketName": "novascan-dev-frontend-bucket-xyz",
    "ReceiptsBucketName": "novascan-dev-receipts-bucket-xyz",
    "DistributionId": "E1234567890ABC"
  }
}
```

### Deploy Frontend

After infrastructure is deployed, build and upload the frontend:

```bash
# 3. Build frontend with stack outputs
cd frontend && \
  VITE_API_URL="https://abc123.execute-api.us-east-1.amazonaws.com" \
  VITE_COGNITO_USER_POOL_ID="us-east-1_AbCdEf" \
  VITE_COGNITO_CLIENT_ID="1a2b3c4d5e6f7g8h9i0j" \
  VITE_AWS_REGION="us-east-1" \
  npm run build

# 4. Upload to S3
aws s3 sync frontend/dist/ s3://novascan-dev-frontend-bucket-xyz/ --delete

# 5. Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id E1234567890ABC \
  --paths "/*"
```

Alternatively, set the variables in `frontend/.env` (gitignored) and just run `cd frontend && npm run build`. See `frontend/.env.example` for the template.

### Create Initial User

Self-service sign-up is disabled. Create users via the admin script:

```bash
# Create a user (receives email invitation from Cognito)
uv run scripts/add_user.py --stage dev --email you@example.com --group admin
```

Available groups: `user` (default), `staff`, `admin`.

### Verify Dev Deployment

```bash
# Check CloudFront serves the app
curl -s -o /dev/null -w "%{http_code}" https://d1234abcdef.cloudfront.net
# Expected: 200

# Check API health
curl -s https://abc123.execute-api.us-east-1.amazonaws.com/api/health
```

### Update (Subsequent Deploys)

Same commands as the initial deploy. CDK performs an update-in-place (CloudFormation changeset).

```bash
# Infrastructure update
cd infra && uv run cdk deploy --context stage=dev --outputs-file cdk-outputs-dev.json

# Frontend rebuild + upload (only needed if frontend code or env vars changed)
cd frontend && npm run build
aws s3 sync frontend/dist/ s3://novascan-dev-frontend-bucket-xyz/ --delete
aws cloudfront create-invalidation --distribution-id E1234567890ABC --paths "/*"
```

If only backend/infra code changed (Lambda, Step Functions, DynamoDB, etc.), `cdk deploy` is sufficient. The Lambda code is bundled and deployed as part of the CDK stack. No separate frontend deploy is needed.

If only frontend code changed, skip `cdk deploy` and just rebuild + upload + invalidate.

### Teardown Dev Stack

```bash
# Destroy all dev resources
cd infra && uv run cdk destroy --context stage=dev

# Confirm when prompted: y
```

This deletes all resources in the `novascan-dev` CloudFormation stack. S3 buckets with `RemovalPolicy.DESTROY` and `autoDeleteObjects=True` are emptied and deleted automatically. DynamoDB tables follow the same pattern.

**WARNING:** Teardown deletes all data (receipts, images, user accounts). There is no recovery.

---

## Prod Stack

### First-Time Deploy (with Custom Domain)

Prod deployment requires additional DNS steps for the custom domain `subdomain.example.com`. The full DNS setup is documented in [cloudflare-custom-domain.md](cloudflare-custom-domain.md).

```bash
# 1. Deploy infrastructure
cd infra && uv run cdk deploy --context stage=prod --outputs-file cdk-outputs-prod.json
```

**IMPORTANT:** The deploy will block waiting for ACM certificate validation. While it is running, you must add the ACM DNS validation CNAME record in Cloudflare. See [cloudflare-custom-domain.md](cloudflare-custom-domain.md) Step 1 for the exact procedure.

After the deploy completes and DNS is configured:

```bash
# 2. Build frontend with prod stack outputs
cd frontend && \
  VITE_API_URL="<ApiUrl from outputs>" \
  VITE_COGNITO_USER_POOL_ID="<UserPoolId from outputs>" \
  VITE_COGNITO_CLIENT_ID="<AppClientId from outputs>" \
  VITE_AWS_REGION="us-east-1" \
  npm run build

# 3. Upload to S3
aws s3 sync frontend/dist/ s3://<FrontendBucketName from outputs>/ --delete

# 4. Invalidate CloudFront cache
aws cloudfront create-invalidation \
  --distribution-id <DistributionId from outputs> \
  --paths "/*"
```

After frontend upload, add the CloudFront CNAME in Cloudflare (Step 2 in [cloudflare-custom-domain.md](cloudflare-custom-domain.md)).

### Verify Prod Deployment

```bash
# Check custom domain resolves
dig subdomain.example.com CNAME +short
# Expected: d1234abcdef.cloudfront.net.

# Check HTTPS
curl -s -o /dev/null -w "%{http_code}" https://subdomain.example.com
# Expected: 200

# Check security headers
curl -sI https://subdomain.example.com | grep -E "strict-transport|x-frame|x-content-type"
# Expected:
#   strict-transport-security: max-age=63072000; includeSubdomains
#   x-frame-options: DENY
#   x-content-type-options: nosniff

# Check API
curl -s https://<ApiUrl from outputs>/api/health
```

### Update Prod Stack

```bash
# 1. Run pre-deploy checklist (see top of this guide)

# 2. Deploy infrastructure update
cd infra && uv run cdk deploy --context stage=prod --outputs-file cdk-outputs-prod.json

# 3. Rebuild + upload frontend (if frontend code changed)
cd frontend && npm run build
aws s3 sync frontend/dist/ s3://<FrontendBucketName>/ --delete
aws cloudfront create-invalidation --distribution-id <DistributionId> --paths "/*"
```

On subsequent deploys (after the first), the ACM certificate already exists and is validated. CDK will not re-create it. No DNS changes are needed for updates.

### Teardown Prod Stack

```bash
# 1. Remove Cloudflare DNS records FIRST
#    In Cloudflare DNS, delete:
#    - CNAME: novascan -> d1234abcdef.cloudfront.net
#    - CNAME: _abc123.subdomain.example.com -> _def456.acm-validations.aws.
#    (Leaving stale CNAMEs pointing to deleted resources is harmless but messy.)

# 2. Destroy the stack
cd infra && uv run cdk destroy --context stage=prod

# Confirm when prompted: y
```

**WARNING:** Teardown deletes all prod data (receipts, images, user accounts, Cognito pool). There is no recovery. The ACM certificate is also deleted.

---

## Rollback Instructions

CDK does not have a built-in "rollback to previous version" command. To roll back, redeploy the previous known-good commit.

### Rollback Procedure

```bash
# 1. Find the last known-good commit
git log --oneline -10

# 2. Check out that commit
git checkout <commit-hash>

# 3. Redeploy infrastructure
cd infra && uv run cdk deploy --context stage=<stage> --outputs-file cdk-outputs-<stage>.json

# 4. Rebuild and redeploy frontend (if frontend was part of the issue)
cd frontend && npm run build
aws s3 sync frontend/dist/ s3://<FrontendBucketName>/ --delete
aws cloudfront create-invalidation --distribution-id <DistributionId> --paths "/*"

# 5. Return to main branch
git checkout main
```

### Infrastructure-Only Rollback

If the issue is only in Lambda/Step Functions/DynamoDB schema (backend infra), step 4 can be skipped.

### Frontend-Only Rollback

If the issue is only in the frontend (UI bug, wrong env var), skip step 3 and just rebuild + upload.

### CloudFormation Automatic Rollback

If a `cdk deploy` fails mid-way, CloudFormation automatically rolls back the stack to its previous state. You do not need to intervene. Check the rollback status:

```bash
aws cloudformation describe-stacks \
  --stack-name novascan-<stage> \
  --query 'Stacks[0].StackStatus' \
  --output text
# Expected after failed deploy: UPDATE_ROLLBACK_COMPLETE
```

---

## Quick Reference

### Deploy Script

`scripts/deploy.py` automates the full deploy workflow. It queries CloudFormation directly for live stack outputs (no stale local JSON files).

```bash
python scripts/deploy.py frontend dev    # build + S3 sync + CloudFront invalidate
python scripts/deploy.py backend prod    # cdk deploy only
python scripts/deploy.py all dev         # backend then frontend
```

### Resource Naming

All resources follow the pattern `novascan-{stage}-{resource}`:
- Stack name: `novascan-dev` / `novascan-prod`
- S3 buckets: `novascan-dev-frontend-*`, `novascan-dev-receipts-*`
- DynamoDB table: `novascan-dev-table` / `novascan-prod-table`
- Cognito pool: `novascan-dev-users` / `novascan-prod-users`

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
| `domainName` | (none) | (none — add your domain here if needed) |

### Frontend Build Environment Variables

These are Vite build-time variables sourced from CDK stack outputs. They are baked into the JavaScript bundle at `npm run build` time.

| Variable | Description | Source (stack output key) |
|----------|-------------|--------------------------|
| `VITE_API_URL` | API Gateway URL | `ApiUrl` |
| `VITE_COGNITO_CLIENT_ID` | Cognito App Client ID | `AppClientId` |
| `VITE_AWS_REGION` | AWS region | Derived from stack |

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

The deploy script handles everything: CDK deploy, frontend build with auto-injected stack outputs, S3 upload, and CloudFront invalidation.

```bash
python scripts/deploy.py all dev
```

To deploy only backend (infra) or only frontend:

```bash
python scripts/deploy.py backend dev    # cdk deploy only
python scripts/deploy.py frontend dev   # build + S3 sync + CloudFront invalidate
```

The script queries CloudFormation for live stack outputs — no manual copy-pasting of IDs or URLs.

<details>
<summary>Manual deploy (without script)</summary>

```bash
# 1. Deploy infrastructure
cd infra && uv run cdk deploy --context stage=dev --outputs-file cdk-outputs-dev.json

# 2. Build frontend with stack outputs (substitute real values from step 1)
cd frontend && \
  VITE_API_URL="<ApiUrl>" \
  VITE_COGNITO_CLIENT_ID="<AppClientId>" \
  VITE_AWS_REGION="us-east-1" \
  npm run build

# 3. Upload to S3
aws s3 sync frontend/dist/ s3://<FrontendBucketName>/ --delete

# 4. Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id <DistributionId> --paths "/*"
```

</details>

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
python scripts/deploy.py all dev         # full redeploy
python scripts/deploy.py backend dev     # infra only (Lambda, DynamoDB, etc.)
python scripts/deploy.py frontend dev    # frontend only (build + upload + invalidate)
```

If only backend/infra code changed, `backend` is sufficient — Lambda code is bundled in the CDK stack. If only frontend code changed, `frontend` skips the CDK deploy.

### Teardown Dev Stack

```bash
uv run scripts/dangerous_full_teardown.py dev
```

This runs `cdk destroy` and cleans up all resources. Dev resources use `RemovalPolicy.DESTROY` so `cdk destroy` handles everything, but the script provides a unified interface for both stages.

**WARNING:** Teardown deletes all data (receipts, images, user accounts). There is no recovery.

---

## Prod Stack

### First-Time Deploy (with Custom Domain)

Prod deployment requires additional DNS steps if you configured a custom domain in `cdk.json`. The full DNS setup is documented in [cloudflare-custom-domain.md](cloudflare-custom-domain.md).

```bash
# 1. Deploy infrastructure (blocks waiting for ACM validation if custom domain is set)
python scripts/deploy.py backend prod
```

**IMPORTANT:** If you have a custom domain, the deploy will block waiting for ACM certificate validation. While it is running, you must add the ACM DNS validation CNAME record in Cloudflare. See [cloudflare-custom-domain.md](cloudflare-custom-domain.md) Step 1 for the exact procedure.

```bash
# 2. Build + upload frontend (queries CloudFormation for outputs automatically)
python scripts/deploy.py frontend prod
```

After frontend upload, add the CloudFront CNAME in Cloudflare if using a custom domain (Step 2 in [cloudflare-custom-domain.md](cloudflare-custom-domain.md)).

If you are NOT using a custom domain, no DNS steps are needed — the CloudFront default URL works immediately.

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

# 2. Deploy
python scripts/deploy.py all prod        # full redeploy
python scripts/deploy.py backend prod    # infra only
python scripts/deploy.py frontend prod   # frontend only
```

On subsequent deploys (after the first), the ACM certificate already exists and is validated. CDK will not re-create it. No DNS changes are needed for updates.

### Teardown Prod Stack

If you have a custom domain, remove Cloudflare DNS records first (CNAME for the domain and ACM validation CNAME). Then:

```bash
uv run scripts/dangerous_full_teardown.py prod
```

This runs `cdk destroy` and then cleans up the four retained prod resources: DynamoDB table (disables deletion protection first), both S3 buckets (empties all objects and versions), and Cognito User Pool.

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

# 3. Redeploy
python scripts/deploy.py all <stage>       # full redeploy
python scripts/deploy.py backend <stage>   # infra only (skip if frontend-only issue)
python scripts/deploy.py frontend <stage>  # frontend only (skip if infra-only issue)

# 4. Return to main branch
git checkout main
```

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

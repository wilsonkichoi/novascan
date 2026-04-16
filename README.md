# NovaScan

AI-powered receipt scanner and spending tracker.

## Overview

NovaScan is a mobile-optimized web application that lets users photograph or bulk-upload receipt images. The system extracts merchant, date, line items, and totals using a dual OCR pipeline (Amazon Textract + Bedrock Nova for OCR-AI, and Bedrock Nova multimodal for AI-multimodal) and presents spending data through a receipt management interface.

Built on AWS serverless infrastructure with a scale-to-zero cost model. Personal use, ~100 users, $25/month budget.

<!-- Milestone merge checklist: update capabilities list and test counts below -->
### Current Capabilities (through Milestone 5)

- Passwordless email OTP authentication (Cognito)
- Receipt image upload via camera capture or file picker (up to 10 files, JPEG/PNG, max 10 MB)
- Automatic OCR processing via dual pipelines with ranking and fallback
- Receipt list with status badges (processing/confirmed/failed), date filtering, pagination
- Receipt detail view with image alongside extracted data (responsive layout)
- Inline line item editing: add, remove, edit name/quantity/price/subcategory
- Category management: 13 predefined categories with subcategories, custom category creation/deletion
- Staff-only pipeline comparison toggle (side-by-side OCR-AI vs AI-multimodal results)
- Receipt deletion with confirmation dialog
- Dashboard: weekly/monthly spending totals with % change, top categories, recent activity
- Transactions ledger: sortable table (date/amount/merchant), date range/category/status filters, merchant search
- Analytics page: "Coming Soon" placeholder
- Security hardened: input validation, error sanitization, scoped IAM, rate limiting

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 22 LTS
- Docker (for DynamoDB Local in tests)
- AWS CLI v2 (configured with your AWS account)
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- AWS CDK CLI: `npm install -g aws-cdk`

### Installation

```bash
# Backend
cd backend && uv venv --python 3.13 && uv sync && cd ..

# Frontend
cd frontend && npm install && cd ..

# Infrastructure
cd infra && uv venv --python 3.13 && uv sync && cd ..
```

### Deploy to Dev

```bash
cd infra && uv run cdk deploy --context stage=dev
```

### Run Tests

```bash
# Backend (553 tests)
cd backend && uv run pytest

# Frontend (331 tests)
cd frontend && npm run test -- --run

# Infrastructure (100 tests)
cd infra && uv run pytest

# Lint
cd backend && uv run ruff check src/
```

### Run Locally

```bash
# Start DynamoDB Local
docker run -d -p 8000:8000 amazon/dynamodb-local

# Frontend dev server
cd frontend && npm run dev
```

## Deploy to Your Own AWS Account

1. Fork and clone this repo
2. Install prerequisites (see above)
3. Configure AWS credentials (`aws configure` or set `AWS_PROFILE`)
4. Bootstrap CDK in your account:
   ```bash
   cd infra && uv run cdk bootstrap
   ```
5. Deploy the dev stack:
   ```bash
   python scripts/deploy.py all dev
   ```
6. Create a user:
   ```bash
   uv run scripts/add_user.py --stage dev --email you@example.com
   ```
7. Open the CloudFront URL printed in the deploy output

No custom domain is required. The dev stage uses CloudFront's default URL.

### Teardown

```bash
uv run scripts/dangerous_full_teardown.py dev
```

This destroys the CloudFormation stack and cleans up any retained resources (prod DynamoDB table, S3 buckets, Cognito User Pool). All data is permanently deleted.

### Optional: Custom Domain (prod)

Add `"domainName": "your-domain.example.com"` to the `config.prod` section of
`infra/cdk.json`, then deploy with `python scripts/deploy.py all prod`.
See `workflow/guides/cloudflare-custom-domain.md` for DNS setup.

## Architecture

```
Browser (React SPA)
  ├── CloudFront → S3 (static frontend)
  ├── API Gateway → Lambda (Powertools REST API)
  └── S3 (presigned URL upload)
        ↓
  SQS → EventBridge Pipes → Step Functions
      ├── LoadCustomCategories
      ├── Parallel:
      │   ├── Textract AnalyzeExpense → Bedrock Nova (OCR-AI)
      │   └── Bedrock Nova multimodal (AI-multimodal)
      └── Finalize (ranking + DynamoDB update)
        ↓
  DynamoDB (single-table)
```

- **Frontend:** Vite + React + Tailwind CSS v4 + shadcn/ui
- **Backend:** AWS Lambda Powertools (Python) + Pydantic
- **Auth:** Cognito email OTP (passwordless), JWT authorizer
- **Storage:** DynamoDB (on-demand, single-table design) + S3 (receipt images)
- **Pipeline:** SQS + EventBridge Pipes + Step Functions (dual OCR with ranking)
- **IaC:** AWS CDK (Python), single stack per stage (dev/prod)

See [workflow/spec/SPEC.md](workflow/spec/SPEC.md) for the full technical specification.

## License

MIT

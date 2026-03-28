# NovaScan

AI-powered receipt scanner and spending tracker.

## Overview

NovaScan is a mobile-optimized web application that lets users photograph or bulk-upload receipt images. The system extracts merchant, date, line items, and totals using a tiered OCR pipeline (Amazon Textract + Bedrock Nova) and presents spending data through a dashboard and transaction ledger.

Built on AWS serverless infrastructure with a scale-to-zero cost model. Personal use, <20 users, $25/month budget.

## Getting Started

### Prerequisites

- Python 3.13+
- Node.js 22 LTS
- Docker (for DynamoDB Local)
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

### Run Locally

```bash
# Start DynamoDB Local
docker run -d -p 8000:8000 amazon/dynamodb-local

# Backend tests
cd backend && uv run pytest

# Frontend dev server
cd frontend && npm run dev
```

## Architecture

```
Browser (React SPA)
  ├── CloudFront → S3 (static frontend)
  ├── API Gateway → Lambda (Powertools REST API)
  └── S3 (presigned URL upload)
        ↓
  EventBridge → Step Functions
      ├── Textract AnalyzeExpense → Bedrock Nova (tiered)
      └── Bedrock Nova multimodal (single)
        ↓
  DynamoDB (single-table)
```

- **Frontend:** Vite + React + Tailwind CSS v4 + shadcn/ui
- **Backend:** AWS Lambda Powertools (Python) + Pydantic
- **Auth:** Cognito email OTP (passwordless)
- **Storage:** DynamoDB (on-demand) + S3
- **IaC:** AWS CDK (Python)

See [workflow/spec/SPEC.md](workflow/spec/SPEC.md) for the full technical specification.

## License

MIT

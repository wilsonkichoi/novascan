# NovaScan

AI-powered receipt scanner and spending tracker — personal MVP on AWS serverless.

## Architecture Summary

- **Frontend:** Vite + React + Tailwind CSS v4 + shadcn/ui → static SPA on S3/CloudFront
- **Backend:** Single API Lambda (AWS Lambda Powertools for Python + Pydantic) behind API Gateway HTTP API
- **OCR Pipeline:** Step Functions orchestrating parallel Textract + Nova (tiered) and Bedrock Nova (single) paths
- **Storage:** DynamoDB single-table (on-demand), S3 for receipt images (presigned URL upload)
- **Auth:** Cognito email OTP (passwordless), JWT validation via API Gateway authorizer
- **IaC:** AWS CDK (Python), single stack per stage (dev/prod)
- **Domain:** subdomain.example.com (prod), CloudFront default URL (dev)

## Build & Test Commands

```bash
# Backend
cd backend && uv run pytest                        # run tests
cd backend && uv run ruff check .                   # lint
cd backend && uv run mypy src/                      # type check

# Frontend
cd frontend && npm run dev                          # dev server
cd frontend && npm run build                        # production build
cd frontend && npm run test                         # vitest

# Infrastructure
cd infra && uv run cdk deploy --context stage=dev   # deploy to dev
cd infra && uv run cdk destroy --context stage=dev  # teardown dev
cd infra && uv run cdk synth --context stage=dev    # synthesize CloudFormation
cd infra && uv run pytest --snapshot-update          # update CDK snapshot after infra changes

# Git hooks (auto-regenerates CDK snapshot on commit)
git config core.hooksPath .githooks
```

## Quick Reference

| Phase | Command | Role | Artifacts |
|-------|---------|------|-----------|
| 1 Research | `/agentic-dev:research` | Explore agent | workflow/research/final/ |
| 2 Spec | `/agentic-dev:spec` | Software architect + specialists | workflow/spec/SPEC.md |
| 3 Plan | `/agentic-dev:plan` | Plan agent + senior engineer | workflow/plan/PLAN.md |
| 4 Build | `/agentic-dev:build` | Backend/frontend/QA/DevOps engineers | src/, tests/ |
| 5 Review | `/agentic-dev:review` | Code reviewer + QA | workflow/retro/ |

## Key Documents

- **Specification**: [workflow/spec/SPEC.md](workflow/spec/SPEC.md)
- **API Contracts**: [workflow/spec/api-contracts.md](workflow/spec/api-contracts.md)
- **Category Taxonomy**: [workflow/spec/category-taxonomy.md](workflow/spec/category-taxonomy.md)
- **Handoff**: [workflow/spec/HANDOFF.md](workflow/spec/HANDOFF.md)
- **Implementation Plan**: [workflow/plan/PLAN.md](workflow/plan/PLAN.md) (Phase 3 output)
- **Progress Tracker**: [workflow/plan/PROGRESS.md](workflow/plan/PROGRESS.md)
- **Decisions**: [workflow/decisions/README.md](workflow/decisions/README.md)

## Project Structure

- `backend/` and `infra/` are independent Python subprojects, each with their own `pyproject.toml`, `uv.lock`, and `.venv`
- `frontend/` is a Node.js project with its own `package.json` and `node_modules/`
- Do not share venvs across subprojects — their dependency trees are separate (Lambda code vs CDK)
- Run `uv sync` from the subproject directory to create/update its venv (e.g., `cd backend && uv sync`)

## Tooling

- **Python:** 3.13+ via uv (NEVER use pip/poetry/conda)
- **Node.js:** 22 LTS
- **Package managers:** uv (Python), npm (frontend)
- **IaC:** AWS CDK (Python)
- **Linting:** ruff (Python), ESLint + Prettier (TypeScript)
- **Testing:** pytest + moto (backend), Vitest + React Testing Library (frontend)
- **Docker:** DynamoDB Local for unit tests

## Preferences

- Minimize third-party dependencies — prefer AWS-native over adapters
- No FastAPI, no Mangum, no Amplify — use Lambda Powertools and AWS SDK directly
- All API data flows through Pydantic models
- Conventional commits: `feat:`, `fix:`, `chore:`, `docs:`
- No premature abstraction — three similar lines > one unnecessary helper

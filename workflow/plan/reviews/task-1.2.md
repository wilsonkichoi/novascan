# Task 1.2 Review: Backend Project Scaffolding

**Date:** 2026-03-28
**Role:** backend-engineer
**Branch:** `task/1.2-backend-scaffolding`
**Status:** Complete

## What was done

Created the `backend/` Python subproject with src layout, all package stubs, shared utilities, and test infrastructure.

### Files created

| File | Purpose |
|------|---------|
| `backend/pyproject.toml` | Project config — runtime deps, dev deps, tool config (ruff, mypy, pytest) |
| `backend/src/novascan/__init__.py` | Root package |
| `backend/src/novascan/api/__init__.py` | API handlers package stub |
| `backend/src/novascan/pipeline/__init__.py` | Pipeline handlers package stub |
| `backend/src/novascan/models/__init__.py` | Pydantic models package stub |
| `backend/src/novascan/shared/__init__.py` | Shared utilities package |
| `backend/src/novascan/shared/dynamo.py` | DynamoDB Table resource helper (reads TABLE_NAME env var) |
| `backend/src/novascan/shared/constants.py` | Entity type constants: PROFILE, RECEIPT, ITEM, PIPELINE, CUSTOMCAT |
| `backend/tests/__init__.py` | Tests root package |
| `backend/tests/conftest.py` | Pytest fixtures: AWS credential mocking, moto DynamoDB table, moto S3 bucket |
| `backend/tests/unit/__init__.py` | Unit tests package |
| `backend/tests/integration/__init__.py` | Integration tests package |

### Dependencies installed

**Runtime:** aws-lambda-powertools[all], pydantic>=2.0, boto3, python-ulid, pandas
**Dev:** pytest>=8.0, pytest-cov, moto[dynamodb,s3,sqs,stepfunctions], ruff, mypy, boto3-stubs[dynamodb,s3,sqs,stepfunctions]

### Tool configuration

- **ruff:** src layout, Python 3.13 target, 120 char line length, rules: E, F, I, UP, B, SIM
- **mypy:** strict mode, Python 3.13
- **pytest:** testpaths = tests, pythonpath = src

## Acceptance criteria verification

| Criterion | Result |
|-----------|--------|
| `uv sync` installs all dependencies | PASS |
| Import `get_table` and `RECEIPT` succeeds | PASS |
| `ruff check src/` passes with no errors | PASS |
| `pytest` runs (0 tests collected, no errors) | PASS |

## Design decisions

1. **Hatchling build backend** — Matches the infra project's build system for consistency across subprojects.
2. **`pythonpath = ["src"]` in pytest config** — Allows tests to import `novascan` without editable install gymnastics.
3. **`autouse=True` on `_aws_env` fixture** — Every test gets mocked AWS credentials automatically to prevent accidental real AWS calls.
4. **moto `mock_aws()` scoped per fixture** — DynamoDB and S3 fixtures each manage their own mock context so tests that need both can compose them.
5. **DynamoDB table fixture matches spec schema** — PK/SK key schema plus GSI1 with GSI1PK/GSI1SK, PAY_PER_REQUEST billing, ALL projection — mirrors SPEC.md Section 7.

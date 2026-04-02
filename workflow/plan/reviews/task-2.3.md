# Task 2.3: Upload URLs API Endpoint

## Work Summary
- **Branch:** `task/2.3-upload-urls-api` (based on `feature/m2-wave2-api-endpoints`)
- **What was implemented:** POST /api/receipts/upload-urls endpoint — generates ULIDs for each file, creates DynamoDB receipt records with status=processing and GSI1 keys, returns presigned S3 PUT URLs.
- **Key decisions:**
  - Used Lambda Powertools `Router` pattern (not direct `@app` decorator) for modular route registration — each endpoint file creates its own Router, included via `app.include_router()`.
  - Extension derived from `contentType` (not filename) for S3 key reliability — `image/jpeg` → `.jpg`, `image/png` → `.png`.
  - Used `batch_writer()` for DynamoDB writes (up to 10 items per request) — more efficient than individual `put_item` calls.
  - Added `src/novascan` to `pythonpath`, `ruff.src`, and `mypy_path` in `pyproject.toml` to resolve Lambda-flat import paths (`from models.xxx import ...`) working in both dev tooling and Lambda runtime. Also added `explicit_package_bases = true` for mypy to avoid duplicate module name conflicts.
  - DynamoDB writes happen before presigned URL generation to ensure records exist before client can upload.
- **Files created/modified:**
  - `backend/src/novascan/api/upload.py` (created)
  - `backend/src/novascan/api/app.py` (modified — import and include upload router)
  - `backend/pyproject.toml` (modified — pythonpath, ruff src, mypy config)
- **Test results:** ruff PASS, mypy PASS, pytest 0 collected (no backend tests yet)
- **Spec gaps found:** none
- **Obstacles encountered:**
  - Lambda bundling flattens `src/novascan/` to root, so internal imports use `from models.receipt import ...` rather than `from novascan.models.receipt import ...`. Required adding `src/novascan` to dev tooling paths and `explicit_package_bases` for mypy. This is the first time the project has cross-module imports in source code.

## Review Discussion

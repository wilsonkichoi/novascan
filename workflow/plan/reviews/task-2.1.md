# Task 2.1: Receipts S3 Bucket + Pydantic Models

## Work Summary
- **What was implemented:**
  - Added receipts S3 bucket to the Storage construct with BlockPublicAccess.BLOCK_ALL, S3-managed encryption, enforce SSL, versioning enabled, and stage-aware removal policy (RETAIN for prod, DESTROY for dev).
  - Wired receipts bucket through the stack: passed to ApiConstruct, added CfnOutput for bucket name.
  - Added RECEIPTS_BUCKET and PRESIGNED_URL_EXPIRY environment variables to the API Lambda.
  - Granted S3 read/write permissions to the API Lambda when receipts bucket is provided.
  - Created Pydantic models in `backend/src/novascan/models/receipt.py`: UploadFileRequest, UploadRequest, UploadReceiptResponse, UploadResponse, Receipt, ReceiptListItem, ReceiptListResponse.
  - Updated CDK snapshot to reflect new infrastructure resources.
- **Key decisions:**
  - `receipts_bucket` parameter on ApiConstruct is optional (`s3.IBucket | None = None`) for backward compatibility
  - Versioning enabled on receipts bucket per spec (not on frontend bucket)
  - No S3 event notifications added -- those come in M3 Task 3.5 when the SQS destination exists
  - UploadFileRequest validates contentType as Literal["image/jpeg", "image/png"] and fileSize 1-10MB
  - UploadRequest validates 1-10 files
  - Receipt model uses `str | None` for dates and optional fields, matching SPEC.md Section 5
- **Files created/modified:**
  - `infra/cdkconstructs/storage.py` (modified -- added receipts bucket + property)
  - `infra/cdkconstructs/api.py` (modified -- added receipts_bucket param, env vars, S3 grant)
  - `infra/stacks/novascan_stack.py` (modified -- wired receipts bucket, added CfnOutput)
  - `infra/tests/snapshots/novascan-dev.template.json` (updated -- reflects new resources)
  - `backend/src/novascan/models/receipt.py` (created -- Pydantic models)
- **Test results:** All pass
  - `cdk synth --context stage=dev` succeeds
  - Template contains 2 S3 buckets, 1 with versioning enabled
  - `ruff check src/` passes with no errors
  - `mypy src/` passes with no issues (12 source files)
  - All Pydantic models import and instantiate correctly
  - 47 CDK infrastructure tests pass (including updated snapshot)
- **Spec gaps found:** None
- **Obstacles encountered:** CDK snapshot test required regeneration from the test fixture (not from `cdk synth` CLI) due to asset hash differences between in-process synthesis and CLI synthesis.

## Review Discussion

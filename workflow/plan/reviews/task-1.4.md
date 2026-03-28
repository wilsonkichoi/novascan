# Task 1.4: Storage Construct -- DynamoDB + S3 Frontend Bucket

## Work Summary
- **What was implemented:** DynamoDB single-table with PK(S)/SK(S) key schema, GSI1 (GSI1PK/GSI1SK, ALL projection) for receipt date-range queries, PAY_PER_REQUEST billing, PITR enabled, and stage-aware deletion protection (enabled for prod, disabled for dev). S3 frontend assets bucket with BlockPublicAccess.BLOCK_ALL, S3-managed encryption, enforce SSL, and auto-delete for dev. Exposed table_name, table_arn, and frontend_bucket as construct properties for downstream consumption.
- **Key decisions:**
  - Used `point_in_time_recovery_specification` (non-deprecated API) instead of `point_in_time_recovery`
  - Set `removal_policy` to RETAIN for prod and DESTROY for dev on both DynamoDB table and S3 bucket
  - Enabled `auto_delete_objects` only for dev (requires DESTROY removal policy)
  - Used `enforce_ssl=True` on the S3 bucket for defense-in-depth
  - Used `TableEncryption.DEFAULT` (AWS-owned key) per SPEC.md
- **Files created/modified:**
  - `infra/cdkconstructs/storage.py` (modified -- implemented full construct)
  - `workflow/plan/reviews/task-1.4.md` (created -- this file)
- **Test results:** PASS -- all acceptance criteria verified for both dev and prod stages
  - DynamoDB table named `novascan-{stage}` with correct key schema
  - GSI1 with GSI1PK/GSI1SK and ALL projection
  - PAY_PER_REQUEST billing mode
  - PITR enabled
  - Deletion protection: false for dev, true for prod
  - RemovalPolicy: Delete for dev, Retain for prod
  - S3 bucket with all four BlockPublicAccess flags set to true
  - `cdk synth` succeeds for both --context stage=dev and --context stage=prod
- **Spec gaps found:** None
- **Obstacles encountered:** CDK deprecation warning for `point_in_time_recovery` parameter -- switched to `point_in_time_recovery_specification`

## Review Discussion

# Task 3.9 Review: Replace DynamoDB Scan with GSI2 Query [C2 + M13]

## Summary
Replaced the full DynamoDB table scan in `_lookup_user_id()` with a targeted GSI2 query, added scoped IAM permissions for the LoadCustomCategories Lambda, set GSI2PK on receipt creation, and added RECEIPTS_BUCKET env var to all pipeline Lambdas.

## Changes
- **`infra/cdkconstructs/storage.py`**: Added GSI2 with `GSI2PK` partition key, KEYS_ONLY projection
- **`backend/src/novascan/pipeline/load_custom_categories.py`**: Replaced `table.scan()` with `table.query(IndexName="GSI2", ...)`
- **`backend/src/novascan/api/upload.py`**: Added `GSI2PK: receipt_id` to receipt creation item
- **`infra/cdkconstructs/pipeline.py`**: Replaced `table.grant_read_data()` with scoped `dynamodb:Query`+`dynamodb:GetItem` policy; added `RECEIPTS_BUCKET` env var to all 5 pipeline Lambdas
- **`infra/tests/snapshots/novascan-dev.template.json`**: Regenerated

## Acceptance Criteria Checklist
- [x] DynamoDB table has GSI2: `GSI2PK` (S) partition key, projection KEYS_ONLY
- [x] `_lookup_user_id` uses `table.query(IndexName="GSI2", ...)` instead of `table.scan()`
- [x] LoadCustomCategories Lambda IAM grants only `dynamodb:Query` and `dynamodb:GetItem` (no Scan)
- [x] Upload endpoint sets `GSI2PK = receiptId` on receipt creation
- [x] `RECEIPTS_BUCKET` environment variable set on all pipeline Lambdas
- [x] `cdk synth` succeeds, CDK snapshot regenerated
- [x] Existing tests pass (72 infra tests, 3 integration tests for LoadCustomCategories)

## Test Results
```
72 passed in 17.71s  (infra tests)
3 passed, 28 deselected in 0.34s  (integration tests - LoadCustomCategories)
```

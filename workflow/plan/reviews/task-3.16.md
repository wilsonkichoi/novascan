# Task 3.16 Review: CDK IAM + API Gateway Hardening [M1 + M5 + M9 + M10]

## Summary
Hardened CDK infrastructure with scoped S3 permissions, API Gateway throttling and access logging, documented Textract wildcard, and region-scoped Bedrock ARNs.

## Changes
- **`infra/cdkconstructs/api.py`**:
  - M1: Replaced `grant_read_write(fn)` with `grant_put(fn, "receipts/*")` + `grant_read(fn, "receipts/*")` for scoped S3 access.
  - M5: Added API Gateway route-level throttling (burst=10, rate=5) and access logging to CloudWatch log group via L1 escape hatch (`CfnStage` property overrides).
- **`infra/cdkconstructs/pipeline.py`**:
  - M9: Added comment documenting that Textract does not support resource-level permissions, `resources=["*"]` is required per AWS docs.
  - M10: Scoped Bedrock IAM ARNs from `arn:aws:bedrock:*::foundation-model/amazon.nova-*` to `arn:aws:bedrock:{AWS::Region}::foundation-model/amazon.nova-lite-v1:0` and `amazon.nova-pro-v1:0` for both Nova structure and Bedrock extract Lambdas.
- **`infra/tests/test_pipeline_construct.py`**: Updated Bedrock permission test to use `Match.any_value()` for region-scoped ARN arrays, added wildcard region assertion to `test_bedrock_permissions_scoped_to_nova_models`.
- CDK snapshot regenerated.

## Acceptance Criteria Checklist
- [x] M1 — S3 grants scoped to `receipts/*` prefix
- [x] M5 — API Gateway throttling (burst=10, rate=5) configured
- [x] M5 — Access logging enabled to CloudWatch log group
- [x] M9 — Textract `resources=["*"]` documented with comment
- [x] M10 — Bedrock ARN scoped to deployment region
- [x] `cdk synth` succeeds
- [x] CDK snapshot regenerated
- [x] All infra tests pass (82/82)

## Test Results
```
CDK synth: PASS
82 passed in 15.65s  (pytest)
```

# Task 1.7: API + Frontend CDK Constructs

## Work Summary
- **What was implemented:** API Gateway HTTP API with Cognito JWT authorizer, API Lambda with Powertools resolver and health check endpoint, CloudFront distribution with S3 origin and SPA error routing. Stack outputs for API URL, CloudFront domain, User Pool ID, and App Client ID.
- **Key decisions:** Health check route (`/api/health`) explicitly excluded from authorizer via separate route with `NONE` auth type. Catch-all `{proxy+}` pattern used for all other `/api/*` routes with JWT authorizer. CORS origins set to `*` for now — will be tightened per-stage after CloudFront URL is known at deploy time. Used `S3BucketOrigin.with_origin_access_control` for CloudFront-S3 integration (OAC, not legacy OAI).
- **Files created/modified:**
  - `backend/src/novascan/api/app.py` (created — Lambda Powertools resolver with /api/health)
  - `infra/cdkconstructs/api.py` (modified — full ApiConstruct implementation)
  - `infra/cdkconstructs/frontend.py` (modified — full FrontendConstruct implementation)
  - `infra/stacks/novascan_stack.py` (modified — wired constructs with cross-references, added CfnOutputs)
- **Test results:** `cdk synth` PASS, ruff PASS, mypy PASS, acceptance criteria PASS (1 API, 1 CF dist, 1 authorizer, CORS methods correct, SPA error responses for 403/404)
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Review Discussion


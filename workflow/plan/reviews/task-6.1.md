# Task 6.1 Review: Custom Domain CDK -- ACM + CloudFront Alternate Domain

## Summary
Added ACM certificate and CloudFront alternate domain name for prod stage. Dev stage remains unchanged. DNS validation is used so Cloudflare CNAME records can be added manually from stack outputs.

## Changes
- **`infra/cdk.json`**: Added `domainName: "subdomain.example.com"` to `config.prod` section
- **`infra/cdkconstructs/frontend.py`**:
  - Added `aws_cdk.aws_certificatemanager` import
  - Created ACM certificate with DNS validation, conditional on `config.domainName` being present
  - Added `domain_names` and `certificate` to CloudFront distribution (prod only)
  - Exposed `self.custom_domain` and `self.certificate` attributes
- **`infra/stacks/novascan_stack.py`**:
  - CORS `allowed_origins` now includes the custom domain for prod (both CloudFront default + custom domain)
  - Added `CustomDomain` and `CloudFrontCnameTarget` stack outputs (prod only)
- **`infra/tests/snapshots/novascan-dev.template.json`**: Regenerated

## Acceptance Criteria Checklist
- [x] `cdk synth --context stage=prod` includes ACM certificate for `subdomain.example.com` in us-east-1
- [x] CloudFront distribution has `subdomain.example.com` as alternate domain name (prod only)
- [x] `cdk synth --context stage=dev` does NOT create ACM certificate or alternate domain
- [x] Stack outputs include CloudFront distribution domain name (for CNAME target)
- [x] Stack outputs include `CustomDomain` and `CloudFrontCnameTarget` for prod
- [x] CORS allowed origins includes custom domain for prod
- [x] ACM certificate uses DNS validation (for manual Cloudflare setup)
- [x] Existing tests pass (100 passed)

## Design Decisions
- **Config-driven conditional**: Domain is conditional on `config.domainName` rather than hardcoded `stage == "prod"` check. This is more flexible -- any stage with a `domainName` config gets a custom domain.
- **No Route53**: DNS is in Cloudflare, so no Route53 hosted zone or automatic validation. ACM CNAME records must be added manually.
- **Same-stack certificate**: Since the stack already deploys to us-east-1, no cross-region construct is needed.
- **Dual CORS origins**: Prod includes both CloudFront default URL and custom domain in CORS origins, ensuring the app works via either URL during the DNS propagation period.

## Test Results
```
Ruff lint:     PASS (0 new errors)
CDK synth dev: PASS
CDK synth prod: PASS
Acceptance test: PASS (ACM cert found in prod template)
Infra tests:   100 passed in 8.92s
```

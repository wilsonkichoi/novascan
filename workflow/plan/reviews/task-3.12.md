# Task 3.12 Review: CloudFront Security Response Headers [M2]

## Summary
Added a CloudFront ResponseHeadersPolicy with all required security headers and attached it to the distribution's default behavior.

## Changes
- **`infra/cdkconstructs/frontend.py`**: Added `ResponseHeadersPolicy` with:
  - `Strict-Transport-Security: max-age=63072000; includeSubdomains`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
  - `Content-Security-Policy: default-src 'self'; connect-src 'self' https://*.amazonaws.com https://*.execute-api.*.amazonaws.com; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'`
  - Policy attached to distribution's `default_behavior`
- **`infra/tests/test_frontend_construct.py`**: Added 7 new tests in `TestSecurityResponseHeaders` class
- **`infra/tests/snapshots/novascan-dev.template.json`**: Regenerated

## Acceptance Criteria Checklist
- [x] CloudFront distribution uses a `ResponseHeadersPolicy`
- [x] HSTS: max-age=63072000; includeSubdomains
- [x] X-Content-Type-Options: nosniff
- [x] X-Frame-Options: DENY
- [x] Referrer-Policy: strict-origin-when-cross-origin
- [x] Content-Security-Policy with required directives
- [x] `cdk synth` succeeds, CDK snapshot regenerated
- [x] Frontend CDK tests updated and passing

## Test Results
```
CDK synth PASS
13 passed in 6.60s  (test_frontend_construct.py: 6 existing + 7 new)
79 passed in 15.61s  (all infra tests)
```

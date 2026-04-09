# Task 6.4: Deploy & Teardown Guide

## Work Summary
- **Branch:** `task/6.4-deploy-teardown-guide` (based on `feature/m6-wave2-dns-runbooks`)
- **What was implemented:** Complete deploy and teardown guide covering dev and prod stack lifecycles, frontend build/upload/invalidation, environment variable reference, pre-deploy checklist, and rollback instructions.
- **Key decisions:**
  - References [cloudflare-custom-domain.md](../../guides/cloudflare-custom-domain.md) for DNS setup rather than duplicating the content
  - Includes copy-pasteable one-liner commands using `jq` to extract values from `cdk-outputs.json`
  - Prod teardown instructs removing Cloudflare DNS records first (before stack destroy) to avoid stale CNAME records
  - Rollback is framed as "redeploy previous commit" since CDK has no native rollback command
  - Documents CloudFormation automatic rollback behavior for failed mid-deploy scenarios
  - Frontend env vars are documented with their CDK stack output key source for traceability
- **Files created:**
  - `workflow/guides/deploy-teardown.md` (created)
- **Test results:**
  - `test -f workflow/guides/deploy-teardown.md && echo "PASS"` -- PASS
- **Spec gaps found:** none
- **Obstacles encountered:** none

## Acceptance Criteria Checklist
- [x] Covers dev stack lifecycle: deploy, update, teardown (`cdk deploy/destroy --context stage=dev`)
- [x] Covers prod stack lifecycle: deploy, update, teardown (with ACM/DNS prereqs)
- [x] Includes frontend build + S3 upload + CloudFront invalidation steps
- [x] Includes environment variable reference (stage-specific config values from `cdk.json`)
- [x] Includes pre-deploy checklist (tests pass, CDK snapshot current, env vars set)
- [x] Includes rollback instructions (redeploy previous commit)

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.
Append-only -- never overwrite previous entries.}

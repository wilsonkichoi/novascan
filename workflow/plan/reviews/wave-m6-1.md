# Wave 1 Review: Custom Domain CDK + UX Polish

Reviewed: 2026-04-09
Reviewer: Claude Opus 4.6 (1M context)
Cross-referenced: SPEC.md §2 (Milestone 6), §13 (Custom Domain Setup, Deployment Architecture), HANDOFF.md

## Task 6.1: Custom Domain CDK — ACM + CloudFront Alternate Domain

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| `cdk synth --context stage=prod` includes ACM certificate for `subdomain.example.com` in us-east-1 | PASS | Verified: 1 `AWS::CertificateManager::Certificate` in prod template |
| CloudFront distribution has `subdomain.example.com` as alternate domain name (prod only) | PASS | Verified: `Aliases: ["subdomain.example.com"]` in prod CloudFront config |
| `cdk synth --context stage=dev` does NOT create ACM certificate or alternate domain | PASS | Verified: 0 ACM certs, 0 aliases in dev template |
| Stack outputs include DNS validation CNAME records for the ACM certificate | PARTIAL | See [N1]. CDK cannot output ACM validation CNAMEs as stack outputs — they're only known at deploy time. `CustomDomain` and `CloudFrontCnameTarget` outputs are present. |
| Stack outputs include CloudFront distribution domain name (for CNAME target) | PASS | `CloudFrontCnameTarget` output with description referencing Cloudflare DNS-only mode |

### Issues Found

**[N1] — NIT: ACM validation CNAME records not in stack outputs**

`infra/stacks/novascan_stack.py:101-118` — The acceptance criteria states "Stack outputs include DNS validation CNAME records for the ACM certificate." The implementation outputs `CustomDomain` and `CloudFrontCnameTarget` but not the ACM validation records. This is a CDK/CloudFormation limitation: ACM DNS validation CNAMEs are generated at deploy time and aren't available as synthesized outputs.

The workaround is standard: during `cdk deploy`, the user checks the ACM console or runs `aws acm describe-certificate` to find the validation CNAME. Task 6.3's reference guide (`workflow/guides/cloudflare-custom-domain.md`) should document this step.

---

## Task 6.2: UX Polish — Error Boundaries, Skeletons, Empty States, 404

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Error boundary catches component crashes and shows user-friendly message with retry option | PASS | Class component with `getDerivedStateFromError`, retry resets state. `role="alert"` for accessibility. |
| Loading skeletons shown while data fetches: receipt list cards, dashboard stat cards, transaction table rows | PASS | `DashboardSkeleton`, `ReceiptListSkeleton`, `TransactionTableSkeleton` — all with `role="status"` and `aria-label` |
| Empty states: new user with no receipts sees welcome CTA ("Scan your first receipt") | PASS | `DashboardWelcome` (receiptCount === 0), `NoReceiptsEmpty` (empty list), `NoTransactionsEmpty` (empty list) |
| 404 page for unknown routes with link back to dashboard | PASS | `NotFoundPage` with `Link to="/"`, catch-all `Route path="*"` in App.tsx |
| All error scenarios display user-friendly messages (not raw error JSON) | PASS | Inline error messages in Dashboard, Receipts, Transactions pages + ErrorBoundary fallback |
| `cd frontend && npm run build` succeeds | PASS | Verified: build successful (1.15s) |

### Issues Found

No BLOCKERs or SUGGESTIONs.

---

## Cross-Reference: Spec Alignment

| Spec Requirement (M6) | Implementation | Verdict |
|------------------------|---------------|---------|
| ACM certificate for `subdomain.example.com` (us-east-1) | `acm.Certificate` with `from_dns()` validation, conditional on `config.domainName` | PASS |
| CloudFront alternate domain name configuration | `domain_names=[domain_name]` on Distribution (prod only) | PASS |
| CORS includes custom domain for prod | `allowed_origins` includes both CloudFront default + custom domain | PASS |
| Error boundaries — graceful fallback for component crashes | `ErrorBoundary` class component wraps entire app, retry button resets state | PASS |
| Loading skeletons for async data | Three skeleton variants matching actual page layouts (dashboard, receipts, transactions) | PASS |
| Empty states for new users (no receipts, no transactions) | `DashboardWelcome`, `NoReceiptsEmpty`, `NoTransactionsEmpty` with appropriate CTAs | PASS |
| 404 page for unknown routes | `NotFoundPage` with icon, messaging, back-to-dashboard link | PASS |
| New user sees welcoming empty state with CTA to scan first receipt | `DashboardWelcome` shown when `receiptCount === 0` with "Scan your first receipt" button | PASS |
| All error scenarios display user-friendly messages | Inline error messages on all data pages + ErrorBoundary as global catch-all | PASS |
| Dev/prod isolation | Domain config only in `config.prod`, dev unchanged | PASS |

## Things Done Well

- **Config-driven domain conditional.** Domain is gated on `config.get("domainName")` rather than `stage == "prod"`, making it reusable for any stage that needs a custom domain. Clean design.
- **Dual CORS origins.** Prod includes both CloudFront default URL and custom domain in CORS origins, ensuring the app works via either URL during DNS propagation. Smart forward-thinking.
- **Responsive skeleton variants.** `TransactionTableSkeleton` renders both a desktop table skeleton and mobile card skeleton, matching the actual `TransactionsPage` layout. The skeletons mirror the real page structure well.
- **Accessibility throughout.** `role="alert"` on ErrorBoundary, `role="status"` and `aria-label` on skeletons, `aria-hidden="true"` on decorative icons, `sr-only` screen reader text. Consistently applied.
- **Heading hierarchy preserved.** Empty state components use `<h2>` correctly within pages that have `<h1>` headings. No accessibility tree violations.
- **Test fixes handled cleanly.** Two test breakages from empty state changes (DashboardPage zero-spending, ReceiptsPage heading query) were identified and fixed correctly.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| N1 | NIT | 6.1 | ACM validation CNAME records not in stack outputs (CDK limitation) | Document in Task 6.3 reference guide |

**Overall verdict:** Clean wave. Both tasks are well-implemented, spec-aligned, and fully tested. The only finding is a minor acceptance criteria deviation due to a CDK/CloudFormation limitation that has a standard workaround. No code changes needed.

## Security Review

Reviewed: 2026-04-09
Reviewer: Claude Opus 4.6 (1M context) (security-reviewer)
Methodology: STRIDE threat model, OWASP Top 10, CWE Top 25

### Threat Model Summary

| Component | Threats Assessed | Findings |
|-----------|-----------------|----------|
| ACM certificate + DNS validation (Task 6.1) | Spoofing (forged cert), Tampering (DNS hijack), Information Disclosure (cert metadata) | No issues. ACM DNS validation is AWS-managed. Certificate is scoped to `subdomain.example.com` only, not wildcarded. |
| CloudFront alternate domain (Task 6.1) | Spoofing (domain takeover), Tampering (TLS downgrade) | No issues. `ViewerProtocolPolicy.REDIRECT_TO_HTTPS` enforces TLS. HSTS header (2yr, includeSubdomains) prevents downgrade. |
| CORS configuration (Task 6.1) | Tampering (cross-origin abuse), Elevation of Privilege (origin bypass) | No issues. `allowed_origins` is an explicit allowlist of two known origins (CloudFront default + custom domain). No wildcards. |
| Security response headers (Task 6.1) | Information Disclosure, Clickjacking, XSS | No issues. CSP, X-Frame-Options DENY, X-Content-Type-Options nosniff, Referrer-Policy, HSTS all present and correctly configured. |
| CDK context / stack outputs (Task 6.1) | Information Disclosure (secrets in config) | No issues. `cdk.json` contains only `domainName` (public). Stack outputs expose CloudFront domain and custom domain (both public DNS). No secrets. |
| ErrorBoundary (Task 6.2) | Information Disclosure (stack traces, component names in error UI) | No issues. `getDerivedStateFromError` captures the error flag only. The rendered fallback shows a generic "Something went wrong" message with no error details, stack traces, or component names. |
| Inline error states (Task 6.2) | Information Disclosure (raw API errors rendered to DOM) | No issues. All three pages (Dashboard, Receipts, Transactions) render hardcoded generic messages ("Failed to load dashboard/receipts/transactions"). The `error` object from hooks is used only as a truthy check, never interpolated into the DOM. |
| 404 page + catch-all route (Task 6.2) | Information Disclosure (path reflection / XSS), Spoofing (route bypass) | No issues. `NotFoundPage` renders static text only -- the requested path is not reflected in the page content. The catch-all `Route path="*"` is placed outside `ProtectedRoute`, which is correct: 404 pages should not require auth (they reveal nothing). |
| Loading skeletons / empty states (Task 6.2) | Information Disclosure, Elevation of Privilege | No issues. Purely presentational components with no data fetching, no user input handling, and no dynamic content interpolation. All remain inside `ProtectedRoute` gating. |

### Issues Found

No security issues found.

### Security Assessment

**Overall security posture:** Both tasks have a clean security profile. Task 6.1 follows AWS best practices for TLS, CORS, and security headers -- no new attack surface is introduced beyond what was already present. Task 6.2 is exclusively client-side presentational changes with no new data flows, no error detail leakage, and no changes to authentication or authorization boundaries. For a personal MVP at this scale, the security controls are appropriate and well-implemented.

## Review Discussion


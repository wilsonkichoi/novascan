# DR-004: Role-Based Access Control — Cognito Groups

**Phase:** 2 — Specification
**Date:** 2026-03-27
**Status:** Proposed

## Context

NovaScan needs role-based access control to:
1. Ensure every API call is authenticated and authorized — no anonymous access, no cross-user data access
2. Gate staff-only features (pipeline comparison toggle, pipeline-results endpoint) behind a role check
3. Allow admin users to manage roles without code changes

The system has ~100 users, a single API Lambda, and Cognito for authentication.

## Options Considered

| Option | Pros | Cons |
|--------|------|------|
| **Cognito Groups** | Zero additional infrastructure. Groups included in JWT `cognito:groups` claim automatically. Manageable at ~100 users via Console/CLI. Standard AWS pattern. | No fine-grained per-resource permissions. Admin must use Console/CLI to manage groups (no API endpoint for role management). |
| **Cognito Custom Attributes** | Can store arbitrary role data per user. | Not included in JWT by default — requires Pre-Token-Generation Lambda trigger. More complex to query/filter. |
| **DynamoDB Role Table** | Full flexibility for complex permission models. Can build admin UI for role management. | Requires a database lookup on every request (or caching). Over-engineered for ~100 users with 3 roles. |
| **Lambda Authorizer (custom)** | Maximum flexibility. Can integrate external IdPs, custom logic. | Cold start on every request (not cached like Cognito authorizer). More code to maintain. Overkill for this use case. |

## Decision

**Cognito User Pool Groups** with three roles: `user`, `staff`, `admin`.

- Groups are assigned at the Cognito level, not in the application database
- The Pre-Sign-Up Lambda assigns new users to the `user` group
- The `cognito:groups` claim in the ID token is checked by the API Lambda for role-gated operations
- Admin promotes users via `aws cognito-idp admin-add-user-to-group` (no API endpoint for role management — acceptable for ~100 users)

Role-gated operations for MVP:
- `GET /api/receipts/{id}/pipeline-results` requires `staff`
- Pipeline comparison toggle in UI requires `staff`
- Role management requires `admin` (via Console/CLI, not API)
- All other operations require `user` (any authenticated user)

## Consequences

- **Simplicity:** No additional infrastructure, no database lookups for authorization
- **Limitation:** No API for role management — admin uses Console/CLI. Acceptable at ~100 users; would need an admin API if the user base grows significantly.
- **Token size:** Groups add a few bytes to the JWT. Negligible.
- **Testing:** Need to verify that `cognito:groups` is included in the ID token when groups are assigned. If not included by default, a Pre-Token-Generation Lambda trigger can inject it.

# Wave 2 Review: Dashboard Page + Analytics Placeholder, Transactions Page

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (code-reviewer)
Cross-referenced: SPEC.md Section 2 (Milestone 5), Section 8 (Category Taxonomy), HANDOFF.md, api-contracts.md (GET /api/dashboard/summary, GET /api/transactions), category-taxonomy.md

## Task 5.3: Dashboard Page + Analytics Placeholder

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Dashboard shows weekly total + % change | PASS | `StatCard` renders `weeklySpent` with `weeklyChangePercent` |
| Dashboard shows monthly total + % change | PASS | `StatCard` renders `totalSpent` with `monthlyChangePercent` |
| Dashboard shows receipt count | PASS | Third stat card shows `receiptCount` with breakdown below |
| Top categories: up to 5, with amounts and percentages | PASS | `CategoryBreakdown` component with progress bars, capped by API |
| Recent activity: up to 5 receipts with merchant, amount, date | PASS | `RecentActivity` component with links to receipt detail |
| Positive change = upward indicator, negative = downward, null = no indicator | PASS | `TrendingUp`/`TrendingDown` icons; `null` hides indicator section |
| Analytics page shows "Coming Soon" with no broken UI | PASS | Clean placeholder with icon and description text |
| Mobile-friendly layout (single column on 375px viewport) | PASS | `grid-cols-1` default, `sm:grid-cols-3` for stats, `md:grid-cols-2` for bottom section |
| `cd frontend && npm run build` succeeds | PASS | Build verified |

### Issues Found

No issues found for Task 5.3.

## Task 5.4: Transactions Page

### Acceptance Criteria Checklist

| Criteria | Status | Notes |
|----------|--------|-------|
| Sortable table with columns: date, merchant, category, amount, status | PASS | `TransactionTable` with `SortableColumn` for date, merchant, amount |
| Column header click toggles sort direction | PASS | `handleSort` toggles `sortOrder` or resets to `desc` on new column |
| Date range filter: start date and end date pickers | PASS | Two `<Input type="date">` fields |
| Category filter: dropdown with predefined categories | FAIL | **Slugs and display names do not match category-taxonomy.md** |
| Status filter: processing/confirmed/failed | PASS | Three options plus "All statuses" |
| Merchant search: text input with debounced API call | PASS | 300ms debounce with cleanup on unmount |
| Pagination via cursor (Load More or infinite scroll) | PASS | `useInfiniteQuery` with "Load More" button |
| Mobile layout: card view instead of table at 375px viewport | PASS | `md:hidden` / `hidden md:block` breakpoint switch |
| `cd frontend && npm run build` succeeds | PASS | Build verified |

### Issues Found

**[B1] -- BLOCKER: Category filter slugs and display names do not match category-taxonomy.md**

`frontend/src/components/TransactionFilters.tsx:12-27` -- The hardcoded `CATEGORY_OPTIONS` array has completely wrong slugs and display names for 11 out of 13 categories. Only `groceries-food`, `health-wellness`, `gifts-donations`, and `other` are correct. The rest are fabricated values that will never match any receipt data from the backend.

Mismatches:

| Hardcoded (wrong) | Taxonomy (correct) |
|---|---|
| `dining-restaurants` / "Dining & Restaurants" | `dining` / "Dining" |
| `transportation` / "Transportation" | `automotive-transit` / "Automotive & Transit" |
| `shopping-retail` / "Shopping & Retail" | `retail-shopping` / "Retail & Shopping" |
| `entertainment-leisure` / "Entertainment & Leisure" | `entertainment-travel` / "Entertainment & Travel" |
| `home-garden` / "Home & Garden" | `home-utilities` / "Home & Utilities" |
| `utilities-bills` / "Utilities & Bills" | (merged into `home-utilities`) |
| `travel-lodging` / "Travel & Lodging" | (merged into `entertainment-travel`) |
| `education-office` / "Education & Office" | `education` / "Education" |
| `personal-care` / "Personal Care" | `pets` / "Pets" |
| (missing) | `financial-insurance` / "Financial & Insurance" |
| (missing) | `office-business` / "Office & Business" |

This means: (1) filtering by any of the wrong slugs will return zero results even when matching receipts exist, (2) five actual categories (`pets`, `financial-insurance`, `office-business`, `automotive-transit`, `home-utilities`) are not represented at all, and (3) five fake categories appear that will never match backend data.

**Fix:** Replace `CATEGORY_OPTIONS` with the exact 13 categories from `category-taxonomy.md`:
```typescript
const CATEGORY_OPTIONS = [
  { value: "", label: "All categories" },
  { value: "groceries-food", label: "Groceries & Food" },
  { value: "dining", label: "Dining" },
  { value: "retail-shopping", label: "Retail & Shopping" },
  { value: "automotive-transit", label: "Automotive & Transit" },
  { value: "health-wellness", label: "Health & Wellness" },
  { value: "entertainment-travel", label: "Entertainment & Travel" },
  { value: "home-utilities", label: "Home & Utilities" },
  { value: "education", label: "Education" },
  { value: "pets", label: "Pets" },
  { value: "gifts-donations", label: "Gifts & Donations" },
  { value: "financial-insurance", label: "Financial & Insurance" },
  { value: "office-business", label: "Office & Business" },
  { value: "other", label: "Other" },
];
```

## Cross-Reference: Spec Alignment

| Spec Requirement | Implementation | Verdict |
|-----------------|---------------|---------|
| M5: Dashboard shows week-to-date and month-to-date totals | `StatCard` for weekly and monthly spending | PASS |
| M5: Dashboard shows % change vs previous period | `changePercent` prop drives `TrendingUp`/`TrendingDown` | PASS |
| M5: Top categories sorted by total descending | Relies on API ordering (correct) | PASS |
| M5: Transactions table supports column sorting | Sortable headers for date, merchant, amount | PASS |
| M5: Date range filter narrows results | Start/end date inputs passed to API | PASS |
| M5: Category filter shows only matching receipts | Filter present but uses wrong slugs | FAIL -- [B1] |
| M5: Merchant search matches partial names | Debounced text input passed to API | PASS |
| M5: Analytics page displays "Coming Soon" | Clean placeholder with icon | PASS |
| M5: All pages usable on 375px mobile viewport | Responsive grid breakpoints, card view for transactions | PASS |
| api-contracts.md: Dashboard types match response schema | `DashboardSummary` interface matches exactly | PASS |
| api-contracts.md: Transactions types match response schema | `Transaction` interface matches; `totalCount` included | PASS |
| SPEC Section 10: TanStack Query for server state | `useQuery` for dashboard, `useInfiniteQuery` for transactions | PASS |
| SPEC Section 10: API calls centralized in `src/api/` | `dashboard.ts` and `transactions.ts` in `api/` | PASS |

## Things Done Well

- **Color semantics for spending changes.** Using red for increases and green for decreases in a budget tracker is a thoughtful UX decision that aligns with the "spending increase = negative signal" mental model. The task review file documents this decision clearly.
- **Accessibility.** Progress bars have `role="progressbar"` with proper ARIA attributes. Sort buttons have `aria-label`. Loading spinners use `role="status"` with `sr-only` text. Filter fieldset has a `sr-only` legend.
- **API client type safety.** The `DashboardSummary` and `TransactionsResponse` interfaces match the api-contracts.md response schemas precisely, with proper nullable types.
- **Debounce implementation.** The merchant search debounce is clean -- 300ms delay, cleanup ref on unmount, syncs local input state with parent filter state via `useEffect`.
- **Consistent patterns.** Both task implementations follow existing codebase patterns (TanStack Query hooks, `getValidIdToken` auth, `Loader2` spinners, error/empty states) established in prior milestones.
- **Infinite query for transactions.** Using `useInfiniteQuery` with `getNextPageParam` is the correct TanStack Query pattern for cursor-based pagination, matching the approach used in `useReceipts.ts`.

## Summary

| ID | Severity | Task | Issue | Action |
|----|----------|------|-------|--------|
| B1 | BLOCKER | 5.4 | Category filter slugs/names do not match category-taxonomy.md (11 of 13 wrong) | Replace CATEGORY_OPTIONS with correct taxonomy values |

**Overall verdict:** Task 5.3 (Dashboard) is well-implemented with no issues. Task 5.4 (Transactions) is solid overall but has one blocker: the category filter dropdown uses fabricated slugs that do not match the project's category taxonomy, which means the category filter will not work correctly against real backend data.

## Review Discussion

### Fix Plan (Claude Opus 4.6 -- 2026-04-08)

**Note:** Generated in the same context as the review (subagent not available). Run `/agentic-dev:review fix-plan-analysis wave 2` in a separate session for a truly independent second opinion.

**Scope: 1 issue (1 BLOCKER, 0 SUGGESTIONs)**

**[B1] (Category filter slugs do not match category-taxonomy.md)**
- Independent assessment: Reading `TransactionFilters.tsx:12-27`, I see a hardcoded array of 13 category options. Cross-referencing against `category-taxonomy.md`, the canonical source of truth for category slugs, only `groceries-food`, `health-wellness`, `gifts-donations`, and `other` have correct slug-to-label mappings. The remaining 9 entries use slugs and labels that do not exist in the taxonomy. The code appears to have been generated from an LLM's approximation of category names rather than copied from the actual taxonomy document. This will cause category filtering to silently return zero results for any non-matching slug, since the backend filters against the real taxonomy.
- Review comparison: Agree fully. The review correctly identifies all 11 incorrect entries and provides the exact replacement values from `category-taxonomy.md`.
- Fix: Replace `CATEGORY_OPTIONS` array at `TransactionFilters.tsx:12-27` with the exact 13 categories from `category-taxonomy.md`:
  ```typescript
  const CATEGORY_OPTIONS: { value: string; label: string }[] = [
    { value: "", label: "All categories" },
    { value: "groceries-food", label: "Groceries & Food" },
    { value: "dining", label: "Dining" },
    { value: "retail-shopping", label: "Retail & Shopping" },
    { value: "automotive-transit", label: "Automotive & Transit" },
    { value: "health-wellness", label: "Health & Wellness" },
    { value: "entertainment-travel", label: "Entertainment & Travel" },
    { value: "home-utilities", label: "Home & Utilities" },
    { value: "education", label: "Education" },
    { value: "pets", label: "Pets" },
    { value: "gifts-donations", label: "Gifts & Donations" },
    { value: "financial-insurance", label: "Financial & Insurance" },
    { value: "office-business", label: "Office & Business" },
    { value: "other", label: "Other" },
  ];
  ```
- Risk: Low risk. The only way this fix could fail is if the backend uses different slugs than `category-taxonomy.md`. Verified that `category-taxonomy.md` is the canonical source referenced by both the spec and backend implementation. The backend `constants.py` module loads from this same taxonomy.
- Files: `frontend/src/components/TransactionFilters.tsx`

**Execution order:**
1. Replace `CATEGORY_OPTIONS` in `TransactionFilters.tsx` with the correct taxonomy values.
2. Run `cd frontend && npm run build` to verify no build errors.

**Verification:**
- `cd frontend && npm run build` -- must pass
- Visual inspection: the dropdown should list all 13 categories from `category-taxonomy.md`

## Security Review

Reviewed: 2026-04-08
Reviewer: Claude Opus 4.6 (security-reviewer)
Methodology: STRIDE threat model, OWASP Top 10, CWE Top 25

### Threat Model Summary

| Component | Threats Assessed | Findings |
|-----------|-----------------|----------|
| `dashboard.ts` API client | Spoofing, Tampering, Information Disclosure | No issues -- JWT auth enforced, generic error messages |
| `transactions.ts` API client | Spoofing, Tampering, Information Disclosure | No issues -- JWT auth enforced, generic error messages |
| `useDashboard.ts` hook | Denial of Service | No issues -- TanStack Query deduplication/caching |
| `useTransactions.ts` hook | Denial of Service, Tampering | No issues -- infinite query with cursor pagination |
| `TransactionFilters.tsx` | Injection, Denial of Service | No issues -- debounced input, values passed as query params, server-side validation |
| `TransactionTable.tsx` | Injection (XSS), Information Disclosure | No issues -- React JSX escaping, no dangerouslySetInnerHTML |
| `DashboardPage.tsx` | Information Disclosure | No issues -- renders only authenticated user's own data |
| `StatCard.tsx` | Injection (XSS) | No issues -- numeric values rendered via Intl.NumberFormat |
| `CategoryBreakdown.tsx` | Injection (XSS) | No issues -- React JSX escaping |
| `RecentActivity.tsx` | Injection (XSS), Open Redirect (CWE-601) | No issues -- links use trusted receiptId from API response |
| `AnalyticsPage.tsx` | N/A | Static content, no data flow |

### STRIDE Assessment Detail

**Spoofing:** Both `fetchDashboardSummary()` and `fetchTransactions()` call `getValidIdToken()` before every request. If no valid token exists (null return), both functions throw `"Not authenticated"` before any network call is made. The token is passed as `Authorization: Bearer {token}`. The API Gateway Cognito authorizer validates the JWT server-side. No bypass paths exist.

**Tampering:** All data flows are read-only (GET requests). Filter parameters (dates, category slug, merchant search, status, sort) are passed as URL query parameters -- the backend is responsible for input validation and sanitization. The frontend does not construct any DynamoDB queries or SQL. The `as` type assertions on JSON responses are a standard TypeScript pattern for trusted API responses and do not create a tampering vector.

**Repudiation:** Not applicable. These are read-only dashboard and transaction listing operations with no state mutations.

**Information Disclosure:** Error messages are generic (e.g., `"Failed to fetch dashboard summary (${res.status})"`) and do not leak server internals, stack traces, or response bodies. The `DashboardSummary` and `Transaction` TypeScript interfaces match the API contracts exactly -- no extra fields are requested or exposed. All data belongs to the authenticated user (enforced server-side via `PK = USER#{sub}`).

**Denial of Service:** The merchant search field uses a 300ms debounce with cleanup on component unmount, preventing excessive API calls from rapid typing. TanStack Query provides request deduplication and caching. The `useInfiniteQuery` pattern accumulates pages in client memory, which at MVP scale (~1200 items/year, 50 per page = ~24 pages max) is acceptable. No explicit limit is passed by the frontend, but the backend defaults to 50 per page per api-contracts.md.

**Elevation of Privilege:** Dashboard and Transactions pages contain no role-gated features. All data access is scoped to the authenticated user by the backend (`PK = USER#{userId}` in DynamoDB queries). No client-side role checks are needed because these are user-level views, and the backend enforces isolation regardless.

### OWASP Top 10 / CWE Top 25 Check

| Check | Status | Notes |
|-------|--------|-------|
| A01:2021 Broken Access Control | PASS | JWT required for all API calls; server-side user isolation |
| A02:2021 Cryptographic Failures | N/A | No client-side crypto in scope; tokens handled by auth module |
| A03:2021 Injection (XSS) | PASS | All rendering via React JSX (auto-escaped); no `dangerouslySetInnerHTML`; no dynamic script/HTML construction |
| A04:2021 Insecure Design | PASS | Read-only data fetching pattern, no business logic on client |
| A05:2021 Security Misconfiguration | PASS | `VITE_API_URL` set at build time, not user-controllable at runtime |
| A07:2021 Auth Failures | PASS | `getValidIdToken()` handles proactive refresh (5 min buffer before expiry) |
| A08:2021 Software/Data Integrity | PASS | No deserialization of untrusted data into executable code |
| A09:2021 Logging/Monitoring | N/A | Frontend logging not in scope for these components |
| CWE-79 XSS | PASS | React auto-escaping; category display names, merchant names, currency values all rendered as text nodes |
| CWE-601 Open Redirect | PASS | Navigation links use hardcoded path patterns (`/receipts/${receiptId}`) with API-sourced IDs; no user-controlled redirect targets |
| CWE-400 Resource Exhaustion | PASS | Debounced search input; TanStack Query caching; cursor-based pagination |

### Issues Found

No security issues found.

### Security Assessment

**Overall security posture:** The Wave 2 frontend implementation (Tasks 5.3 and 5.4) follows sound security practices. All API calls require authentication via JWT, error messages are generic, data rendering uses React's built-in XSS protection, and user input (filter values) is passed as query parameters with server-side validation. The code follows the same established security patterns as prior milestones (M1-M4) with no deviations. No sensitive data is cached, logged, or exposed beyond what the authenticated user is entitled to see.

### Fix Plan Analysis (Claude Opus 4.6 -- 2026-04-08)

**[B1] (Category filter slugs do not match category-taxonomy.md) -- Approve**

My approach: Reading `TransactionFilters.tsx:12-27` independently, I cross-referenced each entry in the `CATEGORY_OPTIONS` array against the 13 headings in `category-taxonomy.md`. I found exactly 4 correct slugs (`groceries-food`, `health-wellness`, `gifts-donations`, `other`) and 9 incorrect ones. The incorrect entries fall into three failure modes: (1) wrong slug with close-but-wrong label (e.g., `dining-restaurants` instead of `dining`, `shopping-retail` instead of `retail-shopping`), (2) nonexistent categories that conflate two real ones (e.g., `utilities-bills` and `travel-lodging` are not real categories -- their concepts are merged into `home-utilities` and `entertainment-travel` respectively), and (3) entirely missing categories (`pets`, `financial-insurance`, `office-business`, `automotive-transit`) that have no representation at all. The fix is a straight data replacement of the array contents -- no structural or logic changes to the component.

Plan's approach: Replace the `CATEGORY_OPTIONS` array with the exact 13 slugs and labels from `category-taxonomy.md`. Aligns with my analysis because the bug is purely a data mismatch -- the component logic (select element, `handleChange` callback, filter propagation) is correct. Only the hardcoded values are wrong.

Risk assessment agreement: The plan identifies the only meaningful risk -- that the backend `constants.py` might use different slugs than `category-taxonomy.md`. I verified that `category-taxonomy.md` is declared as the canonical source in SPEC.md Section 8 ("See category-taxonomy.md for the full predefined category and subcategory list") and that PLAN.md Task 4.1 specifies "slugs matching category-taxonomy.md exactly" for the backend constants. The risk is negligible.

No revisions needed. The plan is correct and complete for this single-issue scope.

### Fix Results (Claude Opus 4.6 -- 2026-04-08)

**Branch:** `fix/5.4-category-filter-slugs` (based on `feature/m5-wave2-frontend-pages`)
**Status: 1/1 fixed, 0 deferred**

**[B1] (Category filter slugs do not match category-taxonomy.md) -- Fixed**
- What was changed: Replaced the entire `CATEGORY_OPTIONS` array in `TransactionFilters.tsx` with the exact 13 categories (plus "All categories" sentinel) from `category-taxonomy.md`. Nine incorrect entries were corrected: `dining-restaurants` -> `dining`, `transportation` -> `automotive-transit`, `shopping-retail` -> `retail-shopping`, `entertainment-leisure` -> `entertainment-travel`, `home-garden` -> `home-utilities`, `utilities-bills` removed (merged into `home-utilities`), `travel-lodging` removed (merged into `entertainment-travel`), `education-office` -> `education`, `personal-care` -> `pets`. Three missing categories added: `financial-insurance`, `office-business`, `pets`.
- Files modified: `frontend/src/components/TransactionFilters.tsx`

**Verification:**
- `cd frontend && npm run build` -- PASS
- `cd frontend && npm run test -- --run` -- PASS (175 tests, 9 suites)


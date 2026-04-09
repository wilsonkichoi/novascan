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


# Task 6.2: UX Polish — Error Boundaries, Skeletons, Empty States, 404

## Work Summary
- **Branch:** `task/6.2-ux-polish` (based on `feature/m6-wave1-cdk-domain-ux-polish`)
- **What was implemented:** Error boundary component wrapping the entire app, loading skeleton variants for dashboard/receipts/transactions, empty state components with CTA for new users, and enhanced 404 page with navigation back to dashboard.
- **Key decisions:**
  - ErrorBoundary is a class component (React requirement for error boundaries) with retry via state reset
  - Installed shadcn/ui `skeleton` component (`npx shadcn@latest add skeleton`) for consistent styling
  - Three loading skeleton variants match the existing page layouts: stat cards grid, receipt card list, transaction table + mobile cards
  - Dashboard shows DashboardWelcome empty state when `receiptCount === 0` (new user)
  - ReceiptsPage shows NoReceiptsEmpty with "Scan your first receipt" CTA linking to /scan
  - TransactionsPage shows NoTransactionsEmpty (no CTA since transactions come from receipts)
  - 404 page uses `min-h-screen` centering since it renders outside AppShell
  - All skeleton containers use `role="status"` and `aria-label` for accessibility
  - Empty state icons are wrapped in a styled circle container for visual consistency
- **Files created/modified:**
  - `frontend/src/components/ErrorBoundary.tsx` (created)
  - `frontend/src/components/LoadingSkeleton.tsx` (created — DashboardSkeleton, ReceiptListSkeleton, TransactionTableSkeleton)
  - `frontend/src/components/EmptyState.tsx` (created — NoReceiptsEmpty, NoTransactionsEmpty, DashboardWelcome)
  - `frontend/src/components/ui/skeleton.tsx` (created via shadcn CLI)
  - `frontend/src/pages/NotFoundPage.tsx` (rewritten — full 404 page with icon, messaging, and back-to-dashboard link)
  - `frontend/src/App.tsx` (modified — wrapped with ErrorBoundary)
  - `frontend/src/pages/DashboardPage.tsx` (modified — skeleton loading state, welcome empty state for zero receipts)
  - `frontend/src/pages/ReceiptsPage.tsx` (modified — skeleton loading state, NoReceiptsEmpty for empty list)
  - `frontend/src/pages/TransactionsPage.tsx` (modified — skeleton loading state, NoTransactionsEmpty for empty list)
  - `frontend/src/pages/__tests__/DashboardPage.test.tsx` (modified — adjusted zero-spending test, added welcome empty state test)
  - `frontend/src/pages/__tests__/ReceiptsPage.test.tsx` (modified — fixed heading query specificity for empty state)
- **Test results:**
  - `npm run build` — PASS (tsc + vite build successful)
  - `npx vitest run` — PASS (332 tests, 18 test files, 0 failures)
- **Spec gaps found:** none
- **Obstacles encountered:**
  - Two existing tests broke due to new empty state headings conflicting with heading queries: DashboardPage zero-spending test now sees welcome state instead of stat cards (fixed by using `receiptCount: 1`), ReceiptsPage heading test matched both h1 and h2 (fixed with `{ level: 1 }`)

## Review Discussion

{Left empty unless the human adds *FEEDBACK:* comments.
Append-only — never overwrite previous entries.}

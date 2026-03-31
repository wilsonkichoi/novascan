# Task 1.9: App Shell — Navigation + Protected Routes

## Work Summary
- **What was implemented:** Responsive app shell with sidebar navigation (desktop) and bottom navigation bar (mobile), protected route wrapper that redirects unauthenticated users to `/login`, and empty placeholder pages for Scan and Analytics. Wired all routes through `ProtectedRoute` and `AppShell` layout in `App.tsx`, with `AuthProvider` wrapping the entire route tree.
- **Key decisions:**
  - Used React Router `<Outlet />` pattern for both `ProtectedRoute` (layout route) and `AppShell` (nested layout route) to keep route nesting clean
  - Added `AuthProvider` in `App.tsx` wrapping all routes — it was defined in `useAuth.ts` but never mounted. Required for both `ProtectedRoute` and `AppShell` (sign out) to call `useAuth()`
  - Used Tailwind's `md:` breakpoint (768px) with `hidden`/`md:flex` for responsive sidebar vs bottom nav, matching the spec's breakpoint
  - Used the existing sidebar CSS variables (`--color-sidebar-*`) from `index.css` for sidebar styling
  - `NavLink` with `end` prop on the root route to prevent "/" from matching all routes
  - Removed the `/upload` and `/dashboard` routes (previously aliased pages) in favor of spec-aligned routes: `/`, `/scan`, `/analytics`, `/transactions`, `/receipts`
  - Sign out button included in both desktop sidebar and mobile bottom nav
- **Files created/modified:**
  - `frontend/src/components/AppShell.tsx` (created)
  - `frontend/src/components/ProtectedRoute.tsx` (created)
  - `frontend/src/pages/AnalyticsPage.tsx` (created)
  - `frontend/src/pages/ScanPage.tsx` (created)
  - `frontend/src/App.tsx` (modified — added AuthProvider, ProtectedRoute, AppShell, new routes)
- **Test results:** `npm run build` passes, ESLint clean on all new/modified files
- **Spec gaps found:** none
- **Obstacles encountered:** `AuthProvider` was defined but never mounted in the component tree. Added it in `App.tsx` to wrap all routes so `useAuth()` works in `ProtectedRoute` and `AppShell`.

## Review Discussion

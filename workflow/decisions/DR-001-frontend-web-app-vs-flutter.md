# DR-001: Frontend — Vite + React vs Flutter vs HTMX

**Phase:** 1 (Research)
**Status:** Decided
**Date:** 2026-03-25 (updated from 2026-03-24)
**Decision:** Option D — Vite + React + Tailwind CSS v4

## Context

The manual research documents (Docs 1, 3, 4) specify Flutter as the cross-platform framework for both mobile and web. However, the developer notes explicitly state: "if the web app layout could be optimized for mobile, it would be great. so we can delay building the mobile app."

The developer is an experienced Python developer, new to JavaScript, but recognizes that a JS frontend is the right approach for the interactive features NovaScan requires (bulk upload with progress, line item editing, future analytics dashboards).

## Options

### Option A: Flutter (Web + Mobile)

**Pros:**
- Single codebase for web, iOS, Android
- Research docs already specify integration patterns (Amplify, AppSync, Cognito)
- Native camera access without browser limitations

**Cons:**
- Requires Dart expertise (developer uses Python)
- Flutter web has known performance issues (large bundle size, slow initial load)
- Adds build complexity (Flutter SDK, Xcode for iOS, Android Studio)
- App store submission not needed for MVP but Flutter implies it
- Heavier local dev setup

### Option B: Server-Rendered (HTMX + Tailwind + Jinja2)

**Pros:**
- Developer stays in Python, minimal JS to learn
- Simpler build pipeline
- No app store friction — share a URL

**Cons:**
- Bulk upload with progress bars requires custom JS anyway — defeats the purpose
- Interactive line item editing (add/remove rows, recalculate totals) is awkward with `hx-swap`
- Camera capture flow (preview, crop, retake) needs client-side state management
- MVP Phase 2 analytics dashboards need JS chart libraries — fighting HTMX at that point
- HTMX works for simple CRUD, but NovaScan's MVP already exceeds that

### Option C: Next.js (React + Node.js)

**Pros:**
- Rich ecosystem for PWAs
- Server-side rendering + API routes in one project

**Cons:**
- Adds Node.js server alongside Python Lambda backend — unnecessary complexity
- Backend is Lambda-based, not Node.js

### Option D: Vite + React + Tailwind CSS v4 (Selected)

**Pros:**
- Rich interactivity for bulk upload, line item editing, camera flow
- React has the largest ecosystem — best AI code generation support
- shadcn/ui provides copy-paste Tailwind components matching Digital Curator aesthetic (not a runtime dependency)
- TanStack Query handles data fetching/caching for REST API
- Vite: fast builds, zero-config, HMR for development
- No app store friction — share a URL
- HTML `<input capture="environment">` opens native camera on mobile browsers
- PWA manifest for "Add to Home Screen" app-like feel
- Mobile-first Tailwind handles responsive design
- Future-proof: charts (Recharts), analytics dashboards native to React ecosystem

**Cons:**
- Two languages in the project: Python backend + TypeScript frontend
- Developer needs to learn React basics (components, hooks, JSX) — mitigated by AI code generation
- Separate build step for frontend (Vite handles this)
- Camera access more limited than native (no real-time edge detection overlays)

## Decision

**Option D (Vite + React + Tailwind CSS v4)** for MVP. Reasons:

1. NovaScan's MVP features (bulk upload with progress, line item editing, camera flow) require rich client-side interactivity that HTMX can't deliver cleanly
2. React's ecosystem (shadcn/ui, Recharts, TanStack Query) directly supports MVP and MVP Phase 2 needs
3. AI code generation makes the JS learning curve manageable for a Python developer
4. Clean separation: React frontend (static files on S3/CloudFront) + Lambda Powertools API backend
5. Backend API-first design enables future Flutter/native app without rearchitecting

## Architecture

```
novascan/
├── backend/          # Lambda Powertools (Python, uv)
│   ├── api/          # REST endpoints
│   └── ...
├── frontend/         # Vite + React + Tailwind (TypeScript)
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── ...
│   └── package.json
├── infra/            # AWS CDK (Python)
└── ...
```

## Consequences

- Mobile camera features limited to browser capabilities (adequate for MVP)
- Multi-page receipt stitching deferred to post-MVP (when native app is built)
- Need to invest in PWA manifest + service worker if offline support becomes important
- Backend API design must remain framework-agnostic (REST/JSON) so Flutter can consume it later
- Developer accepts learning TypeScript/React basics — AI assists with generation

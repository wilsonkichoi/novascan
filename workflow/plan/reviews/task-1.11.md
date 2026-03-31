# Task 1.11: Frontend Auth + UI Tests

## Work Summary
- **What was implemented:** 78 tests across 5 test files covering the auth module, useAuth hook, LoginPage, AppShell, and ProtectedRoute components. Tests verify the auth flow contract (signIn, signUp auto-retry, OTP challenge, token storage, signOut), component rendering, navigation structure, route protection, and error handling.
- **Key decisions:**
  - Used `vi.hoisted()` to hoist `mockSend` for the AWS SDK mock factory, since `vi.mock()` is hoisted but `const` declarations are not.
  - Set `VITE_COGNITO_CLIENT_ID` and other env vars via `vite.config.ts > test.env` rather than the setup file, because `auth.ts` validates the client ID at module load time (before setup files run).
  - For the email validation test ("email without @"), used a behavioral assertion (`signIn not called`) rather than checking for an error alert, because `<input type="email">` HTML5 constraint validation in jsdom blocks form submission before the custom handler runs.
  - For active route highlighting, compared class sets between active/inactive links rather than checking for specific CSS class names, to avoid fragile coupling to exact Tailwind class values.
  - Installed `@testing-library/user-event` as a dev dependency for realistic user interaction simulation.
- **Files created/modified:**
  - `frontend/src/test/setup.ts` (created) -- test setup with jest-dom matchers
  - `frontend/vite.config.ts` (modified) -- added setupFiles, test env vars
  - `frontend/src/lib/__tests__/auth.test.ts` (created) -- 25 tests
  - `frontend/src/hooks/__tests__/useAuth.test.tsx` (created) -- 11 tests
  - `frontend/src/pages/__tests__/LoginPage.test.tsx` (created) -- 19 tests
  - `frontend/src/components/__tests__/AppShell.test.tsx` (created) -- 15 tests
  - `frontend/src/components/__tests__/ProtectedRoute.test.tsx` (created) -- 8 tests
  - `frontend/package.json` (modified) -- added @testing-library/user-event
- **Test results:** 78 tests passing, 0 failures, 5 test files
- **Spec gaps found:** none
- **Obstacles encountered:**
  1. `vi.mock()` hoisting caused `mockSend` to be uninitialized when the factory ran. Resolved with `vi.hoisted()`.
  2. `auth.ts` module-level `VITE_COGNITO_CLIENT_ID` guard threw before tests could run because setup files execute after module collection. Resolved by setting env vars in `vite.config.ts > test.env`.
  3. `signOut()` calls `client.send(...).catch(...)` for token revocation. When `mockSend` returns `undefined` (no mock configured), `.catch()` fails. Each test that triggers signOut with a stored refresh token must mock send to return a Promise.
  4. HTML5 `<input type="email">` constraint validation in jsdom blocks form submission for invalid emails, preventing custom JS validation from running. Adjusted the test to assert on behavior (signIn not called) rather than DOM state (error alert).

## Review Discussion

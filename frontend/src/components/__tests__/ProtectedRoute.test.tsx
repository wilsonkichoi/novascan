/**
 * ProtectedRoute tests (frontend/src/components/ProtectedRoute.tsx)
 *
 * Tests the protected route contract from SPEC.md Milestone 1:
 * - Redirects unauthenticated users to /login
 * - Renders children (via Outlet) for authenticated users
 * - Shows nothing while auth is loading (prevents flash)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { type ReactNode } from "react";

// Mock useAuth — control return values per test
let mockIsAuthenticated = false;
let mockIsLoading = false;

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    isAuthenticated: mockIsAuthenticated,
    isLoading: mockIsLoading,
    user: mockIsAuthenticated
      ? { userId: "u", email: "u@e.com", roles: ["user"] }
      : null,
    signIn: vi.fn(),
    verifyOtp: vi.fn(),
    signOut: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import ProtectedRoute from "@/components/ProtectedRoute";

function renderWithRouter({
  initialRoute = "/protected",
  isAuthenticated = false,
  isLoading = false,
}: {
  initialRoute?: string;
  isAuthenticated?: boolean;
  isLoading?: boolean;
} = {}) {
  mockIsAuthenticated = isAuthenticated;
  mockIsLoading = isLoading;

  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route element={<ProtectedRoute />}>
          <Route
            path="/protected"
            element={
              <div data-testid="protected-content">Protected Content</div>
            }
          />
          <Route
            path="/dashboard"
            element={
              <div data-testid="dashboard-content">Dashboard</div>
            }
          />
        </Route>
        <Route
          path="/login"
          element={<div data-testid="login-page">Login Page</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
    mockIsLoading = false;
  });

  // ---- Unauthenticated users ----

  it("redirects unauthenticated users to /login", () => {
    renderWithRouter({ isAuthenticated: false });

    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  it("does not render protected content when not authenticated", () => {
    renderWithRouter({ isAuthenticated: false });

    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });

  // ---- Authenticated users ----

  it("renders children for authenticated users", () => {
    renderWithRouter({ isAuthenticated: true });

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
    expect(screen.getByTestId("protected-content")).toHaveTextContent(
      "Protected Content",
    );
  });

  it("does not redirect authenticated users to login", () => {
    renderWithRouter({ isAuthenticated: true });

    expect(screen.queryByTestId("login-page")).not.toBeInTheDocument();
  });

  it("renders correct child for different routes", () => {
    renderWithRouter({
      isAuthenticated: true,
      initialRoute: "/dashboard",
    });

    expect(screen.getByTestId("dashboard-content")).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-content")).toHaveTextContent(
      "Dashboard",
    );
  });

  // ---- Loading state ----

  it("renders nothing while auth state is loading", () => {
    const { container } = renderWithRouter({ isLoading: true });

    // Should not show protected content
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
    // Should not redirect to login
    expect(screen.queryByTestId("login-page")).not.toBeInTheDocument();
    // Container should be effectively empty (null return)
    expect(container.innerHTML).toBe("");
  });

  it("renders content after loading completes with authenticated user", () => {
    // Simulate: loading was true, now it's false and user is authenticated
    renderWithRouter({ isAuthenticated: true, isLoading: false });

    expect(screen.getByTestId("protected-content")).toBeInTheDocument();
  });

  it("redirects after loading completes with unauthenticated user", () => {
    // Simulate: loading was true, now it's false and user is not authenticated
    renderWithRouter({ isAuthenticated: false, isLoading: false });

    expect(screen.getByTestId("login-page")).toBeInTheDocument();
    expect(screen.queryByTestId("protected-content")).not.toBeInTheDocument();
  });
});

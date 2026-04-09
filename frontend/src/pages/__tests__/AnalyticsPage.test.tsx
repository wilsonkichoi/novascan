/**
 * AnalyticsPage tests (frontend/src/pages/AnalyticsPage.tsx)
 *
 * Tests the analytics page contract from SPEC.md Milestone 5:
 * - Displays a "Coming Soon" placeholder with no broken UI
 *
 * Spec references:
 * - SPEC.md >> Milestone 5 Acceptance Criteria
 */
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    isAuthenticated: true,
    user: { userId: "user-123", email: "user@example.com", roles: ["user"] },
    isLoading: false,
    signIn: vi.fn(),
    verifyOtp: vi.fn(),
    signOut: vi.fn(),
  }),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

import AnalyticsPage from "@/pages/AnalyticsPage";

function renderAnalyticsPage() {
  return render(
    <MemoryRouter initialEntries={["/analytics"]}>
      <AnalyticsPage />
    </MemoryRouter>,
  );
}

describe("AnalyticsPage", () => {
  it("renders 'Coming Soon' text", () => {
    renderAnalyticsPage();

    expect(screen.getByText("Coming Soon")).toBeInTheDocument();
  });

  it("renders a page heading for Analytics", () => {
    renderAnalyticsPage();

    expect(
      screen.getByRole("heading", { name: /analytics/i }),
    ).toBeInTheDocument();
  });

  it("renders without errors (no broken UI)", () => {
    const { container } = renderAnalyticsPage();

    // Container should have rendered content (not empty)
    expect(container.innerHTML.length).toBeGreaterThan(0);
  });

  it("does not display any data tables or charts", () => {
    renderAnalyticsPage();

    // Should not have tables or canvas elements (charts)
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
    expect(document.querySelector("canvas")).toBeNull();
  });
});

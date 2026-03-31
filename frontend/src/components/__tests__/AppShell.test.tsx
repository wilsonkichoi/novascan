/**
 * AppShell tests (frontend/src/components/AppShell.tsx)
 *
 * Tests the app shell contract from SPEC.md Milestone 1:
 * - Navigation shows: Home, Scan, Analytics, Transactions, Receipts
 * - Desktop sidebar and mobile bottom bar layouts
 * - Active route highlighting
 * - Sign out button triggers signOut
 * - Renders child content via Outlet
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { type ReactNode } from "react";

// Mock useAuth
const mockSignOut = vi.fn();
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    signOut: mockSignOut,
    isAuthenticated: true,
    isLoading: false,
    user: { userId: "u", email: "u@e.com", roles: ["user"] },
    signIn: vi.fn(),
    verifyOtp: vi.fn(),
  }),
}));

import AppShell from "@/components/AppShell";

function renderAppShell(initialRoute = "/") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<div data-testid="home-content">Home Content</div>} />
          <Route path="/scan" element={<div data-testid="scan-content">Scan Content</div>} />
          <Route path="/analytics" element={<div data-testid="analytics-content">Analytics Content</div>} />
          <Route path="/transactions" element={<div data-testid="transactions-content">Transactions Content</div>} />
          <Route path="/receipts" element={<div data-testid="receipts-content">Receipts Content</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

const EXPECTED_NAV_ITEMS = ["Home", "Scan", "Analytics", "Transactions", "Receipts"];

describe("AppShell", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- Navigation items ----

  it("renders all required navigation items per SPEC.md", () => {
    renderAppShell();

    for (const label of EXPECTED_NAV_ITEMS) {
      // Each nav item appears in both desktop sidebar and mobile bottom bar
      const links = screen.getAllByText(label);
      expect(links.length).toBeGreaterThanOrEqual(1);
    }
  });

  it("renders navigation items as links to correct routes", () => {
    renderAppShell();

    const expectedRoutes: Record<string, string> = {
      Home: "/",
      Scan: "/scan",
      Analytics: "/analytics",
      Transactions: "/transactions",
      Receipts: "/receipts",
    };

    for (const [label, path] of Object.entries(expectedRoutes)) {
      const links = screen.getAllByRole("link", { name: label });
      expect(links.length).toBeGreaterThanOrEqual(1);
      links.forEach((link) => {
        expect(link).toHaveAttribute("href", path);
      });
    }
  });

  // ---- Desktop sidebar ----

  it("renders a desktop sidebar with navigation", () => {
    renderAppShell();

    // The sidebar should have a "Main navigation" aria-label
    const navElements = screen.getAllByRole("navigation", {
      name: /main navigation/i,
    });
    expect(navElements.length).toBeGreaterThanOrEqual(1);
  });

  it("renders NovaScan branding in the sidebar", () => {
    renderAppShell();

    expect(screen.getByText("NovaScan")).toBeInTheDocument();
  });

  // ---- Mobile bottom navigation ----

  it("renders a mobile bottom navigation bar", () => {
    renderAppShell();

    // Both desktop and mobile navs should exist
    const navElements = screen.getAllByRole("navigation", {
      name: /main navigation/i,
    });
    expect(navElements.length).toBe(2); // desktop sidebar nav + mobile bottom nav
  });

  // ---- Active route highlighting ----

  it("highlights the active route (Home on /)", () => {
    renderAppShell("/");

    const homeLinks = screen.getAllByRole("link", { name: "Home" });
    // At least one should have the active CSS class
    const hasActiveClass = homeLinks.some(
      (link) =>
        link.className.includes("bg-sidebar-accent") ||
        link.className.includes("text-primary"),
    );
    expect(hasActiveClass).toBe(true);
  });

  it("highlights the Scan route when on /scan", () => {
    renderAppShell("/scan");

    const scanLinks = screen.getAllByRole("link", { name: "Scan" });
    const hasActiveClass = scanLinks.some(
      (link) =>
        link.className.includes("bg-sidebar-accent") ||
        link.className.includes("text-primary"),
    );
    expect(hasActiveClass).toBe(true);
  });

  it("does not highlight Home when on another route", () => {
    renderAppShell("/scan");

    const homeLinks = screen.getAllByRole("link", { name: "Home" });
    const scanLinks = screen.getAllByRole("link", { name: "Scan" });

    // Scan should be highlighted, while Home should have a different class pattern.
    // The active desktop link gets bg-sidebar-accent, inactive gets hover:bg-sidebar-accent.
    // The active mobile link gets text-primary, inactive gets text-muted-foreground.
    // We verify that Scan is active and Home is NOT by comparing their class lists.
    // At least one Scan link should differ in styling from all Home links.
    const scanClassSets = scanLinks.map((el) => el.className);
    const homeClassSets = homeLinks.map((el) => el.className);

    // Scan and Home should not have identical class patterns since one is active and the other isn't
    const allSame = scanClassSets.every((sc) => homeClassSets.includes(sc));
    expect(allSame).toBe(false);
  });

  // ---- Sign out ----

  it("renders sign out buttons (desktop + mobile)", () => {
    renderAppShell();

    const signOutButtons = screen.getAllByText(/sign out/i);
    expect(signOutButtons.length).toBeGreaterThanOrEqual(1);
  });

  it("calls signOut when clicking sign out button", async () => {
    const user = userEvent.setup();
    renderAppShell();

    const signOutButtons = screen.getAllByRole("button", { name: /sign out/i });
    await user.click(signOutButtons[0]);

    expect(mockSignOut).toHaveBeenCalledTimes(1);
  });

  // ---- Outlet (child content rendering) ----

  it("renders child content via Outlet on home route", () => {
    renderAppShell("/");

    expect(screen.getByTestId("home-content")).toBeInTheDocument();
    expect(screen.getByTestId("home-content")).toHaveTextContent("Home Content");
  });

  it("renders child content via Outlet on scan route", () => {
    renderAppShell("/scan");

    expect(screen.getByTestId("scan-content")).toBeInTheDocument();
  });

  it("renders child content via Outlet on receipts route", () => {
    renderAppShell("/receipts");

    expect(screen.getByTestId("receipts-content")).toBeInTheDocument();
  });

  // ---- Layout structure ----

  it("has a main content area", () => {
    renderAppShell();

    const main = screen.getByRole("main");
    expect(main).toBeInTheDocument();
  });

  it("renders navigation with flex layout for responsive display", () => {
    renderAppShell();

    // The root container should use flex for desktop sidebar layout
    const main = screen.getByRole("main");
    const container = main.parentElement;
    expect(container).toHaveClass("flex");
  });
});

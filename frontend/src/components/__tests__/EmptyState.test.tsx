/**
 * EmptyState tests (frontend/src/components/EmptyState.tsx)
 *
 * Tests the empty state contract from SPEC.md Milestone 6:
 * - NoReceiptsEmpty: heading, description, link to /scan
 * - NoTransactionsEmpty: heading, description, no action button
 * - DashboardWelcome: heading, description, link to /scan
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
  NoReceiptsEmpty,
  NoTransactionsEmpty,
  DashboardWelcome,
} from "@/components/EmptyState";

describe("NoReceiptsEmpty", () => {
  it("renders heading and description", () => {
    render(
      <MemoryRouter>
        <NoReceiptsEmpty />
      </MemoryRouter>,
    );
    expect(screen.getByText("No receipts yet")).toBeInTheDocument();
    expect(
      screen.getByText(/scan your first receipt to start tracking/i),
    ).toBeInTheDocument();
  });

  it("has a link to /scan", () => {
    render(
      <MemoryRouter>
        <NoReceiptsEmpty />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /scan your first receipt/i });
    expect(link).toHaveAttribute("href", "/scan");
  });
});

describe("NoTransactionsEmpty", () => {
  it("renders heading and description", () => {
    render(
      <MemoryRouter>
        <NoTransactionsEmpty />
      </MemoryRouter>,
    );
    expect(screen.getByText("No transactions found")).toBeInTheDocument();
    expect(
      screen.getByText(/transactions will appear here/i),
    ).toBeInTheDocument();
  });

  it("has no action button or link", () => {
    render(
      <MemoryRouter>
        <NoTransactionsEmpty />
      </MemoryRouter>,
    );
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});

describe("DashboardWelcome", () => {
  it("renders welcome heading and description", () => {
    render(
      <MemoryRouter>
        <DashboardWelcome />
      </MemoryRouter>,
    );
    expect(screen.getByText("Welcome to NovaScan")).toBeInTheDocument();
    expect(
      screen.getByText(/start tracking your spending/i),
    ).toBeInTheDocument();
  });

  it("has a link to /scan", () => {
    render(
      <MemoryRouter>
        <DashboardWelcome />
      </MemoryRouter>,
    );
    const link = screen.getByRole("link", { name: /scan your first receipt/i });
    expect(link).toHaveAttribute("href", "/scan");
  });
});

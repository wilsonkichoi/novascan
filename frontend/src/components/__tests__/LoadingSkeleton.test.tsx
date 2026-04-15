/**
 * LoadingSkeleton tests (frontend/src/components/LoadingSkeleton.tsx)
 *
 * Tests the loading skeleton contract from SPEC.md Milestone 6:
 * - DashboardSkeleton: role="status", aria-label, sr-only text
 * - ReceiptListSkeleton: role="status", aria-label, sr-only text
 * - TransactionTableSkeleton: role="status", aria-label, desktop/mobile layouts
 */
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";

import {
  DashboardSkeleton,
  ReceiptListSkeleton,
  TransactionTableSkeleton,
} from "@/components/LoadingSkeleton";

describe("DashboardSkeleton", () => {
  it("renders with role='status' and correct aria-label", () => {
    render(<DashboardSkeleton />);
    const el = screen.getByRole("status");
    expect(el).toHaveAttribute("aria-label", "Loading dashboard");
  });

  it("includes sr-only text for screen readers", () => {
    render(<DashboardSkeleton />);
    expect(screen.getByText("Loading dashboard")).toBeInTheDocument();
  });
});

describe("ReceiptListSkeleton", () => {
  it("renders with role='status' and correct aria-label", () => {
    render(<ReceiptListSkeleton />);
    const el = screen.getByRole("status");
    expect(el).toHaveAttribute("aria-label", "Loading receipts");
  });

  it("includes sr-only text for screen readers", () => {
    render(<ReceiptListSkeleton />);
    expect(screen.getByText("Loading receipts")).toBeInTheDocument();
  });
});

describe("TransactionTableSkeleton", () => {
  it("renders with role='status' and correct aria-label", () => {
    render(<TransactionTableSkeleton />);
    const el = screen.getByRole("status");
    expect(el).toHaveAttribute("aria-label", "Loading transactions");
  });

  it("includes sr-only text for screen readers", () => {
    render(<TransactionTableSkeleton />);
    expect(screen.getByText("Loading transactions")).toBeInTheDocument();
  });

  it("has a desktop table layout", () => {
    const { container } = render(<TransactionTableSkeleton />);
    const table = container.querySelector("table");
    expect(table).toBeTruthy();
  });

  it("has a mobile card layout", () => {
    const { container } = render(<TransactionTableSkeleton />);
    // Mobile card layout is visible on md:hidden
    const mobileDiv = container.querySelector(".md\\:hidden");
    expect(mobileDiv).toBeTruthy();
  });
});

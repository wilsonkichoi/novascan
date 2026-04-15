/**
 * ErrorBoundary tests (frontend/src/components/ErrorBoundary.tsx)
 *
 * Tests the error boundary contract from SPEC.md Milestone 6:
 * - Catches thrown error, renders fallback UI with role="alert"
 * - Default fallback shows "Something went wrong" + "Try again" button
 * - Clicking retry resets error state and re-renders children
 * - Custom fallback prop renders instead of default UI
 * - Normal rendering passes children through
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import ErrorBoundary from "@/components/ErrorBoundary";

// Component that throws on demand
let shouldThrow = false;
function ThrowingChild() {
  if (shouldThrow) {
    throw new Error("Test error");
  }
  return <div data-testid="child-content">Child rendered</div>;
}

// Suppress React error boundary console noise in tests
beforeEach(() => {
  shouldThrow = false;
  vi.spyOn(console, "error").mockImplementation(() => {});
});

describe("ErrorBoundary", () => {
  // ---- Normal rendering ----

  it("renders children when no error occurs", () => {
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
    expect(screen.getByText("Child rendered")).toBeInTheDocument();
  });

  // ---- Error catching ----

  it("catches error and renders default fallback with role='alert'", () => {
    shouldThrow = true;
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.queryByTestId("child-content")).not.toBeInTheDocument();
  });

  it("shows descriptive message in default fallback", () => {
    shouldThrow = true;
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(
      screen.getByText(/unexpected error occurred/i),
    ).toBeInTheDocument();
  });

  it("shows 'Try again' button in default fallback", () => {
    shouldThrow = true;
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(
      screen.getByRole("button", { name: /try again/i }),
    ).toBeInTheDocument();
  });

  // ---- Retry ----

  it("resets error state and re-renders children on retry", async () => {
    const user = userEvent.setup();
    shouldThrow = true;
    render(
      <ErrorBoundary>
        <ThrowingChild />
      </ErrorBoundary>,
    );

    expect(screen.getByRole("alert")).toBeInTheDocument();

    // Fix the child so it doesn't throw again
    shouldThrow = false;

    await user.click(screen.getByRole("button", { name: /try again/i }));

    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByTestId("child-content")).toBeInTheDocument();
  });

  // ---- Custom fallback ----

  it("renders custom fallback prop instead of default UI", () => {
    shouldThrow = true;
    render(
      <ErrorBoundary fallback={<div data-testid="custom-fallback">Custom error UI</div>}>
        <ThrowingChild />
      </ErrorBoundary>,
    );
    expect(screen.getByTestId("custom-fallback")).toBeInTheDocument();
    expect(screen.getByText("Custom error UI")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});

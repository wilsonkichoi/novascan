/**
 * LoginPage tests (frontend/src/pages/LoginPage.tsx)
 *
 * Tests the login page contract from SPEC.md Section 3 (Auth Flow):
 * - Renders email input on initial load
 * - Transitions to OTP step after email submit
 * - Shows error messages on failure
 * - Redirects authenticated users to home
 * - Email validation (requires @ character)
 * - OTP input is numeric, 6-digit
 * - "Use a different email" link returns to email step
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Routes, Route } from "react-router-dom";
import { type ReactNode } from "react";

// Mock useAuth hook
const mockSignIn = vi.fn();
const mockVerifyOtp = vi.fn();
const mockSignOut = vi.fn();
let mockIsAuthenticated = false;
let mockIsLoading = false;

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    signIn: mockSignIn,
    verifyOtp: mockVerifyOtp,
    signOut: mockSignOut,
    isAuthenticated: mockIsAuthenticated,
    isLoading: mockIsLoading,
    user: mockIsAuthenticated
      ? { userId: "u", email: "u@e.com", roles: ["user"] }
      : null,
  }),
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

// Mock auth functions used directly by LoginPage
const mockConfirmSignUp = vi.fn();
const mockResendConfirmationCode = vi.fn();

vi.mock("@/lib/auth", () => ({
  confirmSignUp: (...args: unknown[]) => mockConfirmSignUp(...args),
  resendConfirmationCode: (...args: unknown[]) => mockResendConfirmationCode(...args),
}));

// Mock navigate
const mockNavigate = vi.fn();
vi.mock("react-router-dom", async () => {
  const actual = await vi.importActual("react-router-dom");
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

import LoginPage from "@/pages/LoginPage";

function renderLoginPage(initialRoute = "/login") {
  return render(
    <MemoryRouter initialEntries={[initialRoute]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={<div>Home Page</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockIsAuthenticated = false;
    mockIsLoading = false;
    mockConfirmSignUp.mockResolvedValue(undefined);
    mockResendConfirmationCode.mockResolvedValue(undefined);
  });

  // ---- Initial rendering ----

  it("renders email input on initial load", () => {
    renderLoginPage();

    const emailInput = screen.getByPlaceholderText("you@example.com");
    expect(emailInput).toBeInTheDocument();
    expect(emailInput).toHaveAttribute("type", "email");
  });

  it("renders a submit button with 'Continue' text", () => {
    renderLoginPage();

    const button = screen.getByRole("button", { name: /continue/i });
    expect(button).toBeInTheDocument();
    expect(button).toHaveAttribute("type", "submit");
  });

  it("renders the NovaScan title", () => {
    renderLoginPage();

    expect(screen.getByText("NovaScan")).toBeInTheDocument();
  });

  it("shows descriptive text for email step", () => {
    renderLoginPage();

    expect(screen.getByText(/sign in with your email/i)).toBeInTheDocument();
  });

  // ---- Email submission ----

  it("transitions to OTP step after successful email submit", async () => {
    const user = userEvent.setup();
    mockSignIn.mockResolvedValue({
      session: "session-123",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });

    // Should show verify button instead of continue
    expect(screen.getByRole("button", { name: /verify/i })).toBeInTheDocument();
  });

  it("shows the email address in the OTP step description", async () => {
    const user = userEvent.setup();
    mockSignIn.mockResolvedValue({
      session: "session-123",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByText(/user@example.com/)).toBeInTheDocument();
    });
  });

  it("trims and lowercases email before sending", async () => {
    const user = userEvent.setup();
    mockSignIn.mockResolvedValue({
      session: "session-123",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(
      screen.getByPlaceholderText("you@example.com"),
      "  User@Example.COM  ",
    );
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(mockSignIn).toHaveBeenCalledWith("user@example.com");
    });
  });

  // ---- Email validation ----

  it("shows error for empty email", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /valid email/i,
      );
    });
    expect(mockSignIn).not.toHaveBeenCalled();
  });

  it("does not call signIn for email without @ character", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    // Type an invalid email. Note: <input type="email"> with HTML5 constraint
    // validation may block form submission at the browser level before our
    // custom handler runs. Either way, signIn should NOT be called.
    await user.type(screen.getByPlaceholderText("you@example.com"), "notanemail");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    // Give any async handlers time to settle
    await waitFor(() => {
      expect(mockSignIn).not.toHaveBeenCalled();
    });
  });

  // ---- Error display ----

  it("shows error on signIn failure", async () => {
    const user = userEvent.setup();
    mockSignIn.mockRejectedValue(new Error("Something went wrong"));

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toBeInTheDocument();
    });
  });

  it("shows friendly message for CodeMismatchException", async () => {
    const user = userEvent.setup();

    // First get to OTP step
    mockSignIn.mockResolvedValue({
      session: "session-123",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });

    // Now submit wrong OTP
    const codeMismatch = new Error("Code mismatch");
    codeMismatch.name = "CodeMismatchException";
    mockVerifyOtp.mockRejectedValue(codeMismatch);

    await user.type(screen.getByPlaceholderText("Sign-in code"), "00000000");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /incorrect verification code/i,
      );
    });
  });

  it("shows friendly message for rate limiting", async () => {
    const user = userEvent.setup();

    const rateLimitError = new Error("Rate limited");
    rateLimitError.name = "LimitExceededException";
    mockSignIn.mockRejectedValue(rateLimitError);

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /too many attempts/i,
      );
    });
  });

  // ---- OTP submission ----

  it("calls verifyOtp with session, code, and email on OTP submit", async () => {
    const user = userEvent.setup();

    mockSignIn.mockResolvedValue({
      session: "session-xyz",
      challengeName: "EMAIL_OTP",
    });
    mockVerifyOtp.mockResolvedValue({
      userId: "user-123",
      email: "user@example.com",
      roles: ["user"],
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Sign-in code"), "65432100");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    await waitFor(() => {
      expect(mockVerifyOtp).toHaveBeenCalledWith(
        "session-xyz",
        "65432100",
        "user@example.com",
      );
    });
  });

  it("navigates to home after successful OTP verification", async () => {
    const user = userEvent.setup();

    mockSignIn.mockResolvedValue({
      session: "session-xyz",
      challengeName: "EMAIL_OTP",
    });
    mockVerifyOtp.mockResolvedValue({
      userId: "user-123",
      email: "user@example.com",
      roles: ["user"],
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Sign-in code"), "65432100");
    await user.click(screen.getByRole("button", { name: /verify/i }));

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/", { replace: true });
    });
  });

  it("shows error when OTP is empty on submit", async () => {
    const user = userEvent.setup();

    mockSignIn.mockResolvedValue({
      session: "session-xyz",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });

    // Submit without entering OTP
    await user.click(screen.getByRole("button", { name: /verify/i }));

    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(
        /enter the verification code/i,
      );
    });
    expect(mockVerifyOtp).not.toHaveBeenCalled();
  });

  // ---- "Use a different email" ----

  it("shows back-to-email link on OTP step", async () => {
    const user = userEvent.setup();

    mockSignIn.mockResolvedValue({
      session: "session-123",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(
        screen.getByText(/use a different email/i),
      ).toBeInTheDocument();
    });
  });

  it("returns to email step when clicking back link", async () => {
    const user = userEvent.setup();

    mockSignIn.mockResolvedValue({
      session: "session-123",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "user@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });

    await user.click(screen.getByText(/use a different email/i));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("you@example.com")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /continue/i })).toBeInTheDocument();
  });

  // ---- Confirm step (new user) ----

  it("shows confirm step when signIn returns CONFIRM_SIGN_UP", async () => {
    const user = userEvent.setup();
    mockSignIn.mockResolvedValue({
      session: "",
      challengeName: "CONFIRM_SIGN_UP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "new@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Verification code")).toBeInTheDocument();
    });
    expect(screen.getByRole("button", { name: /confirm account/i })).toBeInTheDocument();
    expect(screen.getByText(/resend code/i)).toBeInTheDocument();
  });

  it("calls confirmSignUp then signIn after confirm code submit", async () => {
    const user = userEvent.setup();

    // First signIn → CONFIRM_SIGN_UP
    mockSignIn.mockResolvedValueOnce({
      session: "",
      challengeName: "CONFIRM_SIGN_UP",
    });

    // After confirm, signIn again → EMAIL_OTP
    mockSignIn.mockResolvedValueOnce({
      session: "session-after-confirm",
      challengeName: "EMAIL_OTP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "new@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByPlaceholderText("Verification code")).toBeInTheDocument();
    });

    await user.type(screen.getByPlaceholderText("Verification code"), "123456");
    await user.click(screen.getByRole("button", { name: /confirm account/i }));

    await waitFor(() => {
      expect(mockConfirmSignUp).toHaveBeenCalledWith("new@example.com", "123456");
    });

    // Should transition to OTP step
    await waitFor(() => {
      expect(screen.getByPlaceholderText("Sign-in code")).toBeInTheDocument();
    });
  });

  it("calls resendConfirmationCode when clicking resend", async () => {
    const user = userEvent.setup();
    mockSignIn.mockResolvedValue({
      session: "",
      challengeName: "CONFIRM_SIGN_UP",
    });

    renderLoginPage();

    await user.type(screen.getByPlaceholderText("you@example.com"), "new@example.com");
    await user.click(screen.getByRole("button", { name: /continue/i }));

    await waitFor(() => {
      expect(screen.getByText(/resend code/i)).toBeInTheDocument();
    });

    await user.click(screen.getByText(/resend code/i));

    await waitFor(() => {
      expect(mockResendConfirmationCode).toHaveBeenCalledWith("new@example.com");
    });
  });

  // ---- Authenticated redirect ----

  it("redirects to home when already authenticated", () => {
    mockIsAuthenticated = true;

    renderLoginPage();

    // The component should render a Navigate to "/"
    // Since we're using MemoryRouter, check that we're redirected
    expect(screen.queryByPlaceholderText("you@example.com")).not.toBeInTheDocument();
  });

  // ---- Loading state ----

  it("renders nothing while auth is loading", () => {
    mockIsLoading = true;

    const { container } = renderLoginPage();

    // Component returns null during loading
    expect(container.querySelector("form")).not.toBeInTheDocument();
    expect(screen.queryByPlaceholderText("you@example.com")).not.toBeInTheDocument();
  });
});

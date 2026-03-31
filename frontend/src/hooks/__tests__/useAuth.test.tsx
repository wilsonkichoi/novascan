/**
 * useAuth hook tests (frontend/src/hooks/useAuth.ts)
 *
 * Tests the AuthProvider context and useAuth hook contract:
 * - Provides auth state (isAuthenticated, user, isLoading)
 * - signIn delegates to initiateAuth
 * - verifyOtp delegates to respondToChallenge and updates user state
 * - signOut clears user state
 * - Attempts session restoration on mount via refreshTokens
 * - Throws when used outside AuthProvider
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor, act } from "@testing-library/react";
import { renderHook } from "@testing-library/react";
import { type ReactNode } from "react";

// Mock the auth module
const mockInitiateAuth = vi.fn();
const mockRespondToChallenge = vi.fn();
const mockRefreshTokens = vi.fn();
const mockSignOut = vi.fn();

vi.mock("@/lib/auth", () => ({
  initiateAuth: (...args: unknown[]) => mockInitiateAuth(...args),
  respondToChallenge: (...args: unknown[]) => mockRespondToChallenge(...args),
  refreshTokens: () => mockRefreshTokens(),
  signOut: () => mockSignOut(),
}));

import { AuthProvider, useAuth } from "@/hooks/useAuth";

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

describe("useAuth hook", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: no stored session to restore
    mockRefreshTokens.mockResolvedValue(null);
  });

  // ---- Context requirement ----

  it("throws when used outside AuthProvider", () => {
    // Suppress console.error for expected error
    const spy = vi.spyOn(console, "error").mockImplementation(() => {});
    expect(() => {
      renderHook(() => useAuth());
    }).toThrow("useAuth must be used within an AuthProvider");
    spy.mockRestore();
  });

  // ---- Initial state ----

  it("starts in loading state while attempting session restoration", () => {
    // Keep refreshTokens pending so isLoading stays true
    mockRefreshTokens.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAuth(), { wrapper });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  it("transitions to not-loading after session restore completes (no session)", async () => {
    mockRefreshTokens.mockResolvedValue(null);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  // ---- Session restoration ----

  it("restores user from refresh token on mount", async () => {
    const restoredUser = {
      userId: "restored-user-id",
      email: "restored@example.com",
      roles: ["user" as const],
    };

    mockRefreshTokens.mockResolvedValue(restoredUser);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(restoredUser);
  });

  it("stays logged out if refresh token restoration fails", async () => {
    mockRefreshTokens.mockRejectedValue(new Error("refresh failed"));

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  // ---- signIn ----

  it("signIn delegates to initiateAuth and returns challenge result", async () => {
    const challengeResult = {
      session: "session-abc",
      challengeName: "EMAIL_OTP",
    };
    mockInitiateAuth.mockResolvedValue(challengeResult);

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    let signInResult: unknown;
    await act(async () => {
      signInResult = await result.current.signIn("user@example.com");
    });

    expect(mockInitiateAuth).toHaveBeenCalledWith("user@example.com");
    expect(signInResult).toEqual(challengeResult);
  });

  // ---- verifyOtp ----

  it("verifyOtp delegates to respondToChallenge and sets user state", async () => {
    const authenticatedUser = {
      userId: "user-123",
      email: "user@example.com",
      roles: ["user" as const],
    };

    mockRespondToChallenge.mockResolvedValue({
      user: authenticatedUser,
      tokens: {
        idToken: "id-token",
        accessToken: "access-token",
        refreshToken: "refresh-token",
      },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      const user = await result.current.verifyOtp(
        "session-abc",
        "123456",
        "user@example.com",
      );
      expect(user).toEqual(authenticatedUser);
    });

    expect(mockRespondToChallenge).toHaveBeenCalledWith(
      "session-abc",
      "123456",
      "user@example.com",
    );
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.user).toEqual(authenticatedUser);
  });

  it("verifyOtp propagates errors from respondToChallenge", async () => {
    mockRespondToChallenge.mockRejectedValue(
      new Error("Incorrect verification code"),
    );

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await expect(
      act(async () => {
        await result.current.verifyOtp("session", "wrong", "user@example.com");
      }),
    ).rejects.toThrow("Incorrect verification code");

    // User should still be null after failed verification
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
  });

  // ---- signOut ----

  it("signOut clears user state and delegates to auth module", async () => {
    // First, simulate an authenticated user
    const authenticatedUser = {
      userId: "user-123",
      email: "user@example.com",
      roles: ["user" as const],
    };

    mockRespondToChallenge.mockResolvedValue({
      user: authenticatedUser,
      tokens: {
        idToken: "id",
        accessToken: "access",
        refreshToken: "refresh",
      },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    await act(async () => {
      await result.current.verifyOtp("session", "123456", "user@example.com");
    });

    expect(result.current.isAuthenticated).toBe(true);

    act(() => {
      result.current.signOut();
    });

    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.user).toBeNull();
    expect(mockSignOut).toHaveBeenCalled();
  });

  // ---- isAuthenticated derived state ----

  it("isAuthenticated is true when user is set, false when null", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });

    await waitFor(() => {
      expect(result.current.isLoading).toBe(false);
    });

    expect(result.current.isAuthenticated).toBe(false);

    const user = {
      userId: "u",
      email: "u@e.com",
      roles: ["user" as const],
    };
    mockRespondToChallenge.mockResolvedValue({
      user,
      tokens: { idToken: "a", accessToken: "b", refreshToken: "c" },
    });

    await act(async () => {
      await result.current.verifyOtp("s", "123456", "u@e.com");
    });

    expect(result.current.isAuthenticated).toBe(true);

    act(() => {
      result.current.signOut();
    });

    expect(result.current.isAuthenticated).toBe(false);
  });
});

// ---- AuthProvider rendering ----

describe("AuthProvider", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockRefreshTokens.mockResolvedValue(null);
  });

  it("renders children after loading completes", async () => {
    function TestChild() {
      const { isLoading } = useAuth();
      return <div data-testid="child">Loading: {String(isLoading)}</div>;
    }

    render(
      <AuthProvider>
        <TestChild />
      </AuthProvider>,
    );

    await waitFor(() => {
      expect(screen.getByTestId("child")).toHaveTextContent("Loading: false");
    });
  });
});

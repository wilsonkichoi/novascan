/**
 * Auth module tests (frontend/src/lib/auth.ts)
 *
 * Tests the auth flow contract from SPEC.md Section 3:
 * - signIn flow (happy path): InitiateAuth → challenge result with session
 * - UserNotFoundException → signUp → retry InitiateAuth
 * - OTP challenge response: respondToChallenge → tokens stored
 * - Token storage: access/ID in memory, refresh in localStorage
 * - signOut: clears all tokens (memory + localStorage)
 */
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Hoist the mock function so it's available when vi.mock factory runs
const { mockSend } = vi.hoisted(() => ({
  mockSend: vi.fn(),
}));

// Mock the AWS SDK before importing the auth module
vi.mock("@aws-sdk/client-cognito-identity-provider", () => {
  return {
    CognitoIdentityProviderClient: vi.fn().mockImplementation(() => ({
      send: mockSend,
    })),
    InitiateAuthCommand: vi.fn().mockImplementation((input) => ({
      _type: "InitiateAuthCommand",
      input,
    })),
    SignUpCommand: vi.fn().mockImplementation((input) => ({
      _type: "SignUpCommand",
      input,
    })),
    ConfirmSignUpCommand: vi.fn().mockImplementation((input) => ({
      _type: "ConfirmSignUpCommand",
      input,
    })),
    ResendConfirmationCodeCommand: vi.fn().mockImplementation((input) => ({
      _type: "ResendConfirmationCodeCommand",
      input,
    })),
    RespondToAuthChallengeCommand: vi.fn().mockImplementation((input) => ({
      _type: "RespondToAuthChallengeCommand",
      input,
    })),
    RevokeTokenCommand: vi.fn().mockImplementation((input) => ({
      _type: "RevokeTokenCommand",
      input,
    })),
  };
});

// Helper: create a fake JWT with given claims
function fakeJwt(claims: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: "RS256", typ: "JWT" }));
  const payload = btoa(JSON.stringify(claims));
  const signature = "fake-signature";
  return `${header}.${payload}.${signature}`;
}

import {
  initiateAuth,
  signUp,
  confirmSignUp,
  resendConfirmationCode,
  respondToChallenge,
  signOut,
  getIdToken,
  getAccessToken,
  refreshTokens,
  getValidIdToken,
} from "@/lib/auth";

describe("Auth module", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Reset in-memory tokens by signing out
    signOut();
    mockSend.mockReset();
  });

  afterEach(() => {
    localStorage.clear();
  });

  // ---- initiateAuth (signIn flow) ----

  describe("initiateAuth", () => {
    it("returns challenge result with session on happy path", async () => {
      mockSend.mockResolvedValueOnce({
        Session: "test-session-abc",
        ChallengeName: "EMAIL_OTP",
      });

      const result = await initiateAuth("user@example.com");

      expect(result).toEqual({
        session: "test-session-abc",
        challengeName: "EMAIL_OTP",
      });
    });

    it("uses USER_AUTH flow with EMAIL_OTP preferred challenge", async () => {
      const { InitiateAuthCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      mockSend.mockResolvedValueOnce({
        Session: "session-123",
        ChallengeName: "EMAIL_OTP",
      });

      await initiateAuth("user@example.com");

      expect(InitiateAuthCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          AuthFlow: "USER_AUTH",
          AuthParameters: expect.objectContaining({
            USERNAME: "user@example.com",
            PREFERRED_CHALLENGE: "EMAIL_OTP",
          }),
        }),
      );
    });

    it("signs up and returns CONFIRM_SIGN_UP on UserNotFoundException", async () => {
      // First call: UserNotFoundException
      const userNotFoundError = new Error("User does not exist.");
      userNotFoundError.name = "UserNotFoundException";
      mockSend.mockRejectedValueOnce(userNotFoundError);

      // Second call: SignUp succeeds (user created as UNCONFIRMED)
      mockSend.mockResolvedValueOnce({});

      const result = await initiateAuth("newuser@example.com");

      expect(result).toEqual({
        session: "",
        challengeName: "CONFIRM_SIGN_UP",
      });
      // 2 calls: InitiateAuth (fail) → SignUp. No retry — user needs to confirm first.
      expect(mockSend).toHaveBeenCalledTimes(2);
    });

    it("resends code and returns CONFIRM_SIGN_UP on UserNotConfirmedException", async () => {
      const unconfirmedError = new Error("User is not confirmed.");
      unconfirmedError.name = "UserNotConfirmedException";
      mockSend.mockRejectedValueOnce(unconfirmedError);

      // ResendConfirmationCode succeeds
      mockSend.mockResolvedValueOnce({});

      const result = await initiateAuth("unconfirmed@example.com");

      expect(result).toEqual({
        session: "",
        challengeName: "CONFIRM_SIGN_UP",
      });
      expect(mockSend).toHaveBeenCalledTimes(2);
    });

    it("throws non-UserNotFoundException errors without retrying", async () => {
      const networkError = new Error("Network failure");
      networkError.name = "NetworkError";
      mockSend.mockRejectedValueOnce(networkError);

      await expect(initiateAuth("user@example.com")).rejects.toThrow(
        "Network failure",
      );
      // Only 1 call: InitiateAuth (fail), no SignUp
      expect(mockSend).toHaveBeenCalledTimes(1);
    });

    it("throws if session is missing from Cognito response", async () => {
      mockSend.mockResolvedValueOnce({
        Session: null,
        ChallengeName: "EMAIL_OTP",
      });

      await expect(initiateAuth("user@example.com")).rejects.toThrow(
        /missing session or challenge/i,
      );
    });

    it("throws if challengeName is missing from Cognito response", async () => {
      mockSend.mockResolvedValueOnce({
        Session: "session-123",
        ChallengeName: null,
      });

      await expect(initiateAuth("user@example.com")).rejects.toThrow(
        /missing session or challenge/i,
      );
    });
  });

  // ---- signUp ----

  describe("signUp", () => {
    it("calls Cognito SignUp with the provided email", async () => {
      const { SignUpCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      mockSend.mockResolvedValueOnce({});

      await signUp("new@example.com");

      expect(SignUpCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          Username: "new@example.com",
          // Password is generated randomly but must be present
          Password: expect.any(String),
        }),
      );
    });

    it("generates a password for Cognito even though auth is passwordless", async () => {
      const { SignUpCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      mockSend.mockResolvedValueOnce({});

      await signUp("test@example.com");

      const callArgs = (SignUpCommand as unknown as ReturnType<typeof vi.fn>).mock
        .calls[0][0] as { Password?: string };
      expect(callArgs.Password).toBeTruthy();
      expect(callArgs.Password!.length).toBeGreaterThan(0);
    });
  });

  // ---- confirmSignUp ----

  describe("confirmSignUp", () => {
    it("calls Cognito ConfirmSignUp with email and code", async () => {
      const { ConfirmSignUpCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      mockSend.mockResolvedValueOnce({});

      await confirmSignUp("new@example.com", "123456");

      expect(ConfirmSignUpCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          Username: "new@example.com",
          ConfirmationCode: "123456",
        }),
      );
    });

    it("silently succeeds if user is already confirmed (NotAuthorizedException)", async () => {
      const alreadyConfirmed = new Error("User cannot be confirmed. Current status is CONFIRMED");
      alreadyConfirmed.name = "NotAuthorizedException";
      mockSend.mockRejectedValueOnce(alreadyConfirmed);

      // Should not throw
      await expect(confirmSignUp("user@example.com", "123456")).resolves.toBeUndefined();
    });

    it("throws on other errors", async () => {
      const expiredCode = new Error("Code expired");
      expiredCode.name = "ExpiredCodeException";
      mockSend.mockRejectedValueOnce(expiredCode);

      await expect(confirmSignUp("user@example.com", "999999")).rejects.toThrow("Code expired");
    });
  });

  // ---- resendConfirmationCode ----

  describe("resendConfirmationCode", () => {
    it("calls Cognito ResendConfirmationCode with email", async () => {
      const { ResendConfirmationCodeCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      mockSend.mockResolvedValueOnce({});

      await resendConfirmationCode("user@example.com");

      expect(ResendConfirmationCodeCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          Username: "user@example.com",
        }),
      );
    });
  });

  // ---- respondToChallenge (OTP verification) ----

  describe("respondToChallenge", () => {
    const email = "user@example.com";
    const session = "test-session";
    const code = "123456";

    const idTokenClaims = {
      sub: "user-uuid-123",
      email: "user@example.com",
      "cognito:groups": ["user"],
      exp: Math.floor(Date.now() / 1000) + 3600,
      iat: Math.floor(Date.now() / 1000),
    };

    const mockIdToken = fakeJwt(idTokenClaims);
    const mockAccessToken = fakeJwt({ sub: "user-uuid-123", exp: 9999999999 });
    const mockRefreshToken = "refresh-token-abc";

    it("returns user info and tokens on success", async () => {
      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: mockIdToken,
          AccessToken: mockAccessToken,
          RefreshToken: mockRefreshToken,
        },
      });

      const result = await respondToChallenge(session, code, email);

      expect(result.user).toEqual({
        userId: "user-uuid-123",
        email: "user@example.com",
        roles: ["user"],
      });
      expect(result.tokens.idToken).toBe(mockIdToken);
      expect(result.tokens.accessToken).toBe(mockAccessToken);
      expect(result.tokens.refreshToken).toBe(mockRefreshToken);
    });

    it("stores ID and access tokens in memory after authentication", async () => {
      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: mockIdToken,
          AccessToken: mockAccessToken,
          RefreshToken: mockRefreshToken,
        },
      });

      await respondToChallenge(session, code, email);

      expect(getIdToken()).toBe(mockIdToken);
      expect(getAccessToken()).toBe(mockAccessToken);
    });

    it("stores refresh token in localStorage after authentication", async () => {
      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: mockIdToken,
          AccessToken: mockAccessToken,
          RefreshToken: mockRefreshToken,
        },
      });

      await respondToChallenge(session, code, email);

      expect(localStorage.getItem("novascan_refresh_token")).toBe(
        mockRefreshToken,
      );
    });

    it("extracts user roles from cognito:groups claim", async () => {
      const staffToken = fakeJwt({
        ...idTokenClaims,
        "cognito:groups": ["user", "staff"],
      });

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: staffToken,
          AccessToken: mockAccessToken,
          RefreshToken: mockRefreshToken,
        },
      });

      const result = await respondToChallenge(session, code, email);
      expect(result.user.roles).toContain("user");
      expect(result.user.roles).toContain("staff");
    });

    it("handles token with no cognito:groups claim (empty roles)", async () => {
      const noGroupsToken = fakeJwt({
        sub: "user-uuid-123",
        email: "user@example.com",
        exp: Math.floor(Date.now() / 1000) + 3600,
        iat: Math.floor(Date.now() / 1000),
      });

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: noGroupsToken,
          AccessToken: mockAccessToken,
          RefreshToken: mockRefreshToken,
        },
      });

      const result = await respondToChallenge(session, code, email);
      expect(result.user.roles).toEqual([]);
    });

    it("throws if authentication result is missing tokens", async () => {
      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: mockIdToken,
          AccessToken: null,
          RefreshToken: null,
        },
      });

      await expect(
        respondToChallenge(session, code, email),
      ).rejects.toThrow(/missing tokens/i);
    });

    it("sends EMAIL_OTP challenge type with correct parameters", async () => {
      const { RespondToAuthChallengeCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: mockIdToken,
          AccessToken: mockAccessToken,
          RefreshToken: mockRefreshToken,
        },
      });

      await respondToChallenge(session, code, email);

      expect(RespondToAuthChallengeCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          ChallengeName: "EMAIL_OTP",
          Session: session,
          ChallengeResponses: expect.objectContaining({
            USERNAME: email,
            EMAIL_OTP_CODE: code,
          }),
        }),
      );
    });
  });

  // ---- signOut ----

  describe("signOut", () => {
    it("clears in-memory tokens", async () => {
      // First authenticate
      const mockIdToken = fakeJwt({
        sub: "user-uuid",
        email: "user@example.com",
        exp: Math.floor(Date.now() / 1000) + 3600,
        iat: Math.floor(Date.now() / 1000),
      });
      const mockAccessToken = fakeJwt({ sub: "user-uuid", exp: 9999999999 });

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: mockIdToken,
          AccessToken: mockAccessToken,
          RefreshToken: "refresh-abc",
        },
      });

      await respondToChallenge("session", "123456", "user@example.com");
      expect(getIdToken()).not.toBeNull();
      expect(getAccessToken()).not.toBeNull();

      // Now sign out — RevokeTokenCommand is best-effort, mock it
      mockSend.mockResolvedValueOnce({});
      signOut();

      expect(getIdToken()).toBeNull();
      expect(getAccessToken()).toBeNull();
    });

    it("clears refresh token from localStorage", async () => {
      localStorage.setItem("novascan_refresh_token", "some-token");

      // signOut will attempt to revoke the token — mock the send to return a promise
      mockSend.mockResolvedValueOnce({});
      signOut();

      expect(localStorage.getItem("novascan_refresh_token")).toBeNull();
    });

    it("attempts to revoke refresh token server-side (best-effort)", () => {
      localStorage.setItem("novascan_refresh_token", "token-to-revoke");

      // Mock RevokeToken — we just verify it's called
      mockSend.mockResolvedValueOnce({});

      signOut();

      // Revocation is fire-and-forget, so send should be called
      expect(mockSend).toHaveBeenCalledTimes(1);
    });

    it("does not block sign-out if revocation fails", () => {
      localStorage.setItem("novascan_refresh_token", "token-to-revoke");
      mockSend.mockRejectedValueOnce(new Error("Network error"));

      // Should not throw
      expect(() => signOut()).not.toThrow();
      expect(getIdToken()).toBeNull();
      expect(localStorage.getItem("novascan_refresh_token")).toBeNull();
    });
  });

  // ---- refreshTokens ----

  describe("refreshTokens", () => {
    it("returns null when no refresh token is stored", async () => {
      const result = await refreshTokens();
      expect(result).toBeNull();
    });

    it("returns user info when refresh succeeds", async () => {
      const newIdToken = fakeJwt({
        sub: "user-uuid-123",
        email: "user@example.com",
        "cognito:groups": ["user"],
        exp: Math.floor(Date.now() / 1000) + 3600,
        iat: Math.floor(Date.now() / 1000),
      });

      localStorage.setItem("novascan_refresh_token", "stored-refresh-token");

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: newIdToken,
          AccessToken: fakeJwt({ sub: "user-uuid-123", exp: 9999999999 }),
        },
      });

      const user = await refreshTokens();

      expect(user).not.toBeNull();
      expect(user!.userId).toBe("user-uuid-123");
      expect(user!.email).toBe("user@example.com");
    });

    it("clears tokens and returns null when refresh fails", async () => {
      localStorage.setItem("novascan_refresh_token", "expired-refresh-token");

      mockSend.mockRejectedValueOnce(new Error("Token expired"));

      const result = await refreshTokens();

      expect(result).toBeNull();
      expect(localStorage.getItem("novascan_refresh_token")).toBeNull();
    });

    it("uses REFRESH_TOKEN_AUTH flow", async () => {
      const { InitiateAuthCommand } = await import(
        "@aws-sdk/client-cognito-identity-provider"
      );

      localStorage.setItem("novascan_refresh_token", "my-refresh-token");

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: fakeJwt({
            sub: "u",
            email: "u@e.com",
            exp: 9999999999,
            iat: 0,
          }),
          AccessToken: fakeJwt({ sub: "u", exp: 9999999999 }),
        },
      });

      await refreshTokens();

      expect(InitiateAuthCommand).toHaveBeenCalledWith(
        expect.objectContaining({
          AuthFlow: "REFRESH_TOKEN_AUTH",
          AuthParameters: expect.objectContaining({
            REFRESH_TOKEN: "my-refresh-token",
          }),
        }),
      );
    });
  });

  // ---- getValidIdToken ----

  describe("getValidIdToken", () => {
    it("returns null when not authenticated", async () => {
      const result = await getValidIdToken();
      expect(result).toBeNull();
    });

    it("returns the token if it is not near expiry", async () => {
      // Authenticate first
      const futureToken = fakeJwt({
        sub: "user-uuid",
        email: "user@example.com",
        exp: Math.floor(Date.now() / 1000) + 3600, // 1 hour
        iat: Math.floor(Date.now() / 1000),
      });

      mockSend.mockResolvedValueOnce({
        AuthenticationResult: {
          IdToken: futureToken,
          AccessToken: fakeJwt({ sub: "u", exp: 9999999999 }),
          RefreshToken: "refresh-abc",
        },
      });

      await respondToChallenge("session", "123456", "user@example.com");

      const result = await getValidIdToken();
      expect(result).toBe(futureToken);
    });
  });
});

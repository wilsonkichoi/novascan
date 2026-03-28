import {
  CognitoIdentityProviderClient,
  InitiateAuthCommand,
  SignUpCommand,
  RespondToAuthChallengeCommand,
} from "@aws-sdk/client-cognito-identity-provider";
import type {
  AuthChallengeResult,
  AuthTokens,
  AuthUser,
  AuthRole,
  IdTokenClaims,
} from "@/types/auth";

const REGION = import.meta.env.VITE_AWS_REGION ?? "us-east-1";
const USER_POOL_CLIENT_ID = import.meta.env.VITE_COGNITO_CLIENT_ID ?? "";

const REFRESH_TOKEN_KEY = "novascan_refresh_token";

const client = new CognitoIdentityProviderClient({ region: REGION });

// ---- In-memory token storage ----
let idToken: string | null = null;
let accessToken: string | null = null;

/** Return the current ID token for API calls (Authorization header). */
export function getIdToken(): string | null {
  return idToken;
}

/** Return the current access token. */
export function getAccessToken(): string | null {
  return accessToken;
}

// ---- JWT helpers ----

/**
 * Decode a JWT payload without verification.
 * Client-side only — the API Gateway authorizer handles real validation.
 */
function decodeJwtPayload(token: string): IdTokenClaims {
  const parts = token.split(".");
  if (parts.length !== 3) {
    throw new Error("Invalid JWT format");
  }
  // Base64url → base64 → decode
  const base64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
  const json = atob(base64);
  return JSON.parse(json) as IdTokenClaims;
}

/** Extract AuthUser from an ID token. */
function userFromIdToken(token: string): AuthUser {
  const claims = decodeJwtPayload(token);
  const groups = claims["cognito:groups"] ?? [];
  const validRoles: AuthRole[] = ["user", "staff", "admin"];
  const roles = groups.filter((g): g is AuthRole =>
    validRoles.includes(g as AuthRole),
  );

  return {
    userId: claims.sub,
    email: claims.email,
    roles,
  };
}

// ---- Cognito operations ----

/**
 * Register a new user with Cognito.
 * Pre-Sign-Up Lambda auto-confirms and auto-verifies the email.
 * A random password is generated because Cognito requires one for SignUp,
 * but it is never used — auth is passwordless via email OTP.
 */
export async function signUp(email: string): Promise<void> {
  const randomPassword =
    crypto.getRandomValues(new Uint8Array(32)).reduce(
      (s, b) => s + b.toString(16).padStart(2, "0"),
      "",
    ) + "!Aa1";

  await client.send(
    new SignUpCommand({
      ClientId: USER_POOL_CLIENT_ID,
      Username: email,
      Password: randomPassword,
    }),
  );
}

/**
 * Start the USER_AUTH flow.
 * If the user doesn't exist, automatically signs them up and retries.
 * Returns the session token needed for respondToChallenge.
 */
export async function initiateAuth(
  email: string,
): Promise<AuthChallengeResult> {
  try {
    return await sendInitiateAuth(email);
  } catch (error: unknown) {
    if (isUserNotFoundException(error)) {
      await signUp(email);
      return await sendInitiateAuth(email);
    }
    throw error;
  }
}

async function sendInitiateAuth(
  email: string,
): Promise<AuthChallengeResult> {
  const result = await client.send(
    new InitiateAuthCommand({
      AuthFlow: "USER_AUTH",
      ClientId: USER_POOL_CLIENT_ID,
      AuthParameters: {
        USERNAME: email,
        PREFERRED_CHALLENGE: "EMAIL_OTP",
      },
    }),
  );

  if (!result.Session || !result.ChallengeName) {
    throw new Error("Unexpected auth response: missing session or challenge");
  }

  return {
    session: result.Session,
    challengeName: result.ChallengeName,
  };
}

function isUserNotFoundException(error: unknown): boolean {
  if (error instanceof Error && "name" in error) {
    return error.name === "UserNotFoundException";
  }
  return false;
}

/**
 * Submit the EMAIL_OTP code to complete authentication.
 * Stores tokens: access/ID in memory, refresh in localStorage.
 * Returns the parsed user info.
 */
export async function respondToChallenge(
  session: string,
  code: string,
  email: string,
): Promise<{ user: AuthUser; tokens: AuthTokens }> {
  const result = await client.send(
    new RespondToAuthChallengeCommand({
      ClientId: USER_POOL_CLIENT_ID,
      ChallengeName: "EMAIL_OTP",
      Session: session,
      ChallengeResponses: {
        USERNAME: email,
        EMAIL_OTP_CODE: code,
      },
    }),
  );

  const authResult = result.AuthenticationResult;
  if (!authResult?.IdToken || !authResult.AccessToken || !authResult.RefreshToken) {
    throw new Error("Incomplete authentication result: missing tokens");
  }

  const tokens: AuthTokens = {
    idToken: authResult.IdToken,
    accessToken: authResult.AccessToken,
    refreshToken: authResult.RefreshToken,
  };

  storeTokens(tokens);
  const user = userFromIdToken(tokens.idToken);
  return { user, tokens };
}

/**
 * Use the stored refresh token to obtain new access/ID tokens.
 * Returns the user info if refresh succeeds, null otherwise.
 */
export async function refreshTokens(): Promise<AuthUser | null> {
  const storedRefreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!storedRefreshToken) {
    return null;
  }

  try {
    const result = await client.send(
      new InitiateAuthCommand({
        AuthFlow: "REFRESH_TOKEN_AUTH",
        ClientId: USER_POOL_CLIENT_ID,
        AuthParameters: {
          REFRESH_TOKEN: storedRefreshToken,
        },
      }),
    );

    const authResult = result.AuthenticationResult;
    if (!authResult?.IdToken || !authResult.AccessToken) {
      clearTokens();
      return null;
    }

    // Refresh flow does not return a new refresh token — keep the existing one
    idToken = authResult.IdToken;
    accessToken = authResult.AccessToken;

    return userFromIdToken(authResult.IdToken);
  } catch {
    clearTokens();
    return null;
  }
}

/** Clear all stored tokens (sign out). */
export function signOut(): void {
  clearTokens();
}

// ---- Internal helpers ----

function storeTokens(tokens: AuthTokens): void {
  idToken = tokens.idToken;
  accessToken = tokens.accessToken;
  localStorage.setItem(REFRESH_TOKEN_KEY, tokens.refreshToken);
}

function clearTokens(): void {
  idToken = null;
  accessToken = null;
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

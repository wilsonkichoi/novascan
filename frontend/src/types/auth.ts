/** User roles matching Cognito User Pool Groups */
export type AuthRole = "user" | "staff" | "admin";

/** Authenticated user info extracted from Cognito ID token */
export interface AuthUser {
  userId: string;
  email: string;
  roles: AuthRole[];
}

/** Auth module state */
export interface AuthState {
  isAuthenticated: boolean;
  user: AuthUser | null;
  isLoading: boolean;
}

/** Result of initiateAuth — session needed for challenge response */
export interface AuthChallengeResult {
  session: string;
  challengeName: string;
}

/** Tokens returned after successful authentication */
export interface AuthTokens {
  idToken: string;
  accessToken: string;
  refreshToken: string;
}

/** JWT payload claims from Cognito ID token */
export interface IdTokenClaims {
  sub: string;
  email: string;
  "cognito:groups"?: string[];
  exp: number;
  iat: number;
  [key: string]: unknown;
}

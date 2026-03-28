import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  createElement,
  type ReactNode,
} from "react";
import type { AuthUser, AuthChallengeResult } from "@/types/auth";
import {
  initiateAuth,
  respondToChallenge,
  refreshTokens,
  signOut as authSignOut,
} from "@/lib/auth";

interface AuthContextValue {
  isAuthenticated: boolean;
  user: AuthUser | null;
  isLoading: boolean;
  signIn: (email: string) => Promise<AuthChallengeResult>;
  verifyOtp: (
    session: string,
    code: string,
    email: string,
  ) => Promise<AuthUser>;
  signOut: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/**
 * AuthProvider wraps the app and manages authentication state.
 * On mount, attempts to refresh tokens from localStorage.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount, try to restore session from refresh token
  useEffect(() => {
    let cancelled = false;

    async function restoreSession() {
      try {
        const restored = await refreshTokens();
        if (!cancelled) {
          setUser(restored);
        }
      } catch {
        // Refresh failed — user stays logged out
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    void restoreSession();

    return () => {
      cancelled = true;
    };
  }, []);

  const signIn = useCallback(async (email: string) => {
    return await initiateAuth(email);
  }, []);

  const verifyOtp = useCallback(
    async (session: string, code: string, email: string) => {
      const { user: authedUser } = await respondToChallenge(
        session,
        code,
        email,
      );
      setUser(authedUser);
      return authedUser;
    },
    [],
  );

  const handleSignOut = useCallback(() => {
    authSignOut();
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    isAuthenticated: user !== null,
    user,
    isLoading,
    signIn,
    verifyOtp,
    signOut: handleSignOut,
  };

  return createElement(AuthContext.Provider, { value }, children);
}

/**
 * Hook to access auth state and actions.
 * Must be used within an AuthProvider.
 */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (context === null) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

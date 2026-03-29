import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";

type Step = "email" | "otp";

export default function LoginPage() {
  const navigate = useNavigate();
  const { signIn, verifyOtp, isAuthenticated, isLoading } = useAuth();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [session, setSession] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isLoading) return null;

  if (isAuthenticated) {
    return <Navigate to="/" replace />;
  }

  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    const trimmed = email.trim().toLowerCase();
    if (!trimmed || !trimmed.includes("@")) {
      setError("Please enter a valid email address.");
      return;
    }

    setIsSubmitting(true);
    try {
      const result = await signIn(trimmed);
      setSession(result.session);
      setEmail(trimmed);
      setStep("otp");
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleOtpSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!otp.trim()) {
      setError("Please enter the verification code.");
      return;
    }

    setIsSubmitting(true);
    try {
      await verifyOtp(session, otp.trim(), email);
      navigate("/", { replace: true });
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  function handleBackToEmail() {
    setStep("email");
    setOtp("");
    setSession("");
    setError(null);
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight">NovaScan</h1>
          <p className="text-muted-foreground text-sm">
            {step === "email"
              ? "Sign in with your email"
              : `Enter the code sent to ${email}`}
          </p>
        </div>

        {error && (
          <div
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md border border-destructive/20 px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}

        {step === "email" ? (
          <form onSubmit={handleEmailSubmit} className="space-y-4">
            <Input
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              autoFocus
              autoComplete="email"
            />
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="animate-spin" />
              ) : (
                "Continue"
              )}
            </Button>
          </form>
        ) : (
          <form onSubmit={handleOtpSubmit} className="space-y-4">
            <Input
              type="text"
              inputMode="numeric"
              placeholder="Verification code"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              disabled={isSubmitting}
              autoFocus
              autoComplete="one-time-code"
              maxLength={6}
              pattern="[0-9]{6}"
            />
            <Button type="submit" className="w-full" disabled={isSubmitting}>
              {isSubmitting ? (
                <Loader2 className="animate-spin" />
              ) : (
                "Verify"
              )}
            </Button>
            <button
              type="button"
              onClick={handleBackToEmail}
              className="text-muted-foreground hover:text-foreground w-full text-center text-sm transition-colors"
            >
              Use a different email
            </button>
          </form>
        )}
      </div>
    </div>
  );
}

function friendlyError(err: unknown): string {
  if (err instanceof Error) {
    if (err.name === "CodeMismatchException") {
      return "Incorrect verification code. Please try again.";
    }
    if (err.name === "ExpiredCodeException") {
      return "Verification code expired. Please request a new one.";
    }
    if (err.name === "LimitExceededException" || err.name === "TooManyRequestsException") {
      return "Too many attempts. Please wait a moment and try again.";
    }
    if (err.name === "NotAuthorizedException") {
      return "Session expired. Please start over.";
    }
    if (err instanceof TypeError && err.message === "Failed to fetch") {
      return "Network error. Please check your connection and try again.";
    }
    return err.message;
  }
  return "An unexpected error occurred. Please try again.";
}

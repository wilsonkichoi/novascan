import { useState, type FormEvent } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { confirmSignUp, resendConfirmationCode } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Loader2 } from "lucide-react";

type Step = "email" | "confirm" | "otp";

export default function LoginPage() {
  const navigate = useNavigate();
  const { signIn, verifyOtp, isAuthenticated, isLoading } = useAuth();

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [confirmCode, setConfirmCode] = useState("");
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
      setEmail(trimmed);
      if (result.challengeName === "CONFIRM_SIGN_UP") {
        setStep("confirm");
      } else {
        setSession(result.session);
        setStep("otp");
      }
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleConfirmSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);

    if (!confirmCode.trim()) {
      setError("Please enter the verification code.");
      return;
    }

    setIsSubmitting(true);
    try {
      await confirmSignUp(email, confirmCode.trim());
      // Account confirmed — now initiate auth to get the sign-in OTP
      const result = await signIn(email);
      setSession(result.session);
      setStep("otp");
    } catch (err) {
      setError(friendlyError(err));
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handleResendConfirmation() {
    setError(null);
    setIsSubmitting(true);
    try {
      await resendConfirmationCode(email);
      setError(null);
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
    setConfirmCode("");
    setSession("");
    setError(null);
  }

  function stepDescription(): string {
    switch (step) {
      case "email":
        return "Sign in with your email";
      case "confirm":
        return `Enter the verification code sent to ${email} to confirm your account`;
      case "otp":
        return `Enter the sign-in code sent to ${email}`;
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="space-y-2 text-center">
          <h1 className="text-2xl font-bold tracking-tight">NovaScan</h1>
          <p className="text-muted-foreground text-sm">{stepDescription()}</p>
        </div>

        {error && (
          <div
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md border border-destructive/20 px-4 py-3 text-sm"
          >
            {error}
          </div>
        )}

        {step === "email" && (
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
        )}

        {step === "confirm" && (
          <form onSubmit={handleConfirmSubmit} className="space-y-4">
            <Input
              type="text"
              inputMode="numeric"
              placeholder="Verification code"
              value={confirmCode}
              onChange={(e) => setConfirmCode(e.target.value)}
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
                "Confirm Account"
              )}
            </Button>
            <button
              type="button"
              onClick={handleResendConfirmation}
              disabled={isSubmitting}
              className="text-muted-foreground hover:text-foreground w-full text-center text-sm transition-colors disabled:opacity-50"
            >
              Resend code
            </button>
            <button
              type="button"
              onClick={handleBackToEmail}
              className="text-muted-foreground hover:text-foreground w-full text-center text-sm transition-colors"
            >
              Use a different email
            </button>
          </form>
        )}

        {step === "otp" && (
          <form onSubmit={handleOtpSubmit} className="space-y-4">
            <Input
              type="text"
              inputMode="numeric"
              placeholder="Sign-in code"
              value={otp}
              onChange={(e) => setOtp(e.target.value)}
              disabled={isSubmitting}
              autoFocus
              autoComplete="one-time-code"
              maxLength={8}
              pattern="[0-9]{8}"
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
      return "Verification code expired. Please click 'Resend code' to get a new one.";
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

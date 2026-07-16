"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";

export default function SignupPage() {
  return <Suspense><SignupForm /></Suspense>;
}

function SignupForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session } = useAuth();
  const redirectTo = searchParams.get("redirect") || "/";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);

  // Read quiz stash from localStorage (written by design page auth wall).
  // Saved into user metadata during signUp so it survives cross-browser email confirmation.
  const [quizStash, setQuizStash] = useState<Record<string, unknown> | null>(null);
  useEffect(() => {
    try {
      const raw = localStorage.getItem("rk_quiz_pending");
      if (raw) {
        const { answers } = JSON.parse(raw);
        if (answers?.roomType) setQuizStash(answers);
      }
    } catch { /* ignore corrupt data */ }
  }, []);

  useEffect(() => {
    if (session) router.replace(redirectTo);
  }, [session, router]);

  if (session) return null;

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = getSupabaseBrowserClient();
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: {
          age_confirmed: true,
          ...(quizStash ? { quiz_stash: quizStash } : {}),
        },
        emailRedirectTo: `${window.location.origin}/auth/confirmed`,
      },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    if (data.user && data.user.identities && data.user.identities.length === 0) {
      router.replace(redirectTo !== "/" ? `/login?msg=exists&redirect=${encodeURIComponent(redirectTo)}` : "/login?msg=exists");
      return;
    }

    setConfirmSent(true);
    setLoading(false);
  };

  const handleGoogleSignup = async () => {
    const supabase = getSupabaseBrowserClient();
    const callbackUrl = new URL("/auth/callback", window.location.origin);
    if (redirectTo !== "/") callbackUrl.searchParams.set("redirect", redirectTo);
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: callbackUrl.toString() },
    });
  };

  if (confirmSent) {
    return (
      <main className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Check your email</h1>
          <p className="auth-subtitle">
            We sent a confirmation link to <strong>{email}</strong>.
            Click it to activate your account, then come back to this tab to continue.
          </p>
        </div>
      </main>
    );
  }

  return (
    <main className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">RoomKit</h1>
        <p className="auth-subtitle">Create an account to design your room</p>

        <form onSubmit={handleSignup} className="auth-form">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="auth-input"
          />
          <input
            type="password"
            placeholder="Password (min 6 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            className="auth-input"
          />
          {error && <p className="auth-error">{error}</p>}

          <label className="auth-checkbox-label">
            <input
              type="checkbox"
              checked={ageConfirmed}
              onChange={(e) => setAgeConfirmed(e.target.checked)}
              className="auth-checkbox"
            />
            I confirm I am 13 years of age or older
          </label>

          <button
            type="submit"
            disabled={loading || !ageConfirmed}
            className="auth-btn"
          >
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <div className="auth-divider">
          <span className="auth-divider-text">or</span>
        </div>

        <button
          onClick={handleGoogleSignup}
          disabled={!ageConfirmed}
          className="auth-google-btn"
        >
          Continue with Google
        </button>

        <p className="auth-legal">
          By signing up, you agree to our{" "}
          <a href="/terms" className="auth-link">Terms of Service</a> and{" "}
          <a href="/privacy" className="auth-link">Privacy Policy</a>.
        </p>

        <p className="auth-footer">
          Already have an account?{" "}
          <a href={redirectTo !== "/" ? `/login?redirect=${encodeURIComponent(redirectTo)}` : "/login"} className="auth-link">Sign in</a>
        </p>
      </div>
    </main>
  );
}

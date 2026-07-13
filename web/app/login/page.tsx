"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";

export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const existingAccount = searchParams.get("msg") === "exists";
  const redirectTo = searchParams.get("redirect") || "/";

  if (session) {
    router.replace(redirectTo);
    return null;
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = getSupabaseBrowserClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    router.replace(redirectTo);
  };

  const handleGoogleLogin = async () => {
    const supabase = getSupabaseBrowserClient();
    const callbackUrl = new URL("/auth/callback", window.location.origin);
    if (redirectTo !== "/") callbackUrl.searchParams.set("redirect", redirectTo);
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: callbackUrl.toString() },
    });
  };

  return (
    <main className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">RoomKit</h1>
        <p className="auth-subtitle">Sign in to design your room</p>

        {existingAccount && (
          <p className="auth-info">An account with that email already exists. Sign in below.</p>
        )}

        <form onSubmit={handleLogin} className="auth-form">
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
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="auth-input"
          />
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" disabled={loading} className="auth-btn">
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div className="auth-divider">
          <span className="auth-divider-text">or</span>
        </div>

        <button onClick={handleGoogleLogin} className="auth-google-btn">
          Continue with Google
        </button>

        <p className="auth-footer" style={{ marginTop: 16 }}>
          <a href="/forgot-password" className="auth-link">Forgot password?</a>
        </p>

        <p className="auth-footer" style={{ marginTop: 12 }}>
          Don&apos;t have an account?{" "}
          <a href={redirectTo !== "/" ? `/signup?redirect=${encodeURIComponent(redirectTo)}` : "/signup"} className="auth-link">Sign up</a>
        </p>
      </div>
    </main>
  );
}

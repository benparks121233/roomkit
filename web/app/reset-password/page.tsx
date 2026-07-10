"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";

export default function ResetPasswordPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  if (authLoading) return null;

  if (!session) {
    return (
      <main className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Session expired</h1>
          <p className="auth-subtitle">
            This reset link has expired or was already used. Request a new one.
          </p>
          <a href="/forgot-password" className="auth-btn auth-btn--link">
            Request new link
          </a>
        </div>
      </main>
    );
  }

  if (done) {
    return (
      <main className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Password updated</h1>
          <p className="auth-subtitle">Your password has been reset. You&apos;re now signed in.</p>
          <a href="/" className="auth-btn auth-btn--link">
            Start designing
          </a>
        </div>
      </main>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (password !== confirm) {
      setError("Passwords don't match");
      return;
    }

    if (password.length < 6) {
      setError("Password must be at least 6 characters");
      return;
    }

    setLoading(true);

    const supabase = getSupabaseBrowserClient();
    const { error } = await supabase.auth.updateUser({ password });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    setDone(true);
    setLoading(false);
  };

  return (
    <main className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Set new password</h1>
        <p className="auth-subtitle">Enter your new password below.</p>

        <form onSubmit={handleSubmit} className="auth-form">
          <input
            type="password"
            placeholder="New password (min 6 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            className="auth-input"
          />
          <input
            type="password"
            placeholder="Confirm new password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={6}
            className="auth-input"
          />
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" disabled={loading} className="auth-btn">
            {loading ? "Updating..." : "Update password"}
          </button>
        </form>

        <p className="auth-footer">
          <a href="/login" className="auth-link">Back to sign in</a>
        </p>
      </div>
    </main>
  );
}

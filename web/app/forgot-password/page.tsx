"use client";

import { useState } from "react";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    try {
      const supabase = getSupabaseBrowserClient();
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/auth/callback?next=/reset-password`,
      });

      if (error) {
        setError(error.message);
        setLoading(false);
        return;
      }
    } catch {
      // Show confirmation regardless — don't leak whether the email exists
    }

    setSent(true);
    setLoading(false);
  };

  if (sent) {
    return (
      <main className="auth-container">
        <div className="auth-card">
          <h1 className="auth-title">Check your email</h1>
          <p className="auth-subtitle">
            We sent a password reset link to <strong>{email}</strong>.
            Click it to set a new password.
          </p>
          <a href="/login" className="auth-btn auth-btn--link">
            Back to sign in
          </a>
        </div>
      </main>
    );
  }

  return (
    <main className="auth-container">
      <div className="auth-card">
        <h1 className="auth-title">Reset password</h1>
        <p className="auth-subtitle">
          Enter your email and we&apos;ll send you a link to reset your password.
        </p>

        <form onSubmit={handleSubmit} className="auth-form">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="auth-input"
          />
          {error && <p className="auth-error">{error}</p>}
          <button type="submit" disabled={loading} className="auth-btn">
            {loading ? "Sending..." : "Send reset link"}
          </button>
        </form>

        <p className="auth-footer">
          <a href="/login" className="auth-link">Back to sign in</a>
        </p>
      </div>
    </main>
  );
}

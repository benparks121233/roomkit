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
      <main style={styles.container}>
        <div style={styles.card}>
          <h1 style={styles.title}>Check your email</h1>
          <p style={styles.subtitle}>
            We sent a password reset link to <strong>{email}</strong>.
            Click it to set a new password.
          </p>
          <a href="/login" style={{ ...styles.button, textAlign: "center" as const, display: "block", textDecoration: "none" }}>
            Back to sign in
          </a>
        </div>
      </main>
    );
  }

  return (
    <main style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Reset password</h1>
        <p style={styles.subtitle}>
          Enter your email and we&apos;ll send you a link to reset your password.
        </p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={styles.input}
          />
          {error && <p style={styles.error}>{error}</p>}
          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? "Sending..." : "Send reset link"}
          </button>
        </form>

        <p style={styles.footer}>
          <a href="/login" style={styles.link}>Back to sign in</a>
        </p>
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#f8f7f4",
    fontFamily: "'DM Sans', sans-serif",
  },
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: "2.5rem 2rem",
    width: "100%",
    maxWidth: 400,
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
  },
  title: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "1.8rem",
    textAlign: "center" as const,
    margin: 0,
    color: "#1a1a1a",
  },
  subtitle: {
    textAlign: "center" as const,
    color: "#666",
    fontSize: "0.95rem",
    marginTop: 8,
    marginBottom: 24,
  },
  form: {
    display: "flex",
    flexDirection: "column" as const,
    gap: 12,
  },
  input: {
    padding: "12px 14px",
    borderRadius: 8,
    border: "1px solid #ddd",
    fontSize: "0.95rem",
    fontFamily: "'DM Sans', sans-serif",
    outline: "none",
  },
  button: {
    padding: "12px",
    borderRadius: 8,
    border: "none",
    background: "#1a1a1a",
    color: "#fff",
    fontSize: "0.95rem",
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 4,
  },
  error: {
    color: "#d32f2f",
    fontSize: "0.85rem",
    margin: 0,
  },
  footer: {
    textAlign: "center" as const,
    color: "#666",
    fontSize: "0.85rem",
    marginTop: 20,
    marginBottom: 0,
  },
  link: {
    color: "#1a1a1a",
    fontWeight: 600,
    textDecoration: "none",
  },
};

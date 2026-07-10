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
      <main style={styles.container}>
        <div style={styles.card}>
          <h1 style={styles.title}>Session expired</h1>
          <p style={styles.subtitle}>
            This reset link has expired or was already used. Request a new one.
          </p>
          <a href="/forgot-password" style={{ ...styles.button, textAlign: "center" as const, display: "block", textDecoration: "none" }}>
            Request new link
          </a>
        </div>
      </main>
    );
  }

  if (done) {
    return (
      <main style={styles.container}>
        <div style={styles.card}>
          <h1 style={styles.title}>Password updated</h1>
          <p style={styles.subtitle}>Your password has been reset. You&apos;re now signed in.</p>
          <a href="/" style={{ ...styles.button, textAlign: "center" as const, display: "block", textDecoration: "none" }}>
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
    <main style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Set new password</h1>
        <p style={styles.subtitle}>Enter your new password below.</p>

        <form onSubmit={handleSubmit} style={styles.form}>
          <input
            type="password"
            placeholder="New password (min 6 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            style={styles.input}
          />
          <input
            type="password"
            placeholder="Confirm new password"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            required
            minLength={6}
            style={styles.input}
          />
          {error && <p style={styles.error}>{error}</p>}
          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? "Updating..." : "Update password"}
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

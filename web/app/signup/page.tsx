"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabaseBrowserClient } from "@/lib/supabase";
import { useAuth } from "@/components/AuthProvider";

export default function SignupPage() {
  const router = useRouter();
  const { session } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [confirmSent, setConfirmSent] = useState(false);
  const [ageConfirmed, setAgeConfirmed] = useState(false);

  if (session) {
    router.replace("/");
    return null;
  }

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = getSupabaseBrowserClient();
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: { data: { age_confirmed: true } },
    });

    if (error) {
      setError(error.message);
      setLoading(false);
      return;
    }

    // Supabase returns an existing user with no identities when the email is
    // already registered. Detect this and redirect to login instead of showing
    // a fake "check your email" screen.
    if (data.user && data.user.identities && data.user.identities.length === 0) {
      router.replace("/login?msg=exists");
      return;
    }

    setConfirmSent(true);
    setLoading(false);
  };

  const handleGoogleSignup = async () => {
    const supabase = getSupabaseBrowserClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  if (confirmSent) {
    return (
      <main style={styles.container}>
        <div style={styles.card}>
          <h1 style={styles.title}>Check your email</h1>
          <p style={styles.subtitle}>
            We sent a confirmation link to <strong>{email}</strong>.
            Click it to activate your account, then come back here to sign in.
          </p>
          <a href="/login" style={{ ...styles.button, textAlign: "center", display: "block", textDecoration: "none" }}>
            Go to sign in
          </a>
        </div>
      </main>
    );
  }

  return (
    <main style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>RoomKit</h1>
        <p style={styles.subtitle}>Create an account to design your room</p>

        <form onSubmit={handleSignup} style={styles.form}>
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            style={styles.input}
          />
          <input
            type="password"
            placeholder="Password (min 6 characters)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            style={styles.input}
          />
          {error && <p style={styles.error}>{error}</p>}

          <label style={styles.checkboxLabel}>
            <input
              type="checkbox"
              checked={ageConfirmed}
              onChange={(e) => setAgeConfirmed(e.target.checked)}
              style={styles.checkbox}
            />
            I confirm I am 13 years of age or older
          </label>

          <button type="submit" disabled={loading || !ageConfirmed} style={{
            ...styles.button,
            ...(ageConfirmed ? {} : styles.buttonDisabled),
          }}>
            {loading ? "Creating account..." : "Create account"}
          </button>
        </form>

        <div style={styles.divider}>
          <span style={styles.dividerText}>or</span>
        </div>

        <button
          onClick={handleGoogleSignup}
          disabled={!ageConfirmed}
          style={{
            ...styles.googleButton,
            ...(ageConfirmed ? {} : styles.buttonDisabled),
          }}
        >
          Continue with Google
        </button>

        <p style={styles.legal}>
          By signing up, you agree to our{" "}
          <a href="/terms" style={styles.link}>Terms of Service</a> and{" "}
          <a href="/privacy" style={styles.link}>Privacy Policy</a>.
        </p>

        <p style={styles.footer}>
          Already have an account?{" "}
          <a href="/login" style={styles.link}>Sign in</a>
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
    textAlign: "center",
    margin: 0,
    color: "#1a1a1a",
  },
  subtitle: {
    textAlign: "center",
    color: "#666",
    fontSize: "0.95rem",
    marginTop: 8,
    marginBottom: 24,
  },
  form: {
    display: "flex",
    flexDirection: "column",
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
  divider: {
    display: "flex",
    alignItems: "center",
    gap: 12,
    margin: "20px 0",
  },
  dividerText: {
    color: "#999",
    fontSize: "0.85rem",
    flex: 1,
    textAlign: "center",
  },
  googleButton: {
    width: "100%",
    padding: "12px",
    borderRadius: 8,
    border: "1px solid #ddd",
    background: "#fff",
    fontSize: "0.95rem",
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 500,
    cursor: "pointer",
    color: "#333",
  },
  legal: {
    textAlign: "center",
    color: "#999",
    fontSize: "0.75rem",
    marginTop: 16,
    marginBottom: 0,
    lineHeight: 1.5,
  },
  footer: {
    textAlign: "center",
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
  checkboxLabel: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    fontSize: "0.85rem",
    color: "#444",
    cursor: "pointer",
    marginTop: 4,
  },
  checkbox: {
    width: 16,
    height: 16,
    accentColor: "#1a1a1a",
    cursor: "pointer",
    flexShrink: 0,
  },
  buttonDisabled: {
    opacity: 0.45,
    cursor: "not-allowed",
  },
};

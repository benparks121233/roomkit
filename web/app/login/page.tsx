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

  if (session) {
    router.replace("/");
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

    router.replace("/");
  };

  const handleGoogleLogin = async () => {
    const supabase = getSupabaseBrowserClient();
    await supabase.auth.signInWithOAuth({
      provider: "google",
      options: { redirectTo: `${window.location.origin}/auth/callback` },
    });
  };

  return (
    <main style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>RoomKit</h1>
        <p style={styles.subtitle}>Sign in to design your room</p>

        {existingAccount && (
          <p style={styles.info}>An account with that email already exists. Sign in below.</p>
        )}

        <form onSubmit={handleLogin} style={styles.form}>
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
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            style={styles.input}
          />
          {error && <p style={styles.error}>{error}</p>}
          <button type="submit" disabled={loading} style={styles.button}>
            {loading ? "Signing in..." : "Sign in"}
          </button>
        </form>

        <div style={styles.divider}>
          <span style={styles.dividerText}>or</span>
        </div>

        <button onClick={handleGoogleLogin} style={styles.googleButton}>
          Continue with Google
        </button>

        <p style={styles.forgot}>
          <a href="/forgot-password" style={styles.link}>Forgot password?</a>
        </p>

        <p style={styles.footer}>
          Don&apos;t have an account?{" "}
          <a href="/signup" style={styles.link}>Sign up</a>
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
    position: "relative",
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
  forgot: {
    textAlign: "center",
    fontSize: "0.85rem",
    marginTop: 16,
    marginBottom: 0,
  },
  footer: {
    textAlign: "center",
    color: "#666",
    fontSize: "0.85rem",
    marginTop: 12,
    marginBottom: 0,
  },
  link: {
    color: "#1a1a1a",
    fontWeight: 600,
    textDecoration: "none",
  },
  info: {
    background: "#f0f4ff",
    border: "1px solid #d0d8f0",
    borderRadius: 8,
    padding: "10px 14px",
    fontSize: "0.85rem",
    color: "#334",
    marginBottom: 16,
    textAlign: "center",
  },
};

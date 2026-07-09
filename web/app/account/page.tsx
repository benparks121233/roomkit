"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { getSupabaseBrowserClient } from "@/lib/supabase";

export default function AccountPage() {
  const router = useRouter();
  const { session, loading, signOut } = useAuth();
  const [showConfirm, setShowConfirm] = useState(false);
  const [confirmText, setConfirmText] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && !session && !signingOut) router.replace("/login");
  }, [loading, session, signingOut, router]);

  const handleSignOut = async () => {
    setSigningOut(true);
    await signOut();
    router.replace("/");
  };

  if (loading || !session) return null;

  const handleDelete = async () => {
    setError(null);
    setDeleting(true);

    try {
      const supabase = getSupabaseBrowserClient();
      const { data: { session: currentSession } } = await supabase.auth.getSession();
      if (!currentSession) {
        setError("Session expired. Please sign in again.");
        setDeleting(false);
        return;
      }

      const apiBase = process.env.NEXT_PUBLIC_API_URL || "";
      const res = await fetch(`${apiBase}/account`, {
        method: "DELETE",
        headers: {
          Authorization: `Bearer ${currentSession.access_token}`,
          "Content-Type": "application/json",
        },
      });

      const body = await res.json();

      if (body.deleted) {
        await signOut();
        router.replace("/login");
      } else {
        setError(body.message || "Deletion failed. Please try again.");
        setDeleting(false);
        if (body.failed_step === "auth_delete" || body.failed_step === "init" || body.failed_step === "query_run_ids") {
          // Auth still exists — user can retry normally
        } else {
          // Auth was deleted but cleanup incomplete — sign out
          await signOut();
          router.replace("/login");
        }
      }
    } catch {
      setError("Network error. Please check your connection and try again.");
      setDeleting(false);
    }
  };

  return (
    <main style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>Account</h1>

        <div style={styles.field}>
          <span style={styles.fieldLabel}>Email</span>
          <span style={styles.fieldValue}>{session.user.email}</span>
        </div>

        <button
          onClick={handleSignOut}
          disabled={signingOut}
          style={signingOut ? { ...styles.signOutButton, ...styles.buttonDisabled } : styles.signOutButton}
        >
          {signingOut ? "Signing out..." : "Sign out"}
        </button>

        <hr style={styles.divider} />

        {!showConfirm ? (
          <button onClick={() => setShowConfirm(true)} style={styles.deleteButton}>
            Delete my account
          </button>
        ) : (
          <div style={styles.confirmSection}>
            <p style={styles.warning}>
              This will permanently delete your account, all saved designs, renders, and analytics data.
              This action cannot be undone.
            </p>
            <label style={styles.confirmLabel}>
              Type <strong>DELETE</strong> to confirm:
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="DELETE"
              style={styles.input}
              autoFocus
            />
            <div style={styles.confirmButtons}>
              <button
                onClick={handleDelete}
                disabled={confirmText !== "DELETE" || deleting}
                style={{
                  ...styles.confirmDelete,
                  ...(confirmText !== "DELETE" || deleting ? styles.buttonDisabled : {}),
                }}
              >
                {deleting ? "Deleting..." : "Permanently delete"}
              </button>
              <button
                onClick={() => { setShowConfirm(false); setConfirmText(""); setError(null); }}
                style={styles.cancelButton}
                disabled={deleting}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {error && <p style={styles.error}>{error}</p>}

        <p style={styles.privacyLink}>
          See our <a href="/privacy" style={styles.link}>Privacy Policy</a> for
          details on what data we store and how deletion works.
        </p>

        <a href="/" style={styles.backLink}>Back to RoomKit</a>
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
    maxWidth: 440,
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
  },
  title: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "1.8rem",
    margin: 0,
    color: "#1a1a1a",
    marginBottom: 24,
  },
  field: {
    display: "flex",
    flexDirection: "column",
    gap: 4,
  },
  fieldLabel: {
    fontSize: "0.8rem",
    color: "#888",
    textTransform: "uppercase" as const,
    letterSpacing: "0.05em",
  },
  fieldValue: {
    fontSize: "1rem",
    color: "#1a1a1a",
  },
  divider: {
    border: "none",
    borderTop: "1px solid #eee",
    margin: "28px 0",
  },
  signOutButton: {
    width: "100%",
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid #ddd",
    background: "#fff",
    color: "#1a1a1a",
    fontSize: "0.9rem",
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 20,
  },
  deleteButton: {
    padding: "10px 20px",
    borderRadius: 8,
    border: "1px solid #d32f2f",
    background: "#fff",
    color: "#d32f2f",
    fontSize: "0.9rem",
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 600,
    cursor: "pointer",
  },
  confirmSection: {
    display: "flex",
    flexDirection: "column",
    gap: 12,
  },
  warning: {
    fontSize: "0.9rem",
    color: "#d32f2f",
    margin: 0,
    lineHeight: 1.5,
  },
  confirmLabel: {
    fontSize: "0.85rem",
    color: "#444",
  },
  input: {
    padding: "10px 14px",
    borderRadius: 8,
    border: "1px solid #ddd",
    fontSize: "0.95rem",
    fontFamily: "'DM Sans', sans-serif",
    outline: "none",
  },
  confirmButtons: {
    display: "flex",
    gap: 10,
    marginTop: 4,
  },
  confirmDelete: {
    flex: 1,
    padding: "10px",
    borderRadius: 8,
    border: "none",
    background: "#d32f2f",
    color: "#fff",
    fontSize: "0.9rem",
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 600,
    cursor: "pointer",
  },
  cancelButton: {
    flex: 1,
    padding: "10px",
    borderRadius: 8,
    border: "1px solid #ddd",
    background: "#fff",
    color: "#666",
    fontSize: "0.9rem",
    fontFamily: "'DM Sans', sans-serif",
    fontWeight: 500,
    cursor: "pointer",
  },
  buttonDisabled: {
    opacity: 0.45,
    cursor: "not-allowed",
  },
  error: {
    color: "#d32f2f",
    fontSize: "0.85rem",
    marginTop: 16,
    marginBottom: 0,
  },
  privacyLink: {
    textAlign: "center",
    color: "#999",
    fontSize: "0.8rem",
    marginTop: 20,
    marginBottom: 0,
    lineHeight: 1.5,
  },
  link: {
    color: "#1a1a1a",
    fontWeight: 600,
  },
  backLink: {
    display: "block",
    textAlign: "center",
    marginTop: 24,
    color: "#888",
    fontSize: "0.85rem",
    textDecoration: "none",
  },
};

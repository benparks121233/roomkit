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
    <main className="auth-container">
      <div className="auth-card" style={{ maxWidth: 440 }}>
        <a href="/" className="account-back-link">&#8592; Back</a>
        <h1 className="account-title">Account</h1>

        <div className="account-field">
          <span className="account-field-label">Email</span>
          <span className="account-field-value">{session.user.email}</span>
        </div>

        <button
          onClick={handleSignOut}
          disabled={signingOut}
          className="account-signout-btn"
        >
          {signingOut ? "Signing out..." : "Sign out"}
        </button>

        <hr className="account-divider" />

        {!showConfirm ? (
          <button onClick={() => setShowConfirm(true)} className="account-delete-btn">
            Delete my account
          </button>
        ) : (
          <div className="account-confirm-section">
            <p className="account-warning">
              This will permanently delete your account, all saved designs, renders, and analytics data.
              This action cannot be undone.
            </p>
            <label className="account-confirm-label">
              Type <strong>DELETE</strong> to confirm:
            </label>
            <input
              type="text"
              value={confirmText}
              onChange={(e) => setConfirmText(e.target.value)}
              placeholder="DELETE"
              className="auth-input"
              autoFocus
            />
            <div className="account-confirm-buttons">
              <button
                onClick={handleDelete}
                disabled={confirmText !== "DELETE" || deleting}
                className="account-confirm-delete"
              >
                {deleting ? "Deleting..." : "Permanently delete"}
              </button>
              <button
                onClick={() => { setShowConfirm(false); setConfirmText(""); setError(null); }}
                className="account-cancel-btn"
                disabled={deleting}
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {error && <p className="auth-error" style={{ marginTop: 16 }}>{error}</p>}

        <p className="account-privacy-link">
          See our <a href="/privacy" className="auth-link">Privacy Policy</a> for
          details on what data we store and how deletion works.
        </p>

      </div>
    </main>
  );
}

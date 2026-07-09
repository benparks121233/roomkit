"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { getPackBalance, type PackBalance } from "@/lib/api";

export default function SiteShell({ children }: { children: React.ReactNode }) {
  const { session, loading, signOut } = useAuth();
  const router = useRouter();
  const [pack, setPack] = useState<PackBalance | null>(null);
  const [menuOpen, setMenuOpen] = useState(false);

  const fetchBalance = useCallback(async () => {
    try {
      const data = await getPackBalance();
      setPack(data);
    } catch {
      setPack(null);
    }
  }, []);

  useEffect(() => {
    if (!session) {
      setPack(null);
      return;
    }
    fetchBalance();

    const onPackChanged = () => fetchBalance();
    const onVisibility = () => {
      if (document.visibilityState === "visible") fetchBalance();
    };

    window.addEventListener("roomkit:pack-changed", onPackChanged);
    document.addEventListener("visibilitychange", onVisibility);
    return () => {
      window.removeEventListener("roomkit:pack-changed", onPackChanged);
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [session, fetchBalance]);

  useEffect(() => {
    if (!menuOpen) return;
    const close = () => setMenuOpen(false);
    document.addEventListener("click", close);
    return () => document.removeEventListener("click", close);
  }, [menuOpen]);

  const handleSignOut = async () => {
    setMenuOpen(false);
    await signOut();
    router.push("/");
  };

  const showPill = pack && (pack.has_pack || pack.rooms_remaining > 0);

  return (
    <>
      <nav className="site-nav" role="navigation">
        <div className="site-nav-inner">
          <a href="/" className="site-nav-wordmark">roomkit</a>

          <div className="site-nav-right">
            {loading ? null : session ? (
              <>
                <a href="/designs" className="site-nav-link">My Designs</a>
                {showPill && (
                  <span className={`pack-pill ${pack.rooms_remaining === 0 ? "pack-pill--empty" : ""}`}>
                    {pack.rooms_remaining} {pack.rooms_remaining === 1 ? "room" : "rooms"}
                  </span>
                )}
                <div className="account-menu-wrapper">
                  <button
                    className="account-menu-trigger"
                    onClick={(e) => { e.stopPropagation(); setMenuOpen((v) => !v); }}
                    aria-expanded={menuOpen}
                    aria-haspopup="true"
                  >
                    {session.user.email?.split("@")[0] ?? "Account"}
                    <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ marginLeft: 4 }}>
                      <path d="M3 5L6 8L9 5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  </button>
                  {menuOpen && (
                    <div className="account-menu-dropdown">
                      <a href="/account" className="account-menu-item">Account</a>
                      <button onClick={handleSignOut} className="account-menu-item account-menu-signout">
                        Sign out
                      </button>
                    </div>
                  )}
                </div>
              </>
            ) : (
              <a href="/login" className="site-nav-signin">Sign in</a>
            )}
          </div>
        </div>
      </nav>

      {children}

      <footer className="site-footer-shell">
        <div className="site-footer-inner">
          <div className="site-footer-links">
            <a href="/privacy">Privacy</a>
            <span className="site-footer-dot">&middot;</span>
            <a href="/terms">Terms</a>
          </div>
          <p className="site-footer-disclosure">
            As an Amazon Associate, RoomKit earns from qualifying purchases.
            Prices shown were accurate as of the date listed and are subject to change.
          </p>
        </div>
      </footer>
    </>
  );
}

"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { getPackBalance } from "@/lib/api";

export default function PurchaseSuccessPage() {
  const router = useRouter();
  const { session } = useAuth();
  const [rooms, setRooms] = useState<number | null>(null);
  const [polling, setPolling] = useState(true);
  const [hasPendingDesign] = useState(() => {
    if (typeof window === "undefined") return false;
    const val = sessionStorage.getItem("rk_pending");
    console.log("[SUCCESS] sessionStorage rk_pending on mount:", val ? val.slice(0, 80) + "..." : "NULL");
    return val !== null;
  });

  useEffect(() => {
    if (!session) return;

    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 15;
    let initialBalance: number | null = null;

    async function poll() {
      // First call: snapshot the current balance so we can detect the increment
      try {
        const first = await getPackBalance();
        initialBalance = first.has_pack ? first.rooms_remaining : 0;
      } catch {
        initialBalance = 0;
      }

      while (!cancelled && attempts < maxAttempts) {
        attempts++;
        await new Promise((r) => setTimeout(r, 2000));
        try {
          const balance = await getPackBalance();
          if (balance.has_pack && balance.rooms_remaining > (initialBalance ?? 0)) {
            setRooms(balance.rooms_remaining);
            setPolling(false);
            return;
          }
        } catch {
          // ignore, retry
        }
      }
      // Polling timed out — show whatever we have
      try {
        const final = await getPackBalance();
        if (final.has_pack) setRooms(final.rooms_remaining);
      } catch { /* ignore */ }
      setPolling(false);
    }

    poll();
    return () => { cancelled = true; };
  }, [session]);

  useEffect(() => {
    if (!session) router.replace("/login");
  }, [session, router]);

  if (!session) return null;

  return (
    <main style={styles.container}>
      <div style={styles.card}>
        <div style={{ fontSize: "2.5rem", marginBottom: 16, textAlign: "center" }}>
          &#x1F389;
        </div>
        <h1 style={styles.title}>You&apos;re all set!</h1>

        {polling ? (
          <p style={styles.subtitle}>
            Processing your payment...
          </p>
        ) : rooms !== null ? (
          <>
            <p style={styles.subtitle}>
              Your {rooms} rooms are ready.
            </p>
            {hasPendingDesign && (
              <p style={{ ...styles.subtitle, marginBottom: 8, fontWeight: 500, color: "#1C1917" }}>
                Your room design is still saved &mdash; pick up right where you left off.
              </p>
            )}
          </>
        ) : (
          <p style={styles.subtitle}>
            Payment received! Your rooms should appear shortly.
            If they don&apos;t, refresh this page in a minute.
          </p>
        )}

        <a
          href="/"
          style={styles.button}
        >
          {hasPendingDesign ? "Continue designing" : "Design a room"}
        </a>

        <p style={styles.note}>
          Your rooms never expire. Use them whenever you&apos;re ready.
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
    maxWidth: 440,
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
    textAlign: "center" as const,
  },
  title: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "1.6rem",
    margin: "0 0 8px 0",
    color: "#1a1a1a",
  },
  subtitle: {
    color: "#57534E",
    fontSize: "0.95rem",
    lineHeight: 1.6,
    marginBottom: 24,
  },
  button: {
    display: "inline-block",
    padding: "12px 36px",
    borderRadius: 10,
    border: "none",
    background: "#1C1917",
    color: "#FFF",
    fontSize: "0.95rem",
    fontWeight: 600,
    textDecoration: "none",
    cursor: "pointer",
  },
  note: {
    color: "#A8A29E",
    fontSize: "0.8rem",
    marginTop: 16,
    marginBottom: 0,
  },
};

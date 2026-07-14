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
    return val !== null;
  });

  useEffect(() => {
    if (!session) return;

    let cancelled = false;
    let attempts = 0;
    const maxAttempts = 15;
    let initialBalance: number | null = null;

    async function poll() {
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
            window.dispatchEvent(new Event("roomkit:pack-changed"));
            return;
          }
        } catch {
          // ignore, retry
        }
      }
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
    <main className="purchase-page">
      <div className="purchase-card">
        <h1 className="purchase-title">You&apos;re all set!</h1>

        {polling ? (
          <p className="purchase-subtitle">Processing your payment...</p>
        ) : rooms !== null ? (
          <>
            <p className="purchase-subtitle">
              Your {rooms} rooms are ready.
            </p>
            {hasPendingDesign && (
              <p className="purchase-subtitle" style={{ marginBottom: 8, fontWeight: 500, color: "var(--color-text)" }}>
                Your room design is still saved &mdash; pick up right where you left off.
              </p>
            )}
          </>
        ) : (
          <p className="purchase-subtitle">
            Payment received! Your rooms should appear shortly.
            If they don&apos;t, refresh this page in a minute.
          </p>
        )}

        <a href="/" className="purchase-btn">
          {hasPendingDesign ? "Continue designing" : "Design a room"}
        </a>

        <p className="purchase-note">
          Your rooms never expire. Use them whenever you&apos;re ready.
        </p>
      </div>
    </main>
  );
}

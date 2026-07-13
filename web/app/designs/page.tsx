"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/components/AuthProvider";
import { getMyDesigns, type DesignSummary } from "@/lib/api";

const AESTHETIC_LABELS: Record<string, Record<string, string>> = {
  bedroom: {
    cottagecore: "Cottagecore", dark_academia: "Dark Academia", japandi: "Japandi",
    coastal: "Coastal", industrial: "Industrial", quiet_luxury: "Quiet Luxury",
    sports_den: "Sports Den", city_modern: "City Modern", ski_lodge: "Ski Lodge",
    jungle_oasis: "Jungle Oasis", gamer_den: "Gamer Den", poster_maximalist: "Poster Maximalist",
    warm_minimalist: "Warm Minimalist",
  },
  living_room: {
    cottagecore: "Country Parlor", dark_academia: "Library Lounge", japandi: "Still Room",
    coastal: "Shore House", industrial: "Warehouse Loft", quiet_luxury: "The Salon",
    sports_den: "The Den", city_modern: "High Rise", ski_lodge: "Fireside",
    jungle_oasis: "Greenhouse", gamer_den: "Command Center", poster_maximalist: "The Gallery",
    warm_minimalist: "Warm Minimalist",
  },
};

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function formatBudget(n: number): string {
  return "$" + n.toLocaleString("en-US", { maximumFractionDigits: 0 });
}

function aestheticLabel(roomType: string, styleName: string): string {
  return AESTHETIC_LABELS[roomType]?.[styleName] ?? styleName.replace(/_/g, " ");
}

function roomTypeLabel(roomType: string): string {
  return roomType.replace(/_/g, " ");
}

export default function MyDesignsPage() {
  const { session, loading: authLoading } = useAuth();
  const router = useRouter();
  const [designs, setDesigns] = useState<DesignSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) { router.replace("/login"); return; }

    getMyDesigns()
      .then((data) => { setDesigns(data); setLoading(false); })
      .catch(() => { setError("Failed to load designs"); setLoading(false); });
  }, [session, authLoading, router]);

  if (authLoading || (!session && !error)) return null;

  return (
    <main className="designs-page">
      <h1 className="designs-title">My Designs</h1>

      {loading && <p className="designs-loading">Loading your designs...</p>}

      {error && <div className="error-banner">{error}</div>}

      {!loading && !error && designs.length === 0 && (
        <div className="designs-empty">
          <p className="designs-empty-text">No designs yet</p>
          <a href="/design" className="designs-empty-cta">Design your first room</a>
        </div>
      )}

      {!loading && designs.length > 0 && (
        <div className="designs-grid">
          {designs.map((d) => (
            <a key={d.run_id} href={`/result/${d.run_id}`} className="design-card">
              <div className="design-card-thumb">
                {d.render_url && (
                  <img
                    src={d.render_url}
                    alt={`${aestheticLabel(d.room_type, d.style_name)} ${roomTypeLabel(d.room_type)}`}
                    className="design-card-img"
                    onError={(e) => {
                      const img = e.target as HTMLImageElement;
                      img.style.display = "none";
                      img.parentElement?.classList.add("design-card-thumb--fallback");
                    }}
                  />
                )}
                <div className="design-card-placeholder">
                  <span>{aestheticLabel(d.room_type, d.style_name)}</span>
                </div>
              </div>
              <div className="design-card-info">
                <span className="design-card-aesthetic">
                  {aestheticLabel(d.room_type, d.style_name)}
                </span>
                <span className="design-card-room-type">{roomTypeLabel(d.room_type)}</span>
                <div className="design-card-meta">
                  <span>{formatBudget(d.target_budget)}</span>
                  <span className="design-card-date">{formatDate(d.created_at)}</span>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}
    </main>
  );
}

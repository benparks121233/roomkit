"use client";

// Result board — fetches GET /design/{run_id}, renders product grid + budget meter.
// Sticky header with wordmark and "New Design" link.

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { getDesign } from "@/lib/api";
import type { DesignResponse } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import BudgetMeter from "@/components/BudgetMeter";

export default function ResultPage() {
  const params = useParams<{ run_id: string }>();
  const runId = params.run_id;

  const [design, setDesign] = useState<DesignResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    getDesign(runId)
      .then(setDesign)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load design"),
      );
  }, [runId]);

  if (error) {
    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-wordmark">RoomKit</a>
        </div>
        <div className="error-banner">{error}</div>
      </main>
    );
  }

  if (!design) {
    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-wordmark">RoomKit</a>
        </div>
        <div className="loading-state">
          <div className="loading-card">
            <h2 className="loading-title">Loading your design...</h2>
          </div>
        </div>
      </main>
    );
  }

  const filledSlots = design.slots.filter((s) => s.product !== null);
  const emptySlots = design.slots.filter((s) => s.product === null);

  return (
    <main className="result-page">
      {/* Sticky header */}
      <div className="result-sticky-header">
        <a href="/" className="result-wordmark">RoomKit</a>
        <a href="/" className="new-design-btn">
          + New design
        </a>
      </div>

      {/* Hero */}
      <div className="result-hero">
        <h1>Your {design.room_type.replace("_", " ")}</h1>
        <div className="style-badge">
          <span className="style-name">
            {design.style.style_name.replace(/_/g, " ")}
          </span>
          <span className="style-mood">{design.style.mood}</span>
        </div>
      </div>

      {!design.is_feasible && (
        <div className="warning-banner">
          Budget is too tight to furnish this room. Try increasing your budget.
        </div>
      )}

      <BudgetMeter total={design.total_spent} target={design.target_budget} />

      <div className="product-grid">
        {filledSlots.map((slot) => (
          <ProductCard key={slot.slot_id} slot={slot} />
        ))}
        {emptySlots.map((slot) => (
          <ProductCard key={slot.slot_id} slot={slot} />
        ))}
      </div>
    </main>
  );
}

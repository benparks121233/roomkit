"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const ADMIN_SECRET = "roomkit-internal-2024";

interface Summary {
  total_runs: number;
  completed_runs: number;
  completion_pct: number;
  avg_cost_per_run: number;
  total_cost: number;
  total_events: number;
  total_selections: number;
}

interface FunnelStep {
  step: string;
  unique_runs: number;
  total_events: number;
}

interface TopAesthetic {
  aesthetic: string;
  runs: number;
}

interface TopProduct {
  product_id: string;
  name: string;
  price: number;
  count: number;
}

interface RecentRun {
  run_id: string;
  created_at: string;
  aesthetic: string;
  budget: number;
  events: string[];
  cost: number;
}

interface AdminData {
  summary: Summary;
  funnel: FunnelStep[];
  top_aesthetics: TopAesthetic[];
  top_products_by_slot: Record<string, TopProduct[]>;
  recent_runs: RecentRun[];
}

export default function AdminPage() {
  const [data, setData] = useState<AdminData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/admin/stats?secret=${ADMIN_SECRET}`);
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  if (loading) return <div style={styles.page}><p style={styles.muted}>Loading dashboard...</p></div>;
  if (error) return <div style={styles.page}><p style={styles.error}>Error: {error}</p></div>;
  if (!data) return null;

  const { summary, funnel, top_aesthetics, top_products_by_slot, recent_runs } = data;

  // Funnel: compute drop-off percentages
  const funnelWithPct = funnel.map((step, i) => {
    const prev = i === 0 ? step.unique_runs : funnel[i - 1].unique_runs;
    const dropPct = prev > 0 ? ((prev - step.unique_runs) / prev * 100) : 0;
    return { ...step, dropPct };
  });

  return (
    <div style={styles.page}>
      <div style={styles.header}>
        <h1 style={styles.h1}>RoomKit Dashboard</h1>
        <button type="button" style={styles.refreshBtn} onClick={() => { setLoading(true); fetchData(); }}>
          Refresh
        </button>
      </div>

      {/* Summary cards */}
      <div style={styles.cardRow}>
        <StatCard label="Total Runs" value={summary.total_runs} />
        <StatCard label="Completed" value={summary.completed_runs} />
        <StatCard label="Completion %" value={`${summary.completion_pct}%`} />
        <StatCard label="Avg Cost/Run" value={`$${summary.avg_cost_per_run.toFixed(3)}`} />
        <StatCard label="Total Cost" value={`$${summary.total_cost.toFixed(2)}`} />
      </div>

      {/* Funnel */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Funnel</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Step</th>
              <th style={styles.thNum}>Unique Runs</th>
              <th style={styles.thNum}>Total Events</th>
              <th style={styles.thNum}>Drop-off</th>
            </tr>
          </thead>
          <tbody>
            {funnelWithPct.map((step) => (
              <tr key={step.step}>
                <td style={styles.td}>{formatStep(step.step)}</td>
                <td style={styles.tdNum}>{step.unique_runs}</td>
                <td style={styles.tdNum}>{step.total_events}</td>
                <td style={styles.tdNum}>
                  {step.dropPct > 0 ? (
                    <span style={{ color: "#DC2626" }}>-{step.dropPct.toFixed(0)}%</span>
                  ) : (
                    <span style={{ color: "#6B7280" }}>--</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Top Aesthetics */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Top Aesthetics</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Aesthetic</th>
              <th style={styles.thNum}>Runs</th>
            </tr>
          </thead>
          <tbody>
            {top_aesthetics.map((a) => (
              <tr key={a.aesthetic}>
                <td style={styles.td}>{a.aesthetic.replace(/_/g, " ")}</td>
                <td style={styles.tdNum}>{a.runs}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Top Products by Slot */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Top Products by Slot</h2>
        {Object.entries(top_products_by_slot).sort().map(([slot, products]) => (
          <div key={slot} style={{ marginBottom: 20 }}>
            <h3 style={styles.h3}>{slot.replace(/_/g, " ")}</h3>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Product</th>
                  <th style={styles.thNum}>Price</th>
                  <th style={styles.thNum}>Picks</th>
                </tr>
              </thead>
              <tbody>
                {products.map((p) => (
                  <tr key={p.product_id}>
                    <td style={styles.td}>
                      <span style={{ fontSize: "0.8rem" }}>{p.name.slice(0, 60)}{p.name.length > 60 ? "..." : ""}</span>
                    </td>
                    <td style={styles.tdNum}>${p.price.toFixed(2)}</td>
                    <td style={styles.tdNum}>{p.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ))}
      </section>

      {/* Recent Runs */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Recent Runs</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Run ID</th>
              <th style={styles.th}>Time</th>
              <th style={styles.th}>Aesthetic</th>
              <th style={styles.thNum}>Budget</th>
              <th style={styles.thNum}>Cost</th>
              <th style={styles.th}>Events</th>
            </tr>
          </thead>
          <tbody>
            {recent_runs.map((run) => (
              <tr key={run.run_id}>
                <td style={styles.td}>
                  <code style={{ fontSize: "0.7rem" }}>{run.run_id.slice(0, 8)}</code>
                </td>
                <td style={styles.td}>
                  <span style={{ fontSize: "0.8rem" }}>{formatTime(run.created_at)}</span>
                </td>
                <td style={styles.td}>{run.aesthetic.replace(/_/g, " ")}</td>
                <td style={styles.tdNum}>${run.budget}</td>
                <td style={styles.tdNum}>${run.cost.toFixed(3)}</td>
                <td style={styles.td}>
                  <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
                    {run.events.map((evt) => (
                      <span key={evt} style={styles.eventBadge}>{formatStep(evt)}</span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string | number }) {
  return (
    <div style={styles.statCard}>
      <div style={styles.statValue}>{value}</div>
      <div style={styles.statLabel}>{label}</div>
    </div>
  );
}

function formatStep(step: string): string {
  return step.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatTime(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
      " " + d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });
  } catch {
    return iso;
  }
}

const styles: Record<string, React.CSSProperties> = {
  page: {
    maxWidth: 960,
    margin: "0 auto",
    padding: "32px 20px",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    color: "#1C1917",
    background: "#FAFAF9",
    minHeight: "100vh",
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 32,
  },
  h1: { fontSize: "1.5rem", fontWeight: 600, margin: 0 },
  h2: { fontSize: "1.1rem", fontWeight: 600, margin: "0 0 12px 0", color: "#44403C" },
  h3: { fontSize: "0.9rem", fontWeight: 600, margin: "0 0 8px 0", color: "#78716C", textTransform: "capitalize" as const },
  refreshBtn: {
    padding: "6px 16px",
    fontSize: "0.8rem",
    border: "1px solid #D6D3D1",
    borderRadius: 6,
    background: "#FFF",
    cursor: "pointer",
    color: "#44403C",
  },
  muted: { color: "#A8A29E", textAlign: "center" as const, marginTop: 80 },
  error: { color: "#DC2626", textAlign: "center" as const, marginTop: 80 },
  cardRow: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
    gap: 12,
    marginBottom: 32,
  },
  statCard: {
    background: "#FFF",
    border: "1px solid #E7E5E4",
    borderRadius: 10,
    padding: "16px 14px",
    textAlign: "center" as const,
  },
  statValue: { fontSize: "1.4rem", fontWeight: 700, color: "#1C1917" },
  statLabel: { fontSize: "0.75rem", color: "#A8A29E", marginTop: 4, textTransform: "uppercase" as const, letterSpacing: "0.04em" },
  section: {
    background: "#FFF",
    border: "1px solid #E7E5E4",
    borderRadius: 10,
    padding: "20px",
    marginBottom: 20,
  },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: "0.85rem" },
  th: { textAlign: "left" as const, padding: "8px 10px", borderBottom: "1px solid #E7E5E4", color: "#78716C", fontWeight: 500, fontSize: "0.75rem", textTransform: "uppercase" as const },
  thNum: { textAlign: "right" as const, padding: "8px 10px", borderBottom: "1px solid #E7E5E4", color: "#78716C", fontWeight: 500, fontSize: "0.75rem", textTransform: "uppercase" as const },
  td: { padding: "8px 10px", borderBottom: "1px solid #F5F5F4" },
  tdNum: { padding: "8px 10px", borderBottom: "1px solid #F5F5F4", textAlign: "right" as const, fontVariantNumeric: "tabular-nums" },
  eventBadge: {
    display: "inline-block",
    padding: "2px 6px",
    fontSize: "0.65rem",
    background: "#F5F5F4",
    borderRadius: 4,
    color: "#78716C",
  },
};

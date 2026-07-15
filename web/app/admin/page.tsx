"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/components/AuthProvider";

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
  room_type: string;
  is_paid: boolean;
}

interface Users {
  total_signups: number;
  users_with_designs: number;
  users_with_packs: number;
  signup_to_design_pct: number;
  design_to_purchase_pct: number;
}

interface Revenue {
  total_packs_purchased: number;
  total_revenue: number;
  packs_remaining: number;
}

interface RoomBreakdown {
  room_type: string;
  total: number;
  paid: number;
  free: number;
  avg_budget: number;
  avg_spent: number;
}

interface CostTracking {
  total_api_cost: number;
  cost_by_room_type: Record<string, number>;
  avg_cost_per_design: number;
}

interface Engagement {
  render_rate: number;
  finalization_rate: number;
  cart_export_rate: number;
  buy_link_click_rate: number;
}

interface AdminData {
  summary: Summary;
  funnel: FunnelStep[];
  top_aesthetics: TopAesthetic[];
  top_products_by_slot: Record<string, TopProduct[]>;
  recent_runs: RecentRun[];
  users: Users;
  revenue: Revenue;
  room_breakdown: RoomBreakdown[];
  cost_tracking: CostTracking;
  engagement: Engagement;
}

export default function AdminPage() {
  const { session, loading: authLoading } = useAuth();
  const [data, setData] = useState<AdminData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    if (!session) return;
    try {
      const res = await fetch("/api/admin", {
        headers: { Authorization: `Bearer ${session.access_token}` },
      });
      if (res.status === 403) throw new Error("Not authorized");
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      setData(await res.json());
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load");
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    if (authLoading) return;
    if (!session) { setError("Sign in required"); setLoading(false); return; }
    fetchData();
  }, [session, authLoading, fetchData]);

  if (loading) return <div style={styles.page}><p style={styles.muted}>Loading dashboard...</p></div>;
  if (error) return <div style={styles.page}><p style={styles.error}>Error: {error}</p></div>;
  if (!data) return null;

  const { summary, funnel, top_aesthetics, top_products_by_slot, recent_runs, users, revenue, room_breakdown, cost_tracking, engagement } = data;

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

      {/* Users & Revenue side-by-side */}
      <div style={styles.twoCol}>
        <section style={styles.section}>
          <h2 style={styles.h2}>Users</h2>
          <div style={styles.cardRowCompact}>
            <StatCard label="Total Signups" value={users.total_signups} />
            <StatCard label="With Designs" value={users.users_with_designs} />
            <StatCard label="With Packs" value={users.users_with_packs} />
          </div>
          <div style={{ ...styles.cardRowCompact, marginTop: 8 }}>
            <StatCard label="Signup→Design" value={`${users.signup_to_design_pct.toFixed(1)}%`} />
            <StatCard label="Design→Purchase" value={`${users.design_to_purchase_pct.toFixed(1)}%`} />
          </div>
        </section>
        <section style={styles.section}>
          <h2 style={styles.h2}>Revenue</h2>
          <div style={styles.cardRowCompact}>
            <StatCard label="Packs Sold" value={revenue.total_packs_purchased} />
            <StatCard label="Revenue" value={`$${revenue.total_revenue.toFixed(2)}`} />
            <StatCard label="Packs Remaining" value={revenue.packs_remaining} />
          </div>
        </section>
      </div>

      {/* Room Breakdown */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Room Breakdown</h2>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Room Type</th>
              <th style={styles.thNum}>Total Designs</th>
              <th style={styles.thNum}>Paid</th>
              <th style={styles.thNum}>Free</th>
              <th style={styles.thNum}>Avg Budget</th>
              <th style={styles.thNum}>Avg Spent</th>
            </tr>
          </thead>
          <tbody>
            {room_breakdown.map((rb) => (
              <tr key={rb.room_type}>
                <td style={styles.td}>{capitalize(rb.room_type)}</td>
                <td style={styles.tdNum}>{rb.total}</td>
                <td style={styles.tdNum}>{rb.paid}</td>
                <td style={styles.tdNum}>{rb.free}</td>
                <td style={styles.tdNum}>${rb.avg_budget.toFixed(0)}</td>
                <td style={styles.tdNum}>${rb.avg_spent.toFixed(0)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Cost Tracking */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Cost Tracking</h2>
        <div style={{ ...styles.cardRowCompact, marginBottom: 16 }}>
          <StatCard label="Total API Cost" value={`$${cost_tracking.total_api_cost.toFixed(2)}`} />
          <StatCard label="Avg Cost/Design" value={`$${cost_tracking.avg_cost_per_design.toFixed(3)}`} />
        </div>
        <h3 style={styles.h3}>Cost by Room Type</h3>
        <table style={styles.table}>
          <thead>
            <tr>
              <th style={styles.th}>Room Type</th>
              <th style={styles.thNum}>Total Cost</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(cost_tracking.cost_by_room_type).sort().map(([rt, cost]) => (
              <tr key={rt}>
                <td style={styles.td}>{capitalize(rt)}</td>
                <td style={styles.tdNum}>${cost.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {/* Engagement */}
      <section style={styles.section}>
        <h2 style={styles.h2}>Engagement</h2>
        <div style={styles.cardRow}>
          <StatCard label="Render Rate" value={`${engagement.render_rate.toFixed(1)}%`} />
          <StatCard label="Finalization Rate" value={`${engagement.finalization_rate.toFixed(1)}%`} />
          <StatCard label="Cart Export Rate" value={`${engagement.cart_export_rate.toFixed(1)}%`} />
          <StatCard label="Buy Link Click Rate" value={`${engagement.buy_link_click_rate.toFixed(1)}%`} />
        </div>
      </section>

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
              <th style={styles.th}>Room</th>
              <th style={styles.th}>Aesthetic</th>
              <th style={styles.thNum}>Budget</th>
              <th style={styles.thNum}>Cost</th>
              <th style={styles.th}>Paid</th>
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
                <td style={styles.td}>{capitalize(run.room_type)}</td>
                <td style={styles.td}>{run.aesthetic.replace(/_/g, " ")}</td>
                <td style={styles.tdNum}>${run.budget}</td>
                <td style={styles.tdNum}>${run.cost.toFixed(3)}</td>
                <td style={styles.td}>
                  <span style={run.is_paid ? styles.paidBadge : styles.freeBadge}>
                    {run.is_paid ? "Paid" : "Free"}
                  </span>
                </td>
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

function capitalize(s: string): string {
  if (!s) return "";
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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
  cardRowCompact: {
    display: "grid",
    gridTemplateColumns: "repeat(auto-fit, minmax(100px, 1fr))",
    gap: 8,
  },
  twoCol: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
    marginBottom: 20,
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
  paidBadge: {
    display: "inline-block",
    padding: "2px 8px",
    fontSize: "0.7rem",
    background: "#DCFCE7",
    borderRadius: 4,
    color: "#166534",
    fontWeight: 600,
  },
  freeBadge: {
    display: "inline-block",
    padding: "2px 8px",
    fontSize: "0.7rem",
    background: "#F5F5F4",
    borderRadius: 4,
    color: "#78716C",
    fontWeight: 500,
  },
};

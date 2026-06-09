// web/components/RoomBoard.tsx
// Full result board: render image on top, then the per-slot ProductCard grid,
// with a BudgetMeter showing running total vs. target.
// Reads from the Design snapshot — never from live product data.
// Stage 9: implement.

export default function RoomBoard({ runId }: { runId: string }) {
  // Stage 9: fetch Design from GET /design/{runId}, render image + cards + meter
  return <div>RoomBoard for run {runId} — Stage 9</div>;
}

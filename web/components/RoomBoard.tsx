// web/components/RoomBoard.tsx
// Re-export note: the board layout is now in app/result/[run_id]/page.tsx directly.
// This file kept for future extraction if the board becomes reusable (share page, etc).

export default function RoomBoard({ runId }: { runId: string }) {
  return <div>RoomBoard for run {runId} — see result page</div>;
}

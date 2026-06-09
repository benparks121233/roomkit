// web/app/result/[run_id]/page.tsx
// Result board screen.
// Fetches GET /design/{run_id} and renders: styled render image,
// per-slot ProductCards, running BudgetMeter, and a link to the share card.
// Stage 9: implement.

type Props = { params: { run_id: string } };

export default function ResultPage({ params }: Props) {
  return (
    <main style={{ maxWidth: 800, margin: "0 auto", padding: "2rem" }}>
      <h1>Your room design</h1>
      <p>run_id: {params.run_id}</p>
      <p>Stage 9: RoomBoard + ProductCards + BudgetMeter go here.</p>
      {/* <RoomBoard runId={params.run_id} /> */}
    </main>
  );
}

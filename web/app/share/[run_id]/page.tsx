// web/app/share/[run_id]/page.tsx
// Share screen — a clean, screenshot-friendly card for the design.
// The viral unit: embed render + top products + total + RoomKit branding.
// Stage 9: implement ShareCard.

type Props = { params: { run_id: string } };

export default function SharePage({ params }: Props) {
  return (
    <main style={{ maxWidth: 600, margin: "0 auto", padding: "2rem" }}>
      <p>Stage 9: ShareCard for run {params.run_id} goes here.</p>
      {/* <ShareCard runId={params.run_id} /> */}
    </main>
  );
}

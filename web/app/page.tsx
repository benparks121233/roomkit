// web/app/page.tsx
// Intake screen — the entry point to the funnel.
// Renders IntakeForm + StyleQuiz + BudgetSlider.
// On submit: POST /design → redirect to /result/[run_id].
// Stage 3/9: wire up form submission and routing.

export default function IntakePage() {
  return (
    <main style={{ maxWidth: 600, margin: "0 auto", padding: "2rem" }}>
      <h1>Design your room.</h1>
      <p>Stage 3/9: intake form goes here.</p>
      {/* <IntakeForm /> */}
      {/* <StyleQuiz /> */}
      {/* <BudgetSlider /> */}
    </main>
  );
}

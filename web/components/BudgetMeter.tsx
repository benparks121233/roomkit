// web/components/BudgetMeter.tsx
// Running budget total vs. target. Shows spent / target and a progress bar.
// Total is computed from snapshot prices — always matches the validator output.
// Stage 9: implement.

export default function BudgetMeter({
  total,
  target,
}: {
  total: number;
  target: number;
}) {
  // Stage 9: display $total / $target with a visual bar
  return <div>BudgetMeter ${total} / ${target} — Stage 9</div>;
}

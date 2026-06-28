// web/components/BudgetMeter.tsx
// Budget total vs. target with a threshold-colored progress bar.

export default function BudgetMeter({
  total,
  target,
}: {
  total: number;
  target: number;
}) {
  const pct = target > 0 ? Math.min((total / target) * 100, 100) : 0;
  const remaining = target - total;

  let fillClass = "budget-bar-fill";
  let remainingClass = "budget-remaining remaining-ok";
  if (remaining < 0) {
    fillClass += " budget-near";
    remainingClass = "budget-remaining remaining-near";
  } else if (pct >= 80) {
    fillClass += " budget-tight";
    remainingClass = "budget-remaining remaining-tight";
  }

  return (
    <div className="budget-meter">
      <div className="budget-numbers">
        <span className="budget-spent">${total.toFixed(2)} spent</span>
        <span className="budget-target">of ${target.toFixed(2)} budget</span>
      </div>
      <div className="budget-bar-track">
        <div className={fillClass} style={{ width: `${pct}%` }} />
      </div>
      <p className={remainingClass}>
        {remaining >= 0
          ? `$${remaining.toFixed(2)} remaining`
          : `$${Math.abs(remaining).toFixed(2)} above target`}
      </p>
    </div>
  );
}

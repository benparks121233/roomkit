// web/components/BudgetMeter.tsx
// Budget total vs. target with a threshold-colored progress bar.
// Shows the user's CHOSEN budget. If over-budget mode is active, the bar
// can fill past 100% up to the effective target (e.g. 130%).

export default function BudgetMeter({
  total,
  target,
  userBudget,
}: {
  total: number;
  target: number;       // Effective budget (may include +30% multiplier)
  userBudget?: number;  // User's stated budget (before multiplier)
}) {
  // Display budget = user's chosen budget (falls back to effective target)
  const displayBudget = userBudget ?? target;
  const isOverBudgetMode = userBudget != null && target > userBudget * 1.01;

  // Progress is measured against the user's chosen budget
  const pct = displayBudget > 0 ? (total / displayBudget) * 100 : 0;
  const remaining = displayBudget - total;

  // Threshold classes — "over" when exceeding the user's chosen budget
  let fillClass = "budget-bar-fill";
  let remainingClass = "budget-remaining remaining-ok";
  if (total > displayBudget) {
    fillClass += " budget-over";
    remainingClass = "budget-remaining remaining-over";
  } else if (pct >= 80) {
    fillClass += " budget-tight";
    remainingClass = "budget-remaining remaining-tight";
  }

  // Cap the visual bar at 130% so it doesn't overflow absurdly
  const barWidth = Math.min(pct, 130);

  return (
    <div className="budget-meter">
      <div className="budget-numbers">
        <span className="budget-spent">${total.toFixed(2)} spent</span>
        <span className="budget-target">of ${displayBudget.toFixed(2)} budget</span>
      </div>
      <div className="budget-bar-track">
        <div className={fillClass} style={{ width: `${barWidth}%` }} />
      </div>
      <p className={remainingClass}>
        {remaining >= 0
          ? `$${remaining.toFixed(2)} remaining`
          : `$${Math.abs(remaining).toFixed(2)} over budget`}
      </p>
      {isOverBudgetMode && total > displayBudget && (
        <p className="budget-over-note" style={{
          fontSize: "0.75rem",
          color: "#B91C1C",
          marginTop: 2,
        }}>
          +30% over-budget mode active (max ${target.toFixed(2)})
        </p>
      )}
    </div>
  );
}

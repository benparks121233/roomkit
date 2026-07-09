# Shared budget-quality thresholds.
# All three quality-tracking mechanisms reference these so the
# "high budget" definition is adjustable in one place.

# Total room budget above which quality-tracking kicks in.
HIGH_BUDGET_THRESHOLD = 1500

# Per-slot allocation above which cheap-backfill diversity is skipped.
BACKFILL_FURNITURE_CAP = 120
BACKFILL_DECOR_CAP = 60

# Minimum price floor as fraction of slot allocation (high budgets only).
PRICE_FLOOR_FRACTION = 0.20

# Minimum candidate count before price floor falls back to zero.
PRICE_FLOOR_MIN_CANDIDATES = 15

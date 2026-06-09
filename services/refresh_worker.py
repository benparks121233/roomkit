# services/refresh_worker.py
# Owns: locked cron job that re-validates prices and links for active designs.
# Runs every 6 hours (see context/freshness_policies.yaml).
# MUST run under an advisory lock — no double-run, no deadlock.
# MUST be idempotent — safe to run twice on the same design.
# MUST NOT run in the request path; Railway cron service only.
# MUST NOT mutate a design's snapshot content — only updates freshness metadata
# and flips dead links to a "link_dead" status.
# Stage 11: implement.


def run_refresh() -> None:
    # 1. Acquire advisory lock (fail fast if already held).
    # 2. Fetch active designs with snapshots older than freshness_hours.
    # 3. For each stale snapshot: check link liveness + current price.
    # 4. Update freshness timestamp; flip dead links to link_dead status.
    # 5. Release lock.
    raise NotImplementedError("Stage 11")


if __name__ == "__main__":
    run_refresh()

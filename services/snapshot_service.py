# services/snapshot_service.py
# Owns: freezing selected products/prices/urls/specs at design-generation time.
# A ProductSnapshot is immutable after creation — never mutated, only superseded
# by the refresh worker when a price/link goes stale.
# Saved designs always reference their snapshot, never live data.
# Stage 8: implement.


def snapshot_selections(run_id: str, selections: list) -> list:
    # Takes a list of selected Products, writes immutable ProductSnapshot records
    # (price, buy_url, specs, sourced_at timestamp) to DB, returns snapshot list.
    raise NotImplementedError("Stage 8")

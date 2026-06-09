# validators/price_link_rules.py
# Owns: price freshness, link liveness, and affiliate tag presence.
# All three must pass before a product is shown to a user.
# Freshness window comes from context/freshness_policies.yaml.
# Stage 8: implement.


def validate_price_freshness(snapshot, freshness_hours: int) -> tuple[bool, str | None]:
    """Return (True, None) if snapshot price is within the freshness window."""
    # Stage 8: compare snapshot.snapshotted_at to now; reject if stale.
    raise NotImplementedError("Stage 8")


def validate_link_live(snapshot) -> tuple[bool, str | None]:
    """Return (True, None) if snapshot.buy_url responds 200."""
    # Stage 8: HEAD request to buy_url; reject if dead.
    raise NotImplementedError("Stage 8")


def validate_affiliate_tag(snapshot, affiliate_tag: str) -> tuple[bool, str | None]:
    """Return (True, None) if affiliate_tag is present in snapshot.buy_url."""
    # Stage 8: string check on buy_url; reject if tag absent.
    raise NotImplementedError("Stage 8")

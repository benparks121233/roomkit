# Sourcing Strategy

## Channel sequence

### v1 — Amazon curated + SiteStripe (ships now)
No API gate. Build a curated product list per slot category; generate affiliate
links via SiteStripe. Every product must carry: normalized_price, a live buy_url
with AMAZON_AFFILIATE_TAG, and all required specs for its slot.

### v1.5 — Amazon PA-API or paid product-data API
Trigger: ~10 qualifying sales (PA-API gate) or sooner via a paid catalog API
(Rainforest, Canopy, or equivalent). Swap the AmazonAdapter internals behind the
frozen SourcingAdapter interface — the pipeline does not change.

### v2 — Temu budget tier (opt-in)
Post-loop, once the consumer loop is validated. Use a paid Temu scraper API.
Implement TemuAdapter behind the same frozen interface. Present as an opt-in
"budget mode" so Amazon remains the trust default.

## The adapter interface is frozen

`services/sourcing/base.py` defines the SourcingAdapter ABC. Every adapter must
implement `fetch_candidates(slot_id, style_keywords, price_band, required_specs)`.

This contract means: adding Temu, swapping Amazon backends, or adding a third
sourcing channel requires touching only the adapter file, not the pipeline.

## Data integrity requirements (non-negotiable)

Every product returned by any adapter must:
1. Carry a `normalized_price` (float, USD)
2. Carry a `buy_url` that is live and contains the correct affiliate tag
3. Carry `specs` satisfying the slot's required spec rules
4. Be validated by `validators/price_link_rules.py` before display

No product bypasses the validators, regardless of source.

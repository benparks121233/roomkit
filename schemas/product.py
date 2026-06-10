# schemas/product.py
# Owns: a live product returned by a SourcingAdapter.
# This is the pre-snapshot live record.  After selection, a product is frozen
# into a ProductSnapshot (schemas/product_snapshot.py, Stage 8).
#
# Critical rule: buy_url MUST contain the affiliate tag.  The adapter is
# responsible for injecting it; validators/price_link_rules.py verifies it.

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class Product(BaseModel):
    product_id: str
    name: str
    normalized_price: float          # USD, inclusive of tax if applicable
    buy_url: str                     # live purchase link, affiliate-tagged
    specs: dict[str, str]            # key-value pairs matching category_spec_rules
    source: str                      # e.g. "amazon"
    image_url: str                   # product image for render/display
    slot_id: str                     # which slot category this product fills
    fetched_at: datetime             # UTC timestamp when this data was retrieved

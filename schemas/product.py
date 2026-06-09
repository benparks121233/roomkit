# schemas/product.py
# Owns: a live product returned by a SourcingAdapter.
# Must carry: normalized_price, buy_url (live + affiliate-tagged), specs, source.
# This is the pre-snapshot live record. Stage 6: add fields.

from pydantic import BaseModel


class Product(BaseModel):
    # Stage 6: product_id, name, normalized_price, buy_url, specs, source, image_url, fetched_at
    pass

# schemas/product_snapshot.py
# Owns: an immutable frozen record of a product at design-generation time.
# Written once by snapshot_service.py; never mutated.
# Designs always read from their snapshot — never from live product data.
# Stage 8: add fields.

from pydantic import BaseModel


class ProductSnapshot(BaseModel):
    # Stage 8: snapshot_id, run_id, slot_id, product_id, name, price, buy_url,
    #          specs, source, affiliate_tag, snapshotted_at, link_status
    pass

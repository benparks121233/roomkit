# services/sourcing/amazon_adapter.py
# Owns: Amazon Associates sourcing via curated list + SiteStripe links (v1).
# Later: swap internals to PA-API or a paid product-data API (Rainforest/Canopy)
# without changing the SourcingAdapter interface.
# Stage 6: implement.

from services.sourcing.base import SourcingAdapter


class AmazonAdapter(SourcingAdapter):
    def fetch_candidates(self, slot_id: str, style_keywords: list[str],
                         price_band: tuple[float, float], required_specs: dict) -> list:
        # v1: query curated product list filtered by slot_id + price_band.
        # Every returned Product must carry normalized_price, buy_url with affiliate tag, specs.
        raise NotImplementedError("Stage 6")

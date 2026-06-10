# services/sourcing/temu_adapter.py
# Placeholder — not implemented in v1.
# Will use a paid scraper API as an opt-in budget-tier sourcing backend.
# Implements the frozen SourcingAdapter interface.

from services.sourcing.base import SourcingAdapter


class TemuAdapter(SourcingAdapter):
    def fetch_candidates(self, slot_id: str, style_keywords: list[str],
                         price_band: tuple[float, float], required_specs: dict,
                         interests: list[str] | None = None) -> list:
        raise NotImplementedError("Temu adapter: post-loop, not v1")

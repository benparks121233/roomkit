# services/sourcing/base.py
# Owns: the SourcingAdapter interface — frozen so that swapping
# Amazon → product-data API → Temu only touches the adapter, not the pipeline.
# All adapters must implement fetch_candidates().

from abc import ABC, abstractmethod


class SourcingAdapter(ABC):
    """Frozen interface for all sourcing backends.

    Every adapter must return Product instances that carry:
    - normalized_price (float)
    - buy_url (str, live, with affiliate tag embedded)
    - specs (dict matching category_spec_rules.yaml requirements)
    - source (str, e.g. "amazon")
    """

    @abstractmethod
    def fetch_candidates(self, slot_id: str, style_keywords: list[str],
                         price_band: tuple[float, float], required_specs: dict) -> list:
        """Return a list of Product candidates for the given slot.

        Args:
            slot_id: the slot being sourced (e.g. "bedding")
            style_keywords: style cues from StyleProfile
            price_band: (min_price, max_price) in USD
            required_specs: spec constraints from category_spec_rules.yaml

        Returns:
            List of Product schema instances. Empty list if no candidates found.
        """
        ...

# services/selection_service.py
# Owns: choosing one product per slot from the sourcing adapter's candidate list.
# LLM (select_products.md) selects within a constrained candidate set.
# If no candidate satisfies required specs or price band, returns null + reason.
# Stage 7: implement.


def select_product(slot_id: str, style_profile, candidates: list,
                   price_band: tuple[float, float], required_specs: dict):
    # Calls LLM with select_products.md template + candidate list.
    # Returns (chosen_product, fit_reason) or (None, "no_spec_match" | "no_candidate").
    raise NotImplementedError("Stage 7")

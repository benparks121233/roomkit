# services/composition_service.py
# Owns: planning which slots to fill and how to split the budget across them.
# LLM (plan_composition.md) proposes weights; CODE clamps so Σ ≤ target_budget.
# Required slots from room preset are enforced here, not in the prompt.
# Stage 5: implement.


def plan_composition(style_profile, target_budget: float, room_preset: str) -> object:
    # Returns a SlotPlan. Budget total is clamped by code after LLM proposal.
    # Required slots for room_preset are injected before returning.
    raise NotImplementedError("Stage 5")

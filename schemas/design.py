# schemas/design.py
# Owns: a complete saved design — the full board the user sees.
# References product snapshots (never live data), render URL, run metadata.
# Stage 9: add fields.

from pydantic import BaseModel


class Design(BaseModel):
    # Stage 9: run_id, room_request_id, style_profile, slot_plan,
    #          snapshots (list[ProductSnapshot]), render_url, total_price,
    #          target_budget, created_at, status
    pass

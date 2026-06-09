# schemas/click_event.py
# Owns: a single impression or click log record.
# Every event carries run_id, slot_id, product_id, style, budget, source.
# This stream is the durable data moat — log from day one. Stage 10: add fields.

from pydantic import BaseModel


class ClickEvent(BaseModel):
    # Stage 10: event_id, event_type (impression|click), run_id, slot_id,
    #           product_id, style_name, budget, source, occurred_at
    pass

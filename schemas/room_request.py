# schemas/room_request.py
# Owns: validated intake output — the contract between intake_service and the pipeline.
# Missing fields are null, never guessed. Stage 3: add fields.

from pydantic import BaseModel


class RoomRequest(BaseModel):
    # Stage 3: run_id, room_type, dimensions, photo_url, budget, style_hints, bed_size, etc.
    pass

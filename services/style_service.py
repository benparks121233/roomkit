# services/style_service.py
# Owns: LLM call that maps a RoomRequest to a StyleProfile.
# Uses prompts/interpret_style.md. Output is schema-constrained.
# Stage 4: implement.


def interpret_style(room_request) -> object:
    # Calls the LLM with interpret_style.md template + RoomRequest fields.
    # Returns a StyleProfile. Never returns free-form prose.
    raise NotImplementedError("Stage 4")

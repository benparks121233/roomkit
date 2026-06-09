# services/intake_service.py
# Owns: parsing photo/dimensions + Q&A into a validated RoomRequest.
# Rule: missing or ambiguous fields → null, never guessed.
# Stage 3: implement.


def parse_intake(raw_input: dict):
    # Takes raw user input (photo path or dimensions, style/budget Q&A answers).
    # Returns a validated RoomRequest schema instance.
    # Missing required fields produce null, not guesses.
    raise NotImplementedError("Stage 3")

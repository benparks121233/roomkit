# services/assembly_service.py
# Owns: deterministic final board assembly — the exact data the user sees.
# Reads from product snapshots (never live data), attaches render URL,
# computes running budget total, returns a Design ready for the UI.
# Stage 9: implement.


def assemble_board(run_id: str, snapshots: list, render_url: str | None,
                   target_budget: float) -> object:
    # Assembles a Design from snapshots + render.
    # Running total is computed here; budget never exceeds target (enforced by validator upstream).
    raise NotImplementedError("Stage 9")

# tests/test_refresh_worker.py
# Tests for services/refresh_worker.py (Stage 11).
# Covers: advisory lock prevents double-run; idempotent (safe to run twice);
# dead links flipped to link_dead status; stale prices updated;
# snapshot content not mutated (only freshness metadata updated).
# Stage 11: add tests.

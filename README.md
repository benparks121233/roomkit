# RoomKit

Whole-room AI design and commerce engine. Takes a room (photo or dimensions) plus
style/budget inputs, plans a composition of slots, selects real buyable products per
slot within budget, snapshots them, validates deterministically, renders a styled image,
and presents a budgeted shoppable board with live affiliate links.

## Local setup

```bash
# Python backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Next.js frontend
cd web && npm install
```

Copy `.env.example` to `.env` and fill in values before running.

## Commands

```bash
# Run all tests
pytest

# Run a single test file
pytest tests/test_budget_rules.py

# Lint
ruff check .

# Type check
mypy app services validators

# Local API server (from repo root)
uvicorn app.main:app --reload

# Local web dev server
cd web && npm run dev

# Build frontend
cd web && npm run build
```

## Architecture

See `docs/system_map.md` for the full pipeline map and `AGENTS.md` for repo rules.
The governing build plan is `docs/RoomKit_Founder_Build_Packet_v2.md`.

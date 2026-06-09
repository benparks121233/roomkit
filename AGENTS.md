# AGENTS.md

## Purpose
This repo powers RoomKit: a whole-room AI design and commerce engine.
It takes a room (photo or dimensions) plus style/budget inputs, plans a
composition of slots, selects real buyable products per slot within budget,
snapshots them, validates budget/specs/links/freshness deterministically,
renders a styled image, and presents a budgeted shoppable board.
Every design is a logged, idempotent run; every shown link earns affiliate revenue.

## Stack
- Frontend: Next.js/React in web/
- Backend: Python + FastAPI in app/ and services/
- DB/state: Supabase (Postgres)
- Deploy: Railway (web, worker, cron); source + CI on GitHub

## Main folders
- web/: consumer UI (intake, board, share) — funnel-critical
- services/: intake, style, composition, sourcing/, selection, snapshot, render, assembly, refresh_worker
- schemas/: typed contracts (room request, style profile, slot, slot plan, product, snapshot, design, click event)
- validators/: deterministic budget, spec, price/link, composition rules
- prompts/: LLM templates (style, composition, selection) + coding_agent/ saved prompts
- context/: slot taxonomy, style profiles, category spec rules, sourcing + freshness policies
- evals/: composition eval set + coherence rubric
- tests/: unit, validator, integration

## Core rules (always true)
- The slot taxonomy and category_spec_rules are authoritative.
- A board's product total MUST NOT exceed the target budget. Ever. This is code-enforced.
- Every product shown to a user MUST have: a validated live link, a price within the
  freshness window, and the correct affiliate tag in the buy URL.
- Each design is run-scoped: assign a run_id, log inputs/outputs, and make generation idempotent.
- Snapshot the exact products/prices used in a design at generation time. A saved design
  must be reconstructable later even if live prices/links have changed.
- Price/link freshness is enforced by code before display and before re-displaying an old design.
- The price/link refresh job runs in the cron worker under a lock; it must not double-run or deadlock.
- Business rules (budget, specs, links, tags, freshness) live in validators/, NEVER in prompts.
- Prompts may only interpret style, propose composition, and select within constraints.
- The render is presentation-only and is NEVER a source of product/price truth.
- Every product impression and every click is logged as data (this is the durable moat).

## Safe commands
- Run tests: `pytest`
- Lint/type: `ruff check .` / `mypy app services validators`
- Local API: `uvicorn app.main:app --reload`
- Local web: `cd web && npm run dev`

## Forbidden in tests / dev
- No writes that mutate a stored design's snapshot after creation.
- No live affiliate calls in tests; use fixtures.
- No skipping the budget/spec/link validators to "make it pass."

## How the agent must work
- Architecture-first: inspect and summarize before editing; propose a plan; wait for approval on
  anything touching budget, links, tags, snapshots, or the refresh lock.
- Build one stage at a time; do not jump ahead.
- After each change: explain changed files in plain English, state assumptions, add/extend tests,
  run them, and show failing evidence before patching.
- Update README, AGENTS.md, prompt templates, and context files when they should change.

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

RoomKit is a whole-room AI design and commerce engine. Given a room photo or dimensions plus style/budget inputs, it generates a coherent, fully-budgeted, shoppable room design. The core product is the **cart, not the picture** — a set of real, buyable products with live purchase links and a running total that never exceeds the user's budget. Revenue is affiliate referral (v1), evolving to subscription and operator sourcing spreads.

The build plan is documented in `LAUNCH_PLAN.md` (master launch plan with phases, dependencies, and hard gates). **Phase 5 complete** — bedroom + living room are production-ready (319 tests). Entering the launch-readiness track (auth, security, compliance, deploy, beta).

## Stack

- **Frontend:** Next.js + React (`web/`)
- **Backend:** Python + FastAPI (`app/`, `services/`)
- **Database:** Supabase (Postgres) — designs, runs, slots, snapshots, click events
- **Deploy:** Railway — three services: `web` (API), `worker` (async), `cron` (refresh)
- **Sourcing v1:** Amazon Associates (curated + SiteStripe affiliate links)
- **Image generation:** Pluggable render backend (presentation layer only)

## Commands

```bash
# Python backend
pytest                                    # run all tests
pytest tests/test_budget_rules.py        # run a single test file
ruff check .                             # lint
mypy app services validators             # type check
uvicorn app.main:app --reload            # local API server

# Next.js frontend
cd web && npm run dev                    # local dev server
cd web && npm run build                  # production build
cd web && npm run lint                   # lint
```

## Architecture: The Pipeline

Every design generation flows through this sequence:

```
User Input (photo/dims + Q&A)
  → [Intake Service]      → RoomRequest (schema-validated)
  → [Style Service]       → StyleProfile  (LLM)
  → [Composition Service] → SlotPlan      (LLM proposes weights; CODE clamps to budget)
  → [Sourcing Adapter]    → Candidates per slot (live, with specs + price)
  → [Selection Service]   → Chosen product per slot (LLM, within constraints)
  → [Snapshot Service]    → ProductSnapshot (freeze price/URL/specs + timestamp)
  → [Validators]          → Deterministic checks (budget, specs, link, affiliate tag)
  → [Render Service]      → Styled image (never a source of truth)
  → [Assembly Service]    → Final shoppable board
  → [Click Event Logger]  → Impressions + clicks recorded with run_id
```

The **Refresh Worker** (locked cron, every 6h) re-validates prices and links on active designs without re-running the LLM pipeline.

## The Hard Rule: Deterministic vs. LLM

This is the most important architectural constraint:

| Always code-enforced | Always LLM |
|---|---|
| Budget totals (never exceed target) | Style interpretation |
| Per-category spec requirements (bed_size, screen_size, rug dimensions) | Composition weight proposals |
| Price freshness (24h window) | Product selection among valid candidates |
| Link validity and affiliate tag presence | |
| Snapshot immutability (never mutate after creation) | |

**Budget logic, spec enforcement, link validation, and affiliate tagging must never appear in prompts.** If it's a money or compliance concern, it lives in `validators/`.

## Key Abstractions

**`SourcingAdapter` interface** (`services/sourcing/base.py`) — frozen contract so swapping Amazon → product-data API → Temu is a backend change, not an architectural one.

**`ProductSnapshot`** — products are frozen at design-generation time (price, URL, specs, timestamp). Saved designs always read from snapshots, never live data. Snapshots are immutable after creation.

**`run_id`** — each design generation is run-scoped and idempotent. Same input → same run, fully logged.

**`slot_taxonomy.yaml`** — the operational definition of "a room." Slots (bed_frame, bedding, rug, sofa, lighting, tv, wall_art, accent), their budget weights, required specs, and room presets (bedroom, living_room) all flow from this file, not from prompts.

**Validators** (`validators/`) — `budget_rules.py`, `spec_rules.py`, `price_link_rules.py`, `composition_rules.py`. These run deterministically after every LLM step. If they pass, the result is safe to show.

**Refresh Worker** (`services/refresh_worker.py`) — single idempotent cron job with an advisory lock (no double-run, no deadlock). Re-validates active designs' snapshots. Must not re-run LLM logic.

## Key Engine Logic (and WHY)

These are the non-obvious design decisions baked into the engine. They exist because real catalog data + real budget math forced them — not because they're round numbers.

**35% entertainment cap** (`composition_service.py:_ENT_MAX_SHARE`): When a user wants a large TV, the entertainment group's budget share inflates to fund the TV's price floor. Capped at 35% (45% with "Prioritize TV") because beyond that, the remaining slots collapse — sofas, rugs, lighting all compress below their cheapest viable products. The cap was found empirically: 35% is the breakpoint where the rest of the room still works.

**TV price floors** (`_TV_PRICE_FLOORS`): $90 small, $160 medium, $300 large, $550 XL. These come from real catalog minimums — the cheapest real TV at each size bucket. Without floors, budget allocation gives a $40 TV slot that has zero viable candidates.

**3x priority-term weighting** (`amazon_adapter.py:_PRIORITY_WEIGHT = 3`): Aesthetic-differentiating terms (e.g. "farmhouse", "cottage", "rattan") score 3x vs generic style terms ("wood", "brown") when ranking candidates. Without this, generic terms dominate the shortlist and every aesthetic converges to the same bland products.

**Safe-center ranking** (selection service): Rank 1-2 for each slot MUST be safe aesthetic-appropriate defaults — these go in unchecked during auto-generate. Rank 3+ can explore the broader palette. This is enforced per-aesthetic via furniture palettes and soft-goods color profiles.

**Furniture palettes** (`selection_service.py:_FURNITURE_PALETTES`): Per-aesthetic material/color anchors injected into selection prompts so all furniture in a room draws from the same palette. Dark academia = dark leather + walnut + brass across sofa, armchair, tables. Without this, the LLM picks individually coherent but room-incoherent furniture.

**Contamination filtering** (`amazon_adapter.py:_SLOT_EXCLUDE_PHRASES`): Per-slot exclusion lists block recliners from sofa results, pillow covers from throw pillows, empty pots from plants, outdoor furniture, loveseat combos, bulk pot packs, and cheugy products. Each filter exists because real Amazon catalog data surfaced these as the top-ranked results without it.

## Context Files (Configuration as Code)

These files in `context/` drive the pipeline — they are not prompts:

- `slot_taxonomy.yaml` — slots, budget weights, required specs, room presets
- `style_profiles.yaml` — named style profiles the LLM maps to
- `category_spec_rules.yaml` — per-slot required specs (bed_size, screen_size, dimensions)
- `sourcing_policies.yaml` — adapter selection and fallback rules
- `freshness_policies.yaml` — `price_freshness_hours: 24`, `refresh_cron: "0 */6 * * *"`, `stale_design_warn_hours: 168`

## Data Moat: Click Events

Click and impression logging is non-negotiable from day one. Every event is recorded with `run_id`, `slot_id`, `product_id`, `style`, `budget`, and `source`. This stream becomes the training data and operator analytics moat.

## Testing Strategy

Tests gate each implementation phase:
- Validators are tested in pure isolation (no LLM calls, no DB)
- Snapshot tests verify immutability and idempotency
- Refresh worker tests verify lock discipline (no double-run)
- Integration tests call the full pipeline with fixture products
- Evals (`evals/`) use `composition_eval_set.csv` against a coherence rubric

No live affiliate calls in tests. Use fixtures in `data/fixtures/`.

## Current Status

**Phase 5 complete — bedroom + living room production-ready.**
- 319 tests passing (validators, composition, selection, sourcing, snapshots, refresh, API)
- 13 aesthetic profiles with sourcing_terms + priority_terms, furniture palettes, soft-goods color profiles
- Living room: full slot taxonomy (sofa, coffee_table, side_table, tv_stand, tv, tv_mount, armchair, bookshelf, rug, floor_lamp, curtains, throw_pillows, throw_blanket, wall_art, plants, ceiling_light, sconce)
- Deep contamination filtering across all slots
- Safe-center auto-generate defaults (rank 1-2 anchors)
- Amazon catalog: 15,122+ products across 30 slots

**Now entering launch-readiness track:** Phase 6 (auth + RLS + rate limiting) → Phase 7 (Stripe + render storage + compliance) → Phase 8 (deploy). Auth + rate limiting is the hard pre-deploy gate — $0.37/room is uncapped to the internet without it.

## Working in This Repo

- Use **Plan mode** before touching the pipeline architecture, schemas, or validator logic.
- **Stop and confirm** before editing anything that touches: budget rules, link validation, affiliate tagging, snapshot write path, or the refresh worker lock.
- Implement and test one phase at a time per the build packet. Don't start a new phase until tests for the current one are green.
- The `prompts/` directory holds LLM templates. Keep business rules out of them.
- The `prompts/coding_agent/` directory holds saved Claude Code prompts (Appendix D of the build packet) — check there before writing a new prompt from scratch.

# Product Overview

## One paragraph

RoomKit is a whole-room AI design and commerce engine. It takes a room (photo or
dimensions) plus a short style and budget Q&A, plans a coherent composition of
product slots, selects real buyable products per slot within the stated budget,
snapshots those selections, validates everything deterministically, renders a styled
room image, and presents a budgeted shoppable board — each product with a live,
affiliate-tagged buy link and a running total that never exceeds the user's budget.

## The core product is the cart, not the picture

The render is a hook. The shoppable, on-budget board is the product. Revenue comes
from affiliate referral (v1) and evolves to subscription + sourcing spread as the
product shifts to operators.

## Pipeline stages

1. Intake — photo/dims + Q&A → RoomRequest
2. Style interpretation — RoomRequest → StyleProfile (LLM)
3. Composition — StyleProfile + budget → SlotPlan (LLM proposes; code enforces)
4. Sourcing — candidates per slot from adapter (Amazon v1)
5. Selection — one product per slot chosen (LLM, constrained)
6. Snapshot — products/prices frozen at generation time
7. Validation — budget, specs, freshness, link, affiliate tag (all deterministic)
8. Render — styled room image (presentation only)
9. Assembly — deterministic final board
10. Click logging — every impression and click recorded (the data moat)

## v1 scope

In scope: bedroom and living room; Amazon-sourced products; 5 named style profiles;
photo or text dimensions input; affiliate revenue.

Out of scope: PA-API, Temu sourcing, operator accounts, billing, 3D spatial layout,
vector search, multi-room designs.

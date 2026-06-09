# System Map

## Input → Processing → Output → State

### Input
- Room photo or dimensions (text: "12×14 bedroom")
- Style/budget Q&A answers
- Slot taxonomy (context/slot_taxonomy.yaml)
- Category spec rules (context/category_spec_rules.yaml)
- Freshness policies (context/freshness_policies.yaml)
- Affiliate tag (env: AMAZON_AFFILIATE_TAG)

### Processing pipeline

```
[Intake Service]        photo/dims + Q&A → RoomRequest
        ↓
[Style Service]         RoomRequest → StyleProfile  (LLM: interpret_style.md)
        ↓
[Composition Service]   StyleProfile + budget → SlotPlan
                        LLM proposes weights (plan_composition.md)
                        Code clamps: Σ ≤ target_budget, required slots present
        ↓
[Sourcing Adapter]      SlotPlan → Candidates per slot
                        Amazon v1: curated list + SiteStripe links
        ↓
[Selection Service]     Candidates → Chosen product per slot  (LLM: select_products.md)
                        Null + reason if no spec match or no candidates
        ↓
[Snapshot Service]      Chosen products → ProductSnapshot (freeze price/url/specs/timestamp)
        ↓
[Validators]            DETERMINISTIC — runs on snapshot:
                        budget_rules: total ≤ target_budget
                        spec_rules: required specs present per slot
                        price_link_rules: freshness, link live, affiliate tag
                        composition_rules: required slots filled, no duplicates
        ↓
[Render Service]        StyleProfile + SlotPlan → room image URL  (async worker)
                        Presentation only — never a source of product/price truth
        ↓
[Assembly Service]      Snapshots + render URL → Design (deterministic final board)
        ↓
[Click Logger]          Design displayed → impression event logged
                        User clicks buy → click event logged
```

### Output
- A Design: run_id, per-slot ProductSnapshots (price, buy_url, specs), render_url,
  total_price, target_budget, created_at
- A room render image (presentation layer)
- A shareable board card

### State (Supabase Postgres)

| Table | Contents |
|---|---|
| `runs` | run_id, status, created_at, room_request_id |
| `designs` | run_id, style_profile, slot_plan, render_url, total_price, created_at |
| `product_snapshots` | snapshot_id, run_id, slot_id, product_id, price, buy_url, specs, snapshotted_at, link_status |
| `click_events` | event_id, type, run_id, slot_id, product_id, style, budget, source, occurred_at |
| `user_inputs` | run_id, room_type, dimensions, photo_url, budget, style_description, qa_answers |

## Deterministic vs. LLM split

| Responsibility | Owner |
|---|---|
| Style interpretation | LLM (interpret_style.md) |
| Slot weight proposals | LLM (plan_composition.md) |
| Product selection per slot | LLM (select_products.md) |
| Budget total ≤ target | Code only (validators/budget_rules.py) |
| Slot weight clamping | Code only (composition_service.py) |
| Spec requirements per slot | Code only (validators/spec_rules.py) |
| Price freshness | Code only (validators/price_link_rules.py) |
| Link liveness | Code only (validators/price_link_rules.py) |
| Affiliate tag presence | Code only (validators/price_link_rules.py) |
| Snapshot immutability | Code only (snapshot_service.py) |
| Final board assembly | Code only (assembly_service.py) |
| Render image | Image model (render_service.py, presentation only) |

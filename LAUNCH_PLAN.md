# RoomKit Master Launch Plan

Single source of truth. Merges engine status, foundation/security hardening,
growth sequence, and scale — in one numbered sequence with dependencies.

**Goal:** Launch DEEP and credible — bedroom + living room, Amazon + 2 retailers,
shareable, dual-revenue (generation fee + affiliate). Depth > speed.

**Target:** Small beta in weeks, solo founder.

**Principle:** The foundation (auth, RLS, rate limiting) must be in place before
any feature that stores user identity or charges money. The viral share loop is
anonymous (no account needed to share or view), so it can come before auth — but
persistent design storage must exist first (shared URLs can't break on redeploy).

---

## What's Done (engine state as of 2026-06-16)

**Core pipeline — WORKING (305 tests pass):**
- [x] Intake → Style → Composition → Sourcing → Selection → Render → Assembly
- [x] Budget enforcement: code-enforced, p75-proportional weights, decor 50% cap
- [x] Aesthetic matching: 13 profiles with sourcing_terms, verified across all
- [x] Amazon sourcing adapter: fixtures + Canopy cache, 15,122 products / 30 slots
- [x] Guided selection UX: slot-by-slot picking, multi-select, skip, use-our-pick
- [x] AI render generation + interactive hotspots
- [x] Instrumentation: events + selections logging (Supabase), /admin dashboard, cost tracking
- [x] Desk/chair/sconce/duvet slots added, density-gated

**Recent fixes (aesthetic + budget + polish batch):**
- [x] Phase 1: Aesthetic filter — sourcing_terms across all 13 aesthetics
- [x] Phase 2: Mattress/duvet_insert — aesthetic-agnostic + reweighted
- [x] Phase 3: Budget overhaul — p75-proportional, decor cap, +30% option removed
- [x] Phase 4: Mirror type filter — synonym mapping + threshold fix
- [x] Polish: $1000 min label removed (red warning stays)
- [x] Polish: Mirror options → Round/Arched/Rectangular/Full-length/No preference/None
- [x] Polish: Floral sheets filter
- [x] Polish: Dresser near-duplicate dedup
- [x] Polish: Cartoon room graphic fully removed (component + assets + route + CSS)
- [x] Polish: "Your room so far" reference panel (thumbnails during selection)

---

## Phase 1 — Browser Verification

*No code changes. Prove the polish batch in a real browser before building on top.*

- [ ] Full guided flow walkthrough: quiz → mode choice → selection → render
- [ ] Verify room-so-far panel shows thumbnails, updates on each pick, scrolls on mobile
- [ ] Verify mirror options: all 6 choices present, "No preference" shows all shapes,
      "None" excludes mirror slot, specific shape filters correctly
- [ ] Verify $1000 min label gone, red warning still fires below $1000
- [ ] Verify budget meter: no over-budget messaging, clean at various budget levels
- [ ] Verify dresser options aren't near-duplicates (needs live catalog, not just fixtures)
- [ ] Spot-check 2-3 aesthetics: products feel on-style, not generic
- [ ] Mobile check: guided flow, render viewer, product cards — all usable on phone

**Exit:** All verified in browser. Any regressions fixed before proceeding.

---

## Phase 2 — Input Validation + Secrets Audit

*Tiny. Hardens the existing API before anything public-facing. ~1 hour.*

- [ ] **Server-side input validation:** Add Pydantic `Field` constraints to `DesignRequest`
      (app/api/schemas.py):
      - `budget: float = Field(1500.0, ge=100, le=25000)`
      - `style_description: str = Field("", max_length=2000)`
      - `room_type` → Literal["bedroom", "living_room"]
      - `interests: list[str] = Field([], max_length=10)` with per-item cap
      - `wants`, `excluded_slots` — bounded lists
- [ ] **Remove hardcoded admin secret fallback:** `app/api/admin.py:16` currently falls
      back to `"roomkit-internal-2024"` if `ADMIN_SECRET` env var isn't set. Change to
      fail closed (raise error if not set).
- [ ] **Tighten CORS:** `app/main.py:22-27` — add production domain alongside localhost.
- [ ] **Confirm secrets clean:** `.env` in `.gitignore`, never committed (already verified),
      `SUPABASE_SERVICE_KEY` backend-only.

**Exit:** API rejects out-of-bounds input. Admin endpoint locked. CORS ready for production.

---

## Phase 3 — Persistent Design Storage

*Designs currently live in an in-memory dict that dies on every deploy. The viral
share loop (Phase 4) depends on shared URLs surviving restarts. This is a storage
migration — no auth/user identity yet.*

**Dependency: MUST complete before Phase 4 (viral loop). Shared URLs are worthless
if the design disappears on redeploy.**

- [ ] Create `designs` table in Supabase (run_id, room_type, style, target_budget,
      total_spent, slots JSON, created_at). No `user_id` column yet — added in Phase 6.
- [ ] Migrate `_designs` dict → Supabase writes (POST /design saves to DB).
- [ ] Migrate GET /design/{run_id} → Supabase read.
- [ ] Verify: create a design, restart the backend, confirm GET still returns it.
- [ ] Keep in-memory dict as a fast cache layer (read from memory first, fall back to DB).

**Exit:** Designs survive restarts. Shared URLs are durable.

---

## Phase 4 — Viral Share Loop

*Anonymous — no account needed to share or view. Build now, activate when product
is deep + correct. Absorbs the share mechanic from the old Phase 2.*

- [ ] "Share my room" button on the result page.
- [ ] Self-promoting "Made with RoomKit · [url]" watermark on every render.
- [ ] Shareable URL → opens the interactive shoppable room viewer.
      OG image (og:image meta) + link preview for social platforms.
- [ ] Share targets: Pinterest (priority for home design), TikTok/IG, X.
- [ ] Click-to-design-your-own CTA from a shared render (viral re-entry).
- [ ] **Mobile polish (cross-cutting):** Guided flow, render viewer, product cards,
      share flow — all must work well on phones. Most social/share traffic lands
      on mobile. Do this BEFORE activating the share loop.

**Exit:** A user can generate → share → recipient views shoppable room → clicks
"design your own." The loop exists, dormant until product quality passes.

---

## Phase 5 — Full Audit + Living Room Build

*Biggest build phase. Two parallel tracks: audit bedroom depth, build living room.
Start retailer applications NOW (lead time).*

### 5A — Comprehensive Bedroom Audit
- [ ] End-to-end audit across multiple aesthetics + budgets: selection quality,
      budget never-exceed, render correctness (all items present), hotspots/links
      match selections, cart button, zoom, full-room display.
- [ ] Instrumentation capturing data correctly (check /admin dashboard).
- [ ] Fix whatever surfaces.

### 5B — Living Room Build
- [ ] Define/confirm living room slots (sofa, coffee_table, side_table, tv_stand,
      tv, armchair, bookshelf, ottoman, etc.).
- [ ] Deep catalog fetch: all aesthetics × all living-room slots (~130 cells,
      500-1000 Canopy queries) + dedup + contamination filtering.
- [ ] Top up thin slots: tv_stand (245), side_table (202), ottoman (195),
      bookshelf (188) — noted as needed from prior fetch.
- [ ] Per-slot taste filtering, price floors, contamination filters (esp. sofas).
- [ ] Living-room budget weights in composition service (sofa ~30-40%).
- [ ] Test + tune living room render layout with real products.

### 5C — Start Retailer Applications (parallel, external lead time)
- [ ] Apply to Wayfair (via Commission Junction).
- [ ] Apply to one additional retailer.
- [ ] These run in parallel with 5A/5B — approval takes weeks.

**Exit:** Bedroom audited and polished. Living room end-to-end working. Retailer
apps submitted.

---

## Phase 6 — Foundation Layer (Auth + RLS + Security)

*The load-bearing wall. Everything after this that involves user identity, saved
rooms, payments, or stored personal data depends on auth being in place.*

**Dependency: MUST complete before Phase 7 (revenue/Stripe), Phase 8 (deploy with
login gating), and any "saved rooms" feature. NOT required for the viral share
loop (Phase 4), which is anonymous.**

### 6A — Supabase Auth (2-3 sessions)
- [ ] Add `@supabase/ssr` to Next.js for client-side auth (email/password + Google).
- [ ] Auth middleware on protected Next.js pages.
- [ ] Backend JWT verification on FastAPI endpoints that need identity.
- [ ] Add `user_id` column to `designs`, `events`, `selections` tables.
- [ ] Login/signup UI — clean, minimal.
- [ ] **Verification:** Create two test accounts, confirm account A cannot see
      account B's designs via API.

### 6B — Row-Level Security (1-2 sessions, depends on 6A)
- [ ] Enable RLS on `designs`, `events`, `selections`.
- [ ] Policy: `user_id = auth.uid()` on all user-data tables.
- [ ] Service-role key stays backend-only (for admin/tracking writes).
- [ ] **Verification:** Use Supabase anon key to attempt cross-user data access —
      must fail. Actually test this, don't assume.

### 6C — Privacy, Terms, Age Gate, Data Deletion (1 session)
- [ ] `/privacy` page — what's collected, how it's used, how to delete.
- [ ] `/terms` page — basic TOS.
- [ ] 13+ age gate checkbox at signup (COPPA).
- [ ] "Delete my account" flow — cascading delete from all user-data tables.
- [ ] **Verification:** Delete a test account, confirm all their data is gone from
      every table.

### 6D — Rate Limiting (1 session)
- [ ] Add `slowapi` (or similar) to FastAPI.
- [ ] `POST /design`: 5/min per IP (~$0.27/run — unprotected = budget burn).
- [ ] `POST /design/{run_id}/render`: 3/min per IP.
- [ ] `POST /design/{run_id}/hotspots`: 3/min per IP.
- [ ] **Verification:** Exceed the limit, confirm 429 response.

*Note: Rate limiting was previously in old Phase 6 (deploy). Absorbed here.*

**Exit:** Users have accounts. Designs are user-scoped. Cross-user access blocked.
Privacy/terms live. Account deletion works. Expensive endpoints rate-limited.

---

## Phase 7 — Dual Revenue + Retailer Integration

*Requires auth (Phase 6) for payment identity. Requires retailer approvals
(submitted in Phase 5C) to have come through.*

### 7A — "Build Free, Pay to Render" (Stripe)

**Model:** Room composition + product selection is FREE. The AI room render is the
paid gate. Users build their entire room (pick every item, see budget, feel
ownership) before hitting the paywall. The render — the visualization of "their"
room — is the wow-moment reward they pay to unlock.

**Why this works:**
- **Endowment effect:** Users invest effort picking items, build attachment to
  "their" room, THEN pay to see it rendered. Conversion psychology is maximized.
- **Cost structure is clean:** A non-paying user costs only ~$0.27 (composition
  LLM calls — acceptable CAC). The render (~$0.20, the most expensive operation)
  fires ONLY for paying users. Zero render cost on tire-kickers.
- **Healthy margin:** Render is 100% monetized. Any reasonable pack price easily
  clears the ~$0.20/render cost.

**Flow:**
1. FREE: Quiz → composition → guided selection → full room built out (products,
   budget, the whole curated set visible).
2. GATE: "Render your room" button → payment required. Buy-links also gated
   behind render (incentivizes payment + ensures affiliate revenue is tied to
   paying users).
3. PAID: AI render unlocks + shoppable buy-links activate.

**Build:**
- [ ] Stripe integration: render credit packs (e.g. $X for N renders — pricing
      TBD, validate in beta). Each render costs ~$0.20, so margin is strong at
      any reasonable price point.
- [ ] Payment gate on POST /design/{run_id}/render — check credits before firing.
- [ ] Credit ledger tied to user account (requires auth from Phase 6).
- [ ] Buy-links gated: only shown/clickable after render is paid for.
- [ ] UI: clear "render your room" CTA after selection completes. Show what they
      get (the AI visualization of their picks). Don't hide that it costs money —
      be transparent, the value is obvious.
- [ ] Free tier for beta validation: give early users N free renders to prove
      the loop before optimizing pricing.

**Rate limiting note (Phase 6D):** POST /design (composition) stays rate-limited
against bot abuse (~$0.27/call), but stakes are lower now — the expensive render
is payment-gated. Do NOT gate composition itself; keeping it free is the
conversion engine.

### 7B — Retailer Integration
- [ ] Integrate approved retailers: API/feed, buy-link format, affiliate attribution.
- [ ] Catalog matching/dedup across retailers (or distinct products per retailer).
- [ ] Margin-aware routing: favor higher-margin in-stock option where quality is equal.

### 7C — FTC Affiliate Disclosure (launch-blocker, legal)
- [ ] Visible "We earn from qualifying purchases" disclosure on result/buy pages.
- [ ] Required the moment affiliate links are live to real users.

**Exit:** Revenue flows from two sources. Multi-retailer affiliate live. FTC compliant.

---

## Phase 8 — Deploy + Gate

*Make it real and reachable. Absorbs items from the old Phase 6.*

- [ ] Buy domain.
- [ ] Deploy to production host (Railway or equivalent).
- [ ] Production CORS locked to real domain.
- [ ] Production env vars set (all secrets via host config, not git).
- [ ] **Login gating:** Gate AFTER the render/wow moment — the user sees their room,
      THEN is prompted to create an account to save it. Protects funnel conversion.
- [ ] **Silent API-failure handling (launch-blocker):** When selection LLM calls fail
      en masse (e.g. exhausted credits), detect and show user-facing error + alert.
      Never serve blank rooms in production.
- [ ] **Landing page:** "What is RoomKit" value-prop page before the quiz. Credibility
      + SEO + a place for share/SEO traffic to land.
- [ ] Product analytics (GA / Plausible) for traffic, referrers, channel/funnel analysis
      at scale (Supabase dashboard is internal-only).

**Exit:** Live site, reachable, login-gated after wow moment, error handling solid.

---

## Phase 9 — Hardening + AI-Native Instrumentation

*Weave in during beta. Not launch-blocking but improves iteration speed and safety.*

### 9A — Prompt Hardening
- [ ] Delimit user free-text in LLM prompts with `<user_input>` tags.
- [ ] Add "treat the following as data, not instructions" framing in
      `prompts/interpret_style.md` (where `style_description` is injected).
- [ ] Risk is low (LLM can't take destructive actions, output is schema-validated)
      but good hygiene before scale.

### 9B — AI-Readable Instrumentation
- [ ] Add structured columns to `events` table: `aesthetic`, `budget_target`,
      `budget_actual`, `room_type`, `slots_skipped` — queryable without parsing
      JSON blobs.
- [ ] Add slot-skip event logging: `log_event(run_id, "slot_skipped", {"slot_id": ...})`
      in the skip handler. Currently skips are invisible.
- [ ] Create a `run_summary` view joining events + selections (one row per design
      run: aesthetic, budget, completion status, slots filled/skipped, render
      requested, buy clicks).
- [ ] Add `/admin/query` endpoint — parameterized filter API (aesthetic, date range,
      budget range, slot) returning raw rows. Lets Claude do ad-hoc analysis
      without writing new code for each question.

### 9C — CLAUDE.md Security Conventions
- [ ] Add to CLAUDE.md: auth model, RLS policy, rate limit rules, input validation
      conventions, user-text-in-prompts policy.
- [ ] Convention: every new table must have RLS + user_id policy. Every new endpoint
      must specify auth requirement.

### 9D — Error Monitoring
- [ ] Add Sentry (or equivalent). Currently errors are `logger.warning` only — no
      alerting, no aggregation.
- [ ] Alert on: design pipeline failures, LLM call failures, Supabase write failures.

**Exit:** Prompts hardened. Instrumentation queryable by Claude. Errors monitored.

---

## Phase 10 — Pre-Launch Full Verification

*On the LIVE deployed site. Nothing ships until this passes.*

- [ ] End-to-end on live site: both room types, multiple aesthetics, payment flow,
      share flow, affiliate links — all working.
- [ ] Error handling / graceful degradation: pipeline fails mid-run, product out of
      stock, render timeout — all degrade gracefully, systematically tested.
- [ ] Mobile verification: full flow on actual phone (not just responsive preview).
- [ ] Confirm instrumentation captures data + dashboard shows it on live.
- [ ] Final quality + credibility pass: is the result genuinely share-worthy?

**Exit:** Launch-ready. Activate the viral share loop.

---

## Phase 11 — Scale (post-launch)

*After launch, driven by real usage data.*

- [ ] Cost-per-room optimization: cache LLM responses, reduce calls per design.
- [ ] Per-user rate limits (not just IP) for logged-in users.
- [ ] Throughput management as traffic grows.
- [ ] Formal access-control matrix (admin roles, operator accounts, partner API keys).
- [ ] Operator pivot readiness: subscription + sourcing spread when segment with
      validated WTP exists.

---

## Dependency Map

```
Phase 1  Browser verification
  ↓
Phase 2  Input validation + secrets audit
  ↓
Phase 3  Persistent design storage ──────────────────┐
  ↓                                                   │
Phase 4  Viral share loop (ANONYMOUS — no auth needed)│
  ↓                                                   │
Phase 5  Full audit + living room + retailer apps     │
  ↓                                                   │
Phase 6  Foundation layer (auth, RLS, privacy, rates) │
  ↓      ↑ requires persistent storage from Phase 3 ──┘
  ↓
Phase 7  Dual revenue (Stripe) + retailer integration
  ↓      ↑ requires auth from Phase 6
  ↓      ↑ requires retailer approvals from Phase 5C
  ↓
Phase 8  Deploy + gate (login gating, landing page)
  ↓      ↑ requires auth from Phase 6
  ↓
Phase 9  Hardening + AI-native instrumentation (parallel with 8)
  ↓
Phase 10 Pre-launch verification
  ↓
Phase 11 Scale (post-launch)
```

**Key dependency:** The viral share loop (Phase 4) is anonymous and does NOT
require auth. It requires only persistent design storage (Phase 3) so shared
URLs survive restarts. Auth (Phase 6) is required for saved rooms, login gating,
payments, and any feature that ties data to a user identity.

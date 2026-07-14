# RoomKit Master Launch Plan

Single source of truth. Merges engine status, foundation/security hardening,
growth sequence, and scale — in one numbered sequence with dependencies.

**Goal:** Launch DEEP and credible — bedroom + living room, Amazon-only,
shareable, affiliate-first revenue with room-pack upsell. Depth > speed.

**Target:** Small beta in weeks, solo founder.

**Retailer strategy:** Amazon Associates at launch — single adapter, proven
attribution, immediate revenue. Multi-retailer expansion (Wayfair, Target, etc.)
moves to post-launch via affiliate aggregator (Skimlinks or Sovrn Commerce).
Aggregators accept newer sites with less traffic history than direct programs
like CJ/Wayfair. Do NOT assume non-Amazon retailers will out-earn Amazon despite
higher per-item rates — volume and conversion matter more than commission %.

**Principle:** The foundation (auth, RLS, rate limiting) must be in place before
any public deploy. The viral share loop is built auth-ready (clean seams for
Phase 6 insertion) but structurally unenforceable until accounts exist.

---

## Phase Index

*Updated 2026-07-13 — Phase 8 near-complete (quiz reskin, free tier messaging, login redirect done).*

| Phase | Description | Status |
|---|---|---|
| 1 | Browser verification | Folded into 11A |
| 2 | Input validation + secrets audit | ✅ Done |
| 3 | Persistent design storage | ✅ Done |
| 4 | Viral share loop + add-all-to-cart | ✅ MOSTLY DONE (share button, OG tags, watermark, navigator.share built; share PAGE stub, affiliate tag smoke-test remain) |
| 4B | Platform-adaptive visual layer | TODO (decision log complete, no code) |
| 5A | Comprehensive bedroom audit | ✅ Done |
| 5B | Living room build | ✅ Done |
| 5C | Maintainability gate (magic-number docs + regression tests) | ✅ Done (CLAUDE.md docs, 27 adapter filter tests, 10 TV reweight tests, priority-term tests) |
| 5D | Staging environment (Railway + Supabase staging) | ✅ Done |
| 6A | Supabase Auth (backend) | ✅ Done |
| 6A | Supabase Auth (frontend — Next.js UI) | ✅ Done (login, signup, Google OAuth CODE, auth middleware, AuthProvider, auth callback; Google OAuth needs Supabase dashboard enable + GCP credentials — YOU step) |
| 6B | Row-Level Security | ✅ Done (staging verified, public schema at Phase 9) |
| 6C | Privacy, terms, age gate, deletion | ✅ Done (privacy page, terms page, 13+ age gate on signup, account page with delete, backend cascade verified 20/20; PLACEHOLDERs remain for entity name/email) |
| 6D | Rate limiting | ✅ Done |
| 6E | Tier enforcement | ✅ Done — atomic free-room claim (advisory lock RPC), pack ledger (decrement/re-credit), watermark toggle, TOCTOU proven on real Postgres (5 concurrent → 1 claim), 526 tests |
| 6F | Scaling architecture (workers, async, concurrency) | ✅ Done — verified on staging (Redis shared state, async render, LLM semaphore cap=30, render semaphore cap=4, LLM resilience, pipeline timing, multi-worker, deleted-user blocklist 20/20) |
| 7 | Revenue activation (Stripe, render storage, compliance) | 7A ✅ Stripe. 7B ✅ render storage. 7C ✅ FTC/disclosure (beta). **7D PA-API migration = pre-full-launch blocker** |
| 8 | Frontend build-out (nav, account, My Designs, landing, robustness) | NEAR-COMPLETE — shell, nav, footer, landing, My Designs, admin auth, quiz reskin, free tier messaging, login redirect all done. Remaining: 404/error pages, mobile responsiveness, accessibility, loading/error states |
| 9 | Deploy + gate | TODO |
| 10 | Hardening + AI-native instrumentation | TODO — Fast-follow |
| 11A | Pre-launch full verification (absorbs Phase 1) | TODO — **Pre-launch gate** |
| 11B | Gated beta (50-100 invite-only users) | TODO — **Pre-launch gate** |
| 12 | Multi-retailer expansion + scale | TODO — Post-launch |

---

## Revenue Model — The Core Inversion

**Affiliate is the profit engine, not fees.** The result page shows the AI render
with all products below it (correct images + prices) and an "ADD ALL TO CART"
button that adds every product to the user's Amazon cart in one action. A
converted ~$1,300 room at 3% (Amazon) drives far more revenue than any
render/pack fee.

**Fees exist to cover cost + qualify intent, NOT to be the profit center.**
Every gating decision must minimize friction on the affiliate funnel. When
fee-protection and affiliate-funnel-flow conflict, affiliate wins.

**Cost structure (per from-scratch room):**

| Component | Cost | Notes |
|---|---|---|
| Composition (LLM) | ~$0.20–0.27 | Sunk cost every user incurs; $0.27 worst case (full 21-slot room) |
| Free render (medium) | $0.10 | gpt-image-1, quality="medium" |
| Paid render (high) | $0.30 | gpt-image-1, quality="high" |
| **Free-tier all-in** | **~$0.37** | Composition + free render. The "37c law" — free-tier ceiling. |
| **Paid-tier all-in** | **~$0.57** | Composition + paid render. First render for a paid room. |
| **Paid re-render** | **$0.30** | Marginal cost per re-roll (composition already sunk). |

Beta pricing note: room pack unit price must comfortably clear the $0.57
paid all-in. Trivially true given affiliate is the primary engine, but the
number must be on record so pack pricing isn't set against the wrong cost.

### Tier Structure

**Accounts are REQUIRED to access the product.** (Enforcement: Phase 6.)

| | Free | Paid (room packs) |
|---|---|---|
| Rooms | 1 per account (bedroom) | N rooms (pack size TBD) |
| Render | Full, WATERMARKED (subtle corner mark) | Full, NO watermark |
| Resolution | Standard (must still look great as OG/social preview) | High |
| Room types | Bedroom only | + living room, bathroom, etc. (beta access) |
| Re-renders | Unlimited | Unlimited |
| Buy links | Full | Full |
| Expiry | N/A | Non-expiring packs |

**Pack unit = ROOMS, not render-credits.** Each room = unlimited re-renders
(uncapped re-rolling surfaces more products = more affiliate clicks; never meter
renders).

**Paid upgrade stacks three kinds of value:** vanity (no watermark), utility
(hi-res), and access/scarcity (new room types). Room-type gating is the
strongest lever — self-enforcing regardless of abuse vectors.

**NO consumer subscription.** Low-frequency episodic tool (people furnish one
room in a burst, not monthly). A monthly allowance would churn out of resentment
AND cap the affiliate funnel. DEFERRED: "pro" lane for realtors/STR
hosts/designers who furnish repeatedly — do not build or architect now.

---

## What's Done (engine state as of 2026-06-28)

**Core pipeline — WORKING (515 tests pass):**
- [x] Intake → Style → Composition → Sourcing → Selection → Render → Assembly
- [x] Budget enforcement: code-enforced, p75-proportional weights, decor 50% cap
- [x] Aesthetic matching: 13 profiles with sourcing_terms, verified across all
- [x] Amazon sourcing adapter: fixtures + Canopy cache, 15,122 products / 30 slots
- [x] Guided selection UX: slot-by-slot picking, multi-select, skip, use-our-pick
- [x] AI render generation + interactive hotspots
- [x] Instrumentation: events + selections logging (Supabase), /admin dashboard, cost tracking
- [x] Desk/chair/sconce/duvet slots added, density-gated
- [x] Phase 2: Input validation + secrets audit (Pydantic constraints, fail-closed admin, CORS env var)
- [x] Phase 3: Persistent design storage (Supabase, write-through cache, RLS default-deny, lossless round-trip verified)

**Foundation layer — WORKING (Phases 6A-6F):**
- [x] Supabase Auth: backend JWT (ES256/JWKS) + frontend (login, signup, Google OAuth code, auth middleware, AuthProvider)
- [x] RLS: user-scoped policies on designs, events, selections (staging verified)
- [x] Privacy/terms pages, 13+ age gate, account deletion with cascade (20/20 verified)
- [x] Rate limiting: Redis-backed slowapi with in-memory fallback
- [x] Scaling: multi-worker uvicorn, async render (202+poll), LLM semaphore (cap=30),
      render semaphore (cap=4, graceful queueing), LLM retry/backoff, shared clients,
      deleted-user blocklist → Redis, pipeline timing decomposition. Load-tested on staging.

**Share/viral loop — MOSTLY BUILT (Phase 4):**
- [x] ShareButton: Pinterest, X, copy link, save image, navigator.share (mobile native)
- [x] OG meta tags: dynamic generateMetadata with render HEAD-check
- [x] Watermark: "Made with RoomKit" via _apply_watermark() in render_service.py

**Recent fixes (aesthetic + budget + polish batch):**
- [x] Aesthetic filter — sourcing_terms across all 13 aesthetics
- [x] Mattress/duvet_insert — aesthetic-agnostic + reweighted
- [x] Budget overhaul — p75-proportional, decor cap, +30% option removed
- [x] Mirror type filter — synonym mapping + threshold fix
- [x] Polish: $1000 min label removed, floral sheets filter, dresser dedup
- [x] Polish: Cartoon room graphic removed, "Your room so far" panel
- [x] Per-aesthetic soft goods color profiles (inclusion-only)
- [x] Back button in guided selection, bedding exclusivity, empty pot filter

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

## Phase 2 — Input Validation + Secrets Audit ✓ DONE

- [x] Server-side input validation (Pydantic Field constraints on DesignRequest)
- [x] Remove hardcoded admin secret fallback (fail closed)
- [x] CORS origins driven by env var
- [x] Secrets clean (.env in .gitignore, service key backend-only)

---

## Phase 3 — Persistent Design Storage ✓ DONE

- [x] `designs` table in Supabase (nullable user_id for Phase 6, RLS default-deny)
- [x] Write-through cache: _designs dict + Supabase persistence
- [x] _get_design() helper: cache → Supabase → 404/503 three-outcome handling
- [x] Verified: lossless round-trip (field-by-field, 342 prices, model_dump equality)
- [x] Verified: restart-survival (fresh process loads from Supabase, identical)
- [x] Verified: RLS blocks anon role (default-deny confirmed)

---

## Phase 4 — Viral Share Loop + Add-All-to-Cart

*Build auth-ready, not auth-blind. The share mechanic + affiliate checkout flow.
Built and tested locally / private-beta. NOT publicly deployed until Phase 6
delivers auth + rate limiting (see Hard Gates below).*

**Sharing model:** Every free user gets a full watermarked render. The
watermarked render IS the share asset and OG image. There is no "unrendered
design" state — no grid/mood-board/preview pipeline needed.

- [x] **Watermark on renders:** `_apply_watermark()` in `render_service.py` — "Made with RoomKit"
      in corner, DM Sans Bold, white at 45% opacity + dark drop shadow.
      Free tier = watermarked, paid tier = clean (toggle via tier field, Phase 6E).
- [x] **"Share my room" button** on the result page (`ShareButton` component).
- [x] **OG meta tags:** Dynamic `generateMetadata()` in `result/[run_id]/layout.tsx` —
      HEAD-checks render existence, sets `og:image`, `og:title`, Twitter card.
      Phase 7 note: switch to `render_url` column when it exists (avoid HEAD probe).
- [x] **Share targets:** Pinterest (Pin It), X, copy link, save image — all built.
      Mobile uses `navigator.share()` (native share sheet). Desktop uses dropdown.
- [ ] **Click-to-design-your-own CTA** on the shared view (viral re-entry).
      Share page (`web/app/share/[run_id]/page.tsx`) is a STUB — needs ShareCard.
- [ ] **"ADD ALL TO CART" — verify existing + confirm affiliate tag carries.**
      Button already exists (`ExportToCartButton` in result page). Uses Amazon's
      `gp/aws/cart/add.html` with `tag=roomkitai-20`. MUST smoke-test: does the
      associate tag actually create an attribution session? Check Associates
      dashboard after clicking. If tag drops, try `AssociateTag` param instead.
      This is the revenue mechanic — verify before building anything on top.
- [ ] **Mobile polish:** Guided flow, render viewer, product cards, share flow —
      all verified on actual phone before activating.

**Auth-ready seams (built now, enforced in Phase 6):**
- Render watermark is driven by a `tier` field (hardcoded "free" now, checked
  against account tier in Phase 6).
- "One free room" limit: designs table already has nullable `user_id`. Phase 6
  populates it + adds a count check. The data model supports it today.
- Share visibility: all shares are public (no auth to view). This is deliberate
  and permanent — shared rooms are the viral surface.

**Exit:** Full loop working locally: generate → render (watermarked) → share →
recipient views shoppable room with OG preview → clicks "design your own."
Add-all-to-cart functional with affiliate tag.

---

## Phase 4B — Platform-Adaptive Visual Layer

*Scoped per the LIGHT model: ONE product, one backend, one source of truth.
Only the visual/presentation layer adapts. No forks, no divergent flows.*

### Decision Log

**1. Platform detection: client-tells-server (no user-agent sniffing)**

The render is generated via `POST /design/{run_id}/render`, triggered by the
user clicking "See your room" on the client. The client already knows its own
viewport. The cleanest path: the client sends the desired aspect (portrait vs
landscape) as a parameter on the render request. The server passes it through
to `render_room()` which maps it to the gpt-image-1 size string.

Why NOT user-agent sniffing: Next.js can read `User-Agent` in server
components / middleware, but the render is generated asynchronously from page
load (user-initiated button click → POST). By the time the render fires, we
have a client JS context that knows `window.innerWidth` precisely — more
reliable than parsing UA strings, which lie (tablets, desktop-mode mobile
browsers, bots). User-agent adds complexity with no benefit here.

What this enables: device-appropriate render dimensions, Pinterest-optimal
OG images, future flexibility (square for Instagram, etc.) — all from one
parameter on an existing endpoint.

What this does NOT cover: server-side `generateMetadata()` for OG tags runs
without a client viewport. OG image selection uses a stored preference or
default, not live device detection (see item 4 below).

**2. Device-appropriate render: landscape desktop, portrait mobile**

gpt-image-1 natively supports exactly three sizes:
- `1024x1024` (square)
- `1536x1024` (landscape, current default)
- `1024x1536` (portrait, 2:3 — Pinterest's preferred ratio)

Key finding: `1024x1536` is native 2:3, which is Pinterest's preferred
format. No cropping or post-processing needed — the API generates it directly
at zero additional cost ($0.10 either way at medium quality).

**DECISION: Client-chosen aspect, device-appropriate defaults.**
- Desktop (viewport ≥ 768px): landscape `1536x1024` — the room fills the
  wide screen naturally, hero asset for the buying decision surface.
- Mobile (viewport < 768px): portrait `1024x1536` — fills the phone,
  Pinterest-native 2:3.

Why NOT portrait-everywhere: the desktop result page is where the render's
job is to make the room feel real enough to buy. A room is spatial — wide
landscape shows it the way you perceive a room. Portrait-on-desktop shrinks
the hero into a narrow strip with dead margin, sacrificing the buying surface
to optimize the share path. The OG image and on-screen render are decoupled
(bots have no viewport), so there's no forced tradeoff.

Options evaluated for cropping/dual-render:

**(a) Crop landscape to portrait:** Cuts ~55% of the image — amputates
furniture. Not viable.

**(b) Two renders per room (both aspects):** Doubles cost from $0.10 to $0.20,
breaches the 37c free ceiling. Rejected.

**(c) Re-render on aspect switch:** User re-renders to switch aspect. Already
unlimited, one file per run_id (overwrite). Clean and free.

The one code touch needed: `InteractiveRoomRender.tsx` line 44 hardcodes
`(containerW * 1024) / 1536` for the image aspect ratio. This must read the
actual image dimensions (via `onLoad` → `naturalWidth/naturalHeight`) instead
of a hardcoded ratio. Works for both orientations automatically.

Cost impact: zero (same $0.10 per render, just a different size string).

**3. Mobile UX: elevate from "polish checkbox" to explicit Phase 4 step**

Current state: mobile is scoped as "verified on actual phone before
activating" — a verification checkbox, not a build task. But mobile is the
PRIMARY traffic surface. The current CSS has three breakpoints (768/640/420px)
covering basic layout collapse, but no mobile-specific interaction patterns.

What already works well:
- Render viewer: pinch-zoom implemented, `width: 100%` is fluid
- Product grid: collapses to 2-col at 640px, 1-col at 420px
- Guided flow: collapses to single column at 768px

What needs a real pass (visual-layer-only, not product forks):
- Touch targets: some interactive elements likely < 44px min touch target
- Share flow: mobile share should use `navigator.share()` (native share
  sheet) rather than a desktop-style share dropdown
- Product cards at phone width: price, name, image, buy link density
- Result page scroll: verify the product list below the render is
  usable on a 375px viewport without the render consuming all visible space
- Quiz/intake: verify input fields, sliders, buttons are thumb-friendly

**RECOMMENDATION:** Add an explicit "4C — Mobile Visual Pass" step in Phase 4,
between the share button build and the affiliate verification. Concrete scope:
touch targets, navigator.share(), product card density, result page scroll.
This is 1-2 sessions of CSS + one JS change (navigator.share), not a rewrite.

**4. OG image: serves whatever render exists, decoupled from viewing**

The OG image is fetched by bots (Googlebot, Pinterest crawler, Twitter card
fetcher). Bots have no viewport — they just GET the URL in the meta tag.
The OG image and the on-screen render are ALREADY DECOUPLED: the user sees
whatever aspect their device generated, the bot sees whatever URL is in the
meta tag. No forced tradeoff.

In practice, the majority of shares originate on mobile → portrait render →
portrait OG (Pinterest-optimal). Desktop sharers produce a landscape OG,
which is suboptimal for Pinterest but functional on all platforms.

**Desktop-sharer wrinkle:** A desktop user generates landscape for viewing,
then shares. Their on-disk render is landscape. What does the OG point to?

Options evaluated:
- **(a) Generate separate portrait for OG (double-cost):** Extra $0.10 only
  for desktop sharers. Requires second file (`{run_id}_og.jpg`), share
  button blocks 15-20s on render generation. Bad UX on the share action.
- **(b) Accept landscape OG for desktop sharers:** generateMetadata serves
  whatever render exists. Zero complexity. Landscape is suboptimal for
  Pinterest but not broken — Pinterest handles it, just letterboxed.
- **(c) Share action triggers background portrait re-render:** Fire-and-forget
  portrait generation on share click. Problem: Pinterest caches aggressively
  — the first pin sets the image permanently. Lazy generation doesn't help
  for the one channel where portrait matters most.

**DECISION: (b) — accept landscape OG for desktop sharers.**

Rationale: mobile is the primary share surface (share-driven, social lands
on mobile). The overwhelming majority of shares originate on mobile →
portrait OG automatically. Desktop sharers are a minority of a minority.
The complexity of (a) or (c) — second file variant, async generation,
blocking UX or Pinterest cache race — buys optimized unfurls for a small
slice of shares on the less-likely path. If Pinterest analytics later show
desktop-originated shares are significant, (a) can be added as a targeted
optimization: one new parameter on `render_room()`, one `_og.jpg` suffix,
generateMetadata prefers it if it exists. Clean incremental addition.

Edge case — user shares before rendering: share button is gated behind
`renderUrl` existence (decided in prior session). No render = no share.

### Build Items (not yet built — pending approval)

- [ ] **4B-1: Aspect parameter on render endpoint.** Add optional `aspect`
      field to `RenderRequest` (`"portrait"` | `"landscape"`, default
      `"landscape"` — preserves current behavior when no aspect sent).
      Map to gpt-image-1 size: portrait → `1024x1536`, landscape →
      `1536x1024`. Pass through to `render_room()`.
- [ ] **4B-2: Frontend aspect detection.** Client sends `aspect: "landscape"`
      when viewport width ≥ 768px, `"portrait"` otherwise. One conditional
      on the existing render-trigger callback.
- [ ] **4B-3: Fix hardcoded aspect ratio in InteractiveRoomRender.** Replace
      `(containerW * 1024) / 1536` with actual `naturalWidth/naturalHeight`
      from the loaded image. Works for both orientations automatically.
- [ ] **4B-4: Mobile visual pass.** Touch targets (44px min), `navigator.share()`
      on mobile, product card density at phone width, result page scroll
      behavior. CSS + one JS API. 1-2 sessions.
- [ ] **4B-5: OG image serves whatever render exists.** When `generateMetadata()`
      is built (Phase 4 OG meta tags item), it serves whatever render exists.
      Mobile-default means most OG images are portrait (Pinterest-optimal)
      automatically. Desktop-originated landscape OG is accepted — see
      decision 4 above.

### Resolved Questions

- **Default aspect per device:** Landscape on desktop (≥768px), portrait on
  mobile (<768px). Desktop preserves the buying surface; mobile fills the
  phone and is Pinterest-native.
- **Re-render aspect switch:** Overwrite. One file per run_id, re-renders
  are unlimited. User can re-render to switch aspect if desired.
- **Existing renders:** Stay as-is (1536x1024 landscape). No migration.
  New renders follow device-appropriate defaults. Phase 7C render storage
  migration is the natural point to regenerate old renders if needed.
- **Desktop-sharer OG:** Accept landscape OG (option b). Revisit with
  dedicated portrait OG file (option a) only if Pinterest analytics show
  desktop-originated shares are hurting conversion.

---

## Phase 5 — Full Audit + Living Room Build ✓ DONE

*Biggest build phase. Two parallel tracks: audit bedroom depth, build living room.*

### 5A — Comprehensive Bedroom Audit ✓
- [x] End-to-end audit across multiple aesthetics + budgets: selection quality,
      budget never-exceed, render correctness (all items present), hotspots/links
      match selections, cart button, zoom, full-room display.
- [x] Instrumentation capturing data correctly (check /admin dashboard).
- [x] Fix whatever surfaced.

### 5B — Living Room Build ✓
- [x] Define/confirm living room slots (sofa, coffee_table, side_table, tv_stand,
      tv, tv_mount, armchair, bookshelf, rug, floor_lamp, curtains, throw_pillows,
      throw_blanket, wall_art, plants, ceiling_light, sconce).
- [x] Deep catalog fetch: all aesthetics × all living-room slots + dedup +
      contamination filtering. 15,122+ products / 30 slots.
- [x] Per-slot contamination filters: recliners from sofa, pillow covers from
      throw pillows, empty pots from plants, outdoor furniture, loveseat combos,
      bulk pot packs, cheugy products, bathroom mirrors, floral sheets.
- [x] Living-room budget weights in composition service. TV-size dynamic
      entertainment reweight with 35% cap (45% with "Prioritize TV").
- [x] TV price floors from real catalog data ($90/$160/$300/$550 by size).
- [x] 3x priority-term weighting in sourcing adapter for aesthetic differentiation.
- [x] Furniture palettes with rank 1-2 anchors: safe-center auto-generate defaults
      that coordinate across slots per aesthetic. Rank 3+ explores broader palette.
- [x] Per-aesthetic soft goods color profiles (inclusion-only).
- [x] Test + tune living room render layout with real products.

**Exit:** Bedroom audited and polished. Living room end-to-end working.
319 tests passing.

---

## Phase 5C — Maintainability Gate

*Document the non-obvious magic numbers and add regression tests before the
codebase gets harder to reason about. This is cheap now and expensive later.*

### Intent comments on magic numbers
- [ ] `_ENT_MAX_SHARE = 0.35` — why 35%: the empirical breakpoint where remaining
      slots collapse below their cheapest viable products.
- [ ] `_ENT_MAX_SHARE_PRIORITY = 0.45` — why 45%: raised cap when user explicitly
      prioritizes TV; accepts thinner furniture to fund it.
- [ ] `_TV_PRICE_FLOORS` ($90/$160/$300/$550) — why these values: real catalog
      minimums per size bucket as of 2026-06. Below these, zero viable candidates.
- [ ] `_PRIORITY_WEIGHT = 3` — why 3x: without it, generic terms ("wood", "brown")
      dominate shortlists and all aesthetics converge. 3x was the minimum multiplier
      that reliably differentiated aesthetics in candidate ranking.
- [ ] Feasibility breakpoints in `fit_slots_to_budget()` — document the MVB
      (minimum viable budget) calculation and the optional-dropping waterfall.
- [ ] TV quiz thresholds — document which budget/screen-size combos trigger the
      feasibility warning and why those boundaries exist.

### Adapter filter regression tests
- [ ] Cheugy pattern exclusion: test that `_CHEUGY_RE` catches known bad products
      and does not false-positive on legitimate ones.
- [ ] Per-slot exclusion phrases: at least one positive + one negative test per
      slot in `_SLOT_EXCLUDE_PHRASES` (recliner blocked from sofa, pillow cover
      blocked from throw_pillows, outdoor blocked from rug, etc.).
- [ ] Priority-terms weighting: test that a product matching a priority term scores
      3x a generic match; verify shortlist ordering changes with/without priority.

### TV reweight unit tests
- [ ] Test `_apply_tv_size_reweight()` at each size bucket: verify entertainment
      share inflates correctly and caps at 35%/45%.
- [ ] Test that non-entertainment slots scale proportionally (not clipped).
- [ ] Edge case: budget so low that TV floor exceeds the cap — verify graceful
      degradation (capped, not crash).

**Exit:** Every magic number has a one-line "why" comment. Adapter filters and
TV reweight have regression tests. Future contributors can modify thresholds
without archaeology.

---

## Phase 5D — Staging Environment

*Verify the full pipeline on real infrastructure before building auth on top.
Catches CORS, connectivity, render storage, and env-var issues early.*

- [ ] Railway staging service (separate from production).
- [ ] Supabase staging project (separate database, separate auth).
- [ ] `.env.staging` with staging-specific values; document in `.env.example`.
- [ ] Deploy current main to staging. Verify:
  - [ ] CORS allows staging frontend origin.
  - [ ] Supabase connectivity (design save + load round-trip).
  - [ ] Render generation works (gpt-image-1 call from Railway worker).
  - [ ] Affiliate links carry `tag=roomkitai-20` through to Amazon.
- [ ] Staging stays alive through launch — used for pre-deploy smoke tests.

**Exit:** Full pipeline working on Railway + Supabase staging. No localhost
dependencies.

---

## Phase 6 — Foundation Layer (Auth + RLS + Security)

*The load-bearing wall. Everything public depends on this.*

**HARD PRE-DEPLOY GATE:** Account-gating + rate limiting must BOTH land before
ANY public deploy. Until Phase 6 completes, the $0.37/room cost is uncapped to
the entire internet with no free-room limit. Phase 4 can be built and tested
locally / private-beta, but NOTHING ships publicly until this phase delivers.
(See also: rate-limiting pre-deploy gate from Phase 3 security review.)

**Auth sequencing consequence:** Between Phase 4 and Phase 6, the tier/gating
model is structurally UNENFORCEABLE. No accounts = no "one free room" limit, no
pack gating, no access wall. The model is DESIGNED in Phase 4, ENFORCED in Phase 6.

### 6A — Supabase Auth (backend) ✅
- [x] Backend JWT verification on FastAPI endpoints that need identity.
      ES256 via JWKS (asymmetric). `app/auth.py`.
- [x] Read/write split: writes use service key (bypasses RLS, app sets user_id),
      reads use anon key + user JWT (RLS enforced via `auth.uid()`).
      `services/supabase_client.py:get_user_postgrest()`.
- [x] Populate `user_id` on `designs`, `events`, `selections` tables.
- [x] **Free-room enforcement:** Count designs where user_id = current user.
      If count >= 1 (free tier), block new design generation. (TOCTOU race
      accepted for beta — 6E adds DB-level unique partial index.)
- [x] **Verification (staging, 2026-06-23):** Two test accounts, A owns design,
      B cannot see it. GET → 404. Render → 404. No auth → 401.
      RLS PROOF: direct PostgREST with B's JWT returns `[]`.
- [x] Add `@supabase/ssr` to Next.js for client-side auth (`web/lib/supabase.ts`
      browser client, `web/middleware.ts` server client, `web/app/auth/callback/route.ts`).
- [x] Auth middleware on protected Next.js pages (`middleware.ts` — redirects to
      `/login` if no session; PUBLIC_ROUTES: login, signup, auth/callback, share,
      privacy, terms).
- [x] Login page (`web/app/login/page.tsx`) — email/password + Google OAuth button.
      Redirects authenticated users. Handles "account already exists" from signup.
- [x] Signup page (`web/app/signup/page.tsx`) — email/password + Google OAuth,
      13+ age gate checkbox (COPPA), email confirmation flow, duplicate-email detection.
- [x] AuthProvider context (`web/components/AuthProvider.tsx`) — session state, signOut.
- [ ] **Google OAuth dashboard setup (YOU):** Enable Google provider in Supabase
      Dashboard → Auth → Providers. Create Google Cloud OAuth consent screen +
      client ID/secret. Code is wired up and ready.

### 6B — Row-Level Security ✅
- [x] RLS + user-scoped SELECT policy on `staging.designs`: `user_id = auth.uid()`.
- [x] RLS + user-scoped SELECT policy on `staging.events`: same pattern.
- [x] RLS + user-scoped SELECT policy on `staging.selections`: same pattern.
- [x] Service-role key backend-only (writes bypass RLS, app sets user_id).
- [x] `/renders/` StaticFiles public — structurally excluded from auth
      (FastAPI middleware, not dependency injection). Permanent exclusion.
- [x] **Verification (staging, 2026-06-25):** Direct PostgREST with anon key +
      JWT. A sees own rows on all 3 tables. B sees `[]` on all 3 tables.
      `/renders/` returns 404 (no file) not 401 (no auth block).
- [ ] Apply same RLS policies to `public` schema before prod deploy (Phase 9).

### 6C — Privacy, Terms, Age Gate, Data Deletion ✅
- [x] `/privacy` page (`web/app/privacy/page.tsx`) — comprehensive: what's collected
      (7-item table), what's NOT collected, third-party services, data retention,
      account deletion, children's privacy. Has PLACEHOLDER for entity name + email.
- [x] `/terms` page (`web/app/terms/page.tsx`) — account requirements, acceptable use,
      AI-generated content disclaimers, affiliate disclosure, third-party links,
      governing law. Has PLACEHOLDER for entity name + state.
- [x] 13+ age gate checkbox at signup (COPPA) — `ageConfirmed` state, disables
      signup button until checked, sends `age_confirmed: true` in user metadata.
- [x] "Delete my account" flow (`web/app/account/page.tsx`) — type "DELETE" to
      confirm, calls `DELETE /account`, cascading delete from all tables + auth.
      Error handling for partial failures (auth deleted but data cleanup incomplete).
- [x] **Verification:** Deletion cascade verified on staging (20/20 cross-worker
      blocklist test, all data removed from designs/events/selections/auth).
- [ ] **PLACEHOLDERs (YOU):** Fill in entity name, state, privacy email in
      privacy.tsx and terms.tsx before launch.

### 6D — Rate Limiting (1 session) ✅
- [x] Add `slowapi` (or similar) to FastAPI.
- [x] `POST /design`: 5/min per IP ($0.37/run — unprotected = budget burn).
- [x] `POST /design/{run_id}/render`: 3/min per IP.
- [x] `POST /design/{run_id}/hotspots`: 3/min per IP.
- [x] **Verification:** Exceed the limit, confirm 429 response.

### 6E — Tier Enforcement ✅

- [x] **Atomic free-room claim:** `claim_and_save_free_design` RPC uses
      `pg_advisory_xact_lock(hashtext(user_id))` to serialize concurrent claims.
      Proven: 5 concurrent RPCs → exactly 1 True, 4 False on real Postgres.
- [x] **Watermark toggle:** `render_room(*, watermark=True)` — free renders
      watermarked, paid renders clean. Keyed on `is_paid` per-design.
- [x] **Room-type gating:** Free tier = bedroom only (403 on living_room+).
      Paid tier unlocks all room types.
- [x] **Pack ledger:** `user_packs` table, `decrement_pack` RPC (single-statement
      UPDATE with row-lock serialization), `re_credit_pack` RPC for clean failures.
- [x] **Fail behavior:** Free save fails open (ephemeral in-memory only).
      Pack decrement fails closed (falls to free path). Re-credit failure → CRITICAL log.
- [x] **11 tests, 526 total:** Free tier (4), paid tier (3), re-credit (1),
      watermark (2), TOCTOU concurrent (1).

### 6F — Scaling Architecture ✅ (verified on staging 2026-06-28)

*All items built, deployed, and load-tested on staging.*

- [x] **Multi-worker uvicorn:** `railway.json` sets `--workers ${UVICORN_WORKERS:-2}`.
      Mutable state audit complete (7 variables classified, 2 moved to Redis).
- [x] **Rate-limit state → Redis:** `slowapi` uses `storage_uri=redis_url` when
      `REDIS_URL` is set, `in_memory_fallback_enabled=True` for Redis-down.
- [x] **Deleted-user blocklist → Redis:** `redis.setex(f"deleted_user:{user_id}", 7200, "1")`.
      Verified: 20/20 cross-worker blocklist test on staging (all 20 requests
      rejected after deletion, across workers).
- [x] **Async render with client polling:** `POST /design/{run_id}/render` returns
      202 + job_id. `GET /design/{run_id}/render/status` polls. Redis hash stores
      status (pending → rendering → complete/failed). Sync fallback when Redis down.
      Frontend polls 60 attempts × 3s = 180s ceiling with "check again" recovery.
- [x] **LLM concurrency semaphore:** Redis counting semaphore (`roomkit:llm_active`,
      cap=30 via `LLM_CONCURRENCY_CAP`, 120s key TTL). All-or-nothing slot
      acquisition, 60s acquire timeout, 503 on timeout. Local
      `threading.Semaphore(CAP // WORKERS)` fallback.
- [x] **Render concurrency semaphore:** Redis counting semaphore (`roomkit:render_active`,
      cap=4 via `RENDER_CONCURRENCY_CAP`, 300s key TTL). One slot per render.
      Graceful queueing: 600s timeout, on timeout proceeds without slot (not
      hard-fail). Cap=4 keeps throughput at ~6.9 IPM, under Tier 3's 7 IPM.
- [x] **Retry + backoff on LLM calls:** Style, composition: 3x retry (1s/2s/4s)
      on 429/529/timeout. Selection: already had retry. Render: 2x retry, 5s backoff.
- [x] **Shared Anthropic/OpenAI clients:** Module-level singletons per worker
      (httpx connection pooling, thread-safe).
- [x] **Structured pipeline logging:** Per-stage timing (intake_ms, style_ms,
      composition_ms, sourcing_ms, semaphore_wait_ms, selection_llm_ms, selection_ms,
      render_ms) in `design_completed` event data. `scripts/pull_timing.py` for analysis.
- [x] **Load testing (staging, 2026-06-28):**
      - Test B: 4 concurrent designs at cap=30 — graceful throttling, no 500s
      - Test D: 20 requests after user deletion — all 401 (cross-worker blocklist)
      - Test E: 5 concurrent designs — secondary throttling proof

**Staging verification:** Real-user design = ~27s server-side. selection_llm_ms
constant ~17s regardless of queue position (no Anthropic rate-limiting at Tier 2+).
Client-observed 63s was cross-region Redis (EU) + concurrent test artifact.

**Deferred to Phase 9:**
- [ ] **Incremental semaphore slot release:** Release each slot as its LLM call
      finishes (not all-or-nothing). Needed when sustained concurrent selections
      exceed 3-4 (beyond beta).
- [ ] **Redis US-East co-location:** ~4s latency savings per design (currently
      cross-region). Infrastructure swap, zero code changes.

**Deferred to Phase 10/scale:**
- [ ] **Test A (rate-limits-global):** Never ran — the one unverified 6F coordination
      piece. Rate limiting is Redis-backed, theoretically correct, not load-tested.
- [ ] **Render concurrency cap scaling:** Cap=4 is tight at Tier 3 (7 IPM).
      At scale, increase OpenAI tier or adjust cap. Not beta-blocking.
- [ ] **Provider-limit-tuned caps:** As Anthropic/OpenAI tiers change, caps
      (LLM_CONCURRENCY_CAP, RENDER_CONCURRENCY_CAP) need tuning.

**Exit (Phase 6 overall):** Users have accounts. Designs are user-scoped.
Free-room limit enforced. Tier gating active. Cross-user access blocked.
Privacy/terms live. Account deletion works. Expensive endpoints rate-limited.
`/renders/` stays public for crawlers. Pipeline scales to beta traffic.

---

## Phase 7 — Revenue Activation + Compliance

*Requires auth (Phase 6) for payment identity and tier enforcement.*

### 7A — Stripe Integration (Room Packs) ✅

**Model:** Packs of rooms. Each pack grants N additional room designs with
hi-res watermark-free renders + access to new room types. Non-expiring. Pricing
TBD in beta.

- [x] Stripe Checkout for pack purchase (`POST /checkout`, authenticated).
- [x] Pack ledger: atomic `process_stripe_payment` RPC (dedup INSERT + pack
      credit UPSERT in one transaction — no orphan state on failure).
- [x] Webhook for payment confirmation (`POST /stripe/webhook`, signature-verified).
      `client_reference_id` = user mapping, `metadata.pack_size` from Price metadata.
- [x] Tier-based render quality: free=medium ($0.063), paid=high ($0.25) at
      1536x1024 via gpt-image-1, driven by `is_paid` flag on the design.
- [x] Migration 004 staging-qualified (`staging.stripe_payments` table +
      `staging.process_stripe_payment` RPC, explicit schema prefixes).
- [x] 18 Stripe tests including 4 using real `stripe.StripeObject` instances.
- [x] **Verified end-to-end on staging:** real test payment → Stripe webhook →
      atomic credit → paid design → clean high-quality render (no watermark).
- [ ] Upgrade CTA when free-room limit hit (Phase 8 frontend scope).

**Bugs found + fixed via real testing (4 total):**
1. StripeObject `.get()` crash ×3: Stripe SDK returns `StripeObject`, not plain
   dicts. `.get()` triggers `__getattr__` (AttributeError), `dict()` triggers
   `__getitem__(0)` (KeyError). Fixed with `to_dict()` conversion at event top +
   `isinstance` fallback for metadata. Tests with real StripeObjects prevent regression.
2. Schema mismatch: migration 004 ran in `public` but app uses
   `SUPABASE_SCHEMA=staging` → PostgREST searched `staging.process_stripe_payment`,
   found nothing (PGRST202). Fixed by re-creating table + RPC in `staging` schema
   with explicit prefixes + dropping the public duplicates.

### 7B — Render Storage (Supabase Storage) ✅

- [x] **Public `renders` bucket** in Supabase Storage — crawler-reachable, no auth.
- [x] **`render_url` column** on `designs` table — durable record of render URL.
      Written after successful upload via `save_render_url()`.
- [x] **Upload after generation:** `render_room()` returns `(local_path, storage_url)`.
      Both async worker and sync fallback upload + persist. Fail-open on upload
      failure (local file still serves via StaticFiles fallback).
- [x] **OG tags** HEAD-probe the Storage URL (deterministic, public, no auth).
- [x] **Frontend** handles absolute Storage URLs with backward-compat for relative.
- [x] **Verified on staging:** render_url is a real Storage URL, loads with no auth,
      survived a redeploy (empty commit push → image still loads from Storage).
- [x] **Designs fully durable:** selections + affiliate links persist in slots JSONB
      (confirmed pre-7B), renders now persist in Storage. Nothing ephemeral remains.

### 7C — FTC / Amazon Associates Compliance ✅ (BETA)

**Elevated to pre-launch review.** Affiliate is primary revenue — an Associates
ban is existential, not cosmetic.

- [x] **Affiliate disclosure** (fine print, 11px muted) on result page (visible
      without scrolling) + site-wide footer.
- [x] **`rel="nofollow sponsored"` on all affiliate `<a>` tags.** ProductCard
      "Buy on Amazon" + gallery "Buy" link. ExportToCartButton uses
      `window.open()` (not crawlable, no SEO concern).
- [x] **Price display: Option A for beta.** Per-price "as of [date]" from real
      catalog fetch timestamp + shared subject-to-change disclaimer (one line,
      fine print). Clean UI — date reads as metadata, disclaimer appears once.
- [x] **Fake-timestamp bug fixed.** Adapter was setting `fetched_at=now()` at
      read-time (always "just now" regardless of data age). Fixed: refresh script
      now writes real ISO timestamp; adapter reads it from cache.
- [x] **Render image-use: Option A for beta (documented decision).**
      Renders pass actual Amazon product photos to gpt-image-1 as reference
      images (images.edit). Output is AI-generated original imagery. Prompt
      softened (Option C) from "recognizably the same items / product showcase"
      to "inspired by the style, materials, colors, and forms" — strengthens
      transformative-use posture without sacrificing visual connection.
- [ ] **ADD-ALL-TO-CART affiliate tag verification:** Smoke-test needed — open a
      real cart-add URL, check Associates dashboard for attribution.

**KNOWN COMPLIANCE RISKS (beta-only, documented and accepted):**

*Risk 1 — Price data sourcing:* Canopy (canopyapi.co) is a scraper, confirmed
not PA-API. Per Amazon's Operating Agreement, displaying non-PA-API price data
is technically non-compliant. Accepted for beta: prices are accurate, disclaimer
covers staleness/honesty. See Phase 7D for the PA-API migration hard gate.

*Risk 2 — Product photos as AI render input (the big one):*

Amazon Associates Program Policies explicitly prohibit using "Program Content"
(including product images) to "directly or indirectly, develop or improve large
language or multimodal models, machine learning models or related technology."
Separately, Associates may not "alter any Program Content in any way" or "cache
Product Advertising Content consisting of an image." Our render pipeline
downloads product photos and feeds them into gpt-image-1 (a multimodal model)
— this violates all three clauses as written. **PA-API migration does NOT cure
this** — the same prohibitions apply to PA-API content.

Copyright law is unsettled: Andersen v. Stability AI trial Sep 2026, no ruling
yet on inference-time image use vs training. Fair-use four factors are mixed
(factors 2-3 against, factor 4 arguably for us).

**Decision: Ship Option A for beta. Reasoning:**

1. **Option B (text-only renders, no product photos) is not a viable product.**
   RoomKit's core value is showing the ACTUAL products the user will buy,
   composed into their room, one tap from cart. Generic style-matched furniture
   is a fundamentally different, worse product.

2. **Demand generation is the strongest argument.** Every render drives paying
   customers directly to Amazon and to the sellers whose images we use. We do
   not compete with sellers — we generate demand for their exact products. On
   copyright's fourth factor (market harm, "the single most important element"),
   our use arguably HELPS the market rather than harming it. No rational seller
   sues a party driving their sales. (Strong equitable argument, untested in
   court — no precedent addresses this demand-generator pattern.)

3. **Amazon-affiliate is a replaceable monetization layer.** If Amazon enforces
   (low probability given we drive them sales), pivot to: (a) subscription /
   pay-to-play (Stripe + user_packs already built), or (b) different retailer
   affiliate (Wayfair, Target, Walmart). Architecture is pivot-ready: clean
   SourcingAdapter interface, one adapter instantiation point, retailer-agnostic
   product schema. Retailer swap = 1-2 sessions, not a rebuild. Amazon
   termination = forced acceleration of a pivot we may do anyway.

4. **Prompt softened (Option C)** from explicitly reproductive ("recognizably
   the same items / product showcase") to transformative ("inspired by the
   style, materials, colors, and forms"). Strengthens fair-use posture without
   sacrificing visual quality.

**Pre-scale items (not beta blockers):**
- IP attorney to interpret whether AI/ML clause covers third-party-model
  inference (vs training/fine-tuning your own model).
- Reconsider render approach before full public launch.
- Copyright question is inherent to product-photo approach and persists across
  any retailer pivot — revisit at scale regardless.

**Pivot readiness (assessed, confirmed real):**
- Backend: SourcingAdapter ABC, one adapter instantiation in routes.py,
  retailer-agnostic Product schema. Swap = 1-2 sessions.
- Frontend: ~15 Amazon-specific strings across 5 files (button text, cart-add
  URL, image-upgrade helper, disclosure text). Find-and-replace, not rebuild.
- Affiliate independence: Stripe + user_packs already built. Remove buy links
  + disclosure = 1 session.

**Exit:** FTC disclosure present. Link attributes correct. Price disclaimer
implemented. Render prompt softened. Decision documented with full reasoning,
known risks, and mitigations. PA-API migration tracked as 7D. Pivot-readiness
confirmed.

---

### 7D — PA-API Migration (PRE-FULL-LAUNCH BLOCKER)

**Hard gate: do NOT go to full/public launch on Canopy-sourced prices.**

PA-API gives identical accurate prices from the sanctioned source. Beta sales
should qualify us for PA-API access (~3 qualifying sales / 180 days threshold).
The clean disclaimer UI stays regardless — Amazon requires subject-to-change
notice even with PA-API data.

**NOTE:** PA-API cures the price-sourcing violation but does NOT cure the
render/image-use issue — the same AI/ML and modification prohibitions apply to
PA-API content. The render approach is a separate risk tracked in 7C notes.

- [ ] Apply for PA-API access (requires Associates account with qualifying sales).
- [ ] Implement PA-API client (replaces Canopy client).
- [ ] Migrate catalog refresh to PA-API (replaces `scripts/refresh_catalog.py`
      Canopy calls).
- [ ] Implement refresh worker (`run_refresh()` — currently a stub) to keep
      prices within 24h freshness window.
- [ ] Verify: all displayed prices sourced via PA-API, refresh worker running,
      freshness validated.

**Exit:** Full price-display compliance. Safe for public launch.

---

---

## Phase 8 — Frontend Build-Out

*The full production-quality product frontend. Built AFTER the backend foundation
(auth, RLS, tiers, scaling, revenue) is complete, so every surface builds against
FINAL contracts — no rework against changing APIs.*

**Why its own late phase:** The robust frontend should front a FINISHED, secure,
scaled product. Building it earlier means rebuilding against changing contracts
(auth flow, async render polling from 6F, tier enforcement from 6E, Stripe
checkout from 7A). Build it once, robustly, against final contracts.

### Navigation & Shell
- [x] Persistent header/nav: logo, nav links, account menu. Logged-in vs
      logged-out states (account menu vs login/signup CTA).
- [x] Footer: privacy, terms, affiliate disclosure links.
- [x] Consistent layout shell wrapping all pages (header + footer + content area).

### Account & Auth Surfaces
- [x] Account/profile page: view email, manage account, account-deletion entry
      point (deletion cascade logic lives in 6C — this is the UI surface).
- [x] Visible logout: surface the existing `signOut()` from AuthProvider into
      the account menu.
- [x] "Logged in as [email]" indicator in header/nav.
- [x] Password reset/change flow (Supabase Auth handles via forgot-password page).

### Core Product Surfaces
- [x] **"My Designs" / history page:** Users see their saved user_id-stamped
      rooms, revisit/re-open past designs.
- [x] **Homepage / landing page:** Hero, how-it-works, showcase renders, room
      cards, aesthetic switcher, free-tier messaging.
- [x] Quiz → design → result flow integrated into the site shell with header/
      footer/nav wrapping.
- [x] **Quiz reskin:** Full design-language alignment — deepened tokens (radii,
      shadows, hover lift, surface-warm, confident typography) match landing page.
- [x] **Free tier messaging:** "Your first room is free" on landing hero, auth
      wall, and mode choice screen.
- [x] **Login redirect:** Auth wall preserves quiz state through login/signup
      round-trip via `?redirect=/design` + localStorage stash.
- [x] **TV budget gate:** canAdvance blocks until budget warning resolved.

### Admin Dashboard Auth (MANDATORY security fix)
- [x] **Fixed:** Server-side proxy with JWT + admin allowlist. Secret rotated,
      never in client bundle.

### Robustness / Production Quality
- [x] Loading, error, and empty states across all pages (My Designs empty/loading,
      result page error/loading, purchase pages migrated to design tokens, error
      banner consistent, 404/error pages styled).
- [ ] Mobile-responsive throughout (real device testing, not just preview).
- [x] Consistent design system / visual language (quiz reskin was last holdout —
      all surfaces now on deepened token system).
- [x] 404 and error pages (custom `not-found.tsx` + `error.tsx`, design-language
      styled, nav/footer via SiteShell).
- [ ] Accessibility basics: semantic HTML, keyboard nav, color contrast, screen
      reader labels (ties to legal-plan ADA/WCAG items).
- [ ] Performance: render-polling UX (progress indicator during 15-25s render
      generation — built against 6F's async `202 Accepted` → poll contract),
      page load optimization.

### Dependencies
- Render-polling frontend depends on 6F's async render contract — build against
  the FINAL async API (`202 Accepted` → poll status), not current synchronous,
  to avoid rework.
- Account-deletion UI ties to 6C (deletion logic lives in 6C, the page surface
  lives here).
- CORS lockdown (Phase 9 deploy) + custom SMTP are part of making the deployed
  frontend production-ready.

**Exit:** Every page has nav, footer, loading/error states. Account management
works. My Designs shows saved rooms. Homepage funnels into the quiz. Mobile is
real-device tested. One cohesive product, not a collection of standalone pages.

### Carried Items (verified, not lost)

These are confirmed facts and tracked debt from Phase 8 work sessions:

- **Billable unit confirmed:** Pack decrements at GENERATION (`routes.py:148`
  via `decrement_pack` RPC), render is free. Pricing/CTA copy is accurate —
  says "5 room designs" (not renders), "Full HD renders" listed as included
  feature. No copy fix needed.
- **Render flakiness FIXED (band-aid):** Cross-worker stale `_designs` dict
  cache. Re-check patches on render endpoint + GET /design endpoint (commits
  `0db2ead`, `400ed64`). All 6 `_get_design` callers audited — only render and
  GET were vulnerable (now fixed). **This is a band-aid — two re-checks in
  place. A third occurrence means do the real fix: Redis-backed design cache
  (Redis already deployed for render jobs).** Track as pre-scale tech debt.
- **Supabase email rate limit (~3-4/hr default) — BETA BLOCKER.** Password
  reset + signup confirmation emails silently fail under default Supabase
  email service rate limits. Multiple beta users hitting signup/reset in one
  hour = silent failures. Custom SMTP (Phase 9) is not optional polish — it
  blocks a real beta. Needs domain first (SPF/DKIM).
- **Showcase images are POST-3A/3B/3C quality.** Generated Jul 13 against
  Railway staging with budget-quality fixes deployed (commit `6546a8e`, Jul 9).
  Budgets included $1500+ designs that trigger the fixes. No swap needed.
- **Pre-existing test failures FIXED:** All 3 broken tests repaired (556/556
  passing). `test_free_user_living_room_rejected` + `test_free_user_at_limit_rejected`:
  tests called `.lower()` on dict detail — fixed to access `detail["message"]`.
  `test_503_when_semaphore_full`: missing LLM mocks caused real API call — added
  style/composition mocks so test reaches semaphore check.

---

## Phase 9 — Deploy + Gate

*Make it real and reachable.*

- [ ] Buy domain.
- [ ] Deploy to production host (TBD — not decided yet).
- [ ] Production CORS locked to real domain.
- [ ] Production env vars set (all secrets via host config, not git).
      **REQUIRED production env vars (localhost defaults silently break):**
      - `NEXT_PUBLIC_SITE_URL` — public frontend URL (OG fallback images point here)
      - `NEXT_PUBLIC_API_URL` — public backend URL (render URLs, design API)
      - `CORS_ORIGINS` — lock to real domain
- [ ] **Account wall:** Users must create account to access product. Gate at
      entry (before quiz) or after first interaction (TBD — test which converts).
- [ ] **Silent API-failure handling (launch-blocker):** When selection LLM calls fail
      en masse (e.g. exhausted credits), detect and show user-facing error + alert.
      Never serve blank rooms in production.
- [ ] Product analytics (GA / Plausible) for traffic, referrers, channel/funnel analysis
      at scale (Supabase dashboard is internal-only).
- [ ] **Structured pipeline logging in production:** Verify per-stage timing
      (from 6F) is flowing to logs. Set up log aggregation (Railway logs or
      external sink) so pipeline bottlenecks and failure patterns are visible
      from day one.
- [ ] **Incremental semaphore slot release (scaling fix):** The concurrency
      semaphore currently holds all ~15 slots all-or-nothing for the entire
      selection phase (~15s), releasing only when the slowest LLM call finishes
      — even though individual calls finish in 2-5s. This wastes slot capacity
      and serializes designs under high concurrency. Fix: release each slot's
      permit as its `select_products()` call returns, so a design's held-slot
      count drops as faster calls complete, letting queued designs fit sooner.
      Needed when sustained concurrent selections exceed ~3-4 (beyond beta
      scale). Changes the acquire/release contract — test against multi-worker
      staging when implemented.
- [ ] **PostgREST schema cache reload after migrations:** After running any
      migration that creates or alters functions/tables, run
      `NOTIFY pgrst, 'reload schema';` in SQL Editor. Without this, PostgREST
      serves stale schema and RPCs return 404. This bit us on staging (6E deploy).
- [ ] **Custom SMTP for auth emails (BETA BLOCKER):** Production email provider
      (Resend or Postmark) from the real domain. Configure SPF/DKIM DNS records.
      Replace Supabase default email service in Dashboard → Auth → SMTP. Default
      rate-limits at ~3-4 emails/hour — multiple beta signups = silent failures.
      Blocked on domain (this phase).
- [ ] **Stripe live mode (BETA BLOCKER for paid tier):** Switch from test/sandbox
      to live Stripe keys. Requires:
      (a) Stripe business verification (2-7 business days — START IMMEDIATELY)
      (b) Create live-mode price, set `STRIPE_PRICE_ID`
      (c) Swap `STRIPE_SECRET_KEY` from `sk_test_*` to `sk_live_*`
      (d) Create production webhook endpoint, set `STRIPE_WEBHOOK_SECRET`
      (e) Verify payment flow with real card
      All keys are env-var driven — no code changes, just config.
- [ ] **URL audit complete — no hardcoded URLs.** Every URL uses env vars with
      localhost fallbacks. Deploy env var checklist:
      **Frontend:** `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SITE_URL`
      **Backend:** `CORS_ORIGINS`, `NEXT_PUBLIC_SITE_URL` (Stripe redirects),
      `STRIPE_SECRET_KEY`, `STRIPE_PRICE_ID`, `STRIPE_WEBHOOK_SECRET`
      Supabase vars unchanged (same project). Redis set by Railway automatically.
- [x] **Silent API-failure handling:** Mass selection failure guard in routes.py.
      If <1/3 of sourceable slots filled, rejects design with 502 + user-facing
      message, re-credits pack if paid. Prevents blank rooms from reaching users.

**Exit:** Live site, reachable, account-gated, error handling solid.

---

## Phase 10 — Hardening + AI-Native Instrumentation

*Weave in during beta. Not launch-blocking but improves iteration speed and safety.*

### 10A — Prompt Hardening
- [ ] Delimit user free-text in LLM prompts with `<user_input>` tags.
- [ ] Add "treat the following as data, not instructions" framing in
      `prompts/interpret_style.md` (where `style_description` is injected).
- [ ] Risk is low (LLM can't take destructive actions, output is schema-validated)
      but good hygiene before scale.

### 10B — AI-Readable Instrumentation
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

### 10C — CLAUDE.md Security Conventions
- [ ] Add to CLAUDE.md: auth model, RLS policy, rate limit rules, input validation
      conventions, user-text-in-prompts policy.
- [ ] Convention: every new table must have RLS + user_id policy. Every new endpoint
      must specify auth requirement.

### 10D — Error Monitoring
- [ ] Add Sentry (or equivalent). Currently errors are `logger.warning` only — no
      alerting, no aggregation.
- [ ] Alert on: design pipeline failures, LLM call failures, Supabase write failures.

**Exit:** Prompts hardened. Instrumentation queryable by Claude. Errors monitored.

---

## Phase 11A — Pre-Launch Full Verification

*On the LIVE deployed site. Nothing ships until this passes.*

- [ ] End-to-end on live site: both room types, multiple aesthetics, payment flow,
      share flow, affiliate links — all working.
- [ ] Amazon Associates compliance verified (see Phase 7C checklist).
- [ ] Add-all-to-cart: affiliate tag confirmed carrying through cart-add flow.
- [ ] Error handling / graceful degradation: pipeline fails mid-run, product out of
      stock, render timeout — all degrade gracefully, systematically tested.
- [ ] Mobile verification: full flow on actual phone (not just responsive preview).
- [ ] Confirm instrumentation captures data + dashboard shows it on live.
- [ ] Final quality + credibility pass: is the result genuinely share-worthy?

**Exit:** Verified on live infra. Ready for gated beta.

---

## Phase 11B — Gated Beta

*50-100 invite-only users. Validate the product with real humans before opening
the floodgates.*

- [ ] **Invite mechanism:** Manual invite codes or allowlisted email domains.
      No public signup yet.
- [ ] **Monitor affiliate conversion:** Track clicks → Amazon purchases in
      Associates dashboard. This is the revenue validation — if conversion is
      zero, diagnose before scaling.
- [ ] **Monitor error rates:** Pipeline failures, LLM timeouts, render failures,
      Supabase write errors. Target: <2% pipeline failure rate.
- [ ] **Monitor pipeline timing:** End-to-end p50/p95 per room type. Identify
      bottleneck stages. Target: <60s end-to-end for composition + selection.
- [ ] **Collect qualitative feedback:** Are rooms share-worthy? Do products feel
      on-style? Is the budget allocation intuitive? Direct conversations with
      beta users, not surveys.
- [ ] **Fix what surfaces.** Beta exists to find the gaps — budget 1-2 sessions
      for fixes before wide launch.

**Exit:** Affiliate conversion confirmed non-zero. Error rate <2%. Pipeline
timing acceptable. Beta users find the product genuinely useful. Ready for
public launch.

---

## Phase 12 — Multi-Retailer Expansion (post-launch)

*After launch, with real traffic data to satisfy aggregator requirements.*

### 12A — Affiliate Aggregator Integration
- [ ] Apply to Skimlinks or Sovrn Commerce (aggregators accept newer sites with
      less traffic history than direct programs like CJ/Wayfair).
- [ ] Integrate aggregator SDK/API — replaces raw Amazon links with
      highest-commission retailer when available.
- [ ] Catalog matching/dedup across retailers (or distinct products per retailer).
- [ ] Margin-aware routing: favor higher-commission in-stock option where quality
      is equal.
- [ ] **Monitor:** Don't assume non-Amazon retailers out-earn Amazon despite higher
      per-item rates. Volume and conversion matter more than commission %. Track
      revenue-per-click by retailer.

### 12B — Scale
- [ ] Cost-per-room optimization: cache LLM responses, reduce calls per design.
- [ ] Per-user rate limits (not just IP) for logged-in users.
- [ ] Throughput management as traffic grows.
- [ ] Formal access-control matrix (admin roles, operator accounts, partner API keys).
- [ ] DEFERRED: "Pro" subscription tier for realtors/STR hosts/designers. Only
      build if segment with validated WTP exists in usage data.

---

## Execution Roadmap (updated 2026-07-02)

Exact order from current state to launch. Each step lists WHO does it
(CLAUDE = programmatic, YOU = manual/judgment, BOTH = collaborative) and
what PROVES it's done. One step at a time — don't start the next until
the current one's proof criteria pass.

```
                    ✅ COMPLETED
      ══════════════════════════════════════════════
      Steps 1-3, 5 — 6B RLS, 6A frontend auth,
      6C privacy/terms/deletion, 6F scaling — ALL DONE
      ══════════════════════════════════════════════

NOW → Step 4 → Step 5.1
      ══════════════════════════════════════════════
                SECURITY GATE CLEARED (Phase 6)
      ══════════════════════════════════════════════
    → Step 6 → Step 7 → Step 8 → Step 9 → Step 10
      ══════════════════════════════════════════════
               REVENUE ACTIVATION DONE (Phase 7)
      ══════════════════════════════════════════════
    → Step 11 → Step 12 → Step 13 → Step 14 → Step 15
      ══════════════════════════════════════════════
             FRONTEND + DEPLOY READY (Phase 8-9)
      ══════════════════════════════════════════════
```

**Estimated: ~8-11 sessions remaining to deploy, 2-4 weeks beta after.**

---

### Step 1 — 6B: RLS verification ✅ DONE

- [x] PostgREST query: A's JWT on A's events → rows, B's JWT → `[]`
- [x] Same for `selections` table
- [x] `/renders/` returns 200/404 with no auth header (crawler-safe, no 401)
- [ ] Apply RLS policies to `public` schema (prod) — deferred to Phase 9 deploy

---

### Step 2 — 6A frontend: Next.js auth UI ✅ DONE

- [x] `@supabase/ssr` installed: browser client (`web/lib/supabase.ts`), server
      client (`web/middleware.ts`), auth callback (`web/app/auth/callback/route.ts`)
- [x] Auth middleware: redirects unauthenticated users to `/login`
- [x] Login page: email/password + Google OAuth button
- [x] Signup page: email/password + Google OAuth, 13+ age gate, email confirmation
- [x] AuthProvider context: session state, signOut
- [x] JWT passed from frontend to API calls via `authHeaders()` in `web/lib/api.ts`

**Remaining (YOU):**
- [ ] Enable Google OAuth in Supabase dashboard (Settings → Auth → Providers)
- [ ] Walk through: signup → email confirm → login → quiz → design (browser)
- [ ] Test on actual phone (not responsive preview)

---

### Step 3 — 6C: Privacy, terms, age gate, deletion ✅ DONE

- [x] `/privacy` page — comprehensive (data table, third parties, retention, deletion)
- [x] `/terms` page — account requirements, AI disclaimers, affiliate disclosure
- [x] 13+ age gate checkbox on signup (disables button until checked)
- [x] Account page with "Delete my account" (type DELETE, cascade)
- [x] Deletion verified on staging (20/20 cross-worker blocklist)

**Remaining (YOU):**
- [ ] Review privacy/terms copy for accuracy
- [ ] Fill in PLACEHOLDER entity name, state, contact email
- [ ] Delete a test account via UI, confirm it feels complete

---

### Step 4 — 6E: Tier enforcement ✅ DONE

- [x] Watermark toggle (render checks `is_paid`: free=watermarked, paid=clean)
- [x] Room-type gating (free=bedroom only, paid unlocks living room+)
- [x] Pack ledger table (`user_packs`, `decrement_pack` / `re_credit_pack` RPCs)
- [x] Atomic free-room claim (`claim_and_save_free_design` RPC with `pg_advisory_xact_lock`)
- [x] TOCTOU fix proven on real Postgres (5 concurrent RPCs → exactly 1 claim, 4 rejected)
- [x] Re-credit on clean pipeline failure (CRITICAL log on re-credit failure)
- [x] 11 new tests, 526 total, 0 regressions

YOU do (still pending):
- [ ] Check watermark quality on staging render ("subtle, not cheapening")
- [ ] Confirm free-tier bedroom render is still share-worthy

---

### Step 5 — 6F: Scaling architecture ✅ DONE (verified on staging 2026-06-28)

All items built, deployed, and load-tested. See Phase 6F section for full details.

- [x] Multi-worker, Redis rate limiting, Redis deleted-user blocklist
- [x] Async render with client polling (202 → poll → complete)
- [x] LLM concurrency semaphore (cap=30) + render semaphore (cap=4, graceful queueing)
- [x] LLM retry/backoff, shared clients, pipeline timing
- [x] Load tests B/D/E passed on staging

**═══ PHASE 6 COMPLETE — ALL ITEMS DONE (6A–6F) ═══**

---

### Step 5.1 — Phase 4: Viral share loop (remaining items only, ~0.5 session)

**Who:** BOTH

Most of Phase 4 is BUILT (ShareButton, OG tags, watermark, navigator.share,
Pinterest/X/copy link). Remaining:

CLAUDE does:
- [ ] Finish share page (`web/app/share/[run_id]/page.tsx` — currently a stub)
- [ ] Click-to-design-your-own CTA on shared view

YOU do:
- [ ] Click "Add All to Cart" → check Associates dashboard for attribution
      **THIS IS THE REVENUE VALIDATION**
- [ ] Share to Pinterest → verify OG unfurl, pin looks good
- [ ] Share to X → verify card renders
- [ ] Open shared link in incognito → works unauthenticated
- [ ] Test full share flow on actual phone

**Proof:** Share loop works. Affiliate tag carries through (Associates dash).

---

### Step 7 — Phase 4B: Platform-adaptive visual layer (1 session)

**Who:** BOTH

CLAUDE does:
- [ ] `aspect` parameter on render endpoint (portrait/landscape)
- [ ] Frontend sends aspect based on viewport
- [ ] Fix hardcoded aspect ratio in InteractiveRoomRender.tsx
- [ ] Mobile visual pass (44px touch targets, product card density, scroll)

YOU do:
- [ ] Render on phone → portrait fills screen
- [ ] Render on desktop → landscape fills hero
- [ ] Full mobile walkthrough: quiz → selection → render → products → share

**Proof:** Both orientations correct. Mobile is thumb-friendly.

---

### Step 8 — Phase 7A: Stripe integration ✅ DONE

- [x] `POST /checkout` (authenticated) → Stripe Checkout Session → redirect URL
- [x] `POST /stripe/webhook` (unauthenticated, signature-verified) → atomic credit
- [x] `process_stripe_payment` RPC: dedup INSERT + pack UPSERT in one transaction
- [x] Migration 004 staging-qualified (all objects in `staging` schema)
- [x] Tier-based render quality: free=medium/$0.063, paid=high/$0.25 (gpt-image-1)
- [x] 18 Stripe tests (including 4 with real `stripe.StripeObject` instances)
- [x] Stripe account created, test keys + webhook configured on Railway
- [x] End-to-end verified: test payment → webhook → credit → paid design → clean render
- [ ] Upgrade CTA when free limit hit (deferred to Phase 8 frontend)

**Bugs found + fixed during real testing (4):**
1. StripeObject `.get()` crash ×3 — Stripe SDK returns StripeObject, not dict.
   Fixed with `to_dict()` at event top + real-StripeObject test coverage.
2. Schema mismatch (PGRST202) — migration ran in `public` but app uses
   `SUPABASE_SCHEMA=staging`. Fixed by rewriting migration with explicit
   `staging.*` prefixes.

**Also fixed during 7A verification:**
- Render flakiness: reload seeding effect + container height collapse → `isInitialLoad` guard + `aspect-ratio` CSS.
- Bedding curation: duvet insert excluded from render prompt (invisible inside cover); quiet luxury palette updated for duvet_cover.

---

### Step 9 — Phase 7B: Render storage ✅ DONE

- [x] Supabase Storage public bucket (`renders`)
- [x] `render_url` column on designs table + NOTIFY schema reload
- [x] Upload after generation (both async worker + sync fallback)
- [x] Frontend handles absolute Storage URLs, OG tags probe Storage
- [x] Verified on staging: render_url populated, public access, survives redeploy
- [x] `NEXT_PUBLIC_SUPABASE_URL` env var added to Railway

**Note:** OpenAI billing hard limit caused a render "crash" scare — not a code bug.
Render path failed gracefully (logged, didn't crash pipeline). Resolved by adding funds.

---

### Step 10 — Phase 7C: FTC / Associates compliance ✅ DONE (beta)

- [x] Affiliate disclosure (fine print) on result page + site-wide footer
- [x] `rel="nofollow sponsored"` on all affiliate `<a>` tags
- [x] Price display: Option A — per-price "as of [date]" + shared disclaimer
- [x] Fake-timestamp bug fixed (adapter was lying about freshness)
- [x] Canopy confirmed as scraper (not PA-API) — accepted for beta, PA-API
      migration tracked as 7D pre-full-launch blocker

YOU do:
- [ ] Verify disclosure visible without scrolling on result page
- [ ] Review: renders use product photos as gpt-image-1 references (flagged)
- [ ] Read Amazon Associates Operating Agreement, confirm compliance
- [ ] Smoke-test cart-add URL in Associates dashboard
- [ ] **Pre-beta: refresh catalog data.** Current catalog = 22k products, zero
      real `fetched_at` timestamps (predate the fix), 1-3 weeks stale by file
      mtime. "As of [date]" will show no date until refreshed. Free Canopy tier
      = 100 requests/month — decide: refresh priority slots only (~15-20 requests
      for highest-traffic slots), upgrade Canopy tier for full refresh, or accept
      staleness with disclaimer for beta. Next refresh writes real timestamps.
      Run: `python scripts/refresh_catalog.py <slot> "<search term>"` or
      `--batch <file>.json` for bulk.

### Step 10b — Phase 7D: PA-API migration (pre-full-launch blocker)

- [ ] Apply for PA-API access after beta qualifying sales
- [ ] Replace Canopy client with PA-API client
- [ ] Implement refresh worker (currently stub)
- [ ] Verify all prices PA-API-sourced + 24h-fresh

**═══ PHASE 7 COMPLETE (beta) — REVENUE ACTIVATION DONE ═══**

---

### Step 11 — Phase 8: Frontend build-out (2-3 sessions)

**Who:** BOTH

CLAUDE does:
- [ ] Layout shell: persistent header/nav (logged-in vs logged-out), footer
      (privacy/terms/about/affiliate links), wrapping all pages
- [ ] Account page: view email, logout, deletion entry point (6C cascade)
- [ ] "Logged in as [email]" indicator, visible logout in account menu
- [ ] Password reset/change flow
- [ ] "My Designs" / history page: list saved rooms, re-open past designs
- [ ] Homepage / landing page: hero, how-it-works, example renders, quiz entry,
      credibility, SEO
- [ ] Integrate quiz → design → result flow into the site shell
- [ ] Loading/error/empty states across all pages
- [ ] 404 and error pages
- [ ] Render-polling UX (progress indicator, built against 6F's async contract)
- [ ] Accessibility basics (semantic HTML, keyboard nav, contrast, labels)

YOU do:
- [ ] Review homepage copy and visual direction
- [ ] Full mobile walkthrough on actual phone (not responsive preview)
- [ ] Verify "My Designs" shows your saved rooms, re-opening works
- [ ] Confirm it feels like one cohesive product, not standalone pages

**Proof:** Every page has nav + footer. My Designs works. Homepage funnels into
quiz. Mobile real-device tested. Consistent visual language throughout.

---

### Step 12 — Phase 9: Deploy (1 session)

**Who:** BOTH

CLAUDE does:
- [ ] Production Railway service
- [ ] CORS locked to real domain
- [ ] All env vars set, no localhost defaults
- [ ] Silent API-failure handling
- [ ] Pipeline logging flowing

YOU do:
- [ ] Buy domain
- [ ] Set DNS to Railway
- [ ] Set production secrets on Railway
- [ ] Decide account wall placement (before quiz vs after first interaction)
- [ ] Custom SMTP: production email provider (Resend/Postmark), SPF/DKIM
      on domain DNS. Replace Supabase default service. Needed before beta.

**Proof:** Site live at real domain. Health green. CORS blocks wrong origins.

**═══ PHASES 8-9 COMPLETE — FRONTEND + DEPLOY READY ═══**

---

### Step 13 — Phase 11A: Full verification on live site (1-2 sessions) — PRE-LAUNCH GATE

Phase 1 (browser verification) folds in here. All manual, on the live site.

**Who:** YOU (full checklist)

- [ ] Full guided flow: quiz → mode → selection → render → result (BOTH room types)
- [ ] Multiple aesthetics — products on-style
- [ ] Budget meter clean, red warning below $1000
- [ ] Mirror options correct (6 choices, None excludes, No preference shows all)
- [ ] Dresser options not near-duplicates
- [ ] Room-so-far panel: thumbnails update, scrolls
- [ ] Payment: hit free limit → CTA → Stripe → paid room works
- [ ] Share: render → share → OG unfurl → recipient views → "design your own"
- [ ] Affiliate: click through, check Associates dashboard
- [ ] Add-all-to-cart: tag carries through
- [ ] Mobile: full flow on actual phone
- [ ] Error: kill API key mid-run — graceful degradation?
- [ ] /admin dashboard shows live data

**Proof:** Every surface touched by your hands on prod infra.

---

### Step 14 — Phase 10: Hardening (parallel with beta prep, not blocking)

**Who:** CLAUDE

- [ ] Prompt hardening (`<user_input>` delimiters, "treat as data" framing)
- [ ] Structured event columns (aesthetic, budget, room_type)
- [ ] Slot-skip event logging
- [ ] `run_summary` view
- [ ] `/admin/query` endpoint
- [ ] CLAUDE.md security conventions
- [ ] Sentry error monitoring + alerts

**Proof:** Tests pass. Error alerts fire on test failures.

---

### Step 15 — Phase 11B: Gated beta (2-4 weeks) — PRE-LAUNCH GATE

**Who:** YOU (with monitoring from CLAUDE)

CLAUDE does:
- [ ] Invite mechanism (codes or allowlisted emails)
- [ ] Monitoring dashboards / pipeline failure alerts

YOU do:
- [ ] Send invites to 50-100 people
- [ ] Monitor affiliate conversion in Associates dashboard (MUST be non-zero)
- [ ] Monitor error rates (target: <2% pipeline failure)
- [ ] Monitor pipeline timing (target: <60s e2e)
- [ ] Direct conversations with beta users ("is this share-worthy?")
- [ ] Fix what surfaces (1-2 sessions)

**Proof:** Affiliate conversion non-zero. Error <2%. Users find it useful.

**═══ READY FOR PUBLIC LAUNCH ═══**

After launch: Phase 12 (multi-retailer via Skimlinks/Sovrn, scale).

---

## Hard Gates (cannot be bypassed)

These are NON-NEGOTIABLE prerequisites for public deploy. They exist because
the product's cost structure ($0.37/room) creates unbounded financial exposure
without them.

| Gate | What it blocks | Why |
|---|---|---|
| Phase 6 Auth + Rate Limiting | ANY public deploy | $0.37/room uncapped to the internet without accounts + rate limits |
| Phase 6 Account Wall | Public access | Free-room limit unenforceable without accounts |
| Phase 6F Scaling Architecture | Public deploy | Sync single-worker breaks at ~10 concurrent users |
| Phase 7C Associates Compliance | Launch with affiliate links | Ban = revenue to zero; must verify before real traffic |
| Phase 11A Full Verification | Public beta | Correctness gate — no silent failures in prod |
| Phase 11B Gated Beta | Wide launch | Must validate affiliate conversion + error rates with real users first |

---

## Dependency Map

```
Phase 1   Browser verification ✓
  ↓
Phase 2   Input validation + secrets audit ✓
  ↓
Phase 3   Persistent design storage ✓ ──────────────────┐
  ↓                                                      │
Phase 4   Viral share loop + add-all-to-cart (AUTH-READY)│
  ↓       + 4B Platform-adaptive visual layer            │
  ↓       Built locally. NOT publicly deployable yet.    │
  ↓                                                      │
Phase 5   Full audit + living room build ✓               │
  ↓                                                      │
Phase 5C  Maintainability gate (docs + regression tests) │
  ↓                                                      │
Phase 5D  Staging environment (Railway + Supabase)       │
  ↓                                                      │
Phase 6   Foundation layer (auth, RLS, tiers, rates) ────┘
  ↓       + 6F Scaling architecture (workers, async, semaphore)
  ↓       ↑ HARD GATE: must complete before public deploy
  ↓       ↑ Enforces: free-room limit, tier gating, rate limiting
  ↓       ↑ Inserts into Phase 4's auth-ready seams
  ↓
Phase 7   Revenue activation (Stripe, render storage, compliance)
  ↓       ↑ requires auth from Phase 6
  ↓
Phase 8   Frontend build-out (nav, account, My Designs, landing, robustness)
  ↓       ↑ builds against FINAL contracts from 6 + 7
  ↓       ↑ async render (6F), tiers (6E), Stripe (7A)
  ↓
Phase 9   Deploy + gate
  ↓       ↑ requires Phase 6 + 6F (HARD GATE)
  ↓
Phase 10  Hardening + instrumentation (parallel with 9)
  ↓
Phase 11A Pre-launch verification (HARD GATE)
  ↓
Phase 11B Gated beta — 50-100 invite-only users (HARD GATE)
  ↓
Phase 12  Multi-retailer expansion + scale (POST-LAUNCH)
          ↑ Amazon-only at launch
          ↑ Add retailers via aggregator (Skimlinks/Sovrn)
```

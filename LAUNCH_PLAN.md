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

## What's Done (engine state as of 2026-06-16)

**Core pipeline — WORKING (318 tests pass):**
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

- [ ] **Watermark on renders:** Subtle "Made with RoomKit" in corner. Must stay
      light enough that the room still feels real and shoppable (a heavy mark
      cheapens the room that monetizes via affiliate). Free tier = watermarked,
      paid tier = clean. Render service produces both variants.
- [ ] **"Share my room" button** on the result page.
- [ ] **OG meta tags:** Dynamic `generateMetadata()` on result page — fetch design,
      set `og:image` to render URL, `og:title` to room description. The render is
      served via the public `/renders/{run_id}.jpg` StaticFiles path (confirmed
      unauthenticated, crawler-reachable).
- [ ] **Share targets:** Pinterest (priority — home design), then X, iMessage/link copy.
- [ ] **Click-to-design-your-own CTA** on the shared view (viral re-entry).
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

## Phase 5 — Full Audit + Living Room Build

*Biggest build phase. Two parallel tracks: audit bedroom depth, build living room.*

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

**Exit:** Bedroom audited and polished. Living room end-to-end working.

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

### 6A — Supabase Auth (2-3 sessions)
- [ ] Add `@supabase/ssr` to Next.js for client-side auth (email/password + Google).
- [ ] Auth middleware on protected Next.js pages.
- [ ] Backend JWT verification on FastAPI endpoints that need identity.
- [ ] Populate `user_id` on `designs` table (column already exists, nullable).
      Add to `events`, `selections` tables.
- [ ] Login/signup UI — clean, minimal.
- [ ] **Free-room enforcement:** Count designs where user_id = current user.
      If count >= 1 (free tier), block new design generation. Upgrade CTA.
- [ ] **Verification:** Create two test accounts, confirm account A cannot see
      account B's designs via API.

### 6B — Row-Level Security (1-2 sessions, depends on 6A)
- [ ] RLS already enabled on `designs` (Phase 3, default-deny). Add user-scoped
      SELECT policy: `user_id = auth.uid()`.
- [ ] Enable RLS on `events`, `selections` with same pattern.
- [ ] Service-role key stays backend-only (for admin/tracking writes).
- [ ] **Critical: `/renders/` StaticFiles path must be EXPLICITLY EXCLUDED from
      any auth middleware.** This path serves OG images to social crawlers. If
      blocked, every shared link loses its preview. Document as a permanent
      exclusion.
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
- [ ] `POST /design`: 5/min per IP ($0.37/run — unprotected = budget burn).
- [ ] `POST /design/{run_id}/render`: 3/min per IP.
- [ ] `POST /design/{run_id}/hotspots`: 3/min per IP.
- [ ] **Verification:** Exceed the limit, confirm 429 response.

### 6E — Tier Enforcement
- [ ] Watermark toggle: render service checks user tier, produces watermarked
      (free) or clean (paid) variant.
- [ ] Room-type gating: free tier = bedroom only. Paid tier unlocks others.
- [ ] Pack ledger: user has N rooms remaining. Decrement on design creation.
      Non-expiring.

**Exit:** Users have accounts. Designs are user-scoped. Free-room limit enforced.
Tier gating active. Cross-user access blocked. Privacy/terms live. Account
deletion works. Expensive endpoints rate-limited. `/renders/` stays public for
crawlers.

---

## Phase 7 — Revenue Activation + Compliance

*Requires auth (Phase 6) for payment identity and tier enforcement.*

### 7A — Stripe Integration (Room Packs)

**Model:** Packs of rooms. Each pack grants N additional room designs with
hi-res watermark-free renders + access to new room types. Non-expiring. Pricing
TBD in beta.

- [ ] Stripe Checkout for pack purchase.
- [ ] Pack ledger: increment room count on successful payment.
- [ ] Upgrade CTA when free-room limit hit.
- [ ] Webhook for payment confirmation (don't trust client-side redirect).

### 7B — Render Storage (Supabase Storage)

**Resolves the render persistence gap found in Phase 3:**
- Renders are currently local JPEGs at `data/renders/{run_id}.jpg` — die on
  ephemeral redeploy.
- Phase 7 introduces TWO render variants: watermarked-standard-res (free) and
  clean-hi-res (paid). Both need durable storage.
- Uncapped paid re-renders need durable storage.

**Build:**
- [ ] Supabase Storage public bucket for renders.
- [ ] Add `render_url` column to `designs` table — the durable record of render
      fulfillment. Written via `save_design()` after successful render.
      **NOTE:** Phase 4's `generateMetadata()` checks render existence. When
      `render_url` lands in the design row, switch metadata to read existence
      from the design row (already fetched), NOT a HEAD probe to storage.
      Avoids a network round-trip to the bucket on every crawler hit.
- [ ] Public bucket URL = crawler-reachable OG image URL, fully decoupled from
      API server (Phase 6 auth/rate-limiting can never accidentally gate it).
- [ ] Migrate from local `StaticFiles` serving to Supabase Storage URLs.

### 7C — FTC / Amazon Associates Compliance (PRE-LAUNCH BLOCKER)

**Elevated to pre-launch review.** Affiliate is primary revenue — an Associates
ban is existential, not cosmetic.

- [ ] Visible "We earn from qualifying purchases" disclosure on result/buy pages.
- [ ] Price display rules compliance review.
- [ ] Image-use rules: confirm AI-composited renders using product images are
      compliant (or that renders use only style/mood, not actual product photos).
- [ ] Price freshness compliance (24h window already enforced in code).
- [ ] **ADD-ALL-TO-CART affiliate tag verification:** Cart-add button already
      exists (Phase 4 scope = verify, not build). Smoke-test can happen NOW:
      open a real cart-add URL, check Associates dashboard for attribution.
      Known risk: `tag` param vs `AssociateTag` param — Amazon docs are
      inconsistent on which creates an attribution session through the cart-add
      endpoint. If `gp/aws/cart/add.html` is fully deprecated in your region,
      fall back to individual buy links (already working, tag confirmed on each).

**Exit:** Revenue active (Stripe + Amazon affiliate). Render storage durable.
FTC + Associates compliant.

---

## Phase 8 — Deploy + Gate

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
- [ ] **Landing page:** "What is RoomKit" value-prop page before the quiz. Credibility
      + SEO + a place for share/SEO traffic to land.
- [ ] Product analytics (GA / Plausible) for traffic, referrers, channel/funnel analysis
      at scale (Supabase dashboard is internal-only).

**Exit:** Live site, reachable, account-gated, error handling solid.

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
- [ ] Amazon Associates compliance verified (see Phase 7D checklist).
- [ ] Add-all-to-cart: affiliate tag confirmed carrying through cart-add flow.
- [ ] Error handling / graceful degradation: pipeline fails mid-run, product out of
      stock, render timeout — all degrade gracefully, systematically tested.
- [ ] Mobile verification: full flow on actual phone (not just responsive preview).
- [ ] Confirm instrumentation captures data + dashboard shows it on live.
- [ ] Final quality + credibility pass: is the result genuinely share-worthy?

**Exit:** Launch-ready. Activate the viral share loop.

---

## Phase 11 — Multi-Retailer Expansion (post-launch)

*After launch, with real traffic data to satisfy aggregator requirements.*

### 11A — Affiliate Aggregator Integration
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

### 11B — Scale
- [ ] Cost-per-room optimization: cache LLM responses, reduce calls per design.
- [ ] Per-user rate limits (not just IP) for logged-in users.
- [ ] Throughput management as traffic grows.
- [ ] Formal access-control matrix (admin roles, operator accounts, partner API keys).
- [ ] DEFERRED: "Pro" subscription tier for realtors/STR hosts/designers. Only
      build if segment with validated WTP exists in usage data.

---

## Hard Gates (cannot be bypassed)

These are NON-NEGOTIABLE prerequisites for public deploy. They exist because
the product's cost structure ($0.37/room) creates unbounded financial exposure
without them.

| Gate | What it blocks | Why |
|---|---|---|
| Phase 6 Auth + Rate Limiting | ANY public deploy | $0.37/room uncapped to the internet without accounts + rate limits |
| Phase 6 Account Wall | Public access | Free-room limit unenforceable without accounts |
| Phase 7C Associates Compliance | Launch with affiliate links | Ban = revenue to zero; must verify before real traffic |
| Phase 10 Full Verification | Launch | Correctness gate — no silent failures in prod |

---

## Dependency Map

```
Phase 1  Browser verification
  ↓
Phase 2  Input validation + secrets audit ✓
  ↓
Phase 3  Persistent design storage ✓ ───────────────────┐
  ↓                                                      │
Phase 4  Viral share loop + add-all-to-cart (AUTH-READY) │
  ↓      + 4B Platform-adaptive visual layer             │
  ↓      Built locally. NOT publicly deployable yet.     │
  ↓                                                      │
Phase 5  Full audit + living room build                  │
  ↓                                                      │
Phase 6  Foundation layer (auth, RLS, tiers, rates) ─────┘
  ↓      ↑ HARD GATE: must complete before public deploy
  ↓      ↑ Enforces: free-room limit, tier gating, rate limiting
  ↓      ↑ Inserts into Phase 4's auth-ready seams
  ↓
Phase 7  Revenue activation (Stripe packs, render storage, compliance)
  ↓      ↑ requires auth from Phase 6
  ↓
Phase 8  Deploy + gate
  ↓      ↑ requires auth from Phase 6 (HARD GATE)
  ↓
Phase 9  Hardening + instrumentation (parallel with 8)
  ↓
Phase 10 Pre-launch verification (HARD GATE)
  ↓
Phase 11 Multi-retailer expansion + scale (POST-LAUNCH)
         ↑ Amazon-only at launch
         ↑ Add retailers via aggregator (Skimlinks/Sovrn) with real traffic data
```

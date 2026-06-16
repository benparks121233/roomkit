# RoomKit Launch Plan

Goal: Launch DEEP and credible — bedroom + living room, Amazon + 2 retailers, shareable,
dual-revenue (generation fee + affiliate). Depth > speed (founder decision, non-negotiable).
Target launch: [TBD]

## Cross-cutting
- [x] Instrumentation: selection + cost/conversion tracking (Supabase) + /admin dashboard — DONE
- [ ] Mobile polish (CROSS-CUTTING — most social/share traffic lands on phones; do before
      activating share loop). Guided flow, render viewer, product cards, payment, share — all
      must work well on mobile.
- [ ] Verify-in-browser discipline on every change (tests-green ≠ works)

## PHASE 0 — Foundation Fix (LAUNCH-BLOCKING, do first)
- [x] AESTHETIC BUG — VERIFIED WORKING. Deterministic path (style_service.py:62-76) locks
      style_name when core_aesthetic is present + valid. Live-tested 4 aesthetics (quiet_luxury,
      coastal, gamer_den, japandi) — all returned correct style_name with confidence=1.0,
      deterministic path confirmed via debug logs. The LLM fallback path only fires when
      core_aesthetic is None/empty (which doesn't happen from the quiz — the frontend always
      sends it). Kept clean info-level logging for production observability.
- [ ] VERIFY (already coded/tested — confirm in browser, don't rebuild): mattress present at
      low budget (floor $80), no decorative pillows in pillows slot, no plant stands in plants
      slot, quiet_luxury feels right.

## PHASE 1 — Full Audit & Check (+ desk/chair)
- [ ] Comprehensive end-to-end audit of current product across multiple aesthetics + budgets:
      selection quality, budget never-exceed, render correctness (all items present + correct),
      hotspots/links match selections, cart button, zoom, full-room display, instrumentation
      capturing data. Fix what it surfaces.
- [x] Add desk + desk_chair slots to bedroom: aesthetic-aware fetch, budget allocation (optional
      slots that actually get included), render layout + hotspot positions.
      DONE — desk, desk_chair, sconce, wallpaper, duvet_insert, duvet_cover all added.
      Taxonomy, price floors, density drops, fixtures, hotspots, frontend groups all wired.
      Survey-gated: new slots are density-dropped by default, activated when user opts in via
      quiz preferences. Contamination filters added for all new + existing slots.
- [x] **CANOPY CATALOG FETCHES — DONE.** Comprehensive per-aesthetic fetch executed:
      137 queries across 25 slots, 4,495 new products added. Catalog: 15,122 products / 30
      slots. Every bedroom slot has full per-aesthetic depth (per-aesthetic-family queries for
      warm_organic, dark_rich, polished, cozy_textured, expressive). All bedroom slots at 265+
      (desk 352, desk_chair 279, sconce 288, wallpaper 351, duvet_cover 291, duvet_insert 107
      — functional slot, depth sufficient). Existing bedroom slots backfilled for thin
      aesthetics (sports_den, jungle_oasis, ski_lodge gaps filled).
      **LIVING-ROOM TOP-UP NEEDED (Phase 3, not blocking):** 4 living-room slots came in
      thin: tv_stand (245), side_table (202), ottoman (195), bookshelf (188). ~7-8 follow-up
      queries when living-room phase begins.

## PHASE 2 — Viral Share Loop (BUILD now, ACTIVATE at launch)
  NOTE: The interactive room viewer (fullscreen, marquee zoom, hotspots) is already built — this
  phase is the SHARE layer on top of it. Do NOT drive traffic until product is deep + correct.
- [ ] "Share my room" mechanic on the result.
- [ ] Self-promoting "Made with RoomKit · [url]" mark on every render.
- [ ] Shareable URL → opens the interactive shoppable room (OG image / link preview for socials).
- [ ] Share targets: Pinterest (priority for home design), TikTok/IG, X.
- [ ] Click-to-design-your-own flow from a shared render.

## PHASE 3 — Living Room (BIGGEST BUILD) + start retailer apps in parallel
  NOTE: Architecture ~60% there (taxonomy preset, render layout, hotspot positions exist). The
  work is CATALOG + taste + tuning. Realistic estimate: 2-3 weeks. Scope below.
- [ ] Define/confirm living room slots (sofa, coffee_table, side_table, tv_stand, tv, armchair,
      bookshelf, ottoman, etc.).
- [ ] Deep catalog fetch across ALL aesthetics × all living-room slots (~130 slot×aesthetic
      cells, est. 500-1000 Canopy queries) + dedup + contamination filtering.
- [ ] Per-slot taste filtering, price floors, contamination filters (esp. sofas — huge taste/
      price range).
- [ ] Living-room budget weights (sofa ~30-40%, different from bedroom) in composition service.
- [ ] Test + tune living room render layout with real products (sofa/TV placement etc.).
- [ ] IN PARALLEL — START RETAILER APPLICATIONS NOW (external approval lead time): apply to
      Wayfair (via Commission Junction) + one more retailer.

## PHASE 4 — Retailer Integration (Wayfair + 1 more)
- [ ] Integrate approved retailers: API/feed, buy-link format, affiliate attribution.
- [ ] Catalog matching/dedup across retailers (or distinct products per retailer).
- [ ] Margin-aware routing: favor higher-margin in-stock option where fit/quality is equal.

## PHASE 5 — Dual Revenue (generation fee + affiliate)
- [ ] Generation fee / credits for the render: free trial (2-3 free) → pay. Gate AFTER the wow
      moment, never before.
- [ ] Payment + credit system (Stripe).
- [ ] Affiliate live (multi-retailer once Phase 4 done) — upside on top of fees.
- [ ] **FTC AFFILIATE DISCLOSURE (LAUNCH-BLOCKER, legal):** visible "We earn from qualifying
      purchases" disclosure on the result/buy pages. Required the moment affiliate links are live.

## PHASE 6 — Deploy + Gate (make it real)
- [ ] Buy domain.
- [ ] Deploy to a real host (reachable, not localhost).
- [ ] **RATE LIMITING (LAUNCH-BLOCKER, financial):** IP-based rate limiting on POST /design
      (~$0.27/run — unprotected = bot/abuse could rack up hundreds in API cost).
- [ ] **SILENT API-FAILURE HANDLING (LAUNCH-BLOCKER, reliability):** when selection LLM calls
      fail en masse (e.g. exhausted credits), the pipeline currently returns blank rooms with
      no error. Detect this and show a user-facing error + alert; never serve blank rooms in
      production.
- [ ] **Landing page:** "what is RoomKit" value-prop page before the quiz (credibility + SEO + a
      place for share/SEO traffic to land).
- [ ] Login gating — gate AFTER the render/wow moment, not before (protect funnel + data).
- [ ] Usage limits (cost control + login reason).
- [ ] Product analytics (GA / Plausible) for traffic, referrers, channel/funnel analysis at
      scale (the Supabase dashboard is internal-only).

## PHASE 7 — Pre-Launch Full Verification (on deployed site)
- [ ] End-to-end on the LIVE site: both rooms, multiple aesthetics, payment flow, share flow,
      affiliate links — all working.
- [ ] Error handling / graceful degradation: pipeline fails mid-run, product out of stock
      between selection + purchase, render timeout — all degrade gracefully, systematically tested.
- [ ] Confirm instrumentation captures data + dashboard shows it.
- [ ] Final quality + credibility pass — is the result genuinely share-worthy?

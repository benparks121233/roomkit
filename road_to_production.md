# Road to Production — RoomKit Pre-Beta Plan

Single source of truth for everything between "code works" and "50 beta users can use it safely." Every item has a priority, a file:line reference where applicable, and an owner (YOU = manual step, CODE = implementable).

**STATUS UPDATES:** This file is updated in the same commit as any code change that touches a tracked item. A pre-commit hook (`.githooks/pre-commit`) warns if files under `app/`, `services/`, `web/`, or `migrations/` are staged without `road_to_production.md`. The hook warns but does not block. After a fresh clone, run `git config core.hooksPath .githooks` to activate it.

**ID stability:** Item IDs use the format `P0-01`, `P1-07`, etc. IDs are permanent — when an item changes priority, it keeps its old ID so external references don't break. Do not reference bare numbers in commit messages or external notes; always use the full ID.

**Last updated:** 2026-07-15

## Business Model Reference

Affiliate revenue is the business. Packs ($4.99/5 rooms) are the abuse gate, not the revenue engine.

| Metric | Value | Confidence |
|---|---|---|
| Commission rate | **UNVERIFIED — assumed 4%** | Needs Table 1 of Amazon Commission Income Statement. All figures below are downstream of this number. |
| Revenue per converting user | $60–120 (at 4% on $1,500–3,000 rooms) | UNVERIFIED — downstream of commission rate |
| Amazon cookie window | 24h to cart + ~89 days to checkout | Verified (Amazon Associates docs) |
| Cost per design (free tier) | ~$0.36 | **ESTIMATED — UNMEASURED** (see P0-12) |
| Cost per design (paid tier) | ~$0.56 | **ESTIMATED — UNMEASURED** (see P0-12) |
| Pack price | $4.99 / 5 rooms = $1.00/room | Exact |
| Break-even | ~$9.50 attributed sale (at assumed 4%) | UNVERIFIED — downstream of commission rate |

Beta goal: 50 users, prove attribution works (affiliate tag → Amazon commission), get qualitative feedback on design quality. Revenue in beta is a signal, not a target.

### Cost Breakdown Per Design (ESTIMATED — UNMEASURED)

All figures below are formula-derived, not metered. Real per-model spend should be pulled from Anthropic Console usage / OpenAI usage, divided by design_completed count (62 designs as of 2026-07-14). See P0-12 for the fix.

| Component | Est. Cost | Notes |
|---|---|---|
| Style (Sonnet 4.6) | ~$0.02 | `services/style_service.py:40,41` — 1 call, 512 max tokens |
| Composition (Sonnet 4.6) | ~$0.03 | `services/composition_service.py:74,75` — 1 call, 512 max tokens |
| Selection (Haiku 4.5) | ~$0.21 | `services/selection_service.py:30,31` — N calls (1/slot, parallel), 2048 max output tokens, 80 candidates input each. Input tokens dominate cost — see note below. |
| Free render (gpt-image-1 medium) | ~$0.10 | `services/render_service.py:34` — 1536x1024 |
| Paid render (gpt-image-1 high) | ~$0.30 | `services/render_service.py:35` — 1536x1024 |

**Note on selection cost:** The ~$0.21 estimate cites "2048 max tokens" (output ceiling) as justification, but P2-01 claims cutting candidates 80→40 saves ~$0.07 — candidates are input. That implies input is ~$0.14 of the $0.21. The derivation conflated input and output cost. Actual split is unknown until usage logging (P0-12) lands.

---

## Priority Key

- **P0 — BLOCKING BETA:** Cannot invite users until this is done.
- **P1 — FIX BEFORE PUBLIC LAUNCH:** OK for 50 invite-only beta users, not OK for the internet.
- **P2 — NICE TO HAVE:** Track for later. Won't kill beta or launch.

---

## P0 — BLOCKING BETA

### P0-01. Inbound email forwarding
**Status:** NOT DONE
**Why:** Terms (`web/app/terms/page.tsx:206`) and Privacy (`web/app/privacy/page.tsx:176`) publicly name `legal@roomkit.studio` and `privacy@roomkit.studio` for contact/data-deletion requests. Resend is outbound-only SMTP — these addresses receive nothing. A privacy policy that names a dead email for data-deletion requests is a legal liability.
**Fix:** Set up ImprovMX (free tier) or Cloudflare Email Routing to forward `legal@` and `privacy@` to `ben14parks@gmail.com`. Takes 5 minutes + DNS TXT record.
**Owner:** YOU

### P0-02. Cost alerting on Anthropic + OpenAI
**Status:** NOT DONE
**Why:** At ~$0.38/design (estimated), a viral spike or abuse loop burns real money with zero notification. No spending caps exist on either provider dashboard.
**Fix:** Set hard monthly spending limits in both Anthropic and OpenAI dashboards. Set alert thresholds at $20/day and $200/month for beta.
**Owner:** YOU (dashboard settings)

### P0-03. Affiliate tag smoke-test
**Status:** VERIFIED (2026-07-15)
**Why:** Clicks confirmed in the Amazon Associates dashboard. The `tag=roomkitai-20` parameter creates attribution sessions.
**Owner:** YOU

### P0-04a. Beta onboarding mechanism
**Status:** NOT DONE
**Why:** Currently anyone can sign up at `/signup`. Need a gate so only invited users can generate designs.
**Fix (options):**
  - (a) Allowlist: check email against a list in Supabase before allowing design generation (simplest — but requires known emails, so mechanism choice depends on whether P0-04b produces emails or not)
  - (b) Invite codes: require a code at signup that maps to a batch (works without knowing emails in advance)
  - (c) Manual: just send 50 people the URL and rely on obscurity (bad but fast)
**Owner:** CODE (a or b) / YOU (c)
**Estimate:** ~2 hours for allowlist, ~4 hours for invite codes
**Note:** The mechanism can be built before the invite list is finalized — invite codes don't require known emails. But email allowlist does, so P0-04b's outcome determines whether option (a) is viable.

### P0-04b. Beta invite list composition
**Status:** UNSOLVED
**Why:** Amazon excludes purchases by friends, relatives, and associates from qualifying sales. If the invite list is seeded from my personal network, beta can succeed on every metric and still produce zero qualifying sales before the 180-day deadline. Need a named source of ~50 non-personal-network users.
**Owner:** YOU
**Depends on:** P0-09 (must know the deadline before knowing how urgent this is)

### P0-05. Customer support channel
**Status:** NOT DONE
**Why:** Beta users who hit issues have no way to reach you. Contact emails are dead (see P0-01). No in-app feedback mechanism.
**Fix:** Once email forwarding works (P0-01), the contact emails become the support channel. Optionally add a simple feedback form or link to a Google Form from the account page.
**Owner:** YOU + CODE
**Depends on:** P0-01

### P0-06. robots.txt
**Status:** NOT DONE
**Why:** No crawl directives. Google will index `/admin`, `/preview`, auth pages, and any other route.
**Fix:** Add `web/app/robots.ts` (Next.js convention) disallowing `/admin`, `/preview`, `/auth`, `/reset-password`, `/forgot-password`.
**Owner:** CODE

### P0-07. Refresh worker crashes every 6 hours
**Status:** DONE (d24c0b8, 2026-07-15)
**Why:** `services/refresh_worker.py:18` was raising `NotImplementedError("Stage 11")`. Railway's cron service executed this every 6h and crashed every time.
**Fix applied:** Replaced the `raise` with a no-op that logs "refresh worker: not yet implemented" and returns cleanly. This does NOT fix price freshness (P1-04) — the no-op just stops the crash loop.
**Owner:** CODE
**Ref:** `services/refresh_worker.py:19-20`

### P0-08. /click endpoint throws unhandled 500
**Status:** DONE (d24c0b8, 2026-07-15)
**Why:** `app/api/routes.py:1254-1256` was raising `NotImplementedError("Stage 10")`. Nothing in the frontend calls `/click` — all client-side tracking uses `/track`. This was an orphan stub.
**Fix applied:** Replaced the `raise` with `return {"status": "ok"}`. Also added `stash_failed` to `_ALLOWED_CLIENT_EVENTS` and wired `trackEvent("stash_failed")` in the design page stash else-branch. Events land with `run_id = ''` (orphan row, invisible to RLS reads, queryable via service key). This is acceptable — the event is a diagnostic signal, not user-facing data.
**Owner:** CODE
**Ref:** `app/api/routes.py:1255,1268`

### P0-09. Amazon Associates 180-day deadline
**Status:** UNKNOWN — application date not recorded
**Why:** Amazon closes Associates accounts that haven't referred 3 qualifying sales within 180 days of application. Self-purchases and purchases by friends, relatives, or associates are excluded and don't count. Application date is UNKNOWN.
**Fix:** (1) Find or estimate application date. (2) Calculate deadline. (3) Plan beta invite list composition — if the list is seeded from your personal network, those buyers may all be filtered as "associates" and none will count toward the 3-sale requirement.
**Owner:** YOU
**Blocks:** P0-04b (beta invite list composition)

### P0-10. Legal page placeholders visible to users
**Status:** NOT DONE
**Why:** Terms (`web/app/terms/page.tsx:10-11`) and Privacy (`web/app/privacy/page.tsx:10-11`) show `[PLACEHOLDER: Your Legal Entity Name]` and `[PLACEHOLDER: State]` in bold. Terms also has `[PLACEHOLDER: State]` and `[PLACEHOLDER: State/County]` for governing law (`web/app/terms/page.tsx:199-200`). Beta users reading the terms see unfinished legal text.
**Fix:** Fill in once LLC is filed. If launching beta before LLC: use "Ben Parks, sole proprietor" and "Illinois" as interim values.
**Owner:** YOU (decision) + CODE (fill in)
**Estimate:** ~15 minutes CODE (find-and-replace 4 placeholders across 2 files)
**Depends on:** P1-11 (LLC decision)

### P0-11. Signup + quiz completion tracking
**Status:** WON'T DO
**Why:** Redundant. `auth.users` already has `created_at` and `email_confirmed_at` for every signup — no event needed. Quiz→design drop-off is derivable from the `designs` table at 50-user beta scale. The events that matter already land: `pack_purchased` (7), `export_cart_clicked` (5), `design_completed` (62). Code for `signup_completed` and `quiz_completed` trackEvent calls is deployed but unverified — left in place (compiles, harmless).
**Owner:** N/A

### P0-12. Log real API usage per design (replaces cost formula)
**Status:** NOT DONE
**Why:** Current api_cost in design_completed events is a formula estimate (`0.012 * selection_count + 0.02`), not metered. Every cost figure in this document is ESTIMATED — UNMEASURED. Beta is the only real cost data we'll get. If this lands after beta, beta cost is unrecoverable.
**Fix:** Log `usage.input_tokens` and `usage.output_tokens` from every Anthropic/OpenAI API response into events. Replace the formula with real metered cost. Then: pull actual per-model spend from Anthropic Console / OpenAI usage for the last 30 days, divide by design_completed count (62 as of 2026-07-14), and update all cost figures in this file.
**Owner:** CODE
**Estimate:** ~2 hours (4 call sites to instrument, event schema addition, update api_cost formula)
**Ref:** `services/style_service.py:156-157`, `services/composition_service.py:649-650`, `services/selection_service.py:330-331`, `services/render_service.py:319`

### P0-13. Google OAuth signup doesn't show terms notice
**Status:** NOT DONE
**Why:** Email signup shows a terms checkbox, but "Continue with Google" bypasses it. Users who sign up via Google are never shown the terms. If the terms don't bind them, the liability cap, indemnification, and refund policy from the legal audit are void for every Google signup.
**Fix:** Add "By continuing, you agree to our Terms and Privacy Policy" text (with links) near the Google button on the signup page.
**Owner:** CODE
**Estimate:** ~15 minutes
**Ref:** `web/app/signup/page.tsx:133`

### P0-14. Stash else-branch proceeds to checkout on failure
**Status:** NOT DONE — AWAITING DECISION
**Why:** In `handleUpgrade` (`web/app/design/page.tsx:271-289`), the else branch (stash fails) fires `trackEvent("stash_failed")` but still calls `startCheckout()`. If the user pays $4.99 and returns from Stripe, their quiz answers are gone. They still have 5 room credits (pack is added by Stripe webhook, not decremented here), so no money is lost — but the UX is bad: user paid expecting to pick up where they left off, finds a blank quiz instead.
**Reachability:** UNVERIFIED. Code read suggests both `pendingResult` and `chosenMode` are always set before `hitFreeLimit` becomes true, but this analysis has not been validated by production data. The `stash_failed` tracking signal exists to verify — once migration 007 is run and the event can land, a period with zero `stash_failed` rows would confirm unreachability. Until then, treat as reachable.
**Refund policy gap:** The refund clause (`terms/page.tsx:72-81`) covers "design fails to generate due to a technical issue" — automatic credit restore. It does NOT cover "quiz answers lost before generation." No credit is consumed in this scenario so the refund path never triggers.
**Fix options:** (a) Bail with an error message if stash fails — don't redirect to Stripe. (b) Block is defensive; accept unreachability and add a regression test. Owner decides.
**Owner:** CODE (after decision)
**Ref:** `web/app/design/page.tsx:275-283`, `web/app/purchase/success/page.tsx:13-17,92-93`
**Depends on:** stash_failed event already lands with `run_id = ''` (d24c0b8). No migration needed — signal is live once code is pushed.

---

## P1 — FIX BEFORE PUBLIC LAUNCH

### P1-01. Error alerting (Sentry or equivalent)
**Status:** NOT DONE
**Why:** Errors are logged to stdout but nobody is notified. A broken pipeline silently eats pack credits. The re-credit path catches generation failures, but partial failures (render succeeds, sourcing returns garbage) go unnoticed.
**Fix:** Add Sentry (Python SDK for FastAPI, JS SDK for Next.js). Free tier covers beta volume.
**Owner:** CODE + YOU (Sentry account)

### P1-02. Free-tier denial-of-wallet attack
**Status:** PARTIALLY FIXED
**Why:** Each free design costs ~$0.37 (estimated). Resend SMTP removed the Supabase rate limit on signups, making throwaway-account abuse easier. Current rate limiting uses `X-Forwarded-For` which is client-settable — `rate_limit.py:11` takes `split(",")[0]` (leftmost = spoofable). Redis support exists (`rate_limit.py:15-22`, `storage_uri=_redis_url or "memory://"`) but REDIS_URL likely not set in Railway, so rate state resets on every deploy.
**What's done:** Rate limiting exists (`app/rate_limit.py`), free-room claim is atomic with advisory lock.
**What's not done:** (a) IP trust chain — change `rate_limit.py:11` to take rightmost trusted proxy IP instead of leftmost. (b) Daily global free-design cap as a spending ceiling. (c) Set REDIS_URL in Railway env to persist rate state across deploys.
**Ref:** `app/rate_limit.py:9-12`, `app/api/routes.py`
**Owner:** CODE (a, b) + YOU (c — Railway env var)

### P1-03. Uptime monitoring
**Status:** NOT DONE
**Why:** If Railway goes down or the health check fails, nobody knows until a user reports it.
**Fix:** Free uptime monitor (UptimeRobot, BetterStack) pinging `/health` every 5 minutes. Alert to email/SMS.
**Owner:** YOU

### P1-04. Price freshness
**Status:** NOT DONE
**Why:** Catalog products in `data/catalog/*.json` have no `fetched_at` timestamps. The snapshot service refresh is a stub. Prices shown to users have no date attribution. Acceptable risk at ~100 invite-only beta users — Amazon is unlikely to review a closed beta. Becomes blocking at public launch or at PA-API application (P1-07), whichever comes first — applying for PA-API invites Amazon to review the site, and undated prices are what they'd find.
**Fix:** (1) Populate `fetched_at` on all catalog entries. (2) Display the freshness date on every price. (3) Implement the real refresh worker (not the no-op from P0-07) to re-validate prices on a schedule.
**Owner:** CODE
**Ref:** `services/snapshot_service.py`, `context/freshness_policies.yaml`, `data/catalog/*.json`
**Depends on:** P0-07 real implementation (the no-op minimum fix does NOT populate fetched_at)
**Blocks:** P1-07 (PA-API application — do not apply until prices are dated)

### P1-05. Kill switch for design generation
**Status:** NOT DONE
**Why:** If the pipeline starts burning money or producing garbage, there's no way to disable design generation without a code deploy. A maintenance mode env var that returns 503 on `/design` would suffice.
**Fix:** Add `MAINTENANCE_MODE` env var check at the top of the design endpoint. Set in Railway dashboard to disable instantly.
**Owner:** CODE

### P1-06. user_id column migration for schema reproducibility
**Status:** VERIFIED WORKING — migration file needed (2026-07-14)
**Why:** Column EXISTS on both events and selections tables in live Supabase. 387 events and 800 selections have user_id populated. `tracking.py:69-70,133-134` conditionally sets user_id when present. But the column was added directly to the DB — not in any migration SQL file. Schema is not reproducible from migrations alone.
**Fix:** Add migration 006: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users(id)` to events and selections.
**Owner:** CODE (migration file only)

### P1-07. PA-API migration (Amazon compliance)
**Status:** NOT DONE
**Why:** Currently using Canopy (third-party) for product data. Amazon could view this as unauthorized. PA-API access requires ~10 qualifying sales. Applying for PA-API invites Amazon to review the site — price freshness (P1-04) must be clean before applying.
**Fix:** Generate 10 qualifying sales through beta, then apply for PA-API access and migrate the sourcing adapter.
**Owner:** YOU (sales) + CODE (adapter swap)
**Depends on:** P1-04 (price freshness must be compliant before application invites Amazon review)

### P1-08. AI render + Amazon product imagery risk
**Status:** AT RISK — no fix, just awareness
**Why:** `render_service.py:272` downloads Amazon product images to compose AI renders. The render contains AI-recomposed versions of Amazon products. Amazon's Operating Agreement prohibits modifying Product Advertising Content. This is a gray area — we're not displaying their images directly, but creating new imagery informed by their products.
**Mitigation:** Renders are labeled as AI visualizations, not product photos. Risk is low at beta scale, increases with virality. Fallback: text-only render prompts (describe products instead of feeding photos).
**Ref:** `services/render_service.py:254-283`

### P1-09. Accessibility basics
**Status:** NOT DONE
**Why:** No skip-nav, no ARIA labels, no keyboard navigation testing. Not a beta blocker for 50 users, but legally required for public launch (ADA).
**Fix:** Add skip-nav link, ARIA labels on interactive elements, test keyboard flow through quiz → design → result.
**Owner:** CODE

### P1-10. Database backup confirmation
**Status:** UNKNOWN
**Why:** Supabase Pro plan includes daily backups + point-in-time recovery. Free plan has no backups. If on Free plan, a bad migration or data corruption is unrecoverable.
**Fix:** Confirm Supabase plan tier. If Free, upgrade to Pro ($25/mo) before beta with real user data.
**Owner:** YOU

### P1-11. LLC decision
**Status:** UNMADE
**Why:** Terms/Privacy have entity name placeholders. Illinois LLC: $150 standard (1-3 business days) or $250 expedited (24-hour processing) online at ilsos.gov. Wyoming: $100 + $60/yr but requires registered agent ($50-100/yr) since you're in Illinois. Illinois is simpler for a solo founder who lives there.
**Impact:** Blocking legal page completion (P0-10). NOT blocking beta if you use "sole proprietor" as interim. However: an LLC formed later does not retroactively cover conduct during a sole-prop beta — personal liability applies to everything before the LLC exists.
**Expedited path:** Illinois 24-hour processing excludes weekends and holidays. Filing on a business day (e.g. today, Wed Jul 15) means the entity exists Thursday and P0-10 fills in the real LLC name with no sole-prop interim. Filing over the weekend means the clock starts Monday and the entity exists Tuesday — mid pre-beta week, not before it.
**Owner:** YOU

### P1-12. Flaky test: test_valid_single_select
**Status:** INTERMITTENT FAILURE
**Why:** `tests/test_api.py::TestValidateSelections::test_valid_single_select` fails intermittently. Cannot reproduce consistently (556/556 x3 passed). Added diagnostic output. A flaky test trains you to ignore a red suite, which masks real failures.
**Fix:** Investigate root cause using diagnostic output on next failure. May be a timing issue or test isolation problem.
**Owner:** CODE
**Ref:** `tests/test_api.py` (TestValidateSelections class)

### P1-13. Assembly service not implemented
**Status:** STUB ONLY
**Why:** `services/assembly_service.py:12` raises `NotImplementedError("Stage 9")`. The final board assembly (snapshot freeze, running total computation) is handled inline in routes.py instead of through the proper service.
**Fix:** Low priority — current inline approach works. Implement when refactoring the pipeline.
**Owner:** CODE
**Ref:** `services/assembly_service.py:12`

### P1-14. Frontend hotspot click tracking
**Status:** NOT DONE — BLOCKED (no hotspot UI exists)
**Why:** `HOTSPOT_POSITIONS` is defined in `web/lib/api.ts:379-421` (bedroom + living_room layouts) and `hotspot_clicked` is in `_ALLOWED_CLIENT_EVENTS` (`routes.py:1274`), but no component in the frontend renders the hotspot overlay on the image. The positions data exists; the UI that uses it doesn't. This isn't "wire up a trackEvent call" — the entire hotspot render overlay component needs to be built first, then tracking is one line.
**Fix:** (1) Build hotspot overlay component. (2) Add `trackEvent(runId, "hotspot_clicked", { slot_id, product_id })` in click handler.
**Owner:** CODE
**Ref:** `web/lib/api.ts:379-421` (positions), `web/app/result/[run_id]/page.tsx` (no hotspot component exists)

### P1-15. JWT error verbosity
**Status:** KNOWN ISSUE
**Why:** `app/auth.py:90` returns `f"Invalid token: {e}"` and line 92 returns `f"Token verification failed: {e}"` — these forward raw exception messages to the client, leaking JWT validation internals (algorithm, claim names, key details) that help attackers craft better attacks.
**Fix:** Replace lines 88-92 with generic `raise HTTPException(401, "Authentication failed")`. Log the real error server-side.
**Owner:** CODE
**Ref:** `app/auth.py:88-92`

---

## P2 — NICE TO HAVE

### P2-01. Reduce _MAX_CANDIDATES (cost optimization)
**Status:** NOT DONE
**Why:** Selection service sends up to 80 candidates per slot to Haiku. Reducing to 40 would reduce input tokens per slot. Estimated savings ~$0.07/design but this is UNMEASURED — actual savings depend on real input token cost (see P0-12). Contamination filters already cull heavily.
**Fix:** Change `_MAX_CANDIDATES = 80` to `40` in `services/sourcing/amazon_adapter.py:37`. Measure impact via P0-12 before and after.
**Owner:** CODE
**Depends on:** P0-12 (measure before cutting, or the savings claim is unverifiable)

### P2-02. Batch invisible slot selections
**Status:** NOT DONE
**Why:** Mattress, duvet_insert, sheets are never visible in renders. Each gets its own Haiku call. Batching into 1 call would save estimated ~$0.02/design (UNMEASURED — see P0-12).
**Owner:** CODE

### P2-03. Cache style interpretation
**Status:** NOT DONE
**Why:** Same quiz answers always produce the same style. Caching could skip the Sonnet call (estimated ~$0.02 saved, UNMEASURED — see P0-12) for repeated combos.
**Owner:** CODE

### P2-04. Frontend analytics
**Status:** NOT DONE
**Why:** No page views, session tracking, or bounce rate data. PostHog or Plausible would cover this without GA's privacy baggage.
**Owner:** CODE + YOU

### P2-05. Secret rotation plan
**Status:** NO PLAN
**Why:** ADMIN_SECRET, Supabase keys, Anthropic/OpenAI API keys have no rotation cadence. Not a beta risk, but should be documented before public launch.
**Owner:** YOU

### P2-06. Cookie consent (GDPR)
**Status:** NOT NEEDED FOR BETA (probably)
**Why:** Current cookies are Supabase auth session cookies only — exempt under most ePrivacy frameworks as "strictly necessary." If EU users join beta, confirm this interpretation.
**Owner:** YOU

### P2-07. Sitemap
**Status:** NOT DONE
**Why:** No sitemap.xml for SEO. Not needed for beta (invite-only), useful for public launch.
**Owner:** CODE

### P2-08. Admin secret in query param
**Status:** KNOWN ISSUE
**Why:** Admin dashboard passes ADMIN_SECRET as a query parameter (`app/api/admin.py:19-23`), which appears in server logs and browser history. Comment on line 3 explicitly says "query param."
**Fix:** Switch `_check_auth` to read from `Authorization` header instead of query param. Update frontend admin dashboard to send header.
**Owner:** CODE
**Ref:** `app/api/admin.py:3,19-23`

### P2-09. ADMIN_SECRET mismatch between environments
**Status:** KNOWN ISSUE
**Why:** Backend `.env` and frontend `web/.env.local` have different ADMIN_SECRET values. The admin dashboard (frontend) sends one secret; the backend checks another. Dashboard auth fails silently.
**Fix:** Sync the ADMIN_SECRET value across both env files. Rotate after sync since the old value may be in shell history.
**Owner:** YOU
**Ref:** `app/api/admin.py:16`, `web/.env.local`

### P2-10. Prompt injection surface
**Status:** KNOWN RISK
**Why:** User-provided text (room description, interests) flows into LLM prompts. The pipeline is designed so LLM output never controls money/links (deterministic validators catch that), but a crafted input could produce unexpected style/composition results.
**Mitigation:** Validators are the safety net. Input validation constrains field lengths. Risk is aesthetic, not financial.
**Owner:** CODE (input sanitization improvements)

---

## Security Audit Items (from 2026-07-14 audit)

These were found and FIXED in the security audit:

- [x] Cache IDOR — `app/api/routes.py:76`: now denies access when user_id missing or mismatched
- [x] Render semaphore fail-open → fail-closed — `app/api/routes.py:841`: now raises 503 instead of proceeding
- [x] list_designs switched to RLS-enforced reads — `app/api/routes.py:556`: uses `get_user_postgrest()` now
- [x] Open redirect in auth callback — `web/app/auth/callback/route.ts`: validates `next` starts with `/` and not `//`
- [x] Stripe redirect URL override — `app/api/stripe_routes.py`: hardcoded server-side, ignores client input
- [x] Security headers — `app/main.py:63-70` and `web/next.config.js:13-23`: X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- [x] CORS restricted — `app/main.py:51-56`: explicit methods and headers
- [x] RLS policies — `migrations/005_rls_policies.sql`: SELECT-only, no INSERT/UPDATE via anon key

---

## Amazon Compliance Summary

| Area | Status | Detail |
|---|---|---|
| Affiliate tag | COMPLIANT | Injected into all buy_urls + cart URL |
| Affiliate attribution | VERIFIED | Smoke-test passed — clicks confirmed in Associates dashboard (P0-03) |
| Price display | NON-COMPLIANT | No `fetched_at` timestamps, no date shown. Tracked as P1-04 |
| Affiliate disclosure | COMPLIANT | FTC-adequate in Terms |
| Add-all-to-cart | COMPLIANT | Uses official Amazon cart-add URL. Smoke-tested (P0-03) |
| 180-day qualifying sales | UNKNOWN | 3 sales required within 180 days or account closes. Tracked as P0-09 |
| Commission rate | UNVERIFIED | Assumed 4% — needs Table 1 of Commission Income Statement |
| Canopy data source | AT RISK | Not PA-API. Tracked as P1-07 |
| AI renders with product images | AT RISK | Gray area. Tracked as P1-08 |
| Mobile app | NOT YET APPLICABLE | Hard gate before any app work |
| UGC shared renders | AT RISK | Increases with scale. Monitor |
| AI/ML clause | SCOPED | Applies to PA-API + training/fine-tuning, not third-party inference. Current Canopy sourcing sidesteps API-specific restrictions but not content-level clauses |

---

## Cosmetic / Feel Audit (2026-07-14)

Items beta users will notice. Ranked by impact.

### C-01. console.log debug lines in production
**Status:** DONE (d24c0b8, 2026-07-15)
**Why:** 4 `console.log("[STASH]...")` debug statements were firing in the upgrade flow. Beta users who opened dev tools saw debug noise.
**Fix applied:** Deleted the 4 debug lines. The console.warn in the else branch was preserved as a proper `trackEvent("stash_failed")` signal.
**Owner:** CODE
**Ref:** `web/app/design/page.tsx`
**Severity:** JANKY — 1 minute fix

### C-02. Terms/Privacy pages off-brand + no nav
**Status:** NOT DONE
**Why:** Both pages use hardcoded inline styles with colors that don't match design tokens (`#f8f7f4` vs `--color-bg: #FAF8F5`, `#444` vs `--color-text-secondary`, `#1a1a1a` vs `--color-text`). Neither page is wrapped in SiteShell — no nav bar, no footer, just a "Back to RoomKit" link. Feels like a different site.
**Fix:** Move to CSS classes using design tokens. Wrap in SiteShell layout.
**Owner:** CODE
**Ref:** `web/app/terms/page.tsx:231,248,262,267,277,283`, `web/app/privacy/page.tsx:201,218,237`
**Severity:** JANKY

### C-03. Auth pages hide nav, show text not logo
**Status:** NOT DONE
**Why:** Login and signup pages use `min-height: 100vh` which pushes SiteShell nav out of view. Title is `<h1>RoomKit</h1>` in plain serif text instead of the wordmark logo. Brand continuity breaks.
**Fix:** Remove `min-height: 100vh` or restructure so nav is visible. Replace text title with logo image.
**Owner:** CODE
**Ref:** `web/app/login/page.tsx:62`, `web/app/signup/page.tsx:87`, `web/styles/globals.css:3139`
**Severity:** JANKY

### C-04. Google OAuth button has no icon, "or" divider has no lines
**Status:** NOT DONE
**Why:** "Continue with Google" is plain text with no G logo — reduces trust. The "or" divider between email/OAuth has no horizontal rule lines, just the word "or" floating.
**Fix:** Add Google G SVG icon. Add `::before`/`::after` pseudo-element lines to `.auth-divider`.
**Owner:** CODE
**Ref:** `web/app/login/page.tsx:96`, `web/app/signup/page.tsx:133`, `web/styles/globals.css:3231-3243`
**Severity:** JANKY

### C-05. Account page missing pack balance
**Status:** NOT DONE
**Why:** Nav shows "X rooms left" pill, but the account page only shows email, sign out, and delete. No pack balance, purchase history, or buy-more link. Users will look here to manage their pack.
**Fix:** Add pack balance display, link to /design for buy-more.
**Owner:** CODE
**Ref:** `web/app/account/page.tsx:72-143`
**Severity:** JANKY

### C-06. No OG image or Twitter card metadata
**Status:** NOT DONE
**Why:** `layout.tsx` has bare-minimum metadata. Shared links on social media show no image, no site name — looks like spam.
**Fix:** Add OG image (render example or logo), Twitter card meta, site name to metadata export.
**Owner:** CODE + YOU (create OG image)
**Ref:** `web/app/layout.tsx:6-9`
**Severity:** JANKY

### C-07. Landing page shopping mockup has empty gray boxes
**Status:** NOT DONE
**Why:** Step 3 "how it works" shows product cards with empty gray `<div>` placeholders instead of product images. The most important selling mockup looks unfinished.
**Fix:** Add sample product images to the mockup cards.
**Owner:** CODE + YOU (images)
**Ref:** `web/app/page.tsx:240`, `web/styles/globals.css:3841-3844`
**Severity:** JANKY

### ~~C-08~~ → Reclassified as P0-13. See P0 section.

---

## Tier / Sequence Conflicts

P1 items scheduled pre-beta. Listed only — not resolved. Will decide after P0-09 deadline is known.

| ID | Label | Scheduled | Conflict |
|---|---|---|---|
| P1-01 | P1 | Pre-beta week (bigger items) | Sentry scheduled pre-beta but labeled P1 |
| P1-05 | P1 | Pre-beta week | Kill switch scheduled pre-beta but labeled P1 |
| P1-11 | P1 | Weekend | LLC filing scheduled pre-beta but labeled P1 |
| P1-15 | P1 | Pre-beta week | JWT error verbosity scheduled pre-beta but labeled P1 |

---

## Beta Launch Gate (PROPOSED — needs approval)

Invites do not go out until every item below is DONE. This is the proposed gate — approve, modify, or reject.

**Hard gates (all P0, non-negotiable):**
- [ ] P0-01 — Inbound email forwarding (legal@ and privacy@ receive mail)
- [ ] P0-02 — Cost alerting (spending caps set on Anthropic + OpenAI)
- [ ] P0-04a — Beta onboarding mechanism (gate exists in code)
- [ ] P0-04b — Beta invite list composition (named list of ~50 users)
- [ ] P0-06 — robots.txt (admin/preview/auth not indexed)
- [x] P0-07 — Refresh worker no-op (crash loop stopped) — d24c0b8
- [x] P0-08 — /click endpoint no-op or deleted (500 eliminated) — d24c0b8
- [ ] P0-09 — Amazon 180-day deadline known (application date found, deadline calculated)
- [ ] P0-10 — Legal page placeholders filled (sole prop or LLC)
- [ ] P0-12 — API usage logging live (beta cost measurable)
- [ ] P0-13 — Google OAuth terms notice (terms must bind all signups or liability cap/indemnification/refund policy are void)
- [ ] P0-14 — Stash else-branch proceeds to checkout on failure (reachability UNVERIFIED, unguarded payment path)

**Status: 2 of 12 hard gates done.**

**Recommended additions from P1 (your call):**
- [ ] P1-05 — Kill switch (ability to disable /design without a deploy — if the pipeline breaks during beta, you're stuck until you push a fix)

**Explicitly NOT gated:**
- P0-03 — Already VERIFIED (not a gate — already passed)
- P0-05 — Support channel resolves automatically once P0-01 lands
- P1-01 (Sentry), P1-15 (JWT), P1-11 (LLC) — useful pre-beta but not gates
- All cosmetic items — polish, not safety

---

## Sequencing Recommendation

**Do these first (weekend — all manual or 1-minute fixes):**
1. Email forwarding (P0-01) — 5 minutes, DNS TXT record
2. Cost alerts (P0-02) — 10 minutes, dashboard settings
3. Find Amazon Associates application date (P0-09) — check email/dashboard
4. ~~Delete console.log debug lines (C-01)~~ — DONE (d24c0b8)
5. LLC filing (P1-11) — $150 standard (1-3 days) or $250 expedited (24h, business days only). If filed today (Wed): entity exists Thu, P0-10 uses real LLC name. If filed weekend: entity exists Tue.
6. Start thinking about invite list composition (P0-04b) — who are the 50 people?

**Then (pre-beta week — code changes):**
7. robots.txt (P0-06) — 5 minutes
8. ~~Refresh worker no-op (P0-07)~~ — DONE (d24c0b8)
9. ~~/click endpoint: delete or no-op (P0-08)~~ — DONE (d24c0b8)
10. Legal placeholders fill (P0-10) — ~15 minutes, sole prop or LLC name depending on #5
11. ~~Signup + quiz tracking (P0-11)~~ — WON'T DO (redundant with auth.users + designs table)
12. API usage logging (P0-12) — ~2 hours, 4 call sites + event schema
13. Beta onboarding mechanism (P0-04a) — ~2 hours allowlist / ~4 hours invite codes
14. Kill switch (P1-05) — MAINTENANCE_MODE env var
15. JWT error verbosity (P1-15) — 5 minutes
16. Auth pages: logo + nav fix (C-03) — 30 minutes
17. Google OAuth icon (C-04) + terms notice (P0-13) — 30 minutes
18. OG image metadata (C-06) — 15 minutes

**Then (pre-beta week — bigger items):**
19. Error alerting with Sentry (P1-01) — 2 hours
20. Terms/Privacy design token fix + SiteShell wrap (C-02) — 1 hour
21. Account page pack balance (C-05) — 1 hour

**Can follow beta launch:**
- Free-tier denial-of-wallet hardening (P1-02)
- Uptime monitoring (P1-03)
- Price freshness (P1-04) — must complete before PA-API application (P1-07)
- PA-API migration (P1-07) — blocked by P1-04
- Hotspot overlay UI + tracking (P1-14) — component doesn't exist yet
- Accessibility (P1-09)
- All P2 items

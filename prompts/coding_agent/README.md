# prompts/coding_agent/

Saved Claude Code prompts for common implementation tasks (Appendix D of the build packet).
Copy-paste these into a Claude Code session rather than writing prompts from scratch.

---

## 1. Repo understanding (run before any change)

```
Before changing anything, inspect this repo and explain in plain English:
1) what it currently does, 2) where intake, style, composition, selection, sourcing, snapshot,
render, assembly, validation, and refresh live, 3) the safest insertion point for [feature],
4) which rules are deterministic vs prompt-driven, 5) which missing artifacts would make you
more reliable here. Do not edit. End with a short plan.
```

---

## 2. Scaffold

```
Create the workflow-first RoomKit scaffold: Next.js web app in web/, FastAPI engine in app/+services/,
typed schemas, validators (budget/spec/price_link/composition), context files, evals, tests, Railway
service defs. Folders + stubs + plain-English ownership comments only. No business logic yet.
```

---

## 3. Composition + budget enforcement

```
Implement only composition planning: StyleProfile + budget -> SlotPlan. The LLM proposes slot weights;
code MUST clamp and re-normalize so the total never exceeds budget, and MUST ensure the room preset's
required slots are present. Add tests for over-budget rejection and missing required slots. Explain each file.
```

---

## 4. Amazon sourcing adapter

```
Implement only the Amazon adapter behind SourcingAdapter (base.py), using [curated list / product-data API].
Every product returned MUST carry normalized_price, a live buy_url, specs, and the affiliate tag.
Freeze the interface. Add tests for missing price, dead link, missing tag, and no-spec-match. Explain assumptions.
```

---

## 5. Snapshot + validation

```
Implement product snapshotting and deterministic validation. Snapshot the chosen products/prices/urls with a
timestamp BEFORE validation; a stored design must reference its snapshot, never live data. Then run budget,
spec, freshness, link, and tag validators; block invalid items. Add idempotency tests (re-run does not mutate a
snapshot) and tests that a stored design reads from its snapshot. Explain trade-offs.
```

---

## 6. Refresh worker

```
Implement the locked cron refresh worker: re-validate active designs' product prices/links on the freshness
schedule, flip dead links, update freshness. It MUST run under a lock (no double-run), be idempotent, never run
in the request path, and never corrupt a stored design's snapshot. Add tests for the lock, idempotency, and dead-link handling.
```

---

## 7. Debugging a failing fixture

```
Given this failing fixture and validator output, classify the failure: bad style interpretation, over-budget
allocation, missing spec, stale price, dead link, missing tag, snapshot/idempotency, or lock/concurrency.
Propose the smallest fix, name the files to change, and say why that layer is the right one.
```

---

## 8. Refactor

```
Map current ownership of composition, selection, snapshot, validation, and refresh. Propose the least disruptive
refactor that keeps budget/link/tag/freshness logic OUT of prompts and inside validators. Do not implement until
you explain what changes, why, what might break, and how to test it.
```

---

## 9. Test expansion

```
Extend tests for: over-budget board, missing bed_size, missing screen_size, stale price, dead link, missing tag,
missing required slot, snapshot immutability, refresh-worker lock + idempotency. Run them; summarize failures;
patch the smallest layer.
```

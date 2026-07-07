"use client";

// Result page — two-phase experience:
//   Phase 1: Guided slot-by-slot selection (pick from alternatives)
//            Single-select slots: pick one, auto-advance.
//            Multi-select slots (wall_art/plants/throw_blanket): pick up to N,
//            pool meter tracks budget, Done button advances.
//   Phase 2: Final room page (product cards + budget meter + swap/gallery)
//
// Slot ordering follows taxonomy groups so the room "builds" naturally:
//   Bedroom: bed → storage → lighting → decor → soft_goods
//   Living room: seating → entertainment → tables → lighting → decor → soft_goods

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams, useSearchParams } from "next/navigation";
import { getDesign, validateSelections, generateRender, checkRenderStatus, RenderTimeoutError, finalizeDesign, trackEvent, API_BASE } from "@/lib/api";
import type { DesignResponse, ProductResult, SlotResult } from "@/lib/api";
import ShareButton from "@/components/ShareButton";
import SlotPicker from "@/components/SlotPicker";
import ProductCard from "@/components/ProductCard";
import BudgetMeter from "@/components/BudgetMeter";
import InteractiveRoomRender from "@/components/InteractiveRoomRender";
import Image from "next/image";
import RoomSoFar from "@/components/RoomSoFar";

function formatPriceDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Taxonomy group ordering — mirrors slot_taxonomy.yaml
// ---------------------------------------------------------------------------

interface GroupDef {
  key: string;
  label: string;
  slotIds: string[];
}

// Room-type-keyed aesthetic display names (internal key → user-facing label)
const AESTHETIC_LABELS: Record<string, Record<string, string>> = {
  bedroom: {
    cottagecore: "Cottagecore", dark_academia: "Dark Academia", japandi: "Japandi",
    coastal: "Coastal", industrial: "Industrial", quiet_luxury: "Quiet Luxury",
    sports_den: "Sports Den", city_modern: "City Modern", ski_lodge: "Ski Lodge",
    jungle_oasis: "Jungle Oasis", gamer_den: "Gamer Den", poster_maximalist: "Poster Maximalist",
    warm_minimalist: "Warm Minimalist",
  },
  living_room: {
    cottagecore: "Country Parlor", dark_academia: "Library Lounge", japandi: "Still Room",
    coastal: "Shore House", industrial: "Warehouse Loft", quiet_luxury: "The Salon",
    sports_den: "The Den", city_modern: "High Rise", ski_lodge: "Fireside",
    jungle_oasis: "Greenhouse", gamer_den: "Command Center", poster_maximalist: "The Gallery",
    warm_minimalist: "Warm Minimalist",
  },
};

const BEDROOM_GROUPS: GroupDef[] = [
  { key: "bed", label: "Bed", slotIds: ["bed_frame", "mattress", "sheets", "comforter", "duvet_insert", "duvet_cover", "pillows"] },
  { key: "storage", label: "Storage & Workspace", slotIds: ["nightstand", "dresser", "desk", "desk_chair"] },
  { key: "lighting", label: "Lighting", slotIds: ["ceiling_light", "table_lamp", "floor_lamp", "sconce"] },
  { key: "decor", label: "Decor", slotIds: ["wall_art", "plants", "mirror"] },
  { key: "soft_goods", label: "Soft Goods", slotIds: ["rug", "curtains", "throw_blanket"] },
];

const LIVING_ROOM_GROUPS: GroupDef[] = [
  { key: "seating", label: "Seating", slotIds: ["sofa", "armchair"] },
  { key: "entertainment", label: "Entertainment", slotIds: ["tv", "tv_stand", "tv_mount"] },
  { key: "tables", label: "Tables", slotIds: ["coffee_table", "side_table"] },
  { key: "lighting", label: "Lighting", slotIds: ["ceiling_light", "floor_lamp", "table_lamp"] },
  { key: "decor", label: "Decor", slotIds: ["wall_art", "plants", "bookshelf"] },
  { key: "soft_goods", label: "Soft Goods", slotIds: ["rug", "curtains", "throw_pillows", "throw_blanket"] },
];

const ROOM_GROUPS: Record<string, GroupDef[]> = {
  bedroom: BEDROOM_GROUPS,
  living_room: LIVING_ROOM_GROUPS,
};

function getOrderedSlotIds(roomType: string): string[] {
  const groups = ROOM_GROUPS[roomType] ?? BEDROOM_GROUPS;
  return groups.flatMap((g) => g.slotIds);
}

function getGroupForSlot(slotId: string, roomType: string): GroupDef | null {
  const groups = ROOM_GROUPS[roomType] ?? BEDROOM_GROUPS;
  return groups.find((g) => g.slotIds.includes(slotId)) ?? null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Decor/accessory slots show fewer options (4) so the page isn't overwhelming.
// Anchor furniture slots show the full list.
// Per-slot display caps — upper bound on listings shown (not selection limit).
// Selection limit is max_quantity on the slot (separate concern).
const _DISPLAY_CAPS: Record<string, number> = {
  wall_art: 24,
  plants: 18,
  mirror: 18,
  throw_blanket: 12,
};

function getChoicesForSlot(slot: SlotResult): ProductResult[] {
  if (!slot.product) return [];
  const all = [slot.product, ...slot.alternatives];
  const cap = _DISPLAY_CAPS[slot.slot_id];
  return cap ? all.slice(0, cap) : all;
}

function upgradeAmazonImage(url: string): string {
  return url.replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL800_.");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ResultPage() {
  const params = useParams<{ run_id: string }>();
  const searchParams = useSearchParams();
  const runId = params.run_id;
  const isAutoMode = searchParams.get("mode") === "auto";

  const [design, setDesign] = useState<DesignResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Selection state — always arrays (length 1 for single-select slots)
  const [phase, setPhase] = useState<"selecting" | "complete">("selecting");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selections, setSelections] = useState<Record<string, ProductResult[]>>({});
  // Validation runs silently — errors logged to console, never shown to user.
  const validationRan = useRef(false);
  const [skippedSlots, setSkippedSlots] = useState<Set<string>>(new Set());
  const [furthestIndex, setFurthestIndex] = useState(0);
  const [overBudgetProduct, setOverBudgetProduct] = useState<ProductResult | null>(null);

  // Finalized state — true once selections are frozen and persisted.
  const [isFinalized, setIsFinalized] = useState(false);

  // AI render state
  const [renderUrl, setRenderUrl] = useState<string | null>(null);
  const [renderLoading, setRenderLoading] = useState(false);
  const [renderFailed, setRenderFailed] = useState(false);
  const [renderTimedOut, setRenderTimedOut] = useState(false);
  const [timeoutJobId, setTimeoutJobId] = useState<string | null>(null);
  const [checkingAgain, setCheckingAgain] = useState(false);

  // Persist curated selections to server. Called at every path to phase="complete".
  const persistFinalize = useCallback(
    (finalSelections: Record<string, ProductResult[]>, finalSkipped: Set<string>) => {
      if (!runId) return;
      const selectionIds: Record<string, string[]> = {};
      for (const [slotId, products] of Object.entries(finalSelections)) {
        selectionIds[slotId] = products.map((p) => p.product_id);
      }
      finalizeDesign(runId, selectionIds, Array.from(finalSkipped))
        .then((updated) => {
          if (updated) {
            setDesign(updated);
          }
          // null = 409 (already finalized) — still mark as finalized locally
          setIsFinalized(true);
        })
        .catch((err) => {
          console.error("Finalize failed:", err);
        });
    },
    [runId],
  );

  // Fetch design
  useEffect(() => {
    if (!runId) return;
    getDesign(runId)
      .then(setDesign)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load design"),
      );
  }, [runId]);

  // Reload seeding: if design is already finalized ON INITIAL LOAD, restore
  // selections from persisted selected_products and jump to complete (read-only).
  // Only runs once on the first design fetch — NOT on setDesign(updated) from
  // persistFinalize, which would re-run this effect and cause a state cascade
  // that can interfere with the render display.
  const reloadApplied = useRef(false);
  const isInitialLoad = useRef(true);
  useEffect(() => {
    if (!design || reloadApplied.current) return;
    if (!isInitialLoad.current) return;
    isInitialLoad.current = false;
    if (design.finalized_at) {
      reloadApplied.current = true;
      const restored: Record<string, ProductResult[]> = {};
      for (const slot of design.slots) {
        if (slot.selected_products && slot.selected_products.length > 0) {
          restored[slot.slot_id] = slot.selected_products;
        }
      }
      setSelections(restored);
      setIsFinalized(true);
      setPhase("complete");
    }
  }, [design]);

  // Auto mode: skip guided selection, fill all defaults, jump to complete
  const autoModeApplied = useRef(false);
  useEffect(() => {
    if (isAutoMode && design && !autoModeApplied.current && !design.finalized_at) {
      autoModeApplied.current = true;
      // Fill all slots with up to max_quantity defaults (rank-1 + top alternatives)
      const defaults: Record<string, ProductResult[]> = {};
      for (const slot of design.slots) {
        if (slot.product) {
          const qty = slot.max_quantity ?? 1;
          const all = [slot.product, ...slot.alternatives];
          defaults[slot.slot_id] = all.slice(0, qty);
        }
      }
      setSelections(defaults);
      setPhase("complete");
      persistFinalize(defaults, new Set());
    }
  }, [isAutoMode, design, persistFinalize]);

  // Build ordered active slot IDs (slots with products, in taxonomy order)
  const activeSlotIds = useMemo(() => {
    if (!design?.slots) return [];
    const ordered = getOrderedSlotIds(design.room_type);
    const sMap = new Map(design.slots.map((s) => [s.slot_id, s]));
    return ordered.filter((id) => {
      const slot = sMap.get(id);
      return slot && slot.product !== null;
    });
  }, [design]);

  const slotMap = useMemo(() => {
    if (!design?.slots) return new Map<string, SlotResult>();
    return new Map(design.slots.map((s) => [s.slot_id, s]));
  }, [design]);

  // Fill rank-1 defaults for un-visited slots (called on skip or flow completion).
  // Skipped slots (user chose "I don't want this") are excluded — no default fill.
  const fillDefaults = useCallback(
    (prev: Record<string, ProductResult[]>) => {
      const filled = { ...prev };
      for (const id of activeSlotIds) {
        if (skippedSlots.has(id)) continue;
        if (filled[id] && filled[id].length > 0) continue;
        const slot = slotMap.get(id);
        if (slot?.product) {
          const qty = slot.max_quantity ?? 1;
          const all = [slot.product, ...slot.alternatives];
          filled[id] = all.slice(0, qty);
        }
      }
      return filled;
    },
    [activeSlotIds, slotMap],
  );

  // Compute live total from all selections
  const totalSpent = useMemo(() => {
    return Object.values(selections)
      .flat()
      .reduce((sum, p) => sum + p.normalized_price, 0);
  }, [selections]);

  // Current slot in guided flow
  const currentSlotId = activeSlotIds[currentIndex] ?? null;
  const currentSlot = currentSlotId ? slotMap.get(currentSlotId) ?? null : null;
  const isMultiSelect = (currentSlot?.max_quantity ?? 1) > 1;

  // Group transition
  const currentGroup = currentSlotId && design
    ? getGroupForSlot(currentSlotId, design.room_type)
    : null;
  const prevSlotId = currentIndex > 0 ? activeSlotIds[currentIndex - 1] : null;
  const prevGroup = prevSlotId && design
    ? getGroupForSlot(prevSlotId, design.room_type)
    : null;
  const isNewGroup = currentGroup && currentGroup.key !== prevGroup?.key;

  // Pool spent for current multi-select slot
  const currentPoolSpent = useMemo(() => {
    if (!currentSlotId) return 0;
    return (selections[currentSlotId] ?? []).reduce(
      (sum, p) => sum + p.normalized_price, 0,
    );
  }, [currentSlotId, selections]);

  // Scroll to top on slot change or phase change
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [currentIndex, phase]);


  // Advance to next slot immediately.
  const advanceWithTransition = useCallback(() => {
    const next = currentIndex + 1;
    if (next >= activeSlotIds.length) {
      setSelections((prev) => {
        const filled = fillDefaults(prev);
        persistFinalize(filled, skippedSlots);
        return filled;
      });
      setPhase("complete");
    } else {
      setCurrentIndex(next);
      setFurthestIndex((prev) => Math.max(prev, next));
      setPhase("selecting");
    }
  }, [currentIndex, activeSlotIds, fillDefaults, persistFinalize, skippedSlots]);

  // Alias for skip buttons that call advanceToNext
  const advanceToNext = advanceWithTransition;

  // Back button — go to previous non-skipped slot, preserving all selections
  const goBack = useCallback(() => {
    let target = currentIndex - 1;
    while (target >= 0 && skippedSlots.has(activeSlotIds[target])) {
      target--;
    }
    if (target >= 0) {
      setCurrentIndex(target);
    }
  }, [currentIndex, activeSlotIds, skippedSlots]);


  // Toggle handler for guided selection (works for both single and multi)
  const handleToggle = useCallback(
    (product: ProductResult) => {
      if (!currentSlotId || !currentSlot) return;
      const maxQty = currentSlot.max_quantity ?? 1;

      if (maxQty === 1) {
        // Single-select: check if this would blow the total budget
        const otherSpend = Object.entries(selections)
          .filter(([id]) => id !== currentSlotId)
          .flatMap(([, prods]) => prods)
          .reduce((sum, p) => sum + p.normalized_price, 0);
        const wouldExceed = design && (otherSpend + product.normalized_price > design.target_budget * 1.05);

        if (wouldExceed) {
          // Show over-budget warning — let user confirm or pick again
          setOverBudgetProduct(product);
          return;
        }

        setSelections((prev) => ({ ...prev, [currentSlotId]: [product] }));

        setTimeout(advanceWithTransition, 300);
      } else {
        // Multi-select: toggle on/off
        setSelections((prev) => {
          const current = prev[currentSlotId] ?? [];
          const exists = current.some(
            (p) => p.product_id === product.product_id,
          );
          if (exists) {
            // Remove
            return {
              ...prev,
              [currentSlotId]: current.filter(
                (p) => p.product_id !== product.product_id,
              ),
            };
          }
          // Add (if under cap — pool is soft limit, not hard block)
          if (current.length >= maxQty) return prev;
          return { ...prev, [currentSlotId]: [...current, product] };
        });

      }
    },
    [currentSlotId, currentSlot, advanceWithTransition],
  );

  // Done handler for multi-select
  const handleDone = useCallback(() => {
    advanceWithTransition();
  }, [advanceWithTransition]);

  // Swap handler for final page (single-select slots)
  const handleSwap = useCallback(
    (slotId: string, product: ProductResult) => {
      setSelections((prev) => ({ ...prev, [slotId]: [product] }));
    },
    [],
  );

  // Server-side validation on phase transition to "complete"
  useEffect(() => {
    if (phase !== "complete" || !runId || validationRan.current) return;
    validationRan.current = true;

    const selectionPayload = Object.entries(selections).map(
      ([slotId, products]) => ({
        slot_id: slotId,
        selected_product_ids: products.map((p) => p.product_id),
      }),
    );

    validateSelections(runId, selectionPayload)
      .then((resp) => {
        if (!resp.valid) {
          // Log internally but never surface raw validation errors to the user.
          // The design is still usable — validation is a guardrail, not a gate.
          const reasons = resp.slots
            .filter((s) => !s.valid)
            .map((s) => `${s.slot_id}: ${s.reason}`)
            .join(", ");
          console.warn("Selection validation issues (hidden from user):", reasons);
        }
      })
      .catch((err) => {
        console.error("Selection validation failed:", err);
      });
  }, [phase, runId, selections]);

  // On-demand render — only generate when the user explicitly requests it.
  // This avoids paying ~$0.10-0.30 per render for users who bail before viewing.
  // Render reads from persisted selected_products — no selections sent.
  const triggerRender = useCallback(() => {
    if (!runId || renderUrl || renderLoading) return;
    setRenderLoading(true);
    setRenderFailed(false);
    setRenderTimedOut(false);

    generateRender(runId)
      .then((renderResp) => {
        const url = renderResp.render_url.startsWith("http")
          ? renderResp.render_url
          : `${API_BASE}${renderResp.render_url}`;
        setRenderUrl(url);
        if (runId) trackEvent(runId, "render_viewed");
      })
      .catch((err) => {
        if (err instanceof RenderTimeoutError) {
          setRenderTimedOut(true);
          setTimeoutJobId(err.jobId);
        } else {
          console.error("Render generation failed:", err);
          setRenderFailed(true);
        }
      })
      .finally(() => {
        setRenderLoading(false);
      });
  }, [runId, renderUrl, renderLoading]);

  const handleCheckAgain = useCallback(() => {
    if (!runId || !timeoutJobId) return;
    setCheckingAgain(true);
    checkRenderStatus(runId, timeoutJobId)
      .then((status) => {
        if (status.status === "complete" && status.render_url) {
          const url = status.render_url.startsWith("http")
            ? status.render_url
            : `${API_BASE}${status.render_url}`;
          setRenderUrl(url);
          setRenderTimedOut(false);
          if (runId) trackEvent(runId, "render_viewed");
        } else if (status.status === "failed") {
          setRenderTimedOut(false);
          setRenderFailed(true);
        }
        // pending/rendering/unknown → stay on "check again" screen
      })
      .finally(() => setCheckingAgain(false));
  }, [runId, timeoutJobId]);

  // --- Error state ---
  if (error) {
    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-wordmark">RoomKit</a>
        </div>
        <div className="error-banner">{error}</div>
      </main>
    );
  }

  // --- Loading state ---
  if (!design) {
    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-wordmark">RoomKit</a>
        </div>
        <div className="build-loading">
          <div className="build-loading-inner">
            <h2 className="build-loading-title">Loading your design...</h2>
          </div>
        </div>
      </main>
    );
  }

  // (Transition pause screen removed — RoomSoFar strip on the selecting
  //  phase gives the user context without interrupting the flow.)

  // --- Phase 1: Guided selection ---
  if (phase === "selecting" && currentSlot) {
    const choices = getChoicesForSlot(currentSlot);
    const currentSelections = selections[currentSlotId!] ?? [];
    const selectedIds = currentSelections.map((p) => p.product_id);

    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-wordmark">RoomKit</a>
          <button
            type="button"
            className="skip-to-results-btn"
            onClick={() => {
              setSelections((prev) => {
                const filled = fillDefaults(prev);
                persistFinalize(filled, skippedSlots);
                return filled;
              });
              setPhase("complete");
            }}
          >
            Skip to results
          </button>
        </div>

        {/* Progress panel */}
        <div style={{
          maxWidth: 640,
          margin: "0 auto",
          padding: "12px 16px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          fontSize: "0.78rem",
          color: "#A8A29E",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            {currentIndex > 0 && activeSlotIds.slice(0, currentIndex).some((id) => !skippedSlots.has(id)) && (
              <button
                type="button"
                onClick={goBack}
                style={{
                  background: "none",
                  border: "none",
                  color: "#8B6F5C",
                  cursor: "pointer",
                  fontSize: "0.82rem",
                  fontWeight: 500,
                  padding: "4px 8px",
                  borderRadius: 6,
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#F5F2EE"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
              >
                ← Back
              </button>
            )}
            <span>
              {currentIndex + 1} of {activeSlotIds.length} items
              {currentGroup ? ` · ${currentGroup.label}` : ""}
            </span>
            {currentIndex < furthestIndex && (
              <button
                type="button"
                onClick={() => {
                  let target = currentIndex + 1;
                  while (target <= furthestIndex && skippedSlots.has(activeSlotIds[target])) {
                    target++;
                  }
                  if (target <= furthestIndex) setCurrentIndex(target);
                }}
                style={{
                  background: "none",
                  border: "none",
                  color: "#8B6F5C",
                  cursor: "pointer",
                  fontSize: "0.82rem",
                  fontWeight: 500,
                  padding: "4px 8px",
                  borderRadius: 6,
                  transition: "background 0.15s",
                }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "#F5F2EE"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "none"; }}
              >
                Forward →
              </button>
            )}
          </div>
          <div style={{ display: "flex", gap: 3 }}>
            {activeSlotIds.map((id, i) => {
              const visited = i <= furthestIndex;
              const isCurrent = i === currentIndex;
              return (
                <button
                  key={id}
                  type="button"
                  disabled={!visited}
                  onClick={() => { if (visited && !isCurrent) setCurrentIndex(i); }}
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: "50%",
                    border: "none",
                    padding: 0,
                    background: isCurrent ? "#8B6F5C" : i < currentIndex ? "#B8A080" : visited ? "#C4B8A8" : "#E2DED6",
                    cursor: visited && !isCurrent ? "pointer" : "default",
                    transition: "background 0.15s",
                  }}
                  aria-label={`Go to slot ${i + 1}`}
                />
              );
            })}
          </div>
        </div>

        {/* Room so far — persistent strip of already-picked items */}
        <RoomSoFar selections={selections} />

        <div className="guided-flow" style={{ display: "block", maxWidth: 640, margin: "0 auto" }}>
          <div className="guided-picker">
            {isNewGroup && currentGroup && (
              <div className="group-transition">
                <span className="group-transition-label">
                  {currentGroup.label}
                </span>
              </div>
            )}

            {/* Skip — exclude slot entirely: at the TOP, clearly accessible */}
            <div style={{ display: "flex", gap: 12, justifyContent: "center", marginBottom: 16 }}>
              <button
                type="button"
                onClick={() => {
                  // Mark slot as skipped — truly excluded, no product, no budget
                  setSkippedSlots((prev) => new Set(prev).add(currentSlotId!));
                  setSelections((prev) => {
                    const next = { ...prev };
                    delete next[currentSlotId!];
                    return next;
                  });
                  advanceToNext();
                }}
                style={{
                  background: "#FAFAF8",
                  border: "1.5px solid #E2DED6",
                  borderRadius: 10,
                  color: "#78716C",
                  fontSize: "0.82rem",
                  fontWeight: 500,
                  cursor: "pointer",
                  padding: "10px 20px",
                  transition: "border-color 0.15s",
                }}
              >
                I don&apos;t need this item
              </button>
              <button
                type="button"
                onClick={() => {
                  // Use our top pick — fills rank-1 default, advances
                  if (currentSlot?.product) {
                    setSelections((prev) => ({
                      ...prev,
                      [currentSlotId!]: [currentSlot.product!],
                    }));
                  }
                  advanceToNext();
                }}
                style={{
                  background: "none",
                  border: "1.5px solid #E2DED6",
                  borderRadius: 10,
                  color: "#A8A29E",
                  fontSize: "0.82rem",
                  cursor: "pointer",
                  padding: "10px 20px",
                  transition: "border-color 0.15s",
                }}
              >
                Use our pick
              </button>
            </div>

            <SlotPicker
              slotId={currentSlotId!}
              choices={choices}
              selectedIds={selectedIds}
              maxQuantity={currentSlot.max_quantity ?? 1}
              poolBudget={currentSlot.allocated_budget}
              poolSpent={currentPoolSpent}
              onToggle={handleToggle}
              onDone={handleDone}
            />
          </div>
        </div>

        {/* Over-budget confirmation modal */}
        {overBudgetProduct && design && (
          <div style={{
            position: "fixed",
            inset: 0,
            background: "rgba(0,0,0,0.4)",
            backdropFilter: "blur(4px)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 100,
            padding: 24,
          }}>
            <div style={{
              background: "#FFF",
              borderRadius: 16,
              padding: "28px 24px",
              maxWidth: 380,
              width: "100%",
              textAlign: "center",
              boxShadow: "0 8px 30px rgba(0,0,0,0.15)",
            }}>
              <p style={{ fontSize: "1.1rem", fontWeight: 600, color: "#1C1917", marginBottom: 8 }}>
                Over budget
              </p>
              <p style={{ fontSize: "0.85rem", color: "#78716C", lineHeight: 1.5, marginBottom: 20 }}>
                Picking <strong>{overBudgetProduct.name.slice(0, 40)}…</strong> (${overBudgetProduct.normalized_price.toFixed(2)}) would put you over your ${design.target_budget.toLocaleString()} budget. You can keep it or pick something else.
              </p>
              <div style={{ display: "flex", gap: 10 }}>
                <button
                  type="button"
                  onClick={() => setOverBudgetProduct(null)}
                  style={{
                    flex: 1,
                    padding: "10px 16px",
                    border: "1.5px solid #E2DED6",
                    borderRadius: 8,
                    background: "#FFF",
                    color: "#1C1917",
                    fontSize: "0.85rem",
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  Pick again
                </button>
                <button
                  type="button"
                  onClick={() => {
                    const product = overBudgetProduct;
                    setOverBudgetProduct(null);
                    setSelections((prev) => ({ ...prev, [currentSlotId!]: [product] }));
                    setTimeout(advanceWithTransition, 300);
                  }}
                  style={{
                    flex: 1,
                    padding: "10px 16px",
                    border: "none",
                    borderRadius: 8,
                    background: "#1C1917",
                    color: "#FFF",
                    fontSize: "0.85rem",
                    fontWeight: 600,
                    cursor: "pointer",
                  }}
                >
                  Keep it anyway
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    );
  }

  // --- Phase 2: Final room page ---
  const groups = ROOM_GROUPS[design.room_type] ?? BEDROOM_GROUPS;

  return (
    <main className="result-page">
      <div className="result-sticky-header">
        <a href="/" className="result-wordmark">RoomKit</a>
        <a href="/" className="new-design-btn">+ New design</a>
      </div>

      <div className="result-hero">
        <h1>Your {design.room_type.replace(/_/g, " ")}</h1>
        <div className="style-badge">
          <span className="style-name">
            {AESTHETIC_LABELS[design.room_type]?.[design.style.style_name]
              ?? design.style.style_name.replace(/_/g, " ")}
          </span>
          <span className="style-mood">{design.style.mood}</span>
        </div>
      </div>

      {!design.is_feasible && (
        <div className="warning-banner">
          Budget is too tight to furnish this room. Try increasing your budget.
        </div>
      )}

      {/* AI Room Render hero — on-demand, not auto-generated */}
      {phase === "complete" && !renderUrl && !renderLoading && !renderFailed && (
        <button
          type="button"
          className="render-cta-btn"
          onClick={triggerRender}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <polyline points="21 15 16 10 5 21" />
          </svg>
          See your room
        </button>
      )}

      {renderLoading && !renderUrl && !renderFailed && !renderTimedOut && (
        <RenderLoadingScreen />
      )}

      {renderTimedOut && !renderUrl && (
        <div className="render-timeout-banner">
          <p>Your render is taking longer than expected.</p>
          <button
            type="button"
            className="render-cta-btn"
            onClick={handleCheckAgain}
            disabled={checkingAgain}
          >
            {checkingAgain ? "Checking..." : "Check again"}
          </button>
        </div>
      )}

      {renderUrl && (
        <InteractiveRoomRender renderUrl={renderUrl} />
      )}

      {renderUrl && (
        <ShareButton
          renderImageUrl={renderUrl}
          pageUrl={typeof window !== "undefined" ? window.location.href : ""}
        />
      )}

      <BudgetMeter total={totalSpent} target={design.target_budget} />

      <p className="affiliate-disclosure">
        As an Amazon Associate, RoomKit earns from qualifying purchases.
        Prices and availability are accurate as of the date shown and are subject to change.
        The price on Amazon at checkout applies.
      </p>

      {/* Export all to Amazon cart */}
      <ExportToCartButton selections={selections} runId={runId} />

      {/* Grouped product grid */}
      {groups.map((group) => {
        // Only render slots that were actually sourced (have products)
        // AND not explicitly skipped by the user.
        const activeSet = new Set(activeSlotIds);
        const groupSlots = group.slotIds
          .filter((id) => activeSet.has(id) && !skippedSlots.has(id))
          .map((id) => slotMap.get(id))
          .filter((s): s is SlotResult => s !== undefined);

        if (groupSlots.length === 0) return null;

        return (
          <section key={group.key} className="room-group">
            <h3 className="room-group-label">{group.label}</h3>
            <div className="product-grid">
              {groupSlots.map((slot) => {
                const isMulti = (slot.max_quantity ?? 1) > 1;
                const slotSelections = selections[slot.slot_id] ?? [];
                const allChoices = getChoicesForSlot(slot);

                if (isMulti && slotSelections.length > 0) {
                  // Multi-select gallery — read-only after finalize
                  return (
                    <MultiSelectGallery
                      key={slot.slot_id}
                      slot={slot}
                      selected={slotSelections}
                      allChoices={allChoices}
                      onRemove={isFinalized ? undefined : (pid) => {
                        setSelections((prev) => ({
                          ...prev,
                          [slot.slot_id]: (prev[slot.slot_id] ?? []).filter(
                            (p) => p.product_id !== pid,
                          ),
                        }));
                      }}
                      onAdd={isFinalized ? undefined : (product) => {
                        setSelections((prev) => {
                          const current = prev[slot.slot_id] ?? [];
                          if (current.length >= slot.max_quantity) return prev;
                          return {
                            ...prev,
                            [slot.slot_id]: [...current, product],
                          };
                        });
                      }}
                    />
                  );
                }

                // Single-select card (existing behavior)
                const activeProduct = slotSelections[0] ?? slot.product;
                const alternatives = allChoices.filter(
                  (p) => p.product_id !== activeProduct?.product_id,
                );

                return (
                  <ProductCard
                    key={slot.slot_id}
                    slot={slot}
                    activeProduct={activeProduct}
                    alternatives={alternatives}
                    onSwap={
                      !isFinalized && alternatives.length > 0
                        ? (product) => handleSwap(slot.slot_id, product)
                        : undefined
                    }
                    onBuyClick={(product, slotId) => {
                      if (runId) trackEvent(runId, "buy_link_clicked", {
                        slot_id: slotId, product_id: product.product_id, price: product.normalized_price,
                      });
                    }}
                  />
                );
              })}
            </div>
          </section>
        );
      })}
    </main>
  );
}

// ---------------------------------------------------------------------------
// Multi-select gallery for final page
// ---------------------------------------------------------------------------

function MultiSelectGallery({
  slot,
  selected,
  allChoices,
  onRemove,
  onAdd,
}: {
  slot: SlotResult;
  selected: ProductResult[];
  allChoices: ProductResult[];
  onRemove?: (productId: string) => void;
  onAdd?: (product: ProductResult) => void;
}) {
  const [showAddTray, setShowAddTray] = useState(false);
  const label = slot.slot_id.replace(/_/g, " ");
  const poolSpent = selected.reduce((s, p) => s + p.normalized_price, 0);
  const remaining = slot.allocated_budget - poolSpent;
  const atCap = selected.length >= slot.max_quantity;
  const selectedIds = new Set(selected.map((p) => p.product_id));
  const addable = allChoices.filter(
    (p) => !selectedIds.has(p.product_id),
  );

  return (
    <div className="multi-gallery">
      <div className="multi-gallery-header">
        <p className="card-slot">{label}</p>
        <p className="multi-gallery-pool">
          ${poolSpent.toFixed(2)} / ${slot.allocated_budget.toFixed(2)}
          <span className="multi-gallery-count">
            {" "}· {selected.length}/{slot.max_quantity}
          </span>
        </p>
      </div>

      <div className="multi-gallery-grid">
        {selected.map((product) => (
          <GalleryItem
            key={product.product_id}
            product={product}
            onRemove={onRemove ? () => onRemove(product.product_id) : undefined}
          />
        ))}
      </div>

      {/* Add more button — hidden when finalized (onAdd undefined) */}
      {onAdd && !atCap && addable.length > 0 && (
        <>
          <button
            type="button"
            className="multi-gallery-add-btn"
            onClick={() => setShowAddTray((prev) => !prev)}
          >
            {showAddTray ? "Hide options" : `+ Add more ${label}`}
          </button>

          {showAddTray && (
            <div className="multi-gallery-add-tray">
              {addable.map((product) => (
                <AddableThumb
                  key={product.product_id}
                  product={product}
                  onAdd={() => {
                    onAdd(product);
                  }}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function GalleryItem({
  product,
  onRemove,
}: {
  product: ProductResult;
  onRemove?: () => void;
}) {
  const [imgErr, setImgErr] = useState(false);
  const showImg = product.image_url && !imgErr;

  return (
    <div className="gallery-item">
      <div className="gallery-item-image">
        {showImg ? (
          <Image
            src={upgradeAmazonImage(product.image_url)}
            alt={product.name}
            width={400}
            height={400}
            sizes="(max-width: 768px) 30vw, 160px"
            style={{ objectFit: "contain", width: "100%", height: "100%" }}
            onError={() => setImgErr(true)}
          />
        ) : (
          <div className="gallery-item-placeholder" />
        )}
        {onRemove && (
          <button
            type="button"
            className="gallery-item-remove"
            onClick={onRemove}
            aria-label={`Remove ${product.name}`}
          >
            ×
          </button>
        )}
      </div>
      <p className="gallery-item-name">{product.name}</p>
      <p className="gallery-item-price">
        ${product.normalized_price.toFixed(2)}
        {formatPriceDate(product.fetched_at) && (
          <span className="price-as-of">as of {formatPriceDate(product.fetched_at)}</span>
        )}
      </p>
      <a
        href={product.buy_url}
        target="_blank"
        rel="noopener noreferrer nofollow sponsored"
        className="gallery-item-buy"
      >
        Buy
      </a>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Phased loading screen for render generation
// ---------------------------------------------------------------------------

const RENDER_PHASES = [
  { title: "Designing your space...", sub: "Analyzing your style selections", delay: 0 },
  { title: "Placing your furniture...", sub: "Arranging each piece in the room", delay: 5000 },
  { title: "Setting the mood...", sub: "Matching lighting and textures to your aesthetic", delay: 12000 },
  { title: "Adding the finishing touches...", sub: "Wall art, plants, and decor details", delay: 22000 },
  { title: "Almost there...", sub: "Polishing your photorealistic room render", delay: 35000 },
];

function RenderLoadingScreen() {
  const [phaseIdx, setPhaseIdx] = useState(0);

  useEffect(() => {
    const timers = RENDER_PHASES.slice(1).map((p, i) =>
      setTimeout(() => setPhaseIdx(i + 1), p.delay),
    );
    return () => timers.forEach(clearTimeout);
  }, []);

  const phase = RENDER_PHASES[phaseIdx];

  return (
    <div className="render-loading">
      <h2 className="render-loading-title" key={phaseIdx} style={{
        animation: "renderPhaseFadeIn 0.5s ease both",
      }}>
        {phase.title}
      </h2>
      <p className="render-loading-subtitle" key={`sub-${phaseIdx}`} style={{
        animation: "renderPhaseFadeIn 0.5s ease 0.15s both",
      }}>
        {phase.sub}
      </p>
      <div className="render-loading-bar">
        <div className="render-loading-bar-fill" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Export all to Amazon cart
// ---------------------------------------------------------------------------

function ExportToCartButton({
  selections,
  runId,
}: {
  selections: Record<string, ProductResult[]>;
  runId: string | null;
}) {
  const allProducts = Object.values(selections).flat();
  if (allProducts.length === 0) return null;

  const handleExport = () => {
    // Amazon add-to-cart URL: each item gets ASIN.{index}.1 + Quantity.{index}.1
    const params = new URLSearchParams();
    allProducts.forEach((product, i) => {
      const idx = i + 1;
      params.set(`ASIN.${idx}`, product.product_id);
      params.set(`Quantity.${idx}`, "1");
    });
    params.set("tag", "roomkitai-20");
    const url = `https://www.amazon.com/gp/aws/cart/add.html?${params.toString()}`;
    window.open(url, "_blank", "noopener,noreferrer");
    if (runId) trackEvent(runId, "export_cart_clicked", {
      product_count: allProducts.length, total_price: total,
    });
  };

  const total = allProducts.reduce((s, p) => s + p.normalized_price, 0);

  return (
    <div className="export-cart-wrapper">
      <button
        type="button"
        className="export-cart-btn"
        onClick={handleExport}
      >
        Add all {allProducts.length} items to Amazon cart — ${total.toFixed(0)}
      </button>
    </div>
  );
}

function AddableThumb({
  product,
  onAdd,
}: {
  product: ProductResult;
  onAdd: () => void;
}) {
  const [imgErr, setImgErr] = useState(false);
  const showImg = product.image_url && !imgErr;

  return (
    <button type="button" className="addable-thumb" onClick={onAdd}>
      <div className="addable-thumb-image">
        {showImg ? (
          <Image
            src={upgradeAmazonImage(product.image_url)}
            alt={product.name}
            width={120}
            height={120}
            style={{ objectFit: "contain", width: "100%", height: "100%" }}
            onError={() => setImgErr(true)}
          />
        ) : (
          <div className="addable-thumb-placeholder" />
        )}
      </div>
      <p className="addable-thumb-price">${product.normalized_price.toFixed(2)}</p>
    </button>
  );
}

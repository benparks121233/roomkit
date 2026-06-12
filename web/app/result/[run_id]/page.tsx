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
import { useParams } from "next/navigation";
import { getDesign, validateSelections } from "@/lib/api";
import type { DesignResponse, ProductResult, SlotResult } from "@/lib/api";
import SlotPicker from "@/components/SlotPicker";
import ProductCard from "@/components/ProductCard";
import BudgetMeter from "@/components/BudgetMeter";
import Image from "next/image";
import RoomSceneImage from "@/components/RoomSceneImage";

// ---------------------------------------------------------------------------
// Taxonomy group ordering — mirrors slot_taxonomy.yaml
// ---------------------------------------------------------------------------

interface GroupDef {
  key: string;
  label: string;
  slotIds: string[];
}

const BEDROOM_GROUPS: GroupDef[] = [
  { key: "bed", label: "Bed", slotIds: ["bed_frame", "mattress", "sheets", "comforter", "pillows"] },
  { key: "storage", label: "Storage", slotIds: ["nightstand", "dresser"] },
  { key: "lighting", label: "Lighting", slotIds: ["ceiling_light", "table_lamp", "floor_lamp"] },
  { key: "decor", label: "Decor", slotIds: ["wall_art", "plants", "mirror"] },
  { key: "soft_goods", label: "Soft Goods", slotIds: ["rug", "curtains", "throw_blanket"] },
];

const LIVING_ROOM_GROUPS: GroupDef[] = [
  { key: "seating", label: "Seating", slotIds: ["sofa", "armchair", "ottoman"] },
  { key: "entertainment", label: "Entertainment", slotIds: ["tv", "tv_stand", "sound_bar"] },
  { key: "tables", label: "Tables", slotIds: ["coffee_table", "side_table"] },
  { key: "lighting", label: "Lighting", slotIds: ["ceiling_light", "floor_lamp", "table_lamp"] },
  { key: "decor", label: "Decor", slotIds: ["wall_art", "plants", "mirror", "bookshelf"] },
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

function getChoicesForSlot(slot: SlotResult): ProductResult[] {
  if (!slot.product) return [];
  return [slot.product, ...slot.alternatives];
}

function upgradeAmazonImage(url: string): string {
  return url.replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL800_.");
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ResultPage() {
  const params = useParams<{ run_id: string }>();
  const runId = params.run_id;

  const [design, setDesign] = useState<DesignResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Selection state — always arrays (length 1 for single-select slots)
  const [phase, setPhase] = useState<"selecting" | "transition" | "complete">("selecting");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selections, setSelections] = useState<Record<string, ProductResult[]>>({});
  const [validationError, setValidationError] = useState<string | null>(null);
  const validationRan = useRef(false);
  const transitionTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [lastPickedSlotId, setLastPickedSlotId] = useState<string | null>(null);
  const [pickCount, setPickCount] = useState(0);
  const [skipAnimations, setSkipAnimations] = useState(false);
  const [overBudgetProduct, setOverBudgetProduct] = useState<ProductResult | null>(null);

  // Fetch design
  useEffect(() => {
    if (!runId) return;
    getDesign(runId)
      .then(setDesign)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Failed to load design"),
      );
  }, [runId]);

  // Build ordered active slot IDs (slots with products, in taxonomy order)
  const activeSlotIds = useMemo(() => {
    if (!design) return [];
    const ordered = getOrderedSlotIds(design.room_type);
    const sMap = new Map(design.slots.map((s) => [s.slot_id, s]));
    return ordered.filter((id) => {
      const slot = sMap.get(id);
      return slot && slot.product !== null;
    });
  }, [design]);

  const slotMap = useMemo(() => {
    if (!design) return new Map<string, SlotResult>();
    return new Map(design.slots.map((s) => [s.slot_id, s]));
  }, [design]);

  // Fill rank-1 defaults for un-visited slots (called on skip or flow completion)
  const fillDefaults = useCallback(
    (prev: Record<string, ProductResult[]>) => {
      const filled = { ...prev };
      for (const id of activeSlotIds) {
        if (filled[id] && filled[id].length > 0) continue;
        const slot = slotMap.get(id);
        if (slot?.product) {
          filled[id] = [slot.product];
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

  // Bed slot IDs — intermediate bed picks skip the transition entirely
  const BED_SLOTS = useMemo(() => new Set(["bed_frame", "mattress", "sheets", "comforter", "pillows"]), []);
  const lastBedSlotInFlow = useMemo(() => {
    const bedSlots = activeSlotIds.filter((id) => BED_SLOTS.has(id));
    return bedSlots[bedSlots.length - 1] ?? null;
  }, [activeSlotIds, BED_SLOTS]);

  // Show transition scene, then advance to next slot after delay
  const advanceWithTransition = useCallback(() => {
    if (transitionTimer.current) clearTimeout(transitionTimer.current);

    // Skip transition for intermediate bed picks or when animations are disabled
    const isIntermediateBedPick = currentSlotId && BED_SLOTS.has(currentSlotId) && currentSlotId !== lastBedSlotInFlow;
    if (skipAnimations || isIntermediateBedPick) {
      const next = currentIndex + 1;
      if (next >= activeSlotIds.length) {
        setSelections((prev) => fillDefaults(prev));
        setPhase("complete");
      } else {
        setCurrentIndex(next);
        setPhase("selecting");
      }
      return;
    }

    setPhase("transition");
    transitionTimer.current = setTimeout(() => {
      const next = currentIndex + 1;
      if (next >= activeSlotIds.length) {
        setSelections((prev) => fillDefaults(prev));
        setPhase("complete");
      } else {
        setCurrentIndex(next);
        setPhase("selecting");
      }
    }, 2000);
  }, [currentIndex, currentSlotId, activeSlotIds, fillDefaults, skipAnimations, BED_SLOTS, lastBedSlotInFlow]);

  // Direct advance (no transition) — for skip
  const advanceToNext = useCallback(() => {
    const next = currentIndex + 1;
    if (next >= activeSlotIds.length) {
      setSelections((prev) => fillDefaults(prev));
      setPhase("complete");
    } else {
      setCurrentIndex(next);
    }
  }, [currentIndex, activeSlotIds, fillDefaults]);

  // Clean up transition timer
  useEffect(() => {
    return () => {
      if (transitionTimer.current) clearTimeout(transitionTimer.current);
    };
  }, []);

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
        setLastPickedSlotId(currentSlotId);
        setPickCount((c) => c + 1);
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
          // Add (if under cap and pool)
          if (current.length >= maxQty) return prev;
          const pool = currentSlot.allocated_budget;
          const spent = current.reduce((s, p) => s + p.normalized_price, 0);
          if (spent + product.normalized_price > pool) return prev;
          return { ...prev, [currentSlotId]: [...current, product] };
        });
        setLastPickedSlotId(currentSlotId);
        setPickCount((c) => c + 1);
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
          const reasons = resp.slots
            .filter((s) => !s.valid)
            .map((s) => `${s.slot_id}: ${s.reason}`)
            .join(", ");
          setValidationError(`Server validation failed: ${reasons}`);
        }
      })
      .catch((err) => {
        // Don't block the UI — log but allow viewing results
        console.error("Selection validation failed:", err);
      });
  }, [phase, runId, selections]);

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

  // --- Transition scene (between picks) ---
  if (phase === "transition") {
    // Figure out what group label to show
    const transGroup = currentSlotId && design
      ? getGroupForSlot(currentSlotId, design.room_type)
      : null;
    const nextIndex = currentIndex + 1;
    const nextSlotId = activeSlotIds[nextIndex] ?? null;
    const nextGroup = nextSlotId && design
      ? getGroupForSlot(nextSlotId, design.room_type)
      : null;
    const showNextLabel = nextGroup && nextGroup.key !== transGroup?.key;

    return (
      <main className="result-page">
        <div
          className="scene-transition"
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            minHeight: "100dvh",
            padding: "24px",
            background: "#F5F0EA",
            animation: "sceneFadeIn 0.4s ease both",
          }}
        >
          <div style={{ width: "100%", maxWidth: 720 }}>
            <RoomSceneImage
              selections={selections}
              lastPickedSlotId={lastPickedSlotId}
              pickCount={pickCount}
              activeSlotIds={activeSlotIds}
            />
          </div>

          {/* Progress dots */}
          <div style={{
            display: "flex",
            gap: 6,
            marginTop: 24,
            alignItems: "center",
          }}>
            {activeSlotIds.map((id, i) => (
              <div
                key={id}
                style={{
                  width: i <= currentIndex ? 10 : 7,
                  height: i <= currentIndex ? 10 : 7,
                  borderRadius: "50%",
                  background: i < currentIndex
                    ? "#B8A080"
                    : i === currentIndex
                    ? "#8B6F5C"
                    : "#DDD6CC",
                  transition: "all 0.3s ease",
                }}
              />
            ))}
          </div>

          {/* Upcoming group label */}
          {showNextLabel && nextGroup && (
            <p style={{
              marginTop: 20,
              color: "#8B6F5C",
              fontSize: "0.85rem",
              fontWeight: 500,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              opacity: 0,
              animation: "sceneFadeIn 0.5s ease 1.5s both",
            }}>
              Next: {nextGroup.label}
            </p>
          )}

          {/* Skip / continue buttons */}
          <div style={{ display: "flex", gap: 16, marginTop: 16, alignItems: "center" }}>
            <button
              type="button"
              onClick={() => {
                if (transitionTimer.current) clearTimeout(transitionTimer.current);
                const next = currentIndex + 1;
                if (next >= activeSlotIds.length) {
                  setSelections((prev) => fillDefaults(prev));
                  setPhase("complete");
                } else {
                  setCurrentIndex(next);
                  setPhase("selecting");
                }
              }}
              style={{
                background: "none",
                border: "none",
                color: "#A8A29E",
                fontSize: "0.8rem",
                cursor: "pointer",
                textDecoration: "underline",
              }}
            >
              Continue
            </button>
            <button
              type="button"
              onClick={() => {
                setSkipAnimations(true);
                if (transitionTimer.current) clearTimeout(transitionTimer.current);
                const next = currentIndex + 1;
                if (next >= activeSlotIds.length) {
                  setSelections((prev) => fillDefaults(prev));
                  setPhase("complete");
                } else {
                  setCurrentIndex(next);
                  setPhase("selecting");
                }
              }}
              style={{
                background: "none",
                border: "none",
                color: "#A8A29E",
                fontSize: "0.75rem",
                cursor: "pointer",
                opacity: 0.7,
              }}
            >
              Skip all animations
            </button>
          </div>
        </div>

        <style>{`
          @keyframes sceneFadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
          }
        `}</style>
      </main>
    );
  }

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
              setSelections((prev) => fillDefaults(prev));
              setPhase("complete");
            }}
          >
            Skip to results
          </button>
        </div>

        <div className="guided-flow" style={{ display: "block", maxWidth: 640, margin: "0 auto" }}>
          <div className="guided-picker">
            {isNewGroup && currentGroup && (
              <div className="group-transition">
                <span className="group-transition-label">
                  {currentGroup.label}
                </span>
              </div>
            )}

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
                    setLastPickedSlotId(currentSlotId);
                    setPickCount((c) => c + 1);
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
            {design.style.style_name.replace(/_/g, " ")}
          </span>
          <span className="style-mood">{design.style.mood}</span>
        </div>
      </div>

      {!design.is_feasible && (
        <div className="warning-banner">
          Budget is too tight to furnish this room. Try increasing your budget.
        </div>
      )}

      {validationError && (
        <div className="warning-banner">{validationError}</div>
      )}

      <BudgetMeter total={totalSpent} target={design.target_budget} />

      {/* Grouped product grid */}
      {groups.map((group) => {
        const groupSlots = group.slotIds
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
                  // Multi-select gallery
                  return (
                    <MultiSelectGallery
                      key={slot.slot_id}
                      slot={slot}
                      selected={slotSelections}
                      allChoices={allChoices}
                      onRemove={(pid) => {
                        setSelections((prev) => ({
                          ...prev,
                          [slot.slot_id]: (prev[slot.slot_id] ?? []).filter(
                            (p) => p.product_id !== pid,
                          ),
                        }));
                      }}
                      onAdd={(product) => {
                        setSelections((prev) => {
                          const current = prev[slot.slot_id] ?? [];
                          if (current.length >= slot.max_quantity) return prev;
                          const spent = current.reduce(
                            (s, p) => s + p.normalized_price, 0,
                          );
                          if (spent + product.normalized_price > slot.allocated_budget) return prev;
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
                      alternatives.length > 0
                        ? (product) => handleSwap(slot.slot_id, product)
                        : undefined
                    }
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
  onRemove: (productId: string) => void;
  onAdd: (product: ProductResult) => void;
}) {
  const [showAddTray, setShowAddTray] = useState(false);
  const label = slot.slot_id.replace(/_/g, " ");
  const poolSpent = selected.reduce((s, p) => s + p.normalized_price, 0);
  const remaining = slot.allocated_budget - poolSpent;
  const atCap = selected.length >= slot.max_quantity;
  const selectedIds = new Set(selected.map((p) => p.product_id));
  const addable = allChoices.filter(
    (p) => !selectedIds.has(p.product_id) && p.normalized_price <= remaining,
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
            onRemove={() => onRemove(product.product_id)}
          />
        ))}
      </div>

      {/* Add more button */}
      {!atCap && addable.length > 0 && (
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
  onRemove: () => void;
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
        <button
          type="button"
          className="gallery-item-remove"
          onClick={onRemove}
          aria-label={`Remove ${product.name}`}
        >
          ×
        </button>
      </div>
      <p className="gallery-item-name">{product.name}</p>
      <p className="gallery-item-price">${product.normalized_price.toFixed(2)}</p>
      <a
        href={product.buy_url}
        target="_blank"
        rel="noopener noreferrer"
        className="gallery-item-buy"
      >
        Buy
      </a>
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

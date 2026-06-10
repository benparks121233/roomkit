"use client";

// Result page — two-phase experience:
//   Phase 1: Guided slot-by-slot selection (pick from alternatives)
//   Phase 2: Final room page (real product cards + budget meter + swap)
//
// Slot ordering follows taxonomy groups so the room "builds" naturally:
//   Bedroom: bed → storage → lighting → decor → soft_goods
//   Living room: seating → entertainment → tables → lighting → decor → soft_goods

import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { getDesign } from "@/lib/api";
import type { DesignResponse, ProductResult, SlotResult } from "@/lib/api";
import SlotPicker from "@/components/SlotPicker";
import ProductCard from "@/components/ProductCard";
import BudgetMeter from "@/components/BudgetMeter";

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

/** Get all slot IDs in taxonomy group order for a room type. */
function getOrderedSlotIds(roomType: string): string[] {
  const groups = ROOM_GROUPS[roomType] ?? BEDROOM_GROUPS;
  return groups.flatMap((g) => g.slotIds);
}

/** Find which group a slot belongs to. */
function getGroupForSlot(slotId: string, roomType: string): GroupDef | null {
  const groups = ROOM_GROUPS[roomType] ?? BEDROOM_GROUPS;
  return groups.find((g) => g.slotIds.includes(slotId)) ?? null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Build the full choices list for a slot: rank-1 product + alternatives. */
function getChoicesForSlot(slot: SlotResult): ProductResult[] {
  if (!slot.product) return [];
  // Rank-1 first, then alternatives (already rank-ordered from backend).
  return [slot.product, ...slot.alternatives];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ResultPage() {
  const params = useParams<{ run_id: string }>();
  const runId = params.run_id;

  const [design, setDesign] = useState<DesignResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  // Selection state
  const [phase, setPhase] = useState<"selecting" | "complete">("selecting");
  const [currentIndex, setCurrentIndex] = useState(0);
  const [selections, setSelections] = useState<Record<string, ProductResult>>({});

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
    const slotMap = new Map(design.slots.map((s) => [s.slot_id, s]));
    return ordered.filter((id) => {
      const slot = slotMap.get(id);
      return slot && slot.product !== null;
    });
  }, [design]);

  // Slot lookup map
  const slotMap = useMemo(() => {
    if (!design) return new Map<string, SlotResult>();
    return new Map(design.slots.map((s) => [s.slot_id, s]));
  }, [design]);

  // Initialize selections with rank-1 products once design loads
  useEffect(() => {
    if (!design || activeSlotIds.length === 0) return;
    const initial: Record<string, ProductResult> = {};
    for (const id of activeSlotIds) {
      const slot = slotMap.get(id);
      if (slot?.product) {
        initial[id] = slot.product;
      }
    }
    setSelections(initial);
  }, [design, activeSlotIds, slotMap]);

  // Compute live total from selections
  const totalSpent = useMemo(() => {
    return Object.values(selections).reduce(
      (sum, p) => sum + p.normalized_price,
      0,
    );
  }, [selections]);

  // Current slot in guided flow
  const currentSlotId = activeSlotIds[currentIndex] ?? null;
  const currentSlot = currentSlotId ? slotMap.get(currentSlotId) ?? null : null;

  // Group transition: is this slot the first in its group?
  const currentGroup = currentSlotId && design
    ? getGroupForSlot(currentSlotId, design.room_type)
    : null;
  const prevSlotId = currentIndex > 0 ? activeSlotIds[currentIndex - 1] : null;
  const prevGroup = prevSlotId && design
    ? getGroupForSlot(prevSlotId, design.room_type)
    : null;
  const isNewGroup = currentGroup && currentGroup.key !== prevGroup?.key;

  // Pick handler for guided selection
  const handlePick = useCallback(
    (product: ProductResult) => {
      if (!currentSlotId) return;
      setSelections((prev) => ({ ...prev, [currentSlotId]: product }));

      // Auto-advance after brief delay
      setTimeout(() => {
        const next = currentIndex + 1;
        if (next >= activeSlotIds.length) {
          setPhase("complete");
        } else {
          setCurrentIndex(next);
        }
      }, 400);
    },
    [currentSlotId, currentIndex, activeSlotIds],
  );

  // Swap handler for final page
  const handleSwap = useCallback(
    (slotId: string, product: ProductResult) => {
      setSelections((prev) => ({ ...prev, [slotId]: product }));
    },
    [],
  );

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

  // --- Phase 1: Guided selection ---
  if (phase === "selecting" && currentSlot) {
    const choices = getChoicesForSlot(currentSlot);
    const progress = activeSlotIds.length > 0
      ? currentIndex / activeSlotIds.length
      : 0;

    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-wordmark">RoomKit</a>
          <button
            type="button"
            className="skip-to-results-btn"
            onClick={() => setPhase("complete")}
          >
            Skip to results
          </button>
        </div>

        <div className="guided-flow">
          {/* Room scene placeholder — Slice B will replace */}
          <div className="guided-scene">
            <div className="scene-placeholder">
              <div className="scene-placeholder-inner">
                <p className="scene-placeholder-count">
                  {currentIndex} / {activeSlotIds.length} pieces placed
                </p>
                <div className="scene-placeholder-bar-track">
                  <div
                    className="scene-placeholder-bar-fill"
                    style={{ width: `${progress * 100}%` }}
                  />
                </div>
                {/* Show dots for placed pieces */}
                <div className="scene-placed-dots">
                  {activeSlotIds.map((id, i) => (
                    <div
                      key={id}
                      className={`scene-dot${i < currentIndex ? " placed" : i === currentIndex ? " current" : ""}`}
                      title={id.replace(/_/g, " ")}
                    />
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Selection panel */}
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
              selectedId={selections[currentSlotId!]?.product_id ?? null}
              onPick={handlePick}
            />
          </div>
        </div>
      </main>
    );
  }

  // --- Phase 2: Final room page ---
  const groups = ROOM_GROUPS[design.room_type] ?? BEDROOM_GROUPS;

  // All slots including empty/owned, for the final grouped grid
  const allSlotMap = slotMap;

  return (
    <main className="result-page">
      {/* Sticky header */}
      <div className="result-sticky-header">
        <a href="/" className="result-wordmark">RoomKit</a>
        <a href="/" className="new-design-btn">+ New design</a>
      </div>

      {/* Hero */}
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

      <BudgetMeter total={totalSpent} target={design.target_budget} />

      {/* Grouped product grid */}
      {groups.map((group) => {
        const groupSlots = group.slotIds
          .map((id) => allSlotMap.get(id))
          .filter((s): s is SlotResult => s !== undefined);

        if (groupSlots.length === 0) return null;

        return (
          <section key={group.key} className="room-group">
            <h3 className="room-group-label">{group.label}</h3>
            <div className="product-grid">
              {groupSlots.map((slot) => {
                const activeProduct = selections[slot.slot_id] ?? slot.product;
                // Build alternatives list: all choices except the active one
                const allChoices = getChoicesForSlot(slot);
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

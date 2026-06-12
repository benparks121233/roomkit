"use client";

import { useEffect, useState } from "react";

// ─── Scene piece definitions ────────────────────────────────────────

interface ScenePiece {
  id: string;
  src: string;
  left: number;
  top: number;
  width: number;
  rotate: number;
  zIndex: number;
  shadow: string;
}

const FLOOR_SHADOW = "drop-shadow(2px 5px 4px rgba(100, 75, 50, 0.3))";
const WALL_SHADOW = "drop-shadow(2px 3px 3px rgba(100, 75, 50, 0.15))";
const CEILING_SHADOW = "drop-shadow(0px 3px 4px rgba(100, 75, 50, 0.2))";

const SCENE_PIECES: ScenePiece[] = [
  { id: "curtains",      src: "/room-assets/curtains.png",       left: 5.5,   top: 7.6,   width: 68,    rotate: 0,  zIndex: 1,  shadow: WALL_SHADOW },
  { id: "wall_art",      src: "/room-assets/wall_art.png",       left: 61.3,  top: 16,    width: 24,    rotate: 0,  zIndex: 2,  shadow: WALL_SHADOW },
  { id: "mirror",        src: "/room-assets/mirror.png",         left: 58.2,  top: 40.4,  width: 18,    rotate: 0,  zIndex: 2,  shadow: WALL_SHADOW },
  { id: "ceiling_light", src: "/room-assets/ceiling_light.png",  left: 29.3,  top: 0.2,   width: 20,    rotate: 0,  zIndex: 10, shadow: CEILING_SHADOW },
  { id: "rug",           src: "/room-assets/rug.png",            left: 10.3,  top: 59.2,  width: 58,    rotate: 1,  zIndex: 3,  shadow: "none" },
  { id: "nightstand",    src: "/room-assets/nightstand.png",     left: 1.2,   top: 56.6,  width: 26,    rotate: 0,  zIndex: 4,  shadow: FLOOR_SHADOW },
  { id: "dresser",       src: "/room-assets/dresser.png",        left: 54.9,  top: 50.9,  width: 34,    rotate: 0,  zIndex: 4,  shadow: FLOOR_SHADOW },
  { id: "bed",           src: "/room-assets/bed.png",            left: 13.3,  top: 49,    width: 52,    rotate: 0,  zIndex: 5,  shadow: FLOOR_SHADOW },
  { id: "throw_blanket", src: "/room-assets/throw_blanket.png",  left: 34.6,  top: 66.9,  width: 22,    rotate: 0,  zIndex: 6,  shadow: "none" },
  { id: "table_lamp",    src: "/room-assets/table_lamp.png",     left: 4.7,   top: 43.2,  width: 20,    rotate: 0,  zIndex: 7,  shadow: FLOOR_SHADOW },
  { id: "floor_lamp",    src: "/room-assets/floor_lamp.png",     left: 70.3,  top: 39.4,  width: 42.5,  rotate: 0,  zIndex: 7,  shadow: FLOOR_SHADOW },
  { id: "plant",         src: "/room-assets/plant.png",          left: 66.8,  top: 37.1,  width: 24,    rotate: 0,  zIndex: 7,  shadow: FLOOR_SHADOW },
];

// Map survey slot IDs → scene piece IDs
const SLOT_TO_PIECE: Record<string, string> = {
  bed_frame: "bed",
  mattress: "bed",
  sheets: "bed",
  comforter: "bed",
  pillows: "bed",
  nightstand: "nightstand",
  dresser: "dresser",
  ceiling_light: "ceiling_light",
  table_lamp: "table_lamp",
  floor_lamp: "floor_lamp",
  wall_art: "wall_art",
  plants: "plant",
  mirror: "mirror",
  rug: "rug",
  curtains: "curtains",
  throw_blanket: "throw_blanket",
};

// Slot-specific labels shown during transition
const SLOT_LABELS: Record<string, string> = {
  bed_frame: "Bed Frame",
  mattress: "Mattress",
  sheets: "Sheets",
  comforter: "Comforter",
  pillows: "Pillows",
  nightstand: "Nightstand",
  dresser: "Dresser",
  ceiling_light: "Ceiling Light",
  table_lamp: "Table Lamp",
  floor_lamp: "Floor Lamp",
  wall_art: "Wall Art",
  plants: "Plants",
  mirror: "Mirror",
  rug: "Rug",
  curtains: "Curtains",
  throw_blanket: "Throw Blanket",
};

// ─── Component ──────────────────────────────────────────────────────

// Bed-related slot IDs (animation only triggers on last bed slot picked)
const BED_SLOT_IDS = new Set(["bed_frame", "mattress", "sheets", "comforter", "pillows"]);

interface RoomSceneImageProps {
  selections: Record<string, unknown[]>;
  /** The slot that was JUST picked (triggers animation on its piece) */
  lastPickedSlotId: string | null;
  /** Incrementing counter to force animation replay even for same piece */
  pickCount: number;
  /** Ordered list of active slot IDs in the survey flow */
  activeSlotIds?: string[];
}

export default function RoomSceneImage({
  selections,
  lastPickedSlotId,
  pickCount,
  activeSlotIds = [],
}: RoomSceneImageProps) {
  // Determine which bed slots are in the flow and whether all are filled
  const bedSlotsInFlow = activeSlotIds.filter((id) => BED_SLOT_IDS.has(id));
  const allBedSlotsFilled = bedSlotsInFlow.length > 0
    && bedSlotsInFlow.every((id) => (selections[id]?.length ?? 0) > 0);

  // Which pieces are visible — bed only shows once ALL bed slots are filled
  const visiblePieces = new Set<string>();
  for (const [slotId, products] of Object.entries(selections)) {
    if (products.length > 0) {
      const pieceId = SLOT_TO_PIECE[slotId];
      if (!pieceId) continue;
      // Hold back the bed piece until all bed slots are done
      if (pieceId === "bed" && !allBedSlotsFilled) continue;
      visiblePieces.add(pieceId);
    }
  }

  // For bed slots: only animate when the LAST bed slot in the flow is picked
  const isBedSlot = lastPickedSlotId ? BED_SLOT_IDS.has(lastPickedSlotId) : false;
  const isLastBedSlot = (() => {
    if (!isBedSlot || !lastPickedSlotId) return false;
    return bedSlotsInFlow[bedSlotsInFlow.length - 1] === lastPickedSlotId;
  })();

  // The piece that should animate (bed only animates on last bed slot)
  const animatingPieceId = (() => {
    if (!lastPickedSlotId) return null;
    if (isBedSlot && !isLastBedSlot) return null;
    return SLOT_TO_PIECE[lastPickedSlotId] ?? null;
  })();

  // Is this the FIRST time this piece appears? (no other slot mapping to it was picked before)
  const isFirstAppearance = (() => {
    if (!animatingPieceId || !lastPickedSlotId) return false;
    // Check if any OTHER slot that maps to same piece was already selected before this pick
    for (const [slotId, pieceId] of Object.entries(SLOT_TO_PIECE)) {
      if (pieceId === animatingPieceId && slotId !== lastPickedSlotId) {
        if ((selections[slotId]?.length ?? 0) > 0) return false;
      }
    }
    return true;
  })();

  // Slot label for the floating text (suppress for intermediate bed picks;
  // show "Bed" instead of "Pillows" when the bed piece finally drops in)
  const slotLabel = (() => {
    if (!lastPickedSlotId) return null;
    if (isBedSlot && !isLastBedSlot) return null;
    if (isBedSlot && isLastBedSlot) return "Bed";
    return SLOT_LABELS[lastPickedSlotId] ?? lastPickedSlotId;
  })();

  // Animate the label appearing
  const [showLabel, setShowLabel] = useState(false);
  useEffect(() => {
    setShowLabel(false);
    const t = setTimeout(() => setShowLabel(true), 400);
    return () => clearTimeout(t);
  }, [pickCount]);

  return (
    <div
      style={{
        position: "relative",
        width: "100%",
        aspectRatio: "1024 / 682",
        overflow: "hidden",
        borderRadius: 16,
        background: "#E8DFD0",
      }}
    >
      {/* Room base */}
      <img
        src="/room-assets/room-base.png"
        alt="Room"
        draggable={false}
        style={{
          position: "absolute",
          inset: 0,
          width: "100%",
          height: "100%",
          objectFit: "cover",
          pointerEvents: "none",
        }}
      />

      {/* Scene pieces */}
      {SCENE_PIECES.map((piece) => {
        const isVisible = visiblePieces.has(piece.id);
        if (!isVisible) return null;

        const isAnimating = piece.id === animatingPieceId;
        const animType = isAnimating
          ? isFirstAppearance ? "drop" : "pulse"
          : "none";

        // Use pickCount in the key to force React to remount the img,
        // which restarts the CSS animation
        const key = isAnimating ? `${piece.id}-${pickCount}` : piece.id;

        return (
          <img
            key={key}
            src={piece.src}
            alt={piece.id}
            draggable={false}
            style={{
              position: "absolute",
              left: `${piece.left}%`,
              top: `${piece.top}%`,
              width: `${piece.width}%`,
              height: "auto",
              transform: piece.rotate ? `rotate(${piece.rotate}deg)` : undefined,
              transformOrigin: "center bottom",
              zIndex: piece.zIndex,
              filter: piece.shadow !== "none" ? piece.shadow : undefined,
              pointerEvents: "none",
              animation:
                animType === "drop"
                  ? "sceneDropIn 1.2s cubic-bezier(0.16, 1, 0.3, 1) both"
                  : animType === "pulse"
                  ? "sceneFluff 0.6s cubic-bezier(0.34, 1.56, 0.64, 1) both"
                  : undefined,
            }}
          />
        );
      })}

      {/* Floating label for what was just added */}
      {slotLabel && showLabel && (
        <div
          key={`label-${pickCount}`}
          style={{
            position: "absolute",
            bottom: "8%",
            left: "50%",
            transform: "translateX(-50%)",
            zIndex: 30,
            background: "rgba(107, 78, 61, 0.85)",
            color: "#FFF8F0",
            padding: "8px 20px",
            borderRadius: 24,
            fontSize: "0.85rem",
            fontWeight: 500,
            letterSpacing: "0.03em",
            backdropFilter: "blur(8px)",
            animation: "labelFadeUp 0.5s ease both",
            pointerEvents: "none",
          }}
        >
          + {slotLabel}
        </div>
      )}

      <style>{`
        @keyframes sceneDropIn {
          0% {
            opacity: 0;
            transform: translateY(-120px) scale(0.9);
            filter: brightness(1.4) blur(3px);
          }
          35% {
            opacity: 1;
            filter: brightness(1.1) blur(0.5px);
          }
          65% {
            transform: translateY(6px) scale(1.02);
            filter: brightness(1.03) blur(0px);
          }
          80% {
            transform: translateY(-4px) scale(0.99);
          }
          90% {
            transform: translateY(1px) scale(1.005);
          }
          100% {
            opacity: 1;
            transform: translateY(0) scale(1);
            filter: brightness(1) blur(0px);
          }
        }
        @keyframes sceneFluff {
          0% {
            transform: scale(1);
            filter: brightness(1);
          }
          15% {
            transform: scale(1.04) translateY(-3px);
            filter: brightness(1.15);
          }
          40% {
            transform: scale(0.98) translateY(1px);
            filter: brightness(1.05);
          }
          60% {
            transform: scale(1.02);
            filter: brightness(1.08);
          }
          100% {
            transform: scale(1);
            filter: brightness(1);
          }
        }
        @keyframes labelFadeUp {
          0% {
            opacity: 0;
            transform: translateX(-50%) translateY(10px);
          }
          100% {
            opacity: 1;
            transform: translateX(-50%) translateY(0);
          }
        }
      `}</style>
    </div>
  );
}

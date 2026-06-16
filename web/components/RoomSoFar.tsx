"use client";

// Compact horizontal strip showing thumbnails of already-picked products.
// Visible during guided selection so users can coordinate items (match
// throw to sheets, curtains to rug, etc.).  Mobile-first: scrollable row.

import type { ProductResult } from "@/lib/api";

const SLOT_LABELS: Record<string, string> = {
  bed_frame: "Bed Frame",
  mattress: "Mattress",
  sheets: "Sheets",
  comforter: "Comforter",
  duvet_insert: "Duvet Insert",
  duvet_cover: "Duvet Cover",
  pillows: "Pillows",
  nightstand: "Nightstand",
  dresser: "Dresser",
  desk: "Desk",
  desk_chair: "Desk Chair",
  ceiling_light: "Ceiling Light",
  table_lamp: "Table Lamp",
  floor_lamp: "Floor Lamp",
  sconce: "Sconce",
  wall_art: "Wall Art",
  plants: "Plants",
  mirror: "Mirror",
  rug: "Rug",
  curtains: "Curtains",
  throw_blanket: "Throw",
  sofa: "Sofa",
  coffee_table: "Coffee Table",
  side_table: "Side Table",
  tv_stand: "TV Stand",
  throw_pillows: "Throw Pillows",
};

interface RoomSoFarProps {
  selections: Record<string, ProductResult[]>;
}

export default function RoomSoFar({ selections }: RoomSoFarProps) {
  // Collect all picked items (slot → first product thumbnail)
  const picks = Object.entries(selections)
    .filter(([, products]) => products.length > 0)
    .map(([slotId, products]) => ({
      slotId,
      label: SLOT_LABELS[slotId] ?? slotId.replace(/_/g, " "),
      image: products[0].image_url,
      count: products.length,
    }));

  if (picks.length === 0) return null;

  return (
    <div className="room-so-far">
      <p className="room-so-far-title">Your room so far</p>
      <div className="room-so-far-strip">
        {picks.map((pick) => (
          <div key={pick.slotId} className="room-so-far-item">
            <div className="room-so-far-thumb">
              <img
                src={pick.image}
                alt={pick.label}
                draggable={false}
              />
              {pick.count > 1 && (
                <span className="room-so-far-count">{pick.count}</span>
              )}
            </div>
            <span className="room-so-far-label">{pick.label}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

"use client";

import { useEffect, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { getPublicDesign, API_BASE } from "@/lib/api";
import type { DesignResponse, ProductResult, SlotResult } from "@/lib/api";
import ProductCard from "@/components/ProductCard";
import BudgetMeter from "@/components/BudgetMeter";
import InteractiveRoomRender from "@/components/InteractiveRoomRender";
import Image from "next/image";

// ---------------------------------------------------------------------------
// Taxonomy group ordering — same as result page
// ---------------------------------------------------------------------------

interface GroupDef {
  key: string;
  label: string;
  slotIds: string[];
}

const AESTHETIC_LABELS: Record<string, Record<string, string>> = {
  bedroom: {
    cottagecore: "Cottagecore", dark_academia: "Dark Academia", japandi: "Japandi",
    coastal: "Coastal", industrial: "Industrial", quiet_luxury: "Quiet Luxury",
    sports_den: "Sports Den", city_modern: "City Modern", ski_lodge: "Ski Lodge",
    jungle_oasis: "Jungle Oasis", gamer_den: "Gamer Den", poster_maximalist: "Poster Maximalist",
  },
  living_room: {
    cottagecore: "Country Parlor", dark_academia: "Library Lounge", japandi: "Still Room",
    coastal: "Shore House", industrial: "Warehouse Loft", quiet_luxury: "The Salon",
    sports_den: "The Den", city_modern: "High Rise", ski_lodge: "Fireside",
    jungle_oasis: "Greenhouse", gamer_den: "Command Center", poster_maximalist: "The Gallery",
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

function upgradeAmazonImage(url: string): string {
  return url.replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL800_.");
}

function formatPriceDate(iso: string | null | undefined): string | null {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function PublicRoomPage() {
  const params = useParams<{ run_id: string }>();
  const runId = params.run_id;

  const [design, setDesign] = useState<DesignResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!runId) return;
    getPublicDesign(runId)
      .then(setDesign)
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Room not found"),
      );
  }, [runId]);

  const selections: Record<string, ProductResult[]> = useMemo(() => {
    if (!design) return {};
    const result: Record<string, ProductResult[]> = {};
    for (const slot of design.slots) {
      if (slot.selected_products && slot.selected_products.length > 0) {
        result[slot.slot_id] = slot.selected_products;
      } else if (slot.product) {
        result[slot.slot_id] = [slot.product];
      }
    }
    return result;
  }, [design]);

  const totalSpent = useMemo(() => {
    return Object.values(selections)
      .flat()
      .reduce((sum, p) => sum + p.normalized_price, 0);
  }, [selections]);

  const activeSlotIds = useMemo(() => {
    if (!design?.slots) return [];
    const ordered = getOrderedSlotIds(design.room_type);
    const sMap = new Map(design.slots.map((s) => [s.slot_id, s]));
    return ordered.filter((id) => {
      const slot = sMap.get(id);
      return slot && (slot.product !== null || (slot.selected_products && slot.selected_products.length > 0));
    });
  }, [design]);

  const slotMap = useMemo(() => {
    if (!design?.slots) return new Map<string, SlotResult>();
    return new Map(design.slots.map((s) => [s.slot_id, s]));
  }, [design]);

  // Render URL
  const renderUrl = useMemo(() => {
    if (!design?.render_url) return null;
    return design.render_url.startsWith("http")
      ? design.render_url
      : `${API_BASE}${design.render_url}`;
  }, [design]);

  if (error) {
    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-back-link" aria-label="Back to home">&#8592; RoomKit</a>
        </div>
        <div className="error-banner">{error}</div>
      </main>
    );
  }

  if (!design) {
    return (
      <main className="result-page">
        <div className="result-sticky-header">
          <a href="/" className="result-back-link" aria-label="Back to home">&#8592; RoomKit</a>
        </div>
        <div className="build-loading">
          <div className="build-loading-inner">
            <h2 className="build-loading-title">Loading room...</h2>
          </div>
        </div>
      </main>
    );
  }

  const groups = ROOM_GROUPS[design.room_type] ?? BEDROOM_GROUPS;
  const allProducts = Object.values(selections).flat();

  return (
    <main className="result-page">
      <div className="result-sticky-header">
        <a href="/" className="result-back-link" aria-label="Back to home">&#8592; RoomKit</a>
      </div>

      <div className="result-hero">
        <h1>
          {AESTHETIC_LABELS[design.room_type]?.[design.style.style_name]
            ?? design.style.style_name.replace(/_/g, " ")}{" "}
          {design.room_type.replace(/_/g, " ")}
        </h1>
        <div className="style-badge">
          <span className="style-mood">{design.style.mood}</span>
        </div>
      </div>

      {renderUrl && <InteractiveRoomRender renderUrl={renderUrl} />}

      <BudgetMeter total={totalSpent} target={design.target_budget} />

      <p className="affiliate-disclosure">
        As an Amazon Associate, RoomKit earns from qualifying purchases.
        Prices and availability are subject to change.
        The price on Amazon at checkout applies.
      </p>

      {allProducts.length > 0 && (
        <CartButton products={allProducts} />
      )}

      {groups.map((group) => {
        const activeSet = new Set(activeSlotIds);
        const groupSlots = group.slotIds
          .filter((id) => activeSet.has(id))
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

                if (isMulti && slotSelections.length > 0) {
                  return (
                    <div key={slot.slot_id} className="multi-gallery">
                      <div className="multi-gallery-header">
                        <p className="card-slot">{slot.slot_id.replace(/_/g, " ")}</p>
                        <p className="multi-gallery-pool">
                          {slotSelections.length} {slotSelections.length === 1 ? "item" : "items"}
                        </p>
                      </div>
                      <div className="multi-gallery-grid">
                        {slotSelections.map((product) => (
                          <GalleryItem key={product.product_id} product={product} />
                        ))}
                      </div>
                    </div>
                  );
                }

                const activeProduct = slotSelections[0] ?? slot.product;
                return (
                  <ProductCard
                    key={slot.slot_id}
                    slot={slot}
                    activeProduct={activeProduct}
                  />
                );
              })}
            </div>
          </section>
        );
      })}

      {allProducts.length > 0 && (
        <CartButton products={allProducts} />
      )}

      <div style={{ textAlign: "center", padding: "32px 16px 48px" }}>
        <a href="/design" className="landing-cta">Design your own room</a>
        <p style={{ marginTop: 12, fontSize: "0.82rem", color: "#A8A29E" }}>
          Your first room is free. No credit card needed.
        </p>
      </div>
    </main>
  );
}

// ---------------------------------------------------------------------------
// Cart button (self-contained, no auth/tracking needed)
// ---------------------------------------------------------------------------

function CartButton({ products }: { products: ProductResult[] }) {
  const total = products.reduce((s, p) => s + p.normalized_price, 0);

  const handleExport = () => {
    const params = new URLSearchParams();
    products.forEach((product, i) => {
      const idx = i + 1;
      params.set(`ASIN.${idx}`, product.product_id);
      params.set(`Quantity.${idx}`, "1");
    });
    params.set("tag", "roomkitai-20");
    const url = `https://www.amazon.com/gp/aws/cart/add.html?${params.toString()}`;
    window.open(url, "_blank", "noopener,noreferrer");
  };

  return (
    <div className="export-cart-wrapper">
      <button type="button" className="export-cart-btn" onClick={handleExport}>
        Add all {products.length} items to Amazon cart — ${total.toFixed(0)}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Gallery item for multi-select slots (read-only)
// ---------------------------------------------------------------------------

function GalleryItem({ product }: { product: ProductResult }) {
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

"use client";

// SlotPicker — "Choose your [slot]" card grid for the guided selection flow.
// Shows all alternatives (including the rank-1 default) as tappable photo cards.

import Image from "next/image";
import { useState } from "react";
import type { ProductResult } from "@/lib/api";

function upgradeAmazonImage(url: string): string {
  return url.replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL800_.");
}

interface SlotPickerProps {
  slotId: string;
  /** All choosable products for this slot (rank-1 first, then alternatives). */
  choices: ProductResult[];
  /** Currently selected product_id (highlighted). */
  selectedId: string | null;
  onPick: (product: ProductResult) => void;
}

export default function SlotPicker({
  slotId,
  choices,
  selectedId,
  onPick,
}: SlotPickerProps) {
  const label = slotId.replace(/_/g, " ");

  return (
    <div className="slot-picker">
      <h2 className="slot-picker-question">
        Choose your <span className="slot-picker-slot">{label}</span>
      </h2>

      <div className="slot-picker-grid">
        {choices.map((product) => (
          <PickerCard
            key={product.product_id}
            product={product}
            isSelected={product.product_id === selectedId}
            onPick={onPick}
          />
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual picker card
// ---------------------------------------------------------------------------

function PickerCard({
  product,
  isSelected,
  onPick,
}: {
  product: ProductResult;
  isSelected: boolean;
  onPick: (product: ProductResult) => void;
}) {
  const [imgError, setImgError] = useState(false);
  const showImage = product.image_url && !imgError;

  return (
    <button
      type="button"
      className={`picker-card${isSelected ? " selected" : ""}`}
      onClick={() => onPick(product)}
    >
      <div className="picker-card-image">
        {showImage ? (
          <Image
            src={upgradeAmazonImage(product.image_url)}
            alt={product.name}
            width={400}
            height={400}
            sizes="(max-width: 768px) 45vw, 200px"
            style={{ objectFit: "contain", width: "100%", height: "100%" }}
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="picker-card-placeholder">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="18" height="18" rx="2" />
              <circle cx="8.5" cy="8.5" r="1.5" />
              <path d="M21 15l-5-5L5 21" />
            </svg>
          </div>
        )}
      </div>
      <div className="picker-card-body">
        <p className="picker-card-name">{product.name}</p>
        <p className="picker-card-price">${product.normalized_price.toFixed(2)}</p>
        <p className="picker-card-reason">{product.fit_reason}</p>
      </div>
      {isSelected && (
        <div className="picker-card-check">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M5 12l5 5L20 7" />
          </svg>
        </div>
      )}
    </button>
  );
}

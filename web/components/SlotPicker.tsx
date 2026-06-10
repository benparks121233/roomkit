"use client";

// SlotPicker — "Choose your [slot]" card grid for the guided selection flow.
// Supports single-select (max_quantity=1) and multi-select (max_quantity>1).
// Multi-select shows a pool meter, toggles items on/off, and has a Done button.

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
  /** Currently selected product_ids (multi-select: array, single: length 0-1). */
  selectedIds: string[];
  /** Max items user can pick (1 = single-select). */
  maxQuantity: number;
  /** Pool budget for this slot (allocated_budget). */
  poolBudget: number;
  /** Sum of prices of currently selected items. */
  poolSpent: number;
  /** Called when user toggles a product on/off. */
  onToggle: (product: ProductResult) => void;
  /** Called when user clicks Done (multi-select only). */
  onDone?: () => void;
}

export default function SlotPicker({
  slotId,
  choices,
  selectedIds,
  maxQuantity,
  poolBudget,
  poolSpent,
  onToggle,
  onDone,
}: SlotPickerProps) {
  const label = slotId.replace(/_/g, " ");
  const isMulti = maxQuantity > 1;
  const remaining = poolBudget - poolSpent;
  const atCap = selectedIds.length >= maxQuantity;
  const selectedSet = new Set(selectedIds);

  return (
    <div className="slot-picker">
      <h2 className="slot-picker-question">
        {isMulti ? (
          <>
            Pick up to {maxQuantity}{" "}
            <span className="slot-picker-slot">{label}</span>
          </>
        ) : (
          <>
            Choose your{" "}
            <span className="slot-picker-slot">{label}</span>
          </>
        )}
      </h2>

      {/* Pool meter — multi-select only */}
      {isMulti && (
        <div className="pool-meter">
          <div className="pool-meter-bar">
            <div
              className="pool-meter-fill"
              style={{ width: `${Math.min(100, (poolSpent / poolBudget) * 100)}%` }}
            />
          </div>
          <p className="pool-meter-label">
            ${poolSpent.toFixed(2)} of ${poolBudget.toFixed(2)} used
            {selectedIds.length > 0 && (
              <span className="pool-meter-count">
                {" "}· {selectedIds.length}/{maxQuantity} selected
              </span>
            )}
          </p>
        </div>
      )}

      <div className="slot-picker-grid">
        {choices.map((product) => {
          const isSelected = selectedSet.has(product.product_id);
          // Disable if: not selected AND (at cap OR adding would exceed pool)
          const wouldExceedPool = !isSelected && product.normalized_price > remaining;
          // Single-select: never disable (clicking replaces selection)
          // Multi-select: disable if at cap or would exceed pool
          const disabled = isMulti && !isSelected && (atCap || wouldExceedPool);

          return (
            <PickerCard
              key={product.product_id}
              product={product}
              isSelected={isSelected}
              disabled={disabled}
              onToggle={onToggle}
            />
          );
        })}
      </div>

      {/* Done button — multi-select only */}
      {isMulti && (
        <button
          type="button"
          className="slot-picker-done"
          onClick={onDone}
          disabled={selectedIds.length === 0}
        >
          {selectedIds.length === 0
            ? "Select at least one"
            : `Done — ${selectedIds.length} ${label} selected`}
        </button>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Individual picker card
// ---------------------------------------------------------------------------

function PickerCard({
  product,
  isSelected,
  disabled,
  onToggle,
}: {
  product: ProductResult;
  isSelected: boolean;
  disabled: boolean;
  onToggle: (product: ProductResult) => void;
}) {
  const [imgError, setImgError] = useState(false);
  const showImage = product.image_url && !imgError;

  return (
    <button
      type="button"
      className={`picker-card${isSelected ? " selected" : ""}${disabled ? " disabled" : ""}`}
      onClick={() => !disabled && onToggle(product)}
      aria-disabled={disabled}
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

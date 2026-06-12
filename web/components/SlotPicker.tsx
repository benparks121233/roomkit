"use client";

// SlotPicker — "Choose your [slot]" card grid for the guided selection flow.
// Supports single-select (max_quantity=1) and multi-select (max_quantity>1).
//
// Single-select: tap a card to expand it and see details. Confirm with
// "Select" button, or tap another card to switch focus. This gives users
// time to review before committing.
//
// Multi-select: toggles items on/off with a pool meter and Done button.

import Image from "next/image";
import { useEffect, useRef, useState } from "react";
import type { ProductResult } from "@/lib/api";

function upgradeAmazonImage(url: string): string {
  return url.replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL800_.");
}

/** Trim long Amazon product names to something readable. */
function trimName(name: string, maxLen = 60): string {
  if (name.length <= maxLen) return name;
  // Try to break at a word boundary
  const trimmed = name.slice(0, maxLen);
  const lastSpace = trimmed.lastIndexOf(" ");
  return (lastSpace > maxLen * 0.6 ? trimmed.slice(0, lastSpace) : trimmed) + "…";
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

  // For single-select: which card is expanded (shows details + confirm)
  const [expandedId, setExpandedId] = useState<string | null>(null);

  // Reset expanded card when slot changes
  useEffect(() => {
    setExpandedId(null);
  }, [slotId]);

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
          const isExpanded = !isMulti && expandedId === product.product_id;
          // Disable if: not selected AND at cap. Pool is informational, not blocking.
          const disabled = isMulti && !isSelected && atCap;

          return (
            <PickerCard
              key={product.product_id}
              product={product}
              isSelected={isSelected}
              isExpanded={isExpanded}
              disabled={disabled}
              isMulti={isMulti}
              onToggle={onToggle}
              onExpand={(id) => setExpandedId(expandedId === id ? null : id)}
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
  isExpanded,
  disabled,
  isMulti,
  onToggle,
  onExpand,
}: {
  product: ProductResult;
  isSelected: boolean;
  isExpanded: boolean;
  disabled: boolean;
  isMulti: boolean;
  onToggle: (product: ProductResult) => void;
  onExpand: (productId: string) => void;
}) {
  const [imgError, setImgError] = useState(false);
  const showImage = product.image_url && !imgError;
  const expandedRef = useRef<HTMLDivElement>(null);

  // Scroll expanded card into view
  useEffect(() => {
    if (isExpanded && expandedRef.current) {
      expandedRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [isExpanded]);

  const handleClick = () => {
    if (disabled) return;
    if (isMulti) {
      // Multi-select: toggle directly
      onToggle(product);
    } else {
      // Single-select: expand to show details
      onExpand(product.product_id);
    }
  };

  return (
    <div
      ref={isExpanded ? expandedRef : undefined}
      className={[
        "picker-card",
        isSelected ? "selected" : "",
        isExpanded ? "expanded" : "",
        disabled ? "disabled" : "",
      ].filter(Boolean).join(" ")}
    >
      <button
        type="button"
        className="picker-card-main"
        onClick={handleClick}
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
          <p className="picker-card-name">{trimName(product.name)}</p>
          <p className="picker-card-price">${product.normalized_price.toFixed(2)}</p>
          {/* Show a short preview of fit_reason on collapsed cards */}
          {!isExpanded && product.fit_reason && (
            <p className="picker-card-reason">{product.fit_reason}</p>
          )}
        </div>
        {isSelected && (
          <div className="picker-card-check">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12l5 5L20 7" />
            </svg>
          </div>
        )}
      </button>

      {/* Expanded detail panel — single-select only */}
      {isExpanded && (
        <div className="picker-card-detail">
          {product.fit_reason && (
            <p className="picker-card-detail-reason">{product.fit_reason}</p>
          )}
          <button
            type="button"
            className="picker-card-select-btn"
            onClick={(e) => {
              e.stopPropagation();
              onToggle(product);
            }}
          >
            Select this {product.normalized_price > 0 ? `— $${product.normalized_price.toFixed(2)}` : ""}
          </button>
        </div>
      )}
    </div>
  );
}

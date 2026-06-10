"use client";

// Product card — shows a filled product or an empty slot with null_reason.
// Supports Feature A swap: toggle opens alternatives tray for swapping.
// Empty cards get dashed borders. Broken images fall back to a placeholder.

import Image from "next/image";
import { useState } from "react";
import type { ProductResult, SlotResult } from "@/lib/api";

/**
 * Upgrade Amazon product image URLs from 320px thumbnails to 800px.
 * Canopy returns URLs like `…/ID._AC_UL320_.jpg`; replacing the size
 * token gives us the same image at higher resolution — no extra API call.
 */
function upgradeAmazonImage(url: string): string {
  return url.replace(/\._AC_[A-Z]{2}\d+_\./, "._AC_SL800_.");
}

interface ProductCardProps {
  slot: SlotResult;
  /** The currently active product (may differ from slot.product after swaps). */
  activeProduct?: ProductResult | null;
  /** Available alternatives to swap to (excludes the active product). */
  alternatives?: ProductResult[];
  /** Called when user picks an alternative. */
  onSwap?: (product: ProductResult) => void;
}

export default function ProductCard({
  slot,
  activeProduct,
  alternatives,
  onSwap,
}: ProductCardProps) {
  const [imgError, setImgError] = useState(false);
  const [trayOpen, setTrayOpen] = useState(false);

  // Use activeProduct if provided, otherwise fall back to slot.product
  const product = activeProduct ?? slot.product;
  const hasAlternatives = alternatives && alternatives.length > 0 && onSwap;

  // --- Empty slot: owned or no match ---
  if (!product) {
    const isOwned = slot.null_reason === "owned";
    const message = isOwned
      ? "Owned"
      : slot.null_reason === "no_spec_match"
        ? "No spec match"
        : "No match found";

    return (
      <div className="product-card empty-card">
        <div className="card-image-placeholder">
          <span className="placeholder-icon">
            {isOwned ? (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12l5 5L20 7" />
              </svg>
            ) : (
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round">
                <path d="M5 12h14" />
              </svg>
            )}
          </span>
        </div>
        <div className="card-body">
          <p className="card-slot">{slot.slot_id.replace(/_/g, " ")}</p>
          <p className="card-null-reason">{message}</p>
        </div>
      </div>
    );
  }

  // --- Filled slot ---
  const showImage = product.image_url && !imgError;

  return (
    <div className="product-card">
      <div className="card-image-wrap">
        {showImage ? (
          <Image
            src={upgradeAmazonImage(product.image_url)}
            alt={product.name}
            width={800}
            height={800}
            sizes="(max-width: 640px) 50vw, 280px"
            style={{ objectFit: "contain", width: "100%", height: "auto" }}
            onError={() => setImgError(true)}
          />
        ) : (
          <div className="card-image-placeholder">
            <span className="placeholder-icon">
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <circle cx="8.5" cy="8.5" r="1.5" />
                <path d="M21 15l-5-5L5 21" />
              </svg>
            </span>
          </div>
        )}

        {/* Swap toggle */}
        {hasAlternatives && (
          <button
            type="button"
            className="swap-toggle"
            onClick={() => setTrayOpen((prev) => !prev)}
            aria-label={trayOpen ? "Close alternatives" : "View alternatives"}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M7 16V4m0 0L3 8m4-4l4 4" />
              <path d="M17 8v12m0 0l4-4m-4 4l-4-4" />
            </svg>
          </button>
        )}
      </div>

      <div className="card-body">
        <p className="card-slot">{slot.slot_id.replace(/_/g, " ")}</p>
        <p className="card-name">{product.name}</p>
        <p className="card-price">${product.normalized_price.toFixed(2)}</p>
        <p className="card-reason">{product.fit_reason}</p>
        <a
          href={product.buy_url}
          target="_blank"
          rel="noopener noreferrer"
          className="buy-btn"
        >
          Buy on Amazon
        </a>
      </div>

      {/* Alternatives tray */}
      {hasAlternatives && trayOpen && (
        <div className="alternatives-tray">
          {alternatives!.map((alt) => (
            <AltThumb
              key={alt.product_id}
              product={alt}
              onPick={() => {
                onSwap!(alt);
                setImgError(false); // reset for new image
              }}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Alternative thumbnail in the swap tray
// ---------------------------------------------------------------------------

function AltThumb({
  product,
  onPick,
}: {
  product: ProductResult;
  onPick: () => void;
}) {
  const [imgErr, setImgErr] = useState(false);
  const showImg = product.image_url && !imgErr;

  return (
    <button type="button" className="alt-thumb" onClick={onPick}>
      <div className="alt-thumb-image">
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
          <div className="alt-thumb-placeholder" />
        )}
      </div>
      <p className="alt-thumb-price">${product.normalized_price.toFixed(2)}</p>
    </button>
  );
}

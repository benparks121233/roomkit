"use client";

import { useState, useRef, useEffect } from "react";

interface Props {
  /** Absolute URL to the watermarked render image (e.g. http://localhost:8000/renders/{run_id}.jpg) */
  renderImageUrl: string;
  /** The shareable page URL (e.g. https://roomkit.ai/result/{run_id}) */
  pageUrl: string;
}

const SHARE_TEXT = "Look at the room I just designed with RoomKit!";
const PIN_DESCRIPTION = "AI-designed room — real, shoppable products, all on budget. Design yours at RoomKit.";

export default function ShareButton({ renderImageUrl, pageUrl }: Props) {
  const [showDropdown, setShowDropdown] = useState(false);
  const [copied, setCopied] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!showDropdown) return;
    const handler = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDropdown(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [showDropdown]);

  const handleNativeShare = async () => {
    // URL-only — no files. Receiving apps unfurl via OG tags.
    try {
      await navigator.share({
        title: SHARE_TEXT,
        text: "Design your own room in minutes — real products, on budget.",
        url: pageUrl,
      });
    } catch {
      // User cancelled or share failed — not an error.
    }
  };

  const handlePinterest = () => {
    const url = new URL("https://pinterest.com/pin/create/button/");
    url.searchParams.set("url", pageUrl);
    url.searchParams.set("media", renderImageUrl);
    url.searchParams.set("description", PIN_DESCRIPTION);
    window.open(url.toString(), "_blank", "noopener,noreferrer");
  };

  const handleX = () => {
    const url = new URL("https://twitter.com/intent/tweet");
    url.searchParams.set("url", pageUrl);
    url.searchParams.set("text", SHARE_TEXT);
    window.open(url.toString(), "_blank", "noopener,noreferrer");
  };

  const handleCopyLink = async () => {
    try {
      await navigator.clipboard.writeText(pageUrl);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const input = document.createElement("input");
      input.value = pageUrl;
      document.body.appendChild(input);
      input.select();
      document.execCommand("copy");
      document.body.removeChild(input);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleSaveImage = async () => {
    // Fetch as blob to bypass cross-origin <a download> restriction.
    try {
      const resp = await fetch(renderImageUrl);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "roomkit-room.jpg";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch {
      // Fallback: open image in new tab
      window.open(renderImageUrl, "_blank", "noopener,noreferrer");
    }
  };

  const hasNativeShare = typeof navigator !== "undefined" && !!navigator.share;

  return (
    <div className="share-wrapper" ref={dropdownRef}>
      <button
        type="button"
        className="share-primary-btn"
        onClick={() => {
          if (hasNativeShare) {
            handleNativeShare();
          } else {
            setShowDropdown((prev) => !prev);
          }
        }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8" />
          <polyline points="16 6 12 2 8 6" />
          <line x1="12" y1="2" x2="12" y2="15" />
        </svg>
        Share my room
      </button>

      {/* Mobile: Pin It + Save Image always visible alongside the Share button */}
      {hasNativeShare && (
        <div className="share-mobile-row">
          <button type="button" className="share-target-btn share-pinterest" onClick={handlePinterest}>
            <PinterestIcon /> Pin It
          </button>
          <button type="button" className="share-target-btn share-save" onClick={handleSaveImage}>
            <DownloadIcon /> Save Image
          </button>
        </div>
      )}

      {/* Desktop dropdown */}
      {!hasNativeShare && showDropdown && (
        <div className="share-dropdown">
          <button type="button" className="share-dropdown-item" onClick={handlePinterest}>
            <PinterestIcon /> Pin It
          </button>
          <button type="button" className="share-dropdown-item" onClick={handleX}>
            <XIcon /> Share on X
          </button>
          <button type="button" className="share-dropdown-item" onClick={handleCopyLink}>
            <LinkIcon /> {copied ? "Copied!" : "Copy Link"}
          </button>
          <button type="button" className="share-dropdown-item" onClick={handleSaveImage}>
            <DownloadIcon /> Save Image
          </button>
        </div>
      )}
    </div>
  );
}

// Minimal inline SVG icons — no external deps
function PinterestIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 0C5.373 0 0 5.373 0 12c0 5.084 3.163 9.426 7.627 11.174-.105-.949-.2-2.405.042-3.441.218-.937 1.407-5.965 1.407-5.965s-.359-.719-.359-1.782c0-1.668.967-2.914 2.171-2.914 1.023 0 1.518.769 1.518 1.69 0 1.029-.655 2.568-.993 3.995-.282 1.193.599 2.165 1.775 2.165 2.128 0 3.768-2.245 3.768-5.487 0-2.861-2.063-4.869-5.008-4.869-3.41 0-5.409 2.562-5.409 5.199 0 1.033.394 2.143.889 2.741.099.12.112.225.084.345-.09.375-.293 1.199-.334 1.363-.053.225-.174.271-.402.163-1.499-.698-2.436-2.889-2.436-4.649 0-3.785 2.75-7.262 7.929-7.262 4.163 0 7.398 2.967 7.398 6.931 0 4.136-2.607 7.464-6.227 7.464-1.216 0-2.359-.631-2.75-1.378l-.748 2.853c-.271 1.043-1.002 2.35-1.492 3.146C9.57 23.812 10.763 24 12 24c6.627 0 12-5.373 12-12S18.627 0 12 0z" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  );
}

function LinkIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71" />
    </svg>
  );
}

function DownloadIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" />
      <polyline points="7 10 12 15 17 10" />
      <line x1="12" y1="15" x2="12" y2="3" />
    </svg>
  );
}

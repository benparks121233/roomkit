"use client";

import { useCallback, useEffect, useRef, useState } from "react";

interface Props {
  renderUrl: string;
}

type ZoomMode = "idle" | "marquee";

export default function InteractiveRoomRender({ renderUrl }: Props) {
  // Zoom/pan state
  const [scale, setScale] = useState(1);
  const [translate, setTranslate] = useState({ x: 0, y: 0 });
  const [mode, setMode] = useState<ZoomMode>("idle");

  // Marquee selection box (in container px)
  const [marquee, setMarquee] = useState<{
    x1: number; y1: number; x2: number; y2: number;
    containerW: number; containerH: number;
  } | null>(null);

  // Pan drag
  const [dragging, setDragging] = useState(false);
  const dragStart = useRef({ x: 0, y: 0 });
  const translateStart = useRef({ x: 0, y: 0 });

  // Fullscreen
  const [fullscreen, setFullscreen] = useState(false);

  // Image loaded
  const [loaded, setLoaded] = useState(false);
  const [imgError, setImgError] = useState(false);
  const retryCount = useRef(0);

  // Clamp translate so image doesn't fly off
  const clampTranslateFor = useCallback(
    (tx: number, ty: number, s: number, containerW: number, containerH: number) => {
      const imgW = containerW * s;
      const imgH = (containerW * 1024) / 1536 * s;
      const maxX = Math.max(0, (imgW - containerW) / 2);
      const maxY = Math.max(0, (imgH - containerH) / 2);
      return {
        x: Math.max(-maxX, Math.min(maxX, tx)),
        y: Math.max(-maxY, Math.min(maxY, ty)),
      };
    },
    [],
  );

  // Reset zoom
  const resetZoom = useCallback(() => {
    setScale(1);
    setTranslate({ x: 0, y: 0 });
    setMode("idle");
  }, []);

  // Activate marquee zoom mode
  const activateMarquee = useCallback(() => {
    if (scale > 1) {
      resetZoom();
    }
    setMode("marquee");
  }, [scale, resetZoom]);

  // Handle pointer events — uses e.currentTarget for correct container
  const handlePointerDown = useCallback(
    (e: React.PointerEvent) => {
      const container = e.currentTarget as HTMLElement;
      const rect = container.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;

      if (mode === "marquee") {
        setMarquee({ x1: x, y1: y, x2: x, y2: y, containerW: rect.width, containerH: rect.height });
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
      } else if (scale > 1) {
        setDragging(true);
        dragStart.current = { x: e.clientX, y: e.clientY };
        translateStart.current = { ...translate };
        (e.target as HTMLElement).setPointerCapture(e.pointerId);
      }
    },
    [mode, scale, translate],
  );

  const handlePointerMove = useCallback(
    (e: React.PointerEvent) => {
      if (mode === "marquee" && marquee) {
        const container = e.currentTarget as HTMLElement;
        const rect = container.getBoundingClientRect();
        setMarquee((prev) => prev ? { ...prev, x2: e.clientX - rect.left, y2: e.clientY - rect.top } : null);
      } else if (dragging && scale > 1) {
        const container = e.currentTarget as HTMLElement;
        const rect = container.getBoundingClientRect();
        const dx = e.clientX - dragStart.current.x;
        const dy = e.clientY - dragStart.current.y;
        setTranslate(
          clampTranslateFor(translateStart.current.x + dx, translateStart.current.y + dy, scale, rect.width, rect.height),
        );
      }
    },
    [mode, marquee, dragging, scale, clampTranslateFor],
  );

  const handlePointerUp = useCallback(
    (e: React.PointerEvent) => {
      if (mode === "marquee" && marquee) {
        const x1 = Math.min(marquee.x1, marquee.x2);
        const y1 = Math.min(marquee.y1, marquee.y2);
        const x2 = Math.max(marquee.x1, marquee.x2);
        const y2 = Math.max(marquee.y1, marquee.y2);
        const boxW = x2 - x1;
        const boxH = y2 - y1;
        const cW = marquee.containerW;
        const cH = marquee.containerH;

        if (boxW > 20 && boxH > 20) {
          const newScale = Math.min(4, Math.max(
            cW / boxW,
            cH / boxH,
          ));
          const boxCenterX = (x1 + x2) / 2;
          const boxCenterY = (y1 + y2) / 2;
          const tx = (cW / 2 - boxCenterX) * newScale;
          const ty = (cH / 2 - boxCenterY) * newScale;

          setScale(newScale);
          setTranslate(clampTranslateFor(tx, ty, newScale, cW, cH));
        }
        setMarquee(null);
        setMode("idle");
      } else {
        setDragging(false);
      }
    },
    [mode, marquee, clampTranslateFor],
  );

  // Pinch zoom (touch)
  const lastPinchDist = useRef<number | null>(null);
  const handleTouchMove = useCallback(
    (e: React.TouchEvent) => {
      if (e.touches.length === 2) {
        e.preventDefault();
        const dx = e.touches[0].clientX - e.touches[1].clientX;
        const dy = e.touches[0].clientY - e.touches[1].clientY;
        const dist = Math.hypot(dx, dy);
        const container = e.currentTarget as HTMLElement;
        const rect = container.getBoundingClientRect();
        if (lastPinchDist.current !== null) {
          const delta = (dist - lastPinchDist.current) * 0.005;
          setScale((prev) => {
            const next = Math.max(1, Math.min(4, prev + delta));
            setTranslate((t) => clampTranslateFor(t.x, t.y, next, rect.width, rect.height));
            return next;
          });
        }
        lastPinchDist.current = dist;
      }
    },
    [clampTranslateFor],
  );

  const handleTouchEnd = useCallback(() => {
    lastPinchDist.current = null;
  }, []);

  // Reset translate when scale hits 1
  useEffect(() => {
    if (scale <= 1) {
      setTranslate({ x: 0, y: 0 });
    }
  }, [scale]);

  // Escape key closes fullscreen
  useEffect(() => {
    if (!fullscreen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setFullscreen(false);
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [fullscreen]);

  const renderContent = (isFullscreenView: boolean) => (
    <div
      className={`room-render-container ${isFullscreenView ? "room-render-fullscreen" : ""}`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onTouchMove={handleTouchMove}
      onTouchEnd={handleTouchEnd}
      style={{
        cursor: mode === "marquee"
          ? "crosshair"
          : scale > 1
            ? (dragging ? "grabbing" : "grab")
            : "default",
      }}
    >
      <div
        className="room-render-transform"
        style={{
          transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale})`,
          transition: dragging ? "none" : "transform 0.2s ease-out",
        }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={imgError ? "" : renderUrl}
          alt="AI-generated room render"
          className="room-render-image"
          onLoad={() => { setLoaded(true); setImgError(false); retryCount.current = 0; }}
          onError={() => {
            console.error("[RoomRender] image failed to load:", renderUrl);
            if (retryCount.current < 3) {
              retryCount.current += 1;
              setImgError(false);
              setTimeout(() => {
                setImgError(true);
                setTimeout(() => setImgError(false), 50);
              }, 1000 * retryCount.current);
            } else {
              setImgError(true);
            }
          }}
          draggable={false}
        />
        {imgError && (
          <div style={{
            position: "absolute", inset: 0,
            display: "flex", flexDirection: "column",
            alignItems: "center", justifyContent: "center",
            color: "#78716C", fontSize: "0.9rem",
          }}>
            <p>Image failed to load</p>
            <button
              type="button"
              onClick={() => { retryCount.current = 0; setImgError(false); }}
              style={{
                marginTop: 8, padding: "8px 16px",
                border: "1.5px solid #E2DED6", borderRadius: 8,
                background: "#FFF", cursor: "pointer", fontSize: "0.85rem",
              }}
            >
              Retry
            </button>
          </div>
        )}

      </div>

      {/* Marquee selection overlay */}
      {marquee && (
        <div
          className="room-render-marquee"
          style={{
            left: Math.min(marquee.x1, marquee.x2),
            top: Math.min(marquee.y1, marquee.y2),
            width: Math.abs(marquee.x2 - marquee.x1),
            height: Math.abs(marquee.y2 - marquee.y1),
          }}
        />
      )}

      {/* Controls */}
      {loaded && (
        <div className="room-render-zoom-controls">
          <button
            type="button"
            className={`room-render-zoom-btn ${mode === "marquee" ? "active" : ""}`}
            onClick={activateMarquee}
            aria-label="Area zoom"
            title="Area zoom — click and drag"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <path d="M21 21l-4.35-4.35" />
              <path d="M11 8v6M8 11h6" />
            </svg>
          </button>
          {scale > 1 && (
            <button
              type="button"
              className="room-render-zoom-btn"
              onClick={resetZoom}
              aria-label="Reset zoom"
              title="Reset zoom"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8" />
                <path d="M21 21l-4.35-4.35" />
                <path d="M8 11h6" />
              </svg>
            </button>
          )}
          {!isFullscreenView && (
            <button
              type="button"
              className="room-render-zoom-btn"
              onClick={() => { resetZoom(); setFullscreen(true); }}
              aria-label="Fullscreen"
              title="Fullscreen"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M8 3H5a2 2 0 00-2 2v3M21 8V5a2 2 0 00-2-2h-3M3 16v3a2 2 0 002 2h3M16 21h3a2 2 0 002-2v-3" />
              </svg>
            </button>
          )}
          {isFullscreenView && (
            <button
              type="button"
              className="room-render-zoom-btn"
              onClick={() => { resetZoom(); setFullscreen(false); }}
              aria-label="Close fullscreen"
              title="Close"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M18 6L6 18M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      )}

      {loaded && mode === "marquee" && (
        <div className="room-render-zoom-hint room-render-zoom-hint-active">
          Click and drag to select an area to zoom into
        </div>
      )}

    </div>
  );

  return (
    <>
      {renderContent(false)}

      {/* Fullscreen overlay */}
      {fullscreen && (
        <div
          className="room-render-fullscreen-overlay"
          onClick={(e) => {
            // Close when clicking the dark background (not the image)
            if (e.target === e.currentTarget) {
              resetZoom();
              setFullscreen(false);
            }
          }}
        >
          {renderContent(true)}
        </div>
      )}
    </>
  );
}

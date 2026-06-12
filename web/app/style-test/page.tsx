"use client";

import { useState, useRef, useCallback, useEffect } from "react";

// Drag-to-place room compositor with rotate + resize + export.

interface PieceConfig {
  id: string;
  label: string;
  src: string;
  left: number;
  top: number;
  width: number;
  rotate: number;
  zIndex: number;
  shadow: string;
}

interface PieceState {
  left: number;
  top: number;
  width: number;
  rotate: number;
}

const FLOOR_SHADOW = "drop-shadow(2px 5px 4px rgba(100, 75, 50, 0.3))";
const WALL_SHADOW = "drop-shadow(2px 3px 3px rgba(100, 75, 50, 0.15))";
const CEILING_SHADOW = "drop-shadow(0px 3px 4px rgba(100, 75, 50, 0.2))";

const INITIAL: PieceConfig[] = [
  { id: "curtains",      label: "Curtains",       src: "/room-assets/curtains.png",       left: 5.5,   top: 7.6,   width: 68,    rotate: 0,  zIndex: 1,  shadow: WALL_SHADOW },
  { id: "wall_art",      label: "Wall Art",        src: "/room-assets/wall_art.png",       left: 61.3,  top: 16,    width: 24,    rotate: 0,  zIndex: 2,  shadow: WALL_SHADOW },
  { id: "mirror",        label: "Mirror",          src: "/room-assets/mirror.png",         left: 58.2,  top: 40.4,  width: 18,    rotate: 0,  zIndex: 2,  shadow: WALL_SHADOW },
  { id: "ceiling_light", label: "Ceiling Light",   src: "/room-assets/ceiling_light.png",  left: 29.3,  top: 0.2,   width: 20,    rotate: 0,  zIndex: 10, shadow: CEILING_SHADOW },
  { id: "rug",           label: "Rug",             src: "/room-assets/rug.png",            left: 10.3,  top: 59.2,  width: 58,    rotate: 1,  zIndex: 3,  shadow: "none" },
  { id: "nightstand",    label: "Nightstand",      src: "/room-assets/nightstand.png",     left: 1.2,   top: 56.6,  width: 26,    rotate: 0,  zIndex: 4,  shadow: FLOOR_SHADOW },
  { id: "dresser",       label: "Dresser",         src: "/room-assets/dresser.png",        left: 54.9,  top: 50.9,  width: 34,    rotate: 0,  zIndex: 4,  shadow: FLOOR_SHADOW },
  { id: "bed",           label: "Bed",              src: "/room-assets/bed.png",            left: 13.3,  top: 49,    width: 52,    rotate: 0,  zIndex: 5,  shadow: FLOOR_SHADOW },
  { id: "throw_blanket", label: "Throw Blanket",   src: "/room-assets/throw_blanket.png",  left: 34.6,  top: 66.9,  width: 22,    rotate: 0,  zIndex: 6,  shadow: "none" },
  { id: "table_lamp",    label: "Table Lamp",      src: "/room-assets/table_lamp.png",     left: 4.7,   top: 43.2,  width: 20,    rotate: 0,  zIndex: 7,  shadow: FLOOR_SHADOW },
  { id: "floor_lamp",    label: "Floor Lamp",      src: "/room-assets/floor_lamp.png",     left: 70.3,  top: 39.4,  width: 42.5,  rotate: 0,  zIndex: 7,  shadow: FLOOR_SHADOW },
  { id: "plant",         label: "Plant",           src: "/room-assets/plant.png",          left: 66.8,  top: 37.1,  width: 24,    rotate: 0,  zIndex: 7,  shadow: FLOOR_SHADOW },
];

export default function StyleTestPage() {
  const containerRef = useRef<HTMLDivElement>(null);
  const [pieces, setPieces] = useState<Record<string, PieceState>>(
    Object.fromEntries(INITIAL.map((p) => [p.id, { left: p.left, top: p.top, width: p.width, rotate: p.rotate }]))
  );
  const [visible, setVisible] = useState<Record<string, boolean>>(
    Object.fromEntries(INITIAL.map((p) => [p.id, true]))
  );
  const [selected, setSelected] = useState<string | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const dragStart = useRef<{ mx: number; my: number; left: number; top: number } | null>(null);
  // Track that a piece interaction just happened so the container click doesn't clear selection
  const pieceInteracted = useRef(false);

  // ── Helpers ──
  const update = useCallback((id: string, patch: Partial<PieceState>) => {
    setPieces((prev) => {
      const existing = prev[id];
      if (!existing) return prev;
      return { ...prev, [id]: { ...existing, ...patch } };
    });
  }, []);

  // ── Drag ──
  const handlePointerDown = useCallback((e: React.PointerEvent, id: string) => {
    e.preventDefault();
    e.stopPropagation();
    if (!containerRef.current) return;
    const pos = pieces[id];
    if (!pos) return;
    pieceInteracted.current = true;
    setSelected(id);
    setDragging(id);
    dragStart.current = { mx: e.clientX, my: e.clientY, left: pos.left, top: pos.top };
    (e.target as HTMLElement).setPointerCapture(e.pointerId);
  }, [pieces]);

  const handlePointerMove = useCallback((e: React.PointerEvent) => {
    if (!dragging) return;
    const ds = dragStart.current;
    if (!ds) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect || rect.width === 0 || rect.height === 0) return;
    const newLeft = Math.round((ds.left + ((e.clientX - ds.mx) / rect.width) * 100) * 10) / 10;
    const newTop = Math.round((ds.top + ((e.clientY - ds.my) / rect.height) * 100) * 10) / 10;
    if (!Number.isFinite(newLeft) || !Number.isFinite(newTop)) return;
    setPieces((prev) => {
      const existing = prev[dragging];
      if (!existing) return prev;
      return { ...prev, [dragging]: { ...existing, left: newLeft, top: newTop } };
    });
  }, [dragging]);

  const handlePointerUp = useCallback(() => {
    setDragging(null);
    dragStart.current = null;
  }, []);

  // Container click: only deselect if the click was on empty space (not on a piece)
  const handleContainerClick = useCallback(() => {
    if (pieceInteracted.current) {
      pieceInteracted.current = false;
      return; // click originated on a piece — don't clear selection
    }
    setSelected(null);
  }, []);

  // ── Export ──
  const exportPositions = useCallback(() => {
    const lines = INITIAL.map((p) => {
      const s = pieces[p.id];
      return `  { id: "${p.id}", left: ${s.left}, top: ${s.top}, width: ${s.width}, rotate: ${s.rotate} },`;
    });
    const text = lines.join("\n");
    navigator.clipboard?.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
    console.log("Positions:\n" + text);
  }, [pieces]);

  // ── Keyboard: arrows = move, [ ] = rotate, - + = resize ──
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!selected) return;
      // Don't capture if user is in an input
      if ((e.target as HTMLElement).tagName === "INPUT") return;
      const step = e.shiftKey ? 2 : 0.5;
      const s = pieces[selected];
      if (!s) return;

      let handled = true;
      switch (e.key) {
        case "ArrowLeft":  update(selected, { left: Math.round((s.left - step) * 10) / 10 }); break;
        case "ArrowRight": update(selected, { left: Math.round((s.left + step) * 10) / 10 }); break;
        case "ArrowUp":    update(selected, { top: Math.round((s.top - step) * 10) / 10 }); break;
        case "ArrowDown":  update(selected, { top: Math.round((s.top + step) * 10) / 10 }); break;
        case "[":          update(selected, { rotate: Math.round((s.rotate - (e.shiftKey ? 5 : 1)) * 10) / 10 }); break;
        case "]":          update(selected, { rotate: Math.round((s.rotate + (e.shiftKey ? 5 : 1)) * 10) / 10 }); break;
        case "-": case "_": update(selected, { width: Math.max(3, Math.round((s.width - (e.shiftKey ? 4 : 1)) * 10) / 10) }); break;
        case "=": case "+": update(selected, { width: Math.min(95, Math.round((s.width + (e.shiftKey ? 4 : 1)) * 10) / 10) }); break;
        default: handled = false;
      }
      if (handled) e.preventDefault();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [selected, pieces, update]);

  const allOn = Object.values(visible).every(Boolean);
  const sel = selected ? pieces[selected] : null;

  return (
    <main style={{ maxWidth: 1200, margin: "0 auto", padding: "24px 24px 60px", background: "#FAF8F5", minHeight: "100vh" }}>
      <h1 style={{ fontFamily: "'DM Serif Display', Georgia, serif", fontSize: "1.5rem", color: "#1C1917", marginBottom: 4 }}>
        Room Compositor
      </h1>
      <p style={{ color: "#78716C", marginBottom: 12, fontSize: "0.8rem" }}>
        Drag to move &middot; Width &amp; Rotation sliders &middot; Arrows nudge, <code style={{ background: "#EDE5DA", padding: "1px 4px", borderRadius: 3 }}>[ ]</code> rotate, <code style={{ background: "#EDE5DA", padding: "1px 4px", borderRadius: 3 }}>- +</code> resize (hold Shift = bigger steps) &middot; Export when done
      </p>

      {/* Toggle row */}
      <div style={{
        display: "flex", flexWrap: "wrap", gap: "4px 10px", marginBottom: 8,
        alignItems: "center", fontSize: "0.73rem",
      }}>
        <button
          onClick={() => { const n = !allOn; setVisible(Object.fromEntries(INITIAL.map((p) => [p.id, n]))); }}
          style={{
            padding: "3px 8px", borderRadius: 5, border: "1px solid #D6D3D1",
            background: allOn ? "#1C1917" : "#fff", color: allOn ? "#fff" : "#1C1917",
            cursor: "pointer", fontSize: "0.7rem",
          }}
        >
          {allOn ? "Hide All" : "Show All"}
        </button>
        {INITIAL.map((p) => (
          <label key={p.id} style={{
            display: "flex", alignItems: "center", gap: 3, cursor: "pointer",
            color: selected === p.id ? "#1C1917" : "#78716C",
            fontWeight: selected === p.id ? 600 : 400,
          }}>
            <input
              type="checkbox" checked={visible[p.id]}
              onChange={() => setVisible((v) => ({ ...v, [p.id]: !v[p.id] }))}
              style={{ accentColor: "#1C1917", width: 12, height: 12 }}
            />
            <span onClick={(e) => { e.preventDefault(); setSelected(selected === p.id ? null : p.id); }}>
              {p.label}
            </span>
          </label>
        ))}
      </div>

      {/* Selected piece controls */}
      {selected && sel && (
        <div style={{
          display: "flex", gap: 12, flexWrap: "wrap", marginBottom: 8, padding: "6px 12px",
          background: "#EDE5DA", borderRadius: 8, alignItems: "center", fontSize: "0.75rem",
        }}>
          <strong style={{ color: "#1C1917", minWidth: 85 }}>
            {INITIAL.find((p) => p.id === selected)?.label}
          </strong>

          {/* Position readout */}
          <span style={{ color: "#57534E", fontFamily: "monospace", fontSize: "0.72rem", minWidth: 120 }}>
            L:{sel.left}% &nbsp; T:{sel.top}%
          </span>

          {/* Width slider */}
          <label style={{ color: "#57534E", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ minWidth: 40 }}>W: {sel.width}%</span>
            <input
              type="range" min={3} max={95} step={0.5}
              value={sel.width}
              onChange={(e) => update(selected, { width: +e.target.value })}
              style={{ width: 110 }}
            />
          </label>

          {/* Rotation slider */}
          <label style={{ color: "#57534E", display: "flex", alignItems: "center", gap: 4 }}>
            <span style={{ minWidth: 50 }}>Rot: {sel.rotate}&deg;</span>
            <input
              type="range" min={-180} max={180} step={0.5}
              value={sel.rotate}
              onChange={(e) => update(selected, { rotate: +e.target.value })}
              style={{ width: 110 }}
            />
            <button
              onClick={() => update(selected, { rotate: 0 })}
              style={{
                padding: "1px 6px", borderRadius: 4, border: "1px solid #C8C5BC",
                background: "#fff", cursor: "pointer", fontSize: "0.65rem", color: "#78716C",
              }}
              title="Reset rotation to 0°"
            >
              0&deg;
            </button>
          </label>

          {/* Export */}
          <button
            onClick={exportPositions}
            style={{
              marginLeft: "auto", padding: "4px 12px", borderRadius: 6,
              border: "1px solid #1C1917", background: copied ? "#1C1917" : "#fff",
              color: copied ? "#fff" : "#1C1917", cursor: "pointer", fontSize: "0.73rem",
              fontWeight: 500, transition: "all 0.2s",
            }}
          >
            {copied ? "Copied!" : "Export All Positions"}
          </button>
        </div>
      )}

      {/* Standalone export when nothing selected */}
      {!selected && (
        <div style={{ marginBottom: 8, display: "flex", justifyContent: "flex-end" }}>
          <button
            onClick={exportPositions}
            style={{
              padding: "4px 12px", borderRadius: 6, border: "1px solid #1C1917",
              background: copied ? "#1C1917" : "#fff", color: copied ? "#fff" : "#1C1917",
              cursor: "pointer", fontSize: "0.73rem", fontWeight: 500, transition: "all 0.2s",
            }}
          >
            {copied ? "Copied!" : "Export All Positions"}
          </button>
        </div>
      )}

      {/* ── COMPOSITE SCENE ── */}
      <div
        ref={containerRef}
        onPointerMove={handlePointerMove}
        onPointerUp={handlePointerUp}
        onClick={handleContainerClick}
        style={{
          position: "relative",
          width: "100%",
          aspectRatio: "1024 / 682",
          borderRadius: 12,
          overflow: "hidden",
          boxShadow: "0 4px 24px rgba(0,0,0,0.1)",
          background: "#EDE5DA",
          cursor: dragging ? "grabbing" : "default",
          userSelect: "none",
          touchAction: "none",
        }}
      >
        <img
          src="/room-assets/room-base.png"
          alt="Empty bedroom"
          draggable={false}
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%", objectFit: "cover", pointerEvents: "none" }}
        />

        {INITIAL.map((p) => {
          if (!visible[p.id]) return null;
          const s = pieces[p.id];
          if (!s) return null;
          return (
            <img
              key={p.id}
              src={p.src}
              alt={p.label}
              draggable={false}
              onPointerDown={(e) => handlePointerDown(e, p.id)}
              style={{
                position: "absolute",
                left: `${s.left}%`,
                top: `${s.top}%`,
                width: `${s.width}%`,
                height: "auto",
                zIndex: selected === p.id ? 50 : p.zIndex,
                filter: p.shadow,
                transform: s.rotate !== 0 ? `rotate(${s.rotate}deg)` : undefined,
                transformOrigin: "center center",
                cursor: dragging === p.id ? "grabbing" : "grab",
                outline: selected === p.id ? "2px dashed rgba(28,25,23,0.4)" : "none",
                outlineOffset: -1,
              }}
            />
          );
        })}
      </div>

      <p style={{ color: "#A8A29E", fontSize: "0.7rem", marginTop: 8, textAlign: "center" }}>
        Click piece to select &middot; Drag to move &middot; <b>Arrows</b> nudge &middot; <b>[ ]</b> rotate &middot; <b>&minus; +</b> resize &middot; Hold <b>Shift</b> for bigger steps &middot; Export when done
      </p>
    </main>
  );
}

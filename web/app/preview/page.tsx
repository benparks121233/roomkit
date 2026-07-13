"use client";

import { useEffect, useState } from "react";

export default function DesignPreviewPage() {
  const [renderVisible, setRenderVisible] = useState(false);
  const [triggerReveal, setTriggerReveal] = useState(false);

  useEffect(() => {
    if (triggerReveal) {
      const t = setTimeout(() => setRenderVisible(true), 100);
      return () => clearTimeout(t);
    }
  }, [triggerReveal]);

  return (
    <div style={tokens.page}>
      {/* ── Hero section (warm gradient bg) ── */}
      <section style={tokens.heroSection}>
        <h1 style={tokens.heroTitle}>
          Pick your aesthetic and budget.
        </h1>
        <p style={tokens.heroSubtitle}>
          Get your dream room, every piece real, every piece buyable, every piece just for you.
        </p>

        {/* Room-type hero cards */}
        <div style={tokens.heroCardRow}>
          <div style={tokens.heroCard}>
            <div style={tokens.heroCardImageSlot}>
              <img
                src="/preview-render.jpg"
                alt="Bedroom"
                style={tokens.heroCardImage}
              />
            </div>
            <div style={tokens.heroCardBody}>
              <h3 style={tokens.heroCardTitle}>Design a bedroom</h3>
              <p style={tokens.heroCardDesc}>12 aesthetics, full room</p>
            </div>
          </div>
          <div style={tokens.heroCard}>
            <div style={tokens.heroCardImageSlot}>
              <img
                src="/preview-render.jpg"
                alt="Living room"
                style={{ ...tokens.heroCardImage, filter: "hue-rotate(30deg) saturate(0.85)" }}
              />
            </div>
            <div style={tokens.heroCardBody}>
              <h3 style={tokens.heroCardTitle}>Design a living room</h3>
              <p style={tokens.heroCardDesc}>12 aesthetics, full room</p>
            </div>
          </div>
        </div>

        <button style={tokens.heroCTA}>Design my room</button>
      </section>

      {/* ── Section header (serif at scale) ── */}
      <section style={tokens.contentSection}>
        <h2 style={tokens.sectionTitle}>Your designs</h2>
        <p style={tokens.sectionSubtitle}>Your designed rooms will appear here</p>

        {/* Design card (My Designs treatment) */}
        <div style={tokens.designCardRow}>
          <div style={tokens.designCard}>
            <div style={tokens.designCardThumb}>
              <img
                src="/preview-render.jpg"
                alt="Coastal bedroom"
                style={tokens.designCardImg}
              />
            </div>
            <div style={tokens.designCardInfo}>
              <span style={tokens.designCardAesthetic}>Coastal</span>
              <span style={tokens.designCardRoomType}>bedroom</span>
              <div style={tokens.designCardMeta}>
                <span>$1,500</span>
                <span style={tokens.designCardDate}>Jun 16, 2026</span>
              </div>
            </div>
          </div>
          <div style={tokens.designCard}>
            <div style={tokens.designCardThumb}>
              <img
                src="/preview-render.jpg"
                alt="Dark Academia bedroom"
                style={{ ...tokens.designCardImg, filter: "saturate(0.7) brightness(0.85)" }}
              />
            </div>
            <div style={tokens.designCardInfo}>
              <span style={tokens.designCardAesthetic}>Dark Academia</span>
              <span style={tokens.designCardRoomType}>bedroom</span>
              <div style={tokens.designCardMeta}>
                <span>$2,500</span>
                <span style={tokens.designCardDate}>Jun 14, 2026</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Render container ("framed photograph" + materialize reveal) ── */}
      <section style={tokens.contentSection}>
        <h2 style={tokens.sectionTitle}>The render reveal</h2>
        <p style={tokens.sectionSubtitle}>
          Click to see the materialize effect (0.4s fade + scale)
        </p>

        {!triggerReveal ? (
          <button
            onClick={() => setTriggerReveal(true)}
            style={tokens.heroCTA}
          >
            Reveal your room
          </button>
        ) : (
          <div style={tokens.renderFrame}>
            <img
              src="/preview-render.jpg"
              alt="Your designed room"
              style={{
                ...tokens.renderImage,
                opacity: renderVisible ? 1 : 0,
                transform: renderVisible ? "scale(1)" : "scale(0.97)",
              }}
            />
          </div>
        )}
      </section>

      {/* ── How it works (accent serif) ── */}
      <section style={tokens.contentSection}>
        <h2 style={tokens.sectionTitle}>How it works</h2>
        <div style={tokens.stepsRow}>
          <div style={tokens.stepCard}>
            <span style={tokens.stepNumber}>1</span>
            <h3 style={tokens.stepTitle}>Pick your style</h3>
            <p style={tokens.stepDesc}>Choose your aesthetic and budget</p>
          </div>
          <div style={tokens.stepCard}>
            <span style={tokens.stepNumber}>2</span>
            <h3 style={tokens.stepTitle}>Get the room</h3>
            <p style={tokens.stepDesc}>AI designs a complete, coordinated room</p>
          </div>
          <div style={tokens.stepCard}>
            <span style={tokens.stepNumber}>3</span>
            <h3 style={tokens.stepTitle}>Shop your pieces</h3>
            <p style={tokens.stepDesc}>Every item curated to your style and budget</p>
          </div>
        </div>
      </section>

      {/* ── Token reference (for your review) ── */}
      <section style={{ ...tokens.contentSection, paddingBottom: 96 }}>
        <h2 style={tokens.sectionTitle}>Token reference</h2>
        <div style={{ display: "flex", flexDirection: "column", gap: 16, fontSize: "0.82rem", color: "#78716C", fontFamily: "'DM Sans', sans-serif" }}>
          <div><strong>--shadow-sm:</strong> 0 1px 3px rgba(28,25,23,0.06), 0 1px 2px rgba(28,25,23,0.04)</div>
          <div><strong>--shadow-md:</strong> 0 8px 24px rgba(28,25,23,0.08), 0 2px 6px rgba(28,25,23,0.04)</div>
          <div><strong>--shadow-lg:</strong> 0 16px 48px rgba(28,25,23,0.12), 0 4px 12px rgba(28,25,23,0.06)</div>
          <div><strong>--radius-sm:</strong> 8px &nbsp; <strong>--radius-md:</strong> 12px &nbsp; <strong>--radius-lg:</strong> 16px</div>
          <div><strong>--color-surface-warm:</strong> #F8F5F0 &nbsp; <strong>--color-surface-selected:</strong> #F8F6F2</div>
          <div><strong>Card border:</strong> 1px solid #E2DED6 + shadow (vs old 1.5px + no shadow)</div>
          <div style={{ marginTop: 8, padding: "12px 16px", background: "#F8F6F2", borderRadius: 8, border: "1px solid #E2DED6" }}>
            <strong>Caution zone:</strong> The cards above use 1px border + shadow. Compare the feel — do they look crisp and intentional, or floaty/mushy? This is the thing to judge.
          </div>
        </div>
      </section>
    </div>
  );
}

/* ── Deepened tokens as inline styles (isolated from globals.css) ── */

const SHADOW_SM = "0 1px 3px rgba(28,25,23,0.06), 0 1px 2px rgba(28,25,23,0.04)";
const SHADOW_MD = "0 8px 24px rgba(28,25,23,0.08), 0 2px 6px rgba(28,25,23,0.04)";
const SHADOW_LG = "0 16px 48px rgba(28,25,23,0.12), 0 4px 12px rgba(28,25,23,0.06)";

const tokens: Record<string, React.CSSProperties> = {
  page: {
    background: "#FAF8F5",
    minHeight: "100vh",
    fontFamily: "'DM Sans', -apple-system, sans-serif",
    color: "#1C1917",
  },

  /* ── Hero ── */
  heroSection: {
    background: "linear-gradient(180deg, #FAF8F5 0%, #F3F0EB 100%)",
    padding: "96px 24px 80px",
    textAlign: "center",
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 24,
  },
  heroTitle: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "2.8rem",
    fontWeight: 400,
    lineHeight: 1.15,
    letterSpacing: "-0.02em",
    color: "#1C1917",
    margin: 0,
    maxWidth: 640,
  },
  heroSubtitle: {
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "1.1rem",
    color: "#78716C",
    margin: 0,
    maxWidth: 520,
    lineHeight: 1.5,
  },
  heroCTA: {
    padding: "14px 40px",
    borderRadius: 12,
    border: "none",
    background: "#1C1917",
    color: "#FFFFFF",
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "1.05rem",
    fontWeight: 600,
    cursor: "pointer",
    marginTop: 8,
    transition: "background 0.15s, transform 0.15s",
    boxShadow: SHADOW_MD,
  },

  /* ── Hero cards ── */
  heroCardRow: {
    display: "flex",
    gap: 24,
    justifyContent: "center",
    marginTop: 16,
    flexWrap: "wrap",
  },
  heroCard: {
    width: 320,
    borderRadius: 16,
    overflow: "hidden",
    background: "#F8F5F0",
    border: "1px solid #E2DED6",
    boxShadow: SHADOW_LG,
    cursor: "pointer",
    transition: "transform 0.3s ease, box-shadow 0.3s ease",
  },
  heroCardImageSlot: {
    aspectRatio: "3 / 2",
    overflow: "hidden",
    background: "#F3F0EB",
  },
  heroCardImage: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    display: "block",
  },
  heroCardBody: {
    padding: "16px 20px 20px",
  },
  heroCardTitle: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "1.25rem",
    fontWeight: 400,
    margin: 0,
    color: "#1C1917",
  },
  heroCardDesc: {
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.85rem",
    color: "#78716C",
    margin: "4px 0 0",
  },

  /* ── Content sections ── */
  contentSection: {
    maxWidth: 900,
    margin: "0 auto",
    padding: "80px 24px 0",
  },
  sectionTitle: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "1.6rem",
    fontWeight: 400,
    color: "#1C1917",
    margin: "0 0 8px",
    letterSpacing: "-0.01em",
  },
  sectionSubtitle: {
    fontFamily: "'DM Sans', sans-serif",
    fontSize: "0.95rem",
    color: "#A8A29E",
    margin: "0 0 32px",
  },

  /* ── Design cards (My Designs) ── */
  designCardRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr",
    gap: 20,
  },
  designCard: {
    borderRadius: 12,
    overflow: "hidden",
    background: "#FFFFFF",
    border: "1px solid #E2DED6",
    boxShadow: SHADOW_SM,
    cursor: "pointer",
    transition: "box-shadow 0.2s ease, transform 0.2s ease, border-color 0.2s ease",
  },
  designCardThumb: {
    aspectRatio: "3 / 2",
    overflow: "hidden",
    background: "#F5F5F4",
  },
  designCardImg: {
    width: "100%",
    height: "100%",
    objectFit: "cover",
    display: "block",
  },
  designCardInfo: {
    padding: "12px 16px 16px",
    display: "flex",
    flexDirection: "column",
    gap: 2,
  },
  designCardAesthetic: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontWeight: 400,
    fontSize: "1rem",
    color: "#1C1917",
  },
  designCardRoomType: {
    fontSize: "0.8rem",
    color: "#78716C",
    textTransform: "capitalize",
  },
  designCardMeta: {
    display: "flex",
    justifyContent: "space-between",
    marginTop: 8,
    fontSize: "0.8rem",
    color: "#A8A29E",
  },
  designCardDate: {
    color: "#A8A29E",
  },

  /* ── Render container (framed photograph) ── */
  renderFrame: {
    maxWidth: 800,
    margin: "0 auto",
    borderRadius: 16,
    overflow: "hidden",
    background: "#1C1917",
    boxShadow: SHADOW_LG,
  },
  renderImage: {
    width: "100%",
    height: "auto",
    display: "block",
    transition: "opacity 0.4s ease, transform 0.4s ease",
    transformOrigin: "center center",
  },

  /* ── How it works steps ── */
  stepsRow: {
    display: "grid",
    gridTemplateColumns: "1fr 1fr 1fr",
    gap: 20,
  },
  stepCard: {
    background: "#FFFFFF",
    border: "1px solid #E2DED6",
    borderRadius: 12,
    padding: "24px 20px",
    boxShadow: SHADOW_SM,
    display: "flex",
    flexDirection: "column",
    gap: 8,
  },
  stepNumber: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "1.5rem",
    color: "#C8C5BC",
    lineHeight: 1,
  },
  stepTitle: {
    fontFamily: "'DM Serif Display', Georgia, serif",
    fontSize: "1.1rem",
    fontWeight: 400,
    color: "#1C1917",
    margin: 0,
  },
  stepDesc: {
    fontSize: "0.85rem",
    color: "#78716C",
    margin: 0,
    lineHeight: 1.45,
  },
};

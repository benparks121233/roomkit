"use client";

// Intake page — unified paginated wizard → POST /design → /result/[run_id].

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { createDesign } from "@/lib/api";
import type { DesignRequest } from "@/lib/api";
import StyleQuiz from "@/components/StyleQuiz";
import type { IntakeResult } from "@/components/StyleQuiz";

// ---------------------------------------------------------------------------
// Loading stages — mapped to real pipeline phases
// ---------------------------------------------------------------------------

const LOADING_STAGES = [
  { label: "Reading your style", duration: 3000 },
  { label: "Setting your budget", duration: 4000 },
  { label: "Finding your pieces", duration: 6000 },
  { label: "Styling your room", duration: 12000 },
];

// Total timeline: 25s across 4 stages. If API returns earlier, we snap.
// If it takes longer, stage 4 holds with a gentle loop.

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IntakePage() {
  const router = useRouter();

  const [loading, setLoading] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [stageProgress, setStageProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pendingResult, setPendingResult] = useState<IntakeResult | null>(null);
  const [chosenMode, setChosenMode] = useState<"curated" | "auto" | null>(null);

  const timersRef = useRef<NodeJS.Timeout[]>([]);
  const rafRef = useRef<number | null>(null);
  const stageStartRef = useRef(0);

  useEffect(() => {
    return () => {
      timersRef.current.forEach(clearTimeout);
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, []);

  const animateProgress = useCallback((stageIdx: number) => {
    const duration = LOADING_STAGES[stageIdx]?.duration ?? 8000;
    stageStartRef.current = performance.now();

    function tick() {
      const elapsed = performance.now() - stageStartRef.current;
      const raw = Math.min(elapsed / duration, 1);
      // Ease-out: fast start, slow finish
      const eased = 1 - Math.pow(1 - raw, 2.5);
      setStageProgress(eased);

      if (raw < 1) {
        rafRef.current = requestAnimationFrame(tick);
      } else {
        // Advance to next stage
        const next = stageIdx + 1;
        if (next < LOADING_STAGES.length) {
          setStageIndex(next);
          setStageProgress(0);
          animateProgress(next);
        } else {
          // Final stage done — hold at 100%, the API will resolve and navigate
          setStageProgress(1);
        }
      }
    }

    rafRef.current = requestAnimationFrame(tick);
  }, []);

  function startLoading() {
    setStageIndex(0);
    setStageProgress(0);
    animateProgress(0);
  }

  function stopLoading() {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    if (rafRef.current) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
  }

  // Wizard completion → show mode choice
  function handleComplete(result: IntakeResult) {
    setPendingResult(result);
  }

  // Mode chosen → API call
  async function handleModeChoice(mode: "curated" | "auto") {
    if (!pendingResult) return;
    setChosenMode(mode);
    setLoading(true);
    setError(null);
    startLoading();

    const req: DesignRequest = {
      room_type: pendingResult.roomType,
      budget: pendingResult.budget,
      style_description: pendingResult.quiz.style.description,
      core_aesthetic: pendingResult.quiz.style.core,
      bed_size: pendingResult.roomType === "bedroom" && pendingResult.bedSize ? pendingResult.bedSize : null,
      density: pendingResult.quiz.style.density,
      interests: pendingResult.quiz.interests.map((i) => i.category),
      full_room: pendingResult.fullRoom,
      wants: pendingResult.wants,
      excluded_slots: pendingResult.excludedSlots,
      mirror_type: pendingResult.mirrorType,
      screen_size: pendingResult.screenSize,
      tv_priority: pendingResult.tvPriority,
    };

    try {
      const design = await createDesign(req);
      stopLoading();
      const suffix = mode === "auto" ? "?mode=auto" : "";
      router.push(`/result/${design.run_id}${suffix}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      if (msg.includes("aborted")) {
        setError("Request timed out. The server may be busy \u2014 try again.");
      } else {
        setError(msg);
      }
      setLoading(false);
      stopLoading();
    }
  }

  // --- Loading view ---
  if (loading) {
    const currentStage = LOADING_STAGES[stageIndex];
    // Overall progress: completed stages + current stage fraction
    const overallProgress =
      (stageIndex + stageProgress) / LOADING_STAGES.length;

    return (
      <main className="intake-page">
        <div className="build-loading">
          <div className="build-loading-inner">
            <h2 className="build-loading-title">
              Building your dream room
            </h2>
            <p className="build-loading-tagline">
              Your personalized AI room renders at the end.
            </p>

            <div className="build-loading-stage-label">
              {currentStage.label}
            </div>

            <div className="build-loading-bar-track">
              <div
                className="build-loading-bar-fill"
                style={{ width: `${overallProgress * 100}%` }}
              />
            </div>

            <div className="build-loading-steps">
              {LOADING_STAGES.map((stage, i) => {
                let state: "done" | "active" | "pending" = "pending";
                if (i < stageIndex) state = "done";
                else if (i === stageIndex) state = "active";
                return (
                  <div
                    key={i}
                    className={`build-loading-step ${state}`}
                  >
                    <div className="build-loading-step-indicator">
                      {state === "done" ? (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M5 12l5 5L20 7" />
                        </svg>
                      ) : (
                        <div className="build-loading-step-dot" />
                      )}
                    </div>
                    <span className="build-loading-step-text">
                      {stage.label}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </main>
    );
  }

  // --- Mode choice (after quiz, before API call) ---
  if (pendingResult && !loading) {
    return (
      <main className="intake-page">
        <div style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          minHeight: "80vh",
          padding: "24px",
          textAlign: "center",
        }}>
          <h2 style={{
            fontSize: "1.3rem",
            fontWeight: 600,
            color: "#1C1917",
            marginBottom: 8,
          }}>
            How do you want to build your room?
          </h2>
          <p style={{
            fontSize: "0.85rem",
            color: "#78716C",
            marginBottom: 32,
            maxWidth: 420,
            lineHeight: 1.5,
          }}>
            Either way, you get the same AI-curated products. You can always swap items after.
          </p>

          {error && <div className="error-banner" style={{ marginBottom: 20 }}>{error}</div>}

          <div style={{ display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
            <button
              type="button"
              onClick={() => setChosenMode("curated")}
              style={{
                padding: "20px 28px",
                borderRadius: 12,
                border: chosenMode === "curated" ? "2px solid #1C1917" : "1.5px solid #E2DED6",
                background: chosenMode === "curated" ? "#FAFAF8" : "#FFF",
                cursor: "pointer",
                width: 220,
                textAlign: "left",
                transition: "border 0.15s, background 0.15s",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: "0.95rem", color: "#1C1917", marginBottom: 4 }}>
                Curated selection <span style={{ fontWeight: 400, fontSize: "0.8rem", opacity: 0.55 }}>(recommended)</span>
              </div>
              <div style={{ fontSize: "0.8rem", color: "#78716C", lineHeight: 1.4 }}>
                Pick each item yourself with our guided flow
              </div>
            </button>

            <button
              type="button"
              onClick={() => setChosenMode("auto")}
              style={{
                padding: "20px 28px",
                borderRadius: 12,
                border: chosenMode === "auto" ? "2px solid #1C1917" : "1.5px solid #E2DED6",
                background: chosenMode === "auto" ? "#1C1917" : "#FFF",
                color: chosenMode === "auto" ? "#FFF" : "#1C1917",
                cursor: "pointer",
                width: 220,
                textAlign: "left",
                transition: "border 0.15s, background 0.15s, color 0.15s",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: "0.95rem", marginBottom: 4 }}>
                Generate for me
              </div>
              <div style={{ fontSize: "0.8rem", opacity: chosenMode === "auto" ? 0.7 : 0.55, lineHeight: 1.4 }}>
                AI picks everything — see the full room instantly
              </div>
            </button>
          </div>

          <button
            type="button"
            disabled={!chosenMode}
            onClick={() => { if (chosenMode) handleModeChoice(chosenMode); }}
            style={{
              marginTop: 28,
              padding: "12px 48px",
              borderRadius: 10,
              border: "none",
              background: chosenMode ? "#1C1917" : "#D6D3D1",
              color: chosenMode ? "#FFF" : "#A8A29E",
              fontSize: "0.95rem",
              fontWeight: 600,
              cursor: chosenMode ? "pointer" : "default",
              transition: "background 0.15s, color 0.15s",
            }}
          >
            Continue
          </button>
        </div>
      </main>
    );
  }

  // --- Wizard view ---
  return (
    <main className="intake-page">
      <div className="intake-header">
        <h1>RoomKit</h1>
        <p className="subtitle">AI-designed rooms. On budget. Shoppable.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <StyleQuiz onComplete={handleComplete} />
    </main>
  );
}

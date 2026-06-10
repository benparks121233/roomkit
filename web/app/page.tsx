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

  // Wizard completion → API call
  async function handleComplete(result: IntakeResult) {
    setLoading(true);
    setError(null);
    startLoading();

    const req: DesignRequest = {
      room_type: result.roomType,
      budget: result.budget,
      style_description: result.quiz.style.description,
      bed_size: result.roomType === "bedroom" ? result.bedSize : null,
      density: result.quiz.style.density,
      interests: result.quiz.interests.map((i) => i.category),
      full_room: result.fullRoom,
      wants: result.wants,
    };

    try {
      const design = await createDesign(req);
      stopLoading();
      router.push(`/result/${design.run_id}`);
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

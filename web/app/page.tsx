"use client";

// Intake page — unified paginated wizard → POST /design → /result/[run_id].

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createDesign } from "@/lib/api";
import type { DesignRequest } from "@/lib/api";
import StyleQuiz from "@/components/StyleQuiz";
import type { IntakeResult } from "@/components/StyleQuiz";

// ---------------------------------------------------------------------------
// Loading step labels
// ---------------------------------------------------------------------------

const LOADING_STEPS = [
  "Interpreting your style...",
  "Planning room composition...",
  "Sourcing products...",
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function IntakePage() {
  const router = useRouter();

  // Loading state
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const timersRef = useRef<NodeJS.Timeout[]>([]);

  useEffect(() => {
    return () => timersRef.current.forEach(clearTimeout);
  }, []);

  function startLoadingSteps() {
    setLoadingStep(0);
    const t1 = setTimeout(() => setLoadingStep(1), 15_000);
    const t2 = setTimeout(() => setLoadingStep(2), 35_000);
    timersRef.current = [t1, t2];
  }

  function stopLoadingSteps() {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
  }

  // Wizard completion → API call
  async function handleComplete(result: IntakeResult) {
    setLoading(true);
    setError(null);
    startLoadingSteps();

    const req: DesignRequest = {
      room_type: result.roomType,
      budget: result.budget,
      style_description: result.quiz.style.description,
      bed_size: result.roomType === "bedroom" ? result.bedSize : null,
      full_room: result.fullRoom,
      wants: result.wants,
    };

    try {
      const design = await createDesign(req);
      router.push(`/result/${design.run_id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      if (msg.includes("aborted")) {
        setError("Request timed out. The server may be busy \u2014 try again.");
      } else {
        setError(msg);
      }
      setLoading(false);
      stopLoadingSteps();
    }
  }

  // --- Loading view ---
  if (loading) {
    return (
      <main className="intake-page">
        <div className="loading-state">
          <div className="loading-card">
            <h2 className="loading-title">Designing your room</h2>
            <div className="loading-steps">
              {LOADING_STEPS.map((label, i) => {
                let cls = "loading-step";
                if (i < loadingStep) cls += " done";
                else if (i === loadingStep) cls += " active";
                return (
                  <div key={i} className={cls}>
                    <div className="loading-step-dot" />
                    <span className="loading-step-text">{label}</span>
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

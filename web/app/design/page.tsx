"use client";

// Intake page — unified paginated wizard → POST /design → /result/[run_id].

import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { createDesign, FreeLimitError, startCheckout, trackEvent } from "@/lib/api";
import type { DesignRequest } from "@/lib/api";
import { useAuth } from "@/components/AuthProvider";
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
  return (
    <Suspense>
      <IntakeForm />
    </Suspense>
  );
}

function IntakeForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { session } = useAuth();
  const initialRoomType = searchParams.get("room") || undefined;

  const [loading, setLoading] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [stageProgress, setStageProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [pendingResult, setPendingResult] = useState<IntakeResult | null>(null);
  const [chosenMode, setChosenMode] = useState<"curated" | "auto" | null>(null);
  const [hitFreeLimit, setHitFreeLimit] = useState(false);
  const [checkoutLoading, setCheckoutLoading] = useState(false);

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

  // Quiz stash: localStorage with 30-min TTL (survives cross-tab email confirmation).
  // Stripe stash (rk_pending): stays on sessionStorage (same-tab redirect).
  const QUIZ_STASH_KEY = "rk_quiz_pending";
  const QUIZ_STASH_TTL_MS = 30 * 60 * 1000;

  const showAuthWall = !!pendingResult && !loading && !session;
  useEffect(() => {
    if (!showAuthWall || !pendingResult) return;
    localStorage.setItem(QUIZ_STASH_KEY, JSON.stringify({ answers: pendingResult, ts: Date.now() }));
  }, [showAuthWall, pendingResult]);

  // Restore stashed state after auth round-trips.
  // rk_pending (Stripe, sessionStorage) wins — it has result + mode.
  // rk_quiz_pending (localStorage) only has result; discarded if older than TTL.
  const quizFreshRef = useRef(false);
  const quizTrackedRef = useRef(false);
  const restoredRef = useRef(false);
  useEffect(() => {
    if (restoredRef.current || !session) return;

    const stripePending = sessionStorage.getItem("rk_pending");
    const quizRaw = localStorage.getItem(QUIZ_STASH_KEY);

    if (stripePending) {
      restoredRef.current = true;
      sessionStorage.removeItem("rk_pending");
      localStorage.removeItem(QUIZ_STASH_KEY);
      try {
        const { result, mode } = JSON.parse(stripePending);
        if (result && mode) {
          setPendingResult(result);
          setChosenMode(mode);
        }
      } catch { /* ignore corrupt data */ }
    } else if (quizRaw) {
      restoredRef.current = true;
      localStorage.removeItem(QUIZ_STASH_KEY);
      try {
        const { answers, ts } = JSON.parse(quizRaw);
        if (answers && answers.roomType && Date.now() - ts < QUIZ_STASH_TTL_MS) {
          setPendingResult(answers);
          quizFreshRef.current = true;
        }
      } catch { /* ignore corrupt data */ }
    }
  }, [session]);

  function handleComplete(result: IntakeResult) {
    localStorage.removeItem(QUIZ_STASH_KEY);
    setPendingResult(result);
    quizFreshRef.current = true;
  }

  useEffect(() => {
    if (session && pendingResult && quizFreshRef.current && !quizTrackedRef.current) {
      quizTrackedRef.current = true;
      trackEvent("", "quiz_completed", {
        roomType: pendingResult.roomType,
        budget: pendingResult.budget,
        aesthetic: pendingResult.quiz.style.core,
      });
    }
  }, [session, pendingResult]);

  // Mode chosen → API call
  async function handleModeChoice(mode: "curated" | "auto") {
    if (!pendingResult) return;
    if (!session) return;
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
      window.dispatchEvent(new Event("roomkit:pack-changed"));
      const suffix = mode === "auto" ? "?mode=auto" : "";
      router.push(`/result/${design.run_id}${suffix}`);
    } catch (err) {
      if (err instanceof FreeLimitError) {
        setHitFreeLimit(true);
        setLoading(false);
        stopLoading();
        return;
      }
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

  // --- Upgrade CTA (hit free limit) ---
  if (hitFreeLimit) {
    const handleUpgrade = async () => {
      setCheckoutLoading(true);
      setError(null);
      try {
        if (pendingResult && chosenMode) {
          const payload = { result: pendingResult, mode: chosenMode };
          sessionStorage.setItem("rk_pending", JSON.stringify(payload));
        } else {
          trackEvent("", "stash_failed", {
            hasPendingResult: !!pendingResult,
            hasChosenMode: !!chosenMode,
          });
        }
        const url = await startCheckout();
        window.location.href = url;
      } catch (err) {
        setError(err instanceof Error ? err.message : "Checkout failed");
        setCheckoutLoading(false);
      }
    };

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
          <div style={{
            fontSize: "2.5rem",
            marginBottom: 16,
          }}>
            &#x2728;
          </div>
          <h2 style={{
            fontSize: "1.3rem",
            fontWeight: 600,
            color: "#1C1917",
            marginBottom: 8,
          }}>
            You&apos;ve used your free room
          </h2>
          <p style={{
            fontSize: "0.9rem",
            color: "#78716C",
            marginBottom: 24,
            maxWidth: 400,
            lineHeight: 1.6,
          }}>
            Your first room design was on us. Upgrade to keep designing with full HD renders, all room types, and no watermarks.
          </p>

          <div style={{
            background: "#FAFAF8",
            border: "1.5px solid #E2DED6",
            borderRadius: 12,
            padding: "20px 28px",
            marginBottom: 24,
            maxWidth: 320,
            width: "100%",
          }}>
            <div style={{ fontWeight: 600, fontSize: "1.1rem", color: "#1C1917", marginBottom: 8 }}>
              Room Pack
            </div>
            <ul style={{
              listStyle: "none",
              padding: 0,
              margin: "0 0 16px 0",
              fontSize: "0.85rem",
              color: "#57534E",
              lineHeight: 1.8,
              textAlign: "left",
            }}>
              <li>&#x2713; 5 room designs</li>
              <li>&#x2713; All room types (bedroom, living room)</li>
              <li>&#x2713; HD renders, no watermark</li>
              <li>&#x2713; Rooms never expire</li>
            </ul>
            <div style={{ fontSize: "1.3rem", fontWeight: 700, color: "#1C1917" }}>
              $4.99
            </div>
            <p style={{ fontSize: "0.75rem", color: "#A8A29E", marginTop: 8, marginBottom: 0 }}>
              All sales are final. Credits restored for technical failures.
            </p>
          </div>

          {error && <p style={{ color: "#d32f2f", fontSize: "0.85rem", marginBottom: 12 }}>{error}</p>}

          <button
            type="button"
            onClick={handleUpgrade}
            disabled={checkoutLoading}
            style={{
              padding: "12px 48px",
              borderRadius: 10,
              border: "none",
              background: "#1C1917",
              color: "#FFF",
              fontSize: "0.95rem",
              fontWeight: 600,
              cursor: checkoutLoading ? "not-allowed" : "pointer",
              opacity: checkoutLoading ? 0.6 : 1,
            }}
          >
            {checkoutLoading ? "Redirecting to checkout..." : "Upgrade now"}
          </button>

          <button
            type="button"
            onClick={() => { setHitFreeLimit(false); setPendingResult(null); setChosenMode(null); }}
            style={{
              marginTop: 12,
              background: "none",
              border: "none",
              color: "#78716C",
              fontSize: "0.85rem",
              cursor: "pointer",
              textDecoration: "underline",
            }}
          >
            Back to home
          </button>
        </div>
      </main>
    );
  }

  // --- Auth wall (after quiz, before generation) ---
  if (pendingResult && !loading && !session) {
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
            Create an account to design your room
          </h2>
          <p style={{
            fontSize: "0.85rem",
            color: "#78716C",
            marginBottom: 28,
            maxWidth: 380,
            lineHeight: 1.5,
          }}>
            Your first design is free, no credit card required. Sign up in seconds and we&apos;ll generate your room.
          </p>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", justifyContent: "center" }}>
            <a
              href="/signup?redirect=/design"
              style={{
                padding: "12px 36px",
                borderRadius: 10,
                border: "none",
                background: "#1C1917",
                color: "#FFF",
                fontSize: "0.95rem",
                fontWeight: 600,
                textDecoration: "none",
                display: "inline-block",
              }}
            >
              Sign up
            </a>
            <a
              href="/login?redirect=/design"
              style={{
                padding: "12px 36px",
                borderRadius: 10,
                border: "1.5px solid #E2DED6",
                background: "#FFF",
                color: "#1C1917",
                fontSize: "0.95rem",
                fontWeight: 600,
                textDecoration: "none",
                display: "inline-block",
              }}
            >
              Log in
            </a>
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

          <div className="mode-choice-row" style={{ display: "flex", gap: 16, flexWrap: "wrap", justifyContent: "center" }}>
            <button
              type="button"
              className="mode-choice-card"
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
              className="mode-choice-card"
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
                RoomKit picks everything based on your style
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

          <p style={{
            marginTop: 16,
            fontSize: "0.75rem",
            color: "#A8A29E",
          }}>
            Your first room is free. No credit card needed.
          </p>
        </div>
      </main>
    );
  }

  // --- Wizard view ---
  return (
    <main className="intake-page">
      <div className="intake-header">
        <p className="subtitle">AI-designed rooms. On budget. Shoppable.</p>
      </div>

      {error && <div className="error-banner">{error}</div>}

      <StyleQuiz onComplete={handleComplete} initialRoomType={initialRoomType} />
    </main>
  );
}

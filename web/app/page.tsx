"use client";

// Intake screen — room type, budget, style quiz, bed size, ownership chips.
// Submit → POST /design (60-90s) → redirect to /result/[run_id].

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createDesign } from "@/lib/api";
import type { DesignRequest } from "@/lib/api";
import StyleQuiz from "@/components/StyleQuiz";
import type { QuizOutput } from "@/components/StyleQuiz";

// ---------------------------------------------------------------------------
// Ownership groups — mirrors slot_taxonomy.yaml groups
// ---------------------------------------------------------------------------

interface OwnershipGroup {
  label: string;
  items: string[];
}

const ROOM_OWNERSHIP_GROUPS: Record<string, OwnershipGroup[]> = {
  bedroom: [
    { label: "Bed",        items: ["bed_frame", "mattress", "sheets", "comforter", "pillows"] },
    { label: "Storage",    items: ["nightstand", "dresser"] },
    { label: "Lighting",   items: ["ceiling_light", "table_lamp", "floor_lamp"] },
    { label: "Decor",      items: ["wall_art", "plants", "mirror"] },
    { label: "Soft Goods", items: ["rug", "curtains", "throw_blanket"] },
  ],
  living_room: [
    { label: "Seating",       items: ["sofa", "armchair", "ottoman"] },
    { label: "Entertainment", items: ["tv", "tv_stand", "sound_bar"] },
    { label: "Tables",        items: ["coffee_table", "side_table"] },
    { label: "Lighting",      items: ["ceiling_light", "floor_lamp", "table_lamp"] },
    { label: "Decor",         items: ["wall_art", "plants", "mirror", "bookshelf"] },
    { label: "Soft Goods",    items: ["rug", "curtains", "throw_pillows", "throw_blanket"] },
  ],
};

const ROOM_TYPES = ["bedroom", "living_room"];
const BED_SIZES = ["twin", "full", "queen", "king"];

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

  // Form state
  const [roomType, setRoomType] = useState("bedroom");
  const [budget, setBudget] = useState(1500);
  const [style, setStyle] = useState("");
  const [styleSummary, setStyleSummary] = useState("");
  const [showQuiz, setShowQuiz] = useState(true);
  const [bedSize, setBedSize] = useState("queen");
  const [alreadyHave, setAlreadyHave] = useState<string[]>([]);

  // Loading state
  const [loading, setLoading] = useState(false);
  const [loadingStep, setLoadingStep] = useState(0);
  const [error, setError] = useState<string | null>(null);

  // Step timers for loading progress
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

  // Ownership chip toggles
  function toggleOwned(item: string) {
    setAlreadyHave((prev) =>
      prev.includes(item) ? prev.filter((i) => i !== item) : [...prev, item],
    );
  }

  function toggleGroup(items: string[]) {
    const allSelected = items.every((i) => alreadyHave.includes(i));
    if (allSelected) {
      setAlreadyHave((prev) => prev.filter((i) => !items.includes(i)));
    } else {
      setAlreadyHave((prev) => Array.from(new Set([...prev, ...items])));
    }
  }

  // Style quiz completion
  function handleQuizComplete(output: QuizOutput, summary: string) {
    setStyle(output.style.description);
    setStyleSummary(summary);
    setShowQuiz(false);
    // Interests captured for future personalization (step 3)
    if (output.interests.length > 0) {
      console.log("[RoomKit] Quiz interests:", output.interests);
    }
  }

  // Clear owned items when room type changes
  function handleRoomTypeChange(newType: string) {
    setRoomType(newType);
    setAlreadyHave([]);
  }

  // Submit
  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    startLoadingSteps();

    const req: DesignRequest = {
      room_type: roomType,
      budget,
      style_description: style,
      bed_size: roomType === "bedroom" ? bedSize : null,
      already_have: alreadyHave,
    };

    try {
      const design = await createDesign(req);
      router.push(`/result/${design.run_id}`);
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Something went wrong";
      if (msg.includes("aborted")) {
        setError("Request timed out. The server may be busy — try again.");
      } else {
        setError(msg);
      }
      setLoading(false);
      stopLoadingSteps();
    }
  }

  const groups = ROOM_OWNERSHIP_GROUPS[roomType] ?? [];

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

  // --- Form view ---
  return (
    <main className="intake-page">
      <div className="intake-header">
        <h1>RoomKit</h1>
        <p className="subtitle">AI-designed rooms. On budget. Shoppable.</p>
      </div>

      <form onSubmit={handleSubmit} className="intake-form">
        {error && <div className="error-banner">{error}</div>}

        {/* Room type */}
        <label className="field">
          <span className="field-label">Room type</span>
          <select value={roomType} onChange={(e) => handleRoomTypeChange(e.target.value)}>
            {ROOM_TYPES.map((t) => (
              <option key={t} value={t}>
                {t.replace("_", " ")}
              </option>
            ))}
          </select>
        </label>

        {/* Budget */}
        <label className="field">
          <span className="field-label">Budget</span>
          <div className="budget-input">
            <span className="budget-prefix">$</span>
            <input
              type="range"
              min={200}
              max={5000}
              step={50}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
            <input
              type="number"
              min={200}
              max={10000}
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
              className="budget-number"
            />
          </div>
        </label>

        {/* Style quiz or summary */}
        <fieldset className="field">
          <legend className="field-label">Style</legend>
          {showQuiz ? (
            <StyleQuiz roomType={roomType} onComplete={handleQuizComplete} />
          ) : (
            <div className="quiz-summary">
              <span className="quiz-summary-text">{styleSummary}</span>
              <button
                type="button"
                className="quiz-summary-edit"
                onClick={() => setShowQuiz(true)}
              >
                Edit
              </button>
            </div>
          )}
        </fieldset>

        {/* Bed size (bedroom only) */}
        {roomType === "bedroom" && (
          <label className="field">
            <span className="field-label">Bed size</span>
            <select value={bedSize} onChange={(e) => setBedSize(e.target.value)}>
              {BED_SIZES.map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </label>
        )}

        {/* Ownership chips */}
        <fieldset className="field">
          <legend className="field-label">I already own</legend>
          <div className="ownership-groups">
            {groups.map((group) => (
              <div key={group.label} className="ownership-section">
                <span
                  className="ownership-section-label"
                  onClick={() => toggleGroup(group.items)}
                >
                  {group.label}
                </span>
                <div className="ownership-chips">
                  {group.items.map((item) => (
                    <button
                      key={item}
                      type="button"
                      className={`ownership-chip ${alreadyHave.includes(item) ? "selected" : ""}`}
                      onClick={() => toggleOwned(item)}
                    >
                      <svg className="chip-check" viewBox="0 0 14 14" fill="none">
                        <path d="M2.5 7.5L5.5 10.5L11.5 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                      {item.replace(/_/g, " ")}
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </fieldset>

        <button type="submit" className="submit-btn" disabled={!style}>
          Design my room
        </button>
      </form>
    </main>
  );
}

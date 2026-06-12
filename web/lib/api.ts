// web/lib/api.ts
// Typed fetch client for all FastAPI endpoints.
// All API calls go through this module — never raw fetch in components.

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ---------------------------------------------------------------------------
// Types — mirrors app/api/schemas.py
// ---------------------------------------------------------------------------

export interface DesignRequest {
  room_type: string;
  budget: number;
  style_description: string;
  bed_size?: string | null;
  qa_answers?: Record<string, string>;
  density?: string;
  interests?: string[];
  full_room?: boolean;
  wants?: string[];
}

export interface ProductResult {
  product_id: string;
  name: string;
  normalized_price: number;
  image_url: string;
  buy_url: string;
  fit_reason: string;
}

export interface SlotResult {
  slot_id: string;
  allocated_budget: number;
  owned: boolean;
  max_quantity: number; // >1 enables multi-select (e.g. wall_art: 4)
  product: ProductResult | null;
  alternatives: ProductResult[];
  null_reason: string | null; // "owned" | "no_candidate" | "no_spec_match" | "llm_error"
}

export interface StyleResult {
  style_name: string;
  keywords: string[];
  mood: string;
  confidence: number;
  fallback: boolean;
}

export interface DesignResponse {
  run_id: string;
  room_type: string;
  style: StyleResult;
  target_budget: number;
  total_spent: number;
  is_feasible: boolean;
  slots: SlotResult[];
}

// ---------------------------------------------------------------------------
// Quiz output — captured by the intake questionnaire, consumed by future
// personalization pipeline. Only style.description is wired to the API today.
// ---------------------------------------------------------------------------

export interface QuizStyleOutput {
  core: string;
  mood: string;
  palette: string;
  materials: string[];
  shape: string;
  density: string;
  description: string;
}

export interface QuizInterest {
  category: string;
  tags: string[];
}

export interface QuizOutput {
  style: QuizStyleOutput;
  interests: QuizInterest[];
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * POST /design — runs the full pipeline (~17 LLM calls, 60-90s).
 * Timeout set to 120s to match backend reality.
 */
export async function createDesign(request: DesignRequest): Promise<DesignResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);

  try {
    const res = await fetch(`${API_BASE}/design`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
      signal: controller.signal,
    });

    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `API error ${res.status}`);
    }

    return (await res.json()) as DesignResponse;
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * GET /design/{run_id} — retrieve a saved board.
 */
export async function getDesign(runId: string): Promise<DesignResponse> {
  const res = await fetch(`${API_BASE}/design/${runId}`);
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `API error ${res.status}`);
  }
  return (await res.json()) as DesignResponse;
}

// ---------------------------------------------------------------------------
// Selection validation (multi-select pool spend check)
// ---------------------------------------------------------------------------

export interface SlotSelection {
  slot_id: string;
  selected_product_ids: string[];
}

export interface SlotValidationResult {
  slot_id: string;
  valid: boolean;
  total: number;
  reason: string | null;
}

export interface ValidateSelectionsResponse {
  valid: boolean;
  total_spent: number;
  slots: SlotValidationResult[];
}

/**
 * POST /design/{run_id}/validate-selections — server-side pool spend check.
 * Prices are looked up from the stored design; client sends only product_ids.
 */
export async function validateSelections(
  runId: string,
  selections: SlotSelection[],
): Promise<ValidateSelectionsResponse> {
  const res = await fetch(`${API_BASE}/design/${runId}/validate-selections`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ selections }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Validation error ${res.status}`);
  }
  return (await res.json()) as ValidateSelectionsResponse;
}

export { API_BASE };

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
  core_aesthetic?: string;
  bed_size?: string | null;
  qa_answers?: Record<string, string>;
  density?: string;
  interests?: string[];
  full_room?: boolean;
  wants?: string[];
  excluded_slots?: string[];
  mirror_type?: string | null;
  allow_over_budget?: boolean;
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
  user_budget: number;  // User's stated budget (before over-budget multiplier)
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

// ---------------------------------------------------------------------------
// Room render (AI-generated photorealistic room image)
// ---------------------------------------------------------------------------

export interface RenderResponse {
  run_id: string;
  render_url: string;
  cached: boolean;
}

export interface Hotspot {
  slot_id: string;
  x: number;      // 0-1 fraction of image width (center)
  y: number;      // 0-1 fraction of image height (center)
  w: number;      // 0-1 fraction width
  h: number;      // 0-1 fraction height
  product_name: string;
  price: number;
  buy_url: string;
}

export interface HotspotsResponse {
  run_id: string;
  hotspots: Hotspot[];
  cached: boolean;
}

/**
 * POST /design/{run_id}/render — generate AI room render.
 * Sends the user's actual product selections so the render uses those,
 * not the server's default rank-1 picks.
 * Takes ~15-60s on first call; cached after that.
 */
export async function generateRender(
  runId: string,
  selections: Record<string, string[]>,
): Promise<RenderResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 120_000);
  try {
    const res = await fetch(`${API_BASE}/design/${runId}/render`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ selections }),
      signal: controller.signal,
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail ?? `Render error ${res.status}`);
    }
    return (await res.json()) as RenderResponse;
  } finally {
    clearTimeout(timeout);
  }
}

// Predetermined hotspot positions — same layout the render prompt specifies.
// Hotspots are built client-side from the user's actual selections + these
// positions, ensuring labels always match what the user selected.
export const HOTSPOT_POSITIONS: Record<string, Record<string, { x: number; y: number; w: number; h: number }>> = {
  bedroom: {
    bed_frame:     { x: 0.42, y: 0.55, w: 0.40, h: 0.35 },
    mattress:      { x: 0.42, y: 0.50, w: 0.35, h: 0.18 },
    sheets:        { x: 0.42, y: 0.52, w: 0.30, h: 0.12 },
    comforter:     { x: 0.42, y: 0.55, w: 0.35, h: 0.20 },
    pillows:       { x: 0.42, y: 0.38, w: 0.25, h: 0.10 },
    nightstand:    { x: 0.14, y: 0.55, w: 0.12, h: 0.18 },
    table_lamp:    { x: 0.14, y: 0.40, w: 0.08, h: 0.14 },
    dresser:       { x: 0.82, y: 0.52, w: 0.18, h: 0.25 },
    floor_lamp:    { x: 0.68, y: 0.38, w: 0.08, h: 0.30 },
    rug:           { x: 0.42, y: 0.78, w: 0.45, h: 0.18 },
    curtains:      { x: 0.42, y: 0.25, w: 0.55, h: 0.15 },
    wall_art:      { x: 0.42, y: 0.18, w: 0.25, h: 0.16 },
    plants:        { x: 0.90, y: 0.62, w: 0.12, h: 0.22 },
    mirror:        { x: 0.82, y: 0.28, w: 0.12, h: 0.18 },
    ceiling_light: { x: 0.45, y: 0.06, w: 0.12, h: 0.10 },
    throw_blanket: { x: 0.42, y: 0.65, w: 0.25, h: 0.10 },
    duvet_insert:  { x: 0.42, y: 0.54, w: 0.35, h: 0.18 },
    duvet_cover:   { x: 0.42, y: 0.55, w: 0.35, h: 0.20 },
    desk:          { x: 0.88, y: 0.50, w: 0.14, h: 0.22 },
    desk_chair:    { x: 0.85, y: 0.60, w: 0.10, h: 0.18 },
    sconce:        { x: 0.22, y: 0.30, w: 0.08, h: 0.12 },
    wallpaper:     { x: 0.42, y: 0.15, w: 0.50, h: 0.30 },
  },
  living_room: {
    sofa:          { x: 0.38, y: 0.55, w: 0.40, h: 0.25 },
    coffee_table:  { x: 0.40, y: 0.72, w: 0.22, h: 0.12 },
    side_table:    { x: 0.65, y: 0.55, w: 0.10, h: 0.15 },
    table_lamp:    { x: 0.65, y: 0.40, w: 0.08, h: 0.14 },
    tv_stand:      { x: 0.82, y: 0.50, w: 0.18, h: 0.20 },
    floor_lamp:    { x: 0.88, y: 0.35, w: 0.08, h: 0.30 },
    rug:           { x: 0.40, y: 0.78, w: 0.40, h: 0.15 },
    curtains:      { x: 0.40, y: 0.22, w: 0.50, h: 0.15 },
    wall_art:      { x: 0.38, y: 0.18, w: 0.25, h: 0.16 },
    plants:        { x: 0.90, y: 0.60, w: 0.12, h: 0.22 },
    mirror:        { x: 0.82, y: 0.25, w: 0.12, h: 0.18 },
    throw_pillows: { x: 0.35, y: 0.48, w: 0.15, h: 0.10 },
    throw_blanket: { x: 0.42, y: 0.58, w: 0.18, h: 0.10 },
    ceiling_light: { x: 0.45, y: 0.06, w: 0.12, h: 0.10 },
  },
};

// ---------------------------------------------------------------------------
// Event tracking (fire-and-forget — never blocks or throws)
// ---------------------------------------------------------------------------

export function trackEvent(
  runId: string,
  eventType: string,
  data: Record<string, unknown> = {},
): void {
  fetch(`${API_BASE}/track`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ run_id: runId, event_type: eventType, data }),
  }).catch(() => {});  // swallow errors — tracking must never affect UX
}

export { API_BASE };

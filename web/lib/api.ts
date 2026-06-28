import { getSupabaseBrowserClient } from "@/lib/supabase";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function authHeaders(): Promise<Record<string, string>> {
  const supabase = getSupabaseBrowserClient();
  const { data: { session } } = await supabase.auth.getSession();
  if (session?.access_token) {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${session.access_token}`,
    };
  }
  return { "Content-Type": "application/json" };
}

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
  screen_size?: string | null;
  tv_priority?: boolean;
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
  selected_products: ProductResult[]; // user's final picks (set at finalize)
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
  finalized_at: string | null; // ISO timestamp; set once at finalize
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
    const headers = await authHeaders();
    const res = await fetch(`${API_BASE}/design`, {
      method: "POST",
      headers,
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
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/design/${runId}`, { headers });
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
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/design/${runId}/validate-selections`, {
    method: "POST",
    headers,
    body: JSON.stringify({ selections }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Validation error ${res.status}`);
  }
  return (await res.json()) as ValidateSelectionsResponse;
}

// ---------------------------------------------------------------------------
// Design finalization (freeze curated selections)
// ---------------------------------------------------------------------------

/**
 * PATCH /design/{run_id}/finalize — freeze the user's curated selections.
 * Called once when selections are settled (auto-fill or guided curation).
 * Returns the updated DesignResponse with selected_products and finalized_at set.
 * Returns 409 if already finalized (safe to ignore — idempotent).
 */
export async function finalizeDesign(
  runId: string,
  selections: Record<string, string[]>,
  skippedSlots: string[],
): Promise<DesignResponse | null> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/design/${runId}/finalize`, {
    method: "PATCH",
    headers,
    body: JSON.stringify({ selections, skipped_slots: skippedSlots }),
  });
  // 409 = already finalized — not an error, but no valid DesignResponse body
  if (res.status === 409) return null;
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Finalize error ${res.status}`);
  }
  return (await res.json()) as DesignResponse;
}

// ---------------------------------------------------------------------------
// Room render (AI-generated photorealistic room image)
// ---------------------------------------------------------------------------

export interface RenderResponse {
  run_id: string;
  render_url: string;
  cached: boolean;
}

export class RenderTimeoutError extends Error {
  runId: string;
  jobId: string;
  constructor(runId: string, jobId: string) {
    super("Render is taking longer than expected");
    this.name = "RenderTimeoutError";
    this.runId = runId;
    this.jobId = jobId;
  }
}

class RenderFailedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "RenderFailedError";
  }
}

interface RenderStatusResponse {
  status: "pending" | "rendering" | "complete" | "failed" | "unknown";
  render_url?: string;
  error?: string;
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

async function pollRenderStatus(
  runId: string,
  jobId: string,
): Promise<RenderResponse> {
  const headers = await authHeaders();
  const maxAttempts = 60;
  const intervalMs = 3_000;

  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, intervalMs));
    try {
      const res = await fetch(
        `${API_BASE}/design/${runId}/render/status?job_id=${jobId}`,
        { headers },
      );
      if (!res.ok) continue;
      const data: RenderStatusResponse = await res.json();

      if (data.status === "complete" && data.render_url) {
        return { run_id: runId, render_url: data.render_url, cached: false };
      }
      if (data.status === "failed") {
        throw new RenderFailedError(data.error ?? "Render generation failed");
      }
      // pending, rendering, unknown → keep polling
    } catch (e) {
      if (e instanceof RenderFailedError) throw e;
      // Network blip, JSON parse error, etc. → keep polling
      continue;
    }
  }

  throw new RenderTimeoutError(runId, jobId);
}

/**
 * POST /design/{run_id}/render — generate AI room render.
 * Handles both sync (200) and async (202 + poll) responses transparently.
 * Throws RenderTimeoutError if polling exhausts — caller should show
 * "taking longer than expected" with a "check again" option, not a hard failure.
 */
export async function generateRender(
  runId: string,
): Promise<RenderResponse> {
  const headers = await authHeaders();
  const res = await fetch(`${API_BASE}/design/${runId}/render`, {
    method: "POST",
    headers,
    body: JSON.stringify({}),
  });

  if (res.status === 202) {
    const body = await res.json();
    return pollRenderStatus(runId, body.job_id);
  }

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail ?? `Render error ${res.status}`);
  }

  const body = await res.json();
  return { run_id: body.run_id, render_url: body.render_url, cached: body.cached ?? false };
}

/**
 * Check render status — used by "check again" button after RenderTimeoutError.
 */
export async function checkRenderStatus(
  runId: string,
  jobId: string,
): Promise<RenderStatusResponse> {
  const headers = await authHeaders();
  const res = await fetch(
    `${API_BASE}/design/${runId}/render/status?job_id=${jobId}`,
    { headers },
  );
  if (!res.ok) return { status: "unknown" };
  return await res.json();
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
  },
  living_room: {
    sofa:          { x: 0.38, y: 0.55, w: 0.40, h: 0.25 },
    coffee_table:  { x: 0.40, y: 0.72, w: 0.22, h: 0.12 },
    side_table:    { x: 0.65, y: 0.55, w: 0.10, h: 0.15 },
    table_lamp:    { x: 0.65, y: 0.40, w: 0.08, h: 0.14 },
    tv:            { x: 0.82, y: 0.38, w: 0.16, h: 0.14 },
    tv_stand:      { x: 0.82, y: 0.50, w: 0.18, h: 0.20 },
    tv_mount:      { x: 0.82, y: 0.35, w: 0.16, h: 0.14 },
    floor_lamp:    { x: 0.88, y: 0.35, w: 0.08, h: 0.30 },
    rug:           { x: 0.40, y: 0.78, w: 0.40, h: 0.15 },
    curtains:      { x: 0.40, y: 0.22, w: 0.50, h: 0.15 },
    wall_art:      { x: 0.38, y: 0.18, w: 0.25, h: 0.16 },
    plants:        { x: 0.90, y: 0.60, w: 0.12, h: 0.22 },
    bookshelf:     { x: 0.12, y: 0.45, w: 0.14, h: 0.30 },
    throw_pillows: { x: 0.35, y: 0.48, w: 0.15, h: 0.10 },
    throw_blanket: { x: 0.42, y: 0.58, w: 0.18, h: 0.10 },
    ceiling_light: { x: 0.45, y: 0.06, w: 0.12, h: 0.10 },
    armchair:      { x: 0.14, y: 0.58, w: 0.16, h: 0.20 },
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
  authHeaders()
    .then((headers) =>
      fetch(`${API_BASE}/track`, {
        method: "POST",
        headers,
        body: JSON.stringify({ run_id: runId, event_type: eventType, data }),
      }),
    )
    .catch(() => {});
}

export { API_BASE };

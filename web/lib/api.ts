// web/lib/api.ts
// Typed fetch client for all FastAPI endpoints.
// All API calls go through this module — never raw fetch in components.
// Stage 3/9: add typed request/response interfaces as endpoints are implemented.

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Stage 3/9: implement typed wrappers
export async function createDesign(_request: unknown): Promise<{ run_id: string }> {
  // POST /design
  throw new Error("Stage 3/9: implement createDesign");
}

export async function getDesign(_runId: string): Promise<unknown> {
  // GET /design/{run_id}
  throw new Error("Stage 9: implement getDesign");
}

export async function recordClick(_event: unknown): Promise<void> {
  // POST /click
  throw new Error("Stage 10: implement recordClick");
}

export { API_BASE };

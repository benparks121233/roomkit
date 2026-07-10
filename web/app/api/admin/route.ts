import { NextRequest, NextResponse } from "next/server";
import { createClient } from "@supabase/supabase-js";

const ADMIN_SECRET = process.env.ADMIN_SECRET ?? "";
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

const ADMIN_USER_IDS = new Set([
  "597ced63-98ff-427e-8606-931e9af7b751",
]);

export async function GET(request: NextRequest) {
  if (!ADMIN_SECRET) {
    return NextResponse.json({ error: "Admin not configured" }, { status: 503 });
  }

  const authHeader = request.headers.get("authorization") ?? "";
  const token = authHeader.startsWith("Bearer ") ? authHeader.slice(7) : "";

  if (!token) {
    return NextResponse.json({ error: "Missing authorization" }, { status: 401 });
  }

  let userId: string;
  try {
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: `Bearer ${token}` } },
    });
    const { data: { user }, error } = await supabase.auth.getUser(token);
    if (error || !user) {
      return NextResponse.json({ error: "Invalid session" }, { status: 401 });
    }
    userId = user.id;
  } catch {
    return NextResponse.json({ error: "Auth verification failed" }, { status: 401 });
  }

  if (!ADMIN_USER_IDS.has(userId)) {
    return NextResponse.json({ error: "Not an admin" }, { status: 403 });
  }

  try {
    const res = await fetch(`${API_BASE}/admin/stats?secret=${encodeURIComponent(ADMIN_SECRET)}`);
    if (!res.ok) {
      return NextResponse.json({ error: `Backend ${res.status}` }, { status: res.status });
    }
    const data = await res.json();
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Backend unreachable" }, { status: 502 });
  }
}

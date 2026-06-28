import type { Metadata } from "next";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";

export async function generateMetadata({
  params,
}: {
  params: Promise<{ run_id: string }>;
}): Promise<Metadata> {
  const { run_id } = await params;

  const title = "Look at the new room I designed with RoomKit!";
  const description =
    "Design your own room in minutes — real products, on budget.";

  // Check if a render exists (HEAD request to the static file path).
  // Phase 7 note: switch to reading render_url from the design row
  // once that column exists, avoiding this network round-trip.
  let ogImage = `${SITE_URL}/og-default.jpg`;
  try {
    const renderUrl = `${API_BASE}/renders/${run_id}.jpg`;
    const head = await fetch(renderUrl, { method: "HEAD" });
    if (head.ok) {
      ogImage = renderUrl;
    }
  } catch {
    // Render check failed — use fallback. Non-blocking.
  }

  return {
    title,
    description,
    openGraph: {
      title,
      description,
      images: [{ url: ogImage }],
      type: "website",
      siteName: "RoomKit",
    },
    twitter: {
      card: "summary_large_image",
      title,
      description,
      images: [ogImage],
    },
  };
}

export default function ResultLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}

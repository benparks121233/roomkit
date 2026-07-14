import type { Metadata } from "next";

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000";
const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

function storageRenderUrl(run_id: string): string | null {
  if (!SUPABASE_URL) return null;
  return `${SUPABASE_URL}/storage/v1/object/public/renders/${run_id}.jpg`;
}

export async function generateMetadata({
  params,
}: {
  params: Promise<{ run_id: string }>;
}): Promise<Metadata> {
  const { run_id } = await params;

  const title = "Look at the new room I designed with RoomKit!";
  const description =
    "Design your own room in minutes. Real products, on budget.";

  let ogImage = `${SITE_URL}/og-default.jpg`;
  try {
    const renderUrl = storageRenderUrl(run_id);
    if (renderUrl) {
      const head = await fetch(renderUrl, { method: "HEAD" });
      if (head.ok) {
        ogImage = renderUrl;
      }
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

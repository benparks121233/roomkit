// web/app/layout.tsx
// Root layout — wraps all routes. Stage 9: add nav, fonts, metadata.

import type { Metadata } from "next";
import "../styles/globals.css";

export const metadata: Metadata = {
  title: "RoomKit",
  description: "AI-designed rooms. On budget. Shoppable.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

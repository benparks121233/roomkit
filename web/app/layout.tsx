import type { Metadata } from "next";
import "../styles/globals.css";
import AuthProvider from "@/components/AuthProvider";
import SiteShell from "@/components/SiteShell";

export const metadata: Metadata = {
  title: "RoomKit",
  description: "AI-designed rooms. On budget. Shoppable.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=DM+Serif+Display&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <AuthProvider>
          <SiteShell>{children}</SiteShell>
        </AuthProvider>
      </body>
    </html>
  );
}

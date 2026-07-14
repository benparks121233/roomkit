import Link from "next/link";

export default function NotFound() {
  return (
    <main className="error-page">
      <h1 className="error-page-code">404</h1>
      <p className="error-page-message">This page doesn&apos;t exist.</p>
      <Link href="/" className="error-page-link">Back to home</Link>
    </main>
  );
}

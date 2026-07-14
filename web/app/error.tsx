"use client";

export default function ErrorPage({
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="error-page">
      <h1 className="error-page-code">Something went wrong</h1>
      <p className="error-page-message">An unexpected error occurred. Please try again.</p>
      <button onClick={reset} className="error-page-link">
        Try again
      </button>
    </main>
  );
}

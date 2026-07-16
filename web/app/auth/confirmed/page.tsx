"use client";

export default function ConfirmedPage() {
  return (
    <main className="auth-container">
      <div className="auth-card" style={{ textAlign: "center" }}>
        <div style={{ fontSize: "2rem", marginBottom: 12 }}>&#x2705;</div>
        <h1 className="auth-title">Email confirmed</h1>
        <p className="auth-subtitle">
          You&apos;re all set. Go back to the tab where you were designing to continue.
        </p>
      </div>
    </main>
  );
}

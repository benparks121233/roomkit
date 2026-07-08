"use client";

export default function PurchaseCancelPage() {
  return (
    <main style={styles.container}>
      <div style={styles.card}>
        <h1 style={styles.title}>No worries</h1>
        <p style={styles.subtitle}>
          Your card wasn&apos;t charged. You can still use your free room design
          or come back to upgrade anytime.
        </p>
        <a href="/" style={styles.button}>
          Back to RoomKit
        </a>
      </div>
    </main>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#f8f7f4",
    fontFamily: "'DM Sans', sans-serif",
  },
  card: {
    background: "#fff",
    borderRadius: 12,
    padding: "2.5rem 2rem",
    width: "100%",
    maxWidth: 440,
    boxShadow: "0 2px 12px rgba(0,0,0,0.08)",
    textAlign: "center" as const,
  },
  title: {
    fontFamily: "'DM Serif Display', serif",
    fontSize: "1.6rem",
    margin: "0 0 8px 0",
    color: "#1a1a1a",
  },
  subtitle: {
    color: "#57534E",
    fontSize: "0.95rem",
    lineHeight: 1.6,
    marginBottom: 24,
  },
  button: {
    display: "inline-block",
    padding: "12px 36px",
    borderRadius: 10,
    border: "none",
    background: "#1C1917",
    color: "#FFF",
    fontSize: "0.95rem",
    fontWeight: 600,
    textDecoration: "none",
  },
};
